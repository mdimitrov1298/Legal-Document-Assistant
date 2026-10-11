"""Tests for score_cases scorer on synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.score_cases import load_run, score_case_records, to_markdown


@pytest.fixture()
def case_run_jsonl(tmp_path: Path) -> Path:
    """Synthetic case run with 4 verify + 2 ask + 2 search records."""
    header = {
        "type": "run",
        "model": "test-model",
        "started_at": "2026-01-01T00:00:00Z",
        "package": {"name": "test-cases", "version": "0.1", "status": "draft"},
        "embedding_backend": "hash_stub",
        "prompt_versions": {"bg": "bg-v1", "en": "en-v1"},
    }
    records = [
        {
            "type": "case_ingest",
            "eval_case_id": "K1",
            "repeat": 1,
            "documents": ["d1.txt"],
            "chunks_indexed": 3,
        },
        {
            "type": "case_summary",
            "eval_case_id": "K1",
            "repeat": 1,
            "summary": "Summary.",
            "citations": [{"text": "chunk", "verbatim": True}],
            "model": "test",
            "stubbed": True,
            "latency_ms": 10,
        },
        {
            "type": "case_verify",
            "eval_case_id": "K1",
            "repeat": 1,
            "claim_id": "C01",
            "gold_label": "SUPPORTED",
            "verdict": "supported",
            "predicted_label": "SUPPORTED",
            "supporting_quotes": [{"verbatim": True}],
            "denying_quotes": [],
            "stubbed": False,
            "latency_ms": 50,
        },
        {
            "type": "case_verify",
            "eval_case_id": "K1",
            "repeat": 1,
            "claim_id": "C02",
            "gold_label": "REFUTED",
            "verdict": "denied",
            "predicted_label": "REFUTED",
            "supporting_quotes": [],
            "denying_quotes": [{"verbatim": False}],
            "stubbed": False,
            "latency_ms": 60,
        },
        {
            "type": "case_verify",
            "eval_case_id": "K1",
            "repeat": 1,
            "claim_id": "C03",
            "gold_label": "NEI",
            "verdict": "supported",
            "predicted_label": "SUPPORTED",
            "supporting_quotes": [],
            "denying_quotes": [],
            "stubbed": False,
            "latency_ms": 40,
        },
        {
            "type": "case_ask",
            "eval_case_id": "K1",
            "repeat": 1,
            "q_id": "Q01",
            "gold_answer": "GBP 100",
            "answer_type": "number",
            "answer": "The fee is GBP 100.",
            "answer_status": "answered",
            "stubbed": False,
            "latency_ms": 100,
        },
        {
            "type": "case_ask",
            "eval_case_id": "K1",
            "repeat": 1,
            "q_id": "Q02",
            "gold_answer": "not_found",
            "answer_type": "not_found",
            "answer": "Not found in documents.",
            "answer_status": "not_found",
            "stubbed": False,
            "latency_ms": 80,
        },
        {
            "type": "case_search",
            "eval_case_id": "K1",
            "repeat": 1,
            "q_id": "Q01",
            "mode": "hybrid",
            "results_count": 3,
            "top_texts": ["chunk1", "chunk2", "chunk3"],
            "duration_ms": 5,
        },
    ]
    footer = {
        "type": "run_end",
        "finished_at": "2026-01-01T00:01:00Z",
        "stubbed_outputs": 1,
        "errors": 0,
        "embedding_stubbed": True,
    }
    path = tmp_path / "case_run.jsonl"
    lines = [json.dumps(header)]
    lines += [json.dumps(r) for r in records]
    lines.append(json.dumps(footer))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_score_case_records(case_run_jsonl: Path) -> None:
    header, records, footer = load_run(case_run_jsonl)
    result = score_case_records(header, records, footer)
    assert result["claims_scored"] == 3
    assert result["label_accuracy"] == pytest.approx(2 / 3, abs=0.01)
    assert "K1" in result["per_case"]
    assert result["per_case"]["K1"]["claims"] == 3
    assert result["ask"]["total"] == 2
    assert result["ask"]["status_accuracy"] == pytest.approx(1.0)
    assert result["ask"]["answer_accuracy"] == pytest.approx(1.0)
    assert result["valid_for_comparison"] is False  # hash_stub + stubbed


def test_to_markdown(case_run_jsonl: Path) -> None:
    header, records, footer = load_run(case_run_jsonl)
    result = score_case_records(header, records, footer)
    md = to_markdown(result, "test")
    assert "K1" in md
    assert "Label accuracy" in md
    assert "Ask" in md
