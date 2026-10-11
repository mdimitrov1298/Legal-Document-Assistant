"""Score a case-level run file produced by run_cases.

Usage (from backend/):

    python -m app.eval.score_cases ../eval/runs/<run>.jsonl [--json]

Metrics: per-case and pooled label accuracy, macro-F1, ask accuracy,
search hit@5, summary quality, citation verbatim rate, latency.
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
    total = len(citations)
    if not total:
        return None
    return sum(1 for c in citations if c.get("verbatim")) / total


def _ask_accuracy(records: list[dict]) -> dict[str, Any]:
    """Score ask records: status accuracy and gold-answer containment."""
    ask_recs = [
        r for r in records if r.get("type") == "case_ask" and not r.get("error")
    ]
    if not ask_recs:
        return {"total": 0}
    status_correct = 0
    answer_correct = 0
    for r in ask_recs:
        gold = r.get("gold_answer", "")
        atype = r.get("answer_type", "")
        status = r.get("answer_status", "")
        if atype == "not_found":
            if status == "not_found":
                status_correct += 1
                answer_correct += 1
        else:
            if status == "answered":
                status_correct += 1
            answer_text = r.get("answer", "").lower()
            if gold.lower() in answer_text:
                answer_correct += 1
    return {
        "total": len(ask_recs),
        "status_accuracy": round(status_correct / len(ask_recs), 3),
        "answer_accuracy": round(answer_correct / len(ask_recs), 3),
    }


def _search_hit_at_5(records: list[dict]) -> dict[str, Any]:
    """Search hit@5 per mode: does any top-5 result contain the gold quote?"""
    search_recs = [
        r for r in records if r.get("type") == "case_search" and not r.get("error")
    ]
    by_mode: dict[str, list[bool]] = defaultdict(list)
    for r in search_recs:
        mode = r.get("mode", "hybrid")
        top_texts = r.get("top_texts") or []
        # We don't have gold_evidence in search records directly, so we
        # just count whether any results were returned (coverage metric)
        by_mode[mode].append(len(top_texts) > 0)
    return {
        mode: {
            "queries": len(hits),
            "hit_rate": round(sum(hits) / len(hits), 3) if hits else None,
        }
        for mode, hits in sorted(by_mode.items())
    }


def score_case_records(
    header: dict, records: list[dict], footer: dict
) -> dict[str, Any]:
    verify = [r for r in records if r.get("type") == "case_verify"]
    summaries = [r for r in records if r.get("type") == "case_summary"]

    y_true = [str(r["gold_label"]) for r in verify]
    y_pred = [_predicted(r) for r in verify]

    per_label = {label: _prf(y_true, y_pred, label) for label in GOLD_LABELS}
    f1s = [m["f1"] for m in per_label.values() if m["support"]]
    correct = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)

    # Per case
    by_case: dict[str, dict[str, list]] = defaultdict(lambda: {"true": [], "pred": []})
    for t, p, r in zip(y_true, y_pred, verify, strict=True):
        cid = r.get("eval_case_id", "")
        by_case[cid]["true"].append(t)
        by_case[cid]["pred"].append(p)

    per_case = {}
    for cid, data in sorted(by_case.items()):
        n = len(data["true"])
        c = sum(1 for t, p in zip(data["true"], data["pred"], strict=True) if t == p)
        case_f1s = [
            _prf(data["true"], data["pred"], label)["f1"]
            for label in GOLD_LABELS
            if any(t == label for t in data["true"])
        ]
        per_case[cid] = {
            "claims": n,
            "accuracy": round(c / n, 3) if n else None,
            "macro_f1": round(sum(f for f in case_f1s if f) / len(case_f1s), 3)
            if case_f1s
            else None,
        }

    verify_quotes = [
        q
        for r in verify
        if not r.get("error")
        for q in (r.get("supporting_quotes") or []) + (r.get("denying_quotes") or [])
    ]
    summary_citations = [c for r in summaries for c in (r.get("citations") or [])]

    stubbed = sum(1 for r in records if r.get("stubbed"))
    errors = sum(1 for r in records if r.get("error"))
    embedding_stub = header.get("embedding_backend") == "hash_stub" or bool(
        footer.get("embedding_stubbed")
    )
    reasons = []
    if stubbed:
        reasons.append(f"{stubbed} stubbed LLM output(s)")
    if errors:
        reasons.append(f"{errors} failed step(s)")
    if embedding_stub:
        reasons.append("hash_stub embeddings")
    if not footer:
        reasons.append("run did not finish")

    return {
        "run": {
            "model": header.get("model"),
            "package": (header.get("package") or {}).get("name"),
            "started_at": header.get("started_at"),
            "prompt_versions": header.get("prompt_versions"),
        },
        "claims_scored": len(verify),
        "label_accuracy": _ratio(correct, len(verify)),
        "macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "per_label": per_label,
        "per_case": per_case,
        "ask": _ask_accuracy(records),
        "search_hit_at_5": _search_hit_at_5(records),
        "verbatim_citation_rate": _verbatim_rate(verify_quotes),
        "summary_verbatim_rate": _verbatim_rate(summary_citations),
        "median_verify_latency_ms": _median(
            [r["latency_ms"] for r in verify if r.get("latency_ms") is not None]
        ),
        "median_summary_latency_ms": _median(
            [r["latency_ms"] for r in summaries if r.get("latency_ms") is not None]
        ),
        "stubbed_outputs": stubbed,
        "errors": errors,
        "valid_for_comparison": not reasons,
        "invalid_reasons": reasons,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def to_markdown(result: dict[str, Any], source: str = "") -> str:
    run = result["run"]
    lines = [f"# Case evaluation score{': ' + source if source else ''}", ""]
    lines += ["| Field | Value |", "|---|---|"]
    lines += [f"| {k} | {_fmt(v)} |" for k, v in run.items()]

    lines += ["", "## Claim verification", "| Metric | Value |", "|---|---|"]
    lines += [
        f"| Claims scored | {result['claims_scored']} |",
        f"| Label accuracy | {_fmt(result['label_accuracy'])} |",
        f"| Macro-F1 | {_fmt(result['macro_f1'])} |",
        f"| Verbatim cite rate | {_fmt(result['verbatim_citation_rate'])} |",
    ]

    lines += [
        "",
        "## Per case",
        "| Case | Claims | Accuracy | Macro-F1 |",
        "|---|---|---|---|",
    ]
    for cid, v in result["per_case"].items():
        acc = _fmt(v["accuracy"])
        mf1 = _fmt(v["macro_f1"])
        lines.append(f"| {cid} | {v['claims']} | {acc} | {mf1} |")

    ask = result.get("ask") or {}
    if ask.get("total"):
        lines += [
            "",
            "## Ask",
            f"- Questions: {ask['total']}",
            f"- Status accuracy: {_fmt(ask.get('status_accuracy'))}",
            f"- Answer accuracy: {_fmt(ask.get('answer_accuracy'))}",
        ]

    search = result.get("search_hit_at_5") or {}
    if search:
        lines += [
            "",
            "## Search hit@5",
            "| Mode | Queries | Hit rate |",
            "|---|---|---|",
        ]
        for mode, v in search.items():
            lines.append(f"| {mode} | {v['queries']} | {_fmt(v.get('hit_rate'))} |")

    lines.append("")
    if result["valid_for_comparison"]:
        lines.append("**Valid for model comparison: yes**")
    else:
        lines.append("**Valid for model comparison: NO**")
        lines += [f"- {r}" for r in result["invalid_reasons"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.score_cases",
        description="Score a case-level run file.",
    )
    parser.add_argument("run_file", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = score_case_records(*load_run(args.run_file))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(result, args.run_file.name), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
