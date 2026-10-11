"""Package loader and validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.eval.manifest import ManifestError, load_package, validate_package

PACKAGE = Path(__file__).resolve().parents[3] / "eval" / "eval-v0.1"


@pytest.fixture
def package_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(PACKAGE, dest)
    return dest


def test_load_committed_package():
    package = load_package(PACKAGE)
    assert package.version == "0.1"
    assert package.status == "frozen"
    assert [p.id for p in package.runnable_passages()] == ["P1", "P2", "P3", "P4"]
    assert not package.passages["P3"].is_pending
    assert package.passages["P4"].companion_passages == ("P2",)
    assert len(package.claims) == 25
    assert package.read_passage("P1").startswith("[СИНТЕТИЧЕН")
    assert package.manifest_sha256().startswith("sha256:")


def test_tampered_passage_fails_hash_check(package_copy: Path):
    path = package_copy / "passages" / "P2.txt"
    path.write_text(path.read_text("utf-8").replace("12 000", "13 000"), "utf-8")
    with pytest.raises(ManifestError) as info:
        load_package(package_copy)
    assert any("P2: file_hash" in p for p in info.value.problems)


def test_bad_span_and_label_are_reported(package_copy: Path):
    claims_path = package_copy / "claims" / "claims.jsonl"
    lines = claims_path.read_text("utf-8").splitlines()
    first = json.loads(lines[0])
    first["gold_evidence"][0]["char_span"] = [0, 5]
    second = json.loads(lines[1])
    second["gold_label"] = "MAYBE"
    lines[0] = json.dumps(first, ensure_ascii=False)
    lines[1] = json.dumps(second, ensure_ascii=False)
    claims_path.write_text("\n".join(lines) + "\n", "utf-8")

    problems = validate_package(load_package(package_copy, validate=False))
    assert any("C01: char_span" in p for p in problems)
    assert any("C02: invalid gold_label" in p for p in problems)


def test_missing_manifest(tmp_path: Path):
    with pytest.raises(ManifestError):
        load_package(tmp_path)
