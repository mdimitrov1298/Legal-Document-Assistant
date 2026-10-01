"""CaseStore persistence: atomic writes and thread safety."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.errors import CaseNotFoundError, DocumentNotFoundError
from app.services.storage import CaseStore


def test_concurrent_writes_are_consistent(isolated_env):
    store = CaseStore()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: store.create_case(f"Дело {i}"), range(40)))
    assert len(store.list_cases()) == 40
    assert len(CaseStore().list_cases()) == 40
    assert not list(isolated_env.glob(".cases_index.*.tmp"))


def test_index_is_utf8_json(isolated_env):
    CaseStore().create_case("Дело за услуги")
    raw = (isolated_env / "cases_index.json").read_text("utf-8")
    assert "Дело за услуги" in raw


def test_returned_dicts_are_copies():
    store = CaseStore()
    case = store.create_case("A")
    case["title"] = "mutated"
    assert store.require_case(case["id"])["title"] == "A"


def test_missing_ids_raise_app_errors():
    store = CaseStore()
    with pytest.raises(CaseNotFoundError):
        store.require_case("nope")
    case = store.create_case("A")
    with pytest.raises(DocumentNotFoundError):
        store.require_document(case["id"], "nope")
    with pytest.raises(DocumentNotFoundError):
        store.delete_document(case["id"], "nope")
