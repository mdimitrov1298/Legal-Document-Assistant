"""Integration test: run_cases with stub LLM and hash embeddings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.run import RunConfig
from app.eval.run_cases import run_case_evaluation
from app.eval.score_cases import load_run, score_case_records


@pytest.fixture()
def mini_case_package(tmp_path: Path) -> Path:
    """Tiny case package with 1 case, 1 doc, 2 claims, 1 question."""
    import hashlib

    pkg = tmp_path / "pkg"
    case = pkg / "cases" / "T1"
    docs = case / "documents"
    docs.mkdir(parents=True)

    text = "Alice paid GBP 500 on 1 January 2025. Bob received it."
    doc = docs / "doc.txt"
    doc.write_text(text, encoding="utf-8")
    doc_hash = "sha256:" + hashlib.sha256(text.encode()).hexdigest()

    manifest = {
        "name": "test-mini",
        "version": "0.1",
        "status": "draft",
        "hash_algorithm": "sha256",
        "cases": [
            {
                "case_id": "T1",
                "language": "en",
                "source": "synthetic",
                "documents": [
                    {
                        "filename": "doc.txt",
                        "path": "cases/T1/documents/doc.txt",
                        "format": "txt",
                        "file_hash": doc_hash,
                    }
                ],
                "claims_file": "cases/T1/claims.jsonl",
                "questions_file": "cases/T1/questions.jsonl",
                "gold_summary_file": "cases/T1/gold_summary.txt",
            }
        ],
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    idx = text.index("GBP 500")
    claims = [
        {
            "claim_id": "C01",
            "claim_text": "Alice paid GBP 500.",
            "gold_label": "SUPPORTED",
            "gold_evidence": [
                {"document": "doc.txt", "char_span": [idx, idx + 7], "quote": "GBP 500"}
            ],
        },
        {
            "claim_id": "C02",
            "claim_text": "The payment was GBP 1000.",
            "gold_label": "REFUTED",
            "gold_evidence": [
                {"document": "doc.txt", "char_span": [idx, idx + 7], "quote": "GBP 500"}
            ],
        },
    ]
    (case / "claims.jsonl").write_text(
        "\n".join(json.dumps(c) for c in claims) + "\n", encoding="utf-8"
    )

    questions = [
        {
            "q_id": "Q01",
            "question": "How much did Alice pay?",
            "gold_answer": "GBP 500",
            "answer_type": "number",
            "gold_evidence": [
                {"document": "doc.txt", "char_span": [idx, idx + 7], "quote": "GBP 500"}
            ],
        }
    ]
    (case / "questions.jsonl").write_text(
        json.dumps(questions[0]) + "\n", encoding="utf-8"
    )
    (case / "gold_summary.txt").write_text(
        "Alice paid GBP 500 to Bob on 1 Jan 2025.", encoding="utf-8"
    )
    return pkg


@pytest.mark.asyncio
async def test_run_cases_stub(mini_case_package: Path, tmp_path: Path) -> None:
    """Run the mini package with stub LLM and verify output structure."""
    config = RunConfig(
        package=mini_case_package,
        out_dir=tmp_path / "out",
        repeats=1,
        allow_stub=True,
        work_dir=tmp_path / "work",
    )
    out_path = await run_case_evaluation(config)
    assert out_path.exists()

    header, records, footer = load_run(out_path)
    assert header["type"] == "run"
    assert (header.get("package") or {}).get("package_type") == "cases"

    types = [r["type"] for r in records]
    assert "case_ingest" in types
    assert "case_summary" in types
    assert "case_verify" in types
    assert "case_ask" in types
    assert "case_search" in types

    verify_recs = [r for r in records if r["type"] == "case_verify"]
    assert len(verify_recs) == 2

    result = score_case_records(header, records, footer)
    assert result["claims_scored"] == 2
    assert "T1" in result["per_case"]
