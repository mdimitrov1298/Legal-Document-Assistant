"""Score a filled human-review CSV.

Usage (from backend/):

    python -m app.eval.review_score ../eval/reviews/<name>.csv [--json]

Reports mean Likert faithfulness, share of sentences with errors, per model.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_review(path: Path) -> list[dict[str, str]]:
    """Load a review CSV into a list of row dicts."""
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def score_review(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute faithfulness metrics grouped by model."""
    by_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_model[row.get("model", "unknown")].append(row)

    results: dict[str, Any] = {}
    for model, model_rows in sorted(by_model.items()):
        scored = [r for r in model_rows if r.get("faithful", "").strip()]
        likerts: list[float] = []
        error_count = 0
        for r in scored:
            try:
                likerts.append(float(r["faithful"]))
            except (ValueError, KeyError):
                pass
            err = r.get("error_type", "").strip().lower()
            if err and err != "none":
                error_count += 1

        total = len(scored)
        results[model] = {
            "sentences_total": len(model_rows),
            "sentences_scored": total,
            "mean_faithful": round(sum(likerts) / len(likerts), 3) if likerts else None,
            "error_share": round(error_count / total, 3) if total else None,
            "error_count": error_count,
        }
    return results


def to_markdown(results: dict[str, Any], source: str = "") -> str:
    lines = [f"# Review scores{': ' + source if source else ''}", ""]
    lines += ["| Model | Scored | Mean faithful | Error share | Errors |"]
    lines += ["|---|---|---|---|---|"]
    for model, m in results.items():
        mf = f"{m['mean_faithful']:.3f}" if m["mean_faithful"] is not None else "n/a"
        es = f"{m['error_share']:.3f}" if m["error_share"] is not None else "n/a"
        lines.append(
            f"| {model} | {m['sentences_scored']}/{m['sentences_total']} "
            f"| {mf} | {es} | {m['error_count']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.review_score",
        description="Score a filled human-review CSV.",
    )
    parser.add_argument("csv_file", type=Path, help="Path to a filled review .csv file")
    parser.add_argument("--json", action="store_true", help="Print JSON instead")
    args = parser.parse_args(argv)
    rows = load_review(args.csv_file)
    results = score_review(rows)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(results, args.csv_file.name), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
