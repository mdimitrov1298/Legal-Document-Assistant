"""Tests for review_sheet and review_score modules."""

from __future__ import annotations

import csv
import json
import textwrap
from pathlib import Path

import pytest

from app.eval.review_score import load_review, score_review, to_markdown
from app.eval.review_sheet import HEADER, generate_rows, write_csv


@pytest.fixture()
def run_jsonl(tmp_path: Path) -> Path:
    """Minimal run JSONL with one summary record."""
    header = {
        "type": "run",
        "model": "test-model",
        "started_at": "2026-01-01T00:00:00Z",
    }
    summary = {
        "type": "summary",
        "passage_id": "P1",
        "repeat": 1,
        "summary": "First sentence. Second sentence. Third!",
        "citations": [{"text": "chunk one"}, {"text": "chunk two"}],
    }
    footer = {"type": "run_end"}
    path = tmp_path / "test_run.jsonl"
    lines = [json.dumps(r) for r in [header, summary, footer]]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_generate_rows_splits_sentences(run_jsonl: Path) -> None:
    from app.eval.score import load_run

    header, records, _footer = load_run(run_jsonl)
    rows = generate_rows(header, records, "test_run")
    assert len(rows) == 3
    assert rows[0]["sentence_id"] == "s1"
    assert rows[0]["sentence"] == "First sentence."
    assert rows[1]["sentence"] == "Second sentence."
    assert rows[2]["sentence"] == "Third!"
    assert all(r["faithful"] == "" for r in rows)
    assert all(r["error_type"] == "" for r in rows)


def test_write_csv_creates_file(tmp_path: Path) -> None:
    rows = [
        {
            "run_file": "r",
            "model": "m",
            "repeat": "1",
            "passage_id": "P1",
            "sentence_id": "s1",
            "sentence": "Hello.",
            "cited_chunk_text": "ctx",
            "faithful": "",
            "error_type": "",
            "comment": "",
        }
    ]
    out = tmp_path / "out.csv"
    write_csv(rows, out)
    assert out.exists()
    with out.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        loaded = list(reader)
    assert len(loaded) == 1
    assert set(loaded[0].keys()) == set(HEADER)


def test_generate_rows_skips_errors() -> None:
    header = {"model": "m"}
    records = [
        {"type": "summary", "passage_id": "P1", "repeat": 1, "error": "ERR"},
        {
            "type": "summary",
            "passage_id": "P2",
            "repeat": 1,
            "summary": "OK sentence.",
            "citations": [],
        },
    ]
    rows = generate_rows(header, records, "run")
    assert len(rows) == 1
    assert rows[0]["passage_id"] == "P2"


@pytest.fixture()
def scored_csv(tmp_path: Path) -> Path:
    """A review CSV with some annotations filled in."""
    content = textwrap.dedent("""\
        run_file,model,repeat,passage_id,sentence_id,sentence,cited_chunk_text,faithful,error_type,comment
        r,modelA,1,P1,s1,Sentence one.,ctx,5,none,
        r,modelA,1,P1,s2,Sentence two.,ctx,3,number,wrong amount
        r,modelA,1,P1,s3,Sentence three.,ctx,4,none,
        r,modelB,1,P2,s1,Sentence one B.,ctx,2,unsupported,made up
        r,modelB,1,P2,s2,Not scored.,ctx,,,
    """)
    path = tmp_path / "filled.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_score_review(scored_csv: Path) -> None:
    rows = load_review(scored_csv)
    results = score_review(rows)
    assert "modelA" in results
    assert "modelB" in results
    ma = results["modelA"]
    assert ma["sentences_scored"] == 3
    assert ma["mean_faithful"] == pytest.approx(4.0, abs=0.01)
    assert ma["error_count"] == 1
    assert ma["error_share"] == pytest.approx(1 / 3, abs=0.01)
    mb = results["modelB"]
    assert mb["sentences_scored"] == 1
    assert mb["mean_faithful"] == pytest.approx(2.0, abs=0.01)


def test_to_markdown_contains_models(scored_csv: Path) -> None:
    rows = load_review(scored_csv)
    results = score_review(rows)
    md = to_markdown(results, "test")
    assert "modelA" in md
    assert "modelB" in md
    assert "Mean faithful" in md
