"""Integrity of the committed eval-v0.1 package (hashes, spans, labels)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[3] / "eval" / "eval-v0.1"
LABELS = {"SUPPORTED", "REFUTED", "NEI"}


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((PACKAGE / "manifest.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def claims() -> list[dict]:
    lines = (PACKAGE / "claims" / "claims.jsonl").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _passages(manifest: dict) -> dict[str, dict]:
    return {p["id"]: p for p in manifest["passages"]}


def test_manifest_is_draft(manifest):
    assert manifest["version"] == "0.1"
    assert manifest["status"] == "draft"
    assert manifest["frozen_at"] is None


def test_manifest_hashes_match_passage_files(manifest):
    for passage in manifest["passages"]:
        if passage["status"] == "pending" or not passage["source"].startswith(
            "synthetic"
        ):
            continue
        raw = (PACKAGE / passage["path"]).read_bytes()
        assert passage["file_hash"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert passage["language"] == "bg"


def test_passages_are_marked_synthetic(manifest):
    for passage in manifest["passages"]:
        if passage["status"] == "pending" or not passage["source"].startswith(
            "synthetic"
        ):
            continue
        first_line = (PACKAGE / passage["path"]).read_text("utf-8").splitlines()[0]
        assert first_line.startswith("[СИНТЕТИЧЕН ДЕМОНСТРАЦИОНЕН ТЕКСТ")


def test_p3_is_eur_lex_sum_source(manifest):
    p3 = _passages(manifest)["P3"]
    assert p3["status"] == "draft"
    assert p3["celex_id"] == "31998R2866"
    assert p3["license"].startswith("CC-BY-SA 4.0")
    assert (PACKAGE / p3["path"]).is_file()


def test_every_gold_quote_is_an_exact_substring(manifest, claims):
    passages = _passages(manifest)
    for claim in claims:
        for evidence in claim["gold_evidence"]:
            text = (PACKAGE / passages[evidence["passage_id"]]["path"]).read_text(
                "utf-8"
            )
            start, end = evidence["char_span"]
            assert evidence["quote"] in text, claim["claim_id"]
            assert text[start:end] == evidence["quote"], claim["claim_id"]


def test_claims_schema_and_balance(manifest, claims):
    passages = _passages(manifest)
    ids = [c["claim_id"] for c in claims]
    assert len(ids) == len(set(ids)) >= 12
    for claim in claims:
        assert claim["gold_label"] in LABELS
        assert claim["language"] == "bg"
        assert passages[claim["passage_id"]]["status"] != "pending"
        if claim["gold_label"] == "NEI":
            assert claim["gold_evidence"] == []
        else:
            assert claim["gold_evidence"]
    counts = Counter(c["gold_label"] for c in claims)
    assert min(counts.values()) >= 4
    assert {c["scenario"] for c in claims} >= {"S1", "S2", "S4", "S5"}
