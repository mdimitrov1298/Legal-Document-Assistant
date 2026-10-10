"""Score a run file produced by `app.eval.run`.

Usage (from backend/):

    python -m app.eval.score ../eval/runs/<run>.jsonl [--json]

Metrics: label accuracy, macro-F1 over SUPPORTED / REFUTED / NEI, NEI
precision and recall, verbatim citation rate and median latency. Verdicts map
supported -> SUPPORTED, denied -> REFUTED, inconclusive -> NEI. Runs that
contain stubbed LLM outputs, errors or hash_stub embeddings are reported as
not valid for model comparison.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.eval.manifest import GOLD_LABELS, VERDICT_TO_LABEL

ERROR_LABEL = "ERROR"


def load_run(path: str | Path) -> tuple[dict, list[dict], dict]:
    header: dict = {}
    footer: dict = {}
    records: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        kind = record.get("type")
        if kind == "run":
            header = record
        elif kind == "run_end":
            footer = record
        else:
            records.append(record)
    return header, records, footer


def _predicted(record: dict) -> str:
    if record.get("error"):
        return ERROR_LABEL
    label = record.get("predicted_label")
    if label:
        return str(label)
    return VERDICT_TO_LABEL.get(str(record.get("verdict")), ERROR_LABEL)


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _prf(y_true: list[str], y_pred: list[str], label: str) -> dict[str, float | None]:
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p == label)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if p == label and t != p)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == label and p != t)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = 0.0 if (tp + fp + fn) else None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _verbatim_rate(citations: list[dict]) -> float | None:
    return _ratio(sum(1 for c in citations if c.get("verbatim")), len(citations))


def score_records(header: dict, records: list[dict], footer: dict) -> dict[str, Any]:
    verify = [r for r in records if r.get("type") == "verify"]
    summaries = [r for r in records if r.get("type") == "summary"]
    y_true = [str(r["gold_label"]) for r in verify]
    y_pred = [_predicted(r) for r in verify]

    per_label = {label: _prf(y_true, y_pred, label) for label in GOLD_LABELS}
    f1s = [m["f1"] for m in per_label.values() if m["support"]]
    correct = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)

    verify_quotes = [
        q
        for r in verify
        if not r.get("error")
        for q in (r.get("supporting_quotes") or []) + (r.get("denying_quotes") or [])
    ]
    summary_citations = [c for r in summaries for c in (r.get("citations") or [])]

    by_scenario: dict[str, list[bool]] = defaultdict(list)
    for t, p, r in zip(y_true, y_pred, verify, strict=True):
        by_scenario[str(r.get("scenario") or "-")].append(t == p)

    stubbed = sum(1 for r in records if r.get("stubbed"))
    errors = sum(1 for r in records if r.get("error"))
    embedding_stub = header.get("embedding_backend") == "hash_stub" or bool(
        footer.get("embedding_stubbed")
    )
    reasons = []
    if stubbed:
        reasons.append(f"{stubbed} stubbed LLM output(s) (Ollama unavailable)")
    if errors:
        reasons.append(f"{errors} failed step(s)")
    if embedding_stub:
        reasons.append("hash_stub embeddings (retrieval is not meaningful)")
    if not footer:
        reasons.append("run did not finish (no run_end record)")
    warnings = []
    package = header.get("package") or {}
    if package.get("status") != "frozen" and not package.get("frozen_at"):
        warnings.append("evaluation package is not frozen (draft)")

    return {
        "run": {
            "model": header.get("model"),
            "num_ctx": header.get("num_ctx"),
            "temperature": header.get("temperature"),
            "top_k": header.get("top_k"),
            "embedding": f"{header.get('embedding_backend')} "
            f"({header.get('embedding_model')})",
            "package": f"{package.get('name')} v{package.get('version')} "
            f"({package.get('status')})",
            "commit": (header.get("git") or {}).get("commit"),
            "ollama_version": (header.get("ollama") or {}).get("version"),
            "started_at": header.get("started_at"),
        },
        "claims_scored": len(verify),
        "label_accuracy": _ratio(correct, len(verify)),
        "macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "per_label": per_label,
        "nei_precision": per_label["NEI"]["precision"],
        "nei_recall": per_label["NEI"]["recall"],
        "verbatim_citation_rate": _verbatim_rate(verify_quotes),
        "verify_citations": len(verify_quotes),
        "summary_verbatim_rate": _verbatim_rate(summary_citations),
        "median_verify_latency_ms": _median(
            [r["latency_ms"] for r in verify if r.get("latency_ms") is not None]
        ),
        "median_verify_retrieval_ms": _median(
            [r["retrieval_ms"] for r in verify if r.get("retrieval_ms") is not None]
        ),
        "median_verify_generation_ms": _median(
            [r["generation_ms"] for r in verify if r.get("generation_ms") is not None]
        ),
        "harness_peak_rss_bytes": footer.get("harness_peak_rss_bytes"),
        "ollama_loaded_models": footer.get("ollama_loaded_models"),
        "median_summary_latency_ms": _median(
            [r["latency_ms"] for r in summaries if r.get("latency_ms") is not None]
        ),
        "per_scenario": {
            s: {"claims": len(v), "accuracy": _ratio(sum(v), len(v))}
            for s, v in sorted(by_scenario.items())
        },
        "stubbed_outputs": stubbed,
        "errors": errors,
        "valid_for_comparison": not reasons,
        "invalid_reasons": reasons,
        "warnings": warnings,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def to_markdown(result: dict[str, Any], source: str = "") -> str:
    run = result["run"]
    lines = [f"# Evaluation score{': ' + source if source else ''}", ""]
    lines += ["| Run field | Value |", "|---|---|"]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in run.items()]
    lines += ["", "| Metric | Value |", "|---|---|"]
    metrics = [
        ("Claims scored", result["claims_scored"]),
        ("Label accuracy", result["label_accuracy"]),
        ("Macro-F1", result["macro_f1"]),
        ("NEI precision", result["nei_precision"]),
        ("NEI recall", result["nei_recall"]),
        ("Verbatim citation rate (verify)", result["verbatim_citation_rate"]),
        ("Verbatim citation rate (summary)", result["summary_verbatim_rate"]),
        ("Median verify latency (ms)", result["median_verify_latency_ms"]),
        ("Median summary latency (ms)", result["median_summary_latency_ms"]),
        ("Median verify retrieval (ms)", result.get("median_verify_retrieval_ms")),
        ("Median verify generation (ms)", result.get("median_verify_generation_ms")),
        ("Harness peak RSS (bytes)", result.get("harness_peak_rss_bytes")),
        ("Stubbed outputs", result["stubbed_outputs"]),
        ("Errors", result["errors"]),
    ]
    lines += [f"| {name} | {_fmt(value)} |" for name, value in metrics]
    lines += ["", "| Scenario | Claims | Accuracy |", "|---|---|---|"]
    lines += [
        f"| {s} | {v['claims']} | {_fmt(v['accuracy'])} |"
        for s, v in result["per_scenario"].items()
    ]
    lines.append("")
    if result["valid_for_comparison"]:
        lines.append("**Valid for model comparison: yes**")
    else:
        lines.append("**Valid for model comparison: NO**")
        lines += [f"- {reason}" for reason in result["invalid_reasons"]]
    lines += [f"- Warning: {w}" for w in result["warnings"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.score", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("run_file", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON instead")
    args = parser.parse_args(argv)
    result = score_records(*load_run(args.run_file))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(result, args.run_file.name), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
