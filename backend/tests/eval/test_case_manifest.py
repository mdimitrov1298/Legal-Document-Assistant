"""Tests for case_manifest loader and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.case_manifest import (
    CaseManifestError,
    load_case_package,
    validate_case_package,
)


@pytest.fixture()
def case_package_dir(tmp_path: Path) -> Path:
    """Create a minimal valid case package in tmp_path."""
    case_dir = tmp_path / "cases" / "K1-test"
    docs_dir = case_dir / "documents"
    docs_dir.mkdir(parents=True)

    doc_text = "Hello world. Fee is GBP 100."
    doc_path = docs_dir / "doc1.txt"
    doc_path.write_text(doc_text, encoding="utf-8")

    import hashlib

    doc_hash = "sha256:" + hashlib.sha256(doc_text.encode()).hexdigest()

    manifest = {
        "name": "test-cases",
        "version": "0.1",
        "status": "draft",
        "hash_algorithm": "sha256",
        "cases": [
            {
                "case_id": "K1-test",
                "language": "en",
                "source": "synthetic",
                "documents": [
                    {
                        "filename": "doc1.txt",
                        "path": "cases/K1-test/documents/doc1.txt",
                        "format": "txt",
                        "file_hash": doc_hash,
                    }
                ],
                "claims_file": "cases/K1-test/claims.jsonl",
                "questions_file": "cases/K1-test/questions.jsonl",
                "gold_summary_file": "cases/K1-test/gold_summary.txt",
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    claim = {
        "claim_id": "C01",
        "claim_text": "Fee is GBP 100.",
        "gold_label": "SUPPORTED",
        "gold_evidence": [
            {
                "document": "doc1.txt",
                "char_span": [doc_text.index("GBP 100"), doc_text.index("GBP 100") + 7],
                "quote": "GBP 100",
            }
        ],
    }
    (case_dir / "claims.jsonl").write_text(json.dumps(claim) + "\n", encoding="utf-8")

    question = {
        "q_id": "Q01",
        "question": "What is the fee?",
        "gold_answer": "GBP 100",
        "answer_type": "number",
        "gold_evidence": [
            {
                "document": "doc1.txt",
                "char_span": [doc_text.index("GBP 100"), doc_text.index("GBP 100") + 7],
                "quote": "GBP 100",
            }
        ],
    }
    (case_dir / "questions.jsonl").write_text(
        json.dumps(question) + "\n", encoding="utf-8"
    )
    (case_dir / "gold_summary.txt").write_text("Fee is GBP 100.", encoding="utf-8")
    return tmp_path


def test_load_valid_package(case_package_dir: Path) -> None:
    pkg = load_case_package(case_package_dir)
    assert pkg.name == "test-cases"
    assert len(pkg.cases) == 1
    case = pkg.cases[0]
    assert case.case_id == "K1-test"
    assert len(case.documents) == 1
    assert len(case.claims) == 1
    assert len(case.questions) == 1
    assert case.gold_summary == "Fee is GBP 100."


def test_hash_validation_fails_on_tamper(case_package_dir: Path) -> None:
    doc = case_package_dir / "cases" / "K1-test" / "documents" / "doc1.txt"
    doc.write_text("TAMPERED", encoding="utf-8")
    with pytest.raises(CaseManifestError, match="hash mismatch"):
        load_case_package(case_package_dir)


def test_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(CaseManifestError, match="manifest.json not found"):
        load_case_package(tmp_path)


def test_real_case_package() -> None:
    """Validate the actual eval-cases-v0.1 package."""
    pkg_path = Path(__file__).resolve().parents[3] / "eval" / "eval-cases-v0.1"
    if not pkg_path.exists():
        pytest.skip("eval-cases-v0.1 not found")
    pkg = load_case_package(pkg_path)
    assert len(pkg.cases) == 4
    problems = validate_case_package(pkg)
    assert problems == [], f"Validation problems: {problems}"
