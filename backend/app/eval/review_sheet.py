"""Generate a human-review CSV from a run JSONL file.

For every summary sentence the sheet contains one row with pre-filled
context columns and empty annotation columns for the human reviewer.

Usage (from backend/):

    python -m app.eval.review_sheet <run.jsonl> --out ../eval/reviews/<stem>.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

from app.eval.score import load_run

# Split on sentence-ending punctuation followed by whitespace or end-of-string.
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split *text* into sentences (crude but good enough for review)."""
    parts = _SENTENCE_RE.split(text.strip())
    return [s.strip() for s in parts if s.strip()]


HEADER = [
    "run_file",
    "model",
    "repeat",
    "passage_id",
    "sentence_id",
    "sentence",
    "cited_chunk_text",
    "faithful",
    "error_type",
    "comment",
]


def generate_rows(
    header: dict[str, Any],
    records: list[dict[str, Any]],
    run_file: str,
) -> list[dict[str, str]]:
    """Return one dict-row per summary sentence (annotation columns blank)."""
    model = header.get("model", "")
    rows: list[dict[str, str]] = []
    for rec in records:
        if rec.get("type") != "summary":
            continue
        if rec.get("error"):
            continue
        passage_id = rec.get("passage_id", rec.get("case_id", ""))
        repeat = str(rec.get("repeat", ""))
        summary = rec.get("summary", "")
        citations = rec.get("citations") or []
        cited_text = " | ".join(
            c.get("text", c.get("quote", ""))[:200] for c in citations[:5]
        )
        sentences = _split_sentences(summary)
        for idx, sentence in enumerate(sentences, 1):
            rows.append(
                {
                    "run_file": run_file,
                    "model": model,
                    "repeat": repeat,
                    "passage_id": passage_id,
                    "sentence_id": f"s{idx}",
                    "sentence": sentence,
                    "cited_chunk_text": cited_text,
                    "faithful": "",
                    "error_type": "",
                    "comment": "",
                }
            )
    return rows


def write_csv(rows: list[dict[str, str]], out: Path) -> Path:
    """Write rows to CSV and return the path."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.review_sheet",
        description="Generate a human-review CSV from a run JSONL file.",
    )
    parser.add_argument("run_file", type=Path, help="Path to a run .jsonl file")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: eval/reviews/<run-stem>.csv)",
    )
    args = parser.parse_args(argv)
    header, records, _footer = load_run(args.run_file)
    run_name = args.run_file.stem
    out = args.out or Path("../eval/reviews") / f"{run_name}.csv"
    rows = generate_rows(header, records, run_name)
    path = write_csv(rows, out)
    print(f"Wrote {len(rows)} rows to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
