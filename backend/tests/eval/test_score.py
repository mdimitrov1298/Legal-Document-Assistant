"""Scorer metrics on a hand-made run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.score import main, score_records, to_markdown

HEADER = {
    "type": "run",
    "model": "qwen2.5:7b",
    "num_ctx": 4096,
    "temperature": 0.0,
    "top_k": 5,
    "embedding_backend": "sentence-transformers",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "prompt_version": "bg-v1",
    "prompt_versions": {"bg": "bg-v1", "en": "en-v1"},
    "package": {"name": "eval-v0.1", "version": "0.1", "status": "draft"},
}
FOOTER = {"type": "run_end", "stubbed_outputs": 0, "errors": 0}


def _verify(gold, verdict, scenario="S1", latency=100.0, quotes=()):
    return {
        "type": "verify",
        "claim_id": f"{gold}-{verdict}",
        "scenario": scenario,
        "gold_label": gold,
        "verdict": verdict,
        "stubbed": False,
        "latency_ms": latency,
        "supporting_quotes": [{"verbatim": v} for v in quotes],
        "denying_quotes": [],
    }


RECORDS = [
    _verify("SUPPORTED", "supported", latency=100, quotes=(True,)),
    _verify("SUPPORTED", "inconclusive", latency=300),
    _verify("REFUTED", "denied", "S2", latency=200, quotes=(True, False)),
    _verify("NEI", "inconclusive", "S5", latency=400),
    _verify("NEI", "supported", "S5", latency=500, quotes=(False,)),
    {
        "type": "summary",
        "stubbed": False,
        "latency_ms": 1000,
        "citations": [{"verbatim": True}, {"verbatim": True}],
    },
]


def test_metrics():
    result = score_records(HEADER, RECORDS, FOOTER)
    assert result["claims_scored"] == 5
    assert result["label_accuracy"] == pytest.approx(3 / 5)
    # SUPPORTED p=1/2 r=1/2 f1=0.5; REFUTED f1=1; NEI p=1/2 r=1/2 f1=0.5
    assert result["macro_f1"] == pytest.approx((0.5 + 1 + 0.5) / 3)
    assert result["nei_precision"] == pytest.approx(0.5)
    assert result["nei_recall"] == pytest.approx(0.5)
    assert result["verbatim_citation_rate"] == pytest.approx(2 / 4)
    assert result["summary_verbatim_rate"] == 1.0
    assert result["median_verify_latency_ms"] == 300
    assert result["median_summary_latency_ms"] == 1000
    assert result["per_scenario"]["S5"] == {"claims": 2, "accuracy": 0.5}
    assert result["valid_for_comparison"] is True
    assert result["warnings"] == ["evaluation package is not frozen (draft)"]
    assert result["run"]["prompt_version"] == "bg-v1"


def test_stubbed_and_errors_invalidate():
    records = [
        {**RECORDS[0], "stubbed": True},
        {**_verify("NEI", "inconclusive"), "error": "llm_unavailable"},
    ]
    result = score_records(HEADER, records, FOOTER)
    assert result["valid_for_comparison"] is False
    assert result["label_accuracy"] == pytest.approx(1 / 2)
    assert len(result["invalid_reasons"]) == 2


def test_markdown_and_cli(tmp_path: Path, capsys):
    md = to_markdown(score_records(HEADER, RECORDS, FOOTER), "run.jsonl")
    assert "| Label accuracy | 0.600 |" in md
    assert "**Valid for model comparison: yes**" in md

    path = tmp_path / "run.jsonl"
    lines = [HEADER, *RECORDS[:2], {**RECORDS[3], "stubbed": True}]
    path.write_text("\n".join(json.dumps(r) for r in lines) + "\n", "utf-8")
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "**Valid for model comparison: NO**" in out
    assert "run did not finish" in out
    assert main([str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["claims_scored"] == 3
