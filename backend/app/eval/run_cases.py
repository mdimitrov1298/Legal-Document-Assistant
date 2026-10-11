"""Run a case-level evaluation package end to end.

Usage (from backend/):

    python -m app.eval.run_cases --package ../eval/eval-cases-v0.1 \
        --out ../eval/runs --model qwen2.5:7b --repeats 3 --no-stub

For every case: create a temporary case via the storage layer, upload all
documents, ingest, summarize, verify every claim, ask every question, and
run search for every question with a gold evidence chunk.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

from app import __version__
from app.core.config import get_settings
from app.core.errors import AppError
from app.eval.case_manifest import CasePackage, EvalCase, load_case_package
from app.eval.manifest import VERDICT_TO_LABEL
from app.eval.run import (
    RunConfig,
    RunWriter,
    _citations,
    _env_overrides,
    _now,
    git_commit,
    isolated_settings,
    peak_rss_bytes,
    run_filename,
)
from app.services import pipeline
from app.services.embeddings import get_embedder, get_embedding_backend
from app.services.llm import OllamaClient, reset_llm
from app.services.prompts import PROMPT_VERSION, get_prompt_version
from app.services.search import search_case
from app.services.storage import get_store


async def _run_case(
    package: CasePackage,
    case: EvalCase,
    repeat: int,
    writer: RunWriter,
    counters: dict[str, int],
) -> None:
    """Run a single case: ingest → summarize → verify → ask → search."""
    store = get_store()
    api_case = store.create_case(f"{package.name} {case.case_id} r{repeat}")
    case_id = api_case["id"]

    base = {"case_id": case_id, "eval_case_id": case.case_id, "repeat": repeat}

    # Upload documents
    for doc in case.documents:
        doc_path = package.root / doc.path
        data = doc_path.read_bytes()
        content_type = "application/pdf" if doc.format == "pdf" else "text/plain"
        store.add_document(case_id, doc.filename, content_type, data)

    # Ingest
    started = time.perf_counter()
    try:
        ingest = await pipeline.ingest_case(case_id)
    except AppError as exc:
        counters["errors"] += 1
        writer.write(
            {"type": "case_ingest", **base, "error": exc.code, "message": str(exc)}
        )
        return
    writer.write(
        {
            "type": "case_ingest",
            **base,
            "documents": [d.filename for d in case.documents],
            "documents_count": len(case.documents),
            "chunks_indexed": ingest.chunks_indexed,
            "embedding_backend": ingest.embedding_backend,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    )

    # Summarize
    started = time.perf_counter()
    try:
        summary = await pipeline.summarize_case(case_id)
        counters["stubbed"] += int(summary.stubbed)
        writer.write(
            {
                "type": "case_summary",
                **base,
                "summary": summary.summary,
                "citations": _citations(summary.citations),
                "chunks_used": summary.chunks_used,
                "retrieval_ms": summary.retrieval_ms,
                "generation_ms": summary.generation_ms,
                "model": summary.model,
                "stubbed": summary.stubbed,
                "answer_language": summary.answer_language,
                "prompt_version": summary.prompt_version,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    except AppError as exc:
        counters["errors"] += 1
        writer.write(
            {"type": "case_summary", **base, "error": exc.code, "message": str(exc)}
        )

    # Verify claims
    for claim in case.claims:
        record: dict[str, Any] = {
            "type": "case_verify",
            **base,
            "claim_id": claim.claim_id,
            "scenario": claim.scenario,
            "trap_type": claim.trap_type,
            "claim_text": claim.claim_text,
            "gold_label": claim.gold_label,
        }
        started = time.perf_counter()
        try:
            result = await pipeline.verify_claim(case_id, claim.claim_text)
        except AppError as exc:
            counters["errors"] += 1
            writer.write({**record, "error": exc.code, "message": str(exc)})
            continue
        counters["stubbed"] += int(result.stubbed)
        writer.write(
            {
                **record,
                "verdict": result.verdict.value,
                "predicted_label": VERDICT_TO_LABEL[result.verdict.value],
                "rationale": result.rationale,
                "supporting_quotes": _citations(result.supporting_quotes),
                "denying_quotes": _citations(result.denying_quotes),
                "retrieved_chunk_ids": [q.chunk_id for q in result.retrieved_quotes],
                "retrieval_ms": result.retrieval_ms,
                "generation_ms": result.generation_ms,
                "model": result.model,
                "stubbed": result.stubbed,
                "answer_language": result.answer_language,
                "prompt_version": result.prompt_version,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )

    # Ask questions
    for q in case.questions:
        record = {
            "type": "case_ask",
            **base,
            "q_id": q.q_id,
            "question": q.question,
            "gold_answer": q.gold_answer,
            "answer_type": q.answer_type,
        }
        started = time.perf_counter()
        try:
            result = await pipeline.ask_question(case_id, q.question)
        except AppError as exc:
            counters["errors"] += 1
            writer.write({**record, "error": exc.code, "message": str(exc)})
            continue
        counters["stubbed"] += int(result.stubbed)
        writer.write(
            {
                **record,
                "answer": result.answer,
                "answer_status": result.answer_status,
                "citations": _citations(result.citations),
                "retrieval_ms": result.retrieval_ms,
                "generation_ms": result.generation_ms,
                "model": result.model,
                "stubbed": result.stubbed,
                "answer_language": result.answer_language,
                "prompt_version": result.prompt_version,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )

    # Search (for questions with gold evidence — check hit@5)
    for q in case.questions:
        if not q.gold_evidence:
            continue
        for mode in ("semantic", "keyword", "hybrid"):
            record = {
                "type": "case_search",
                **base,
                "q_id": q.q_id,
                "query": q.question,
                "mode": mode,
            }
            started = time.perf_counter()
            try:
                sr = search_case(case_id, q.question, top_k=5, mode=mode)
            except AppError as exc:
                counters["errors"] += 1
                writer.write({**record, "error": exc.code, "message": str(exc)})
                continue
            writer.write(
                {
                    **record,
                    "results_count": len(sr.results),
                    "top_texts": [r.text[:200] for r in sr.results[:5]],
                    "duration_ms": sr.duration_ms,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )


async def run_case_evaluation(
    config: RunConfig, *, llm: OllamaClient | None = None
) -> Path:
    """Execute the case package and return the path of the JSONL run file."""
    import shutil
    import tempfile

    package = load_case_package(config.package)
    work_dir = config.work_dir or Path(tempfile.mkdtemp(prefix="eval-cases-"))
    config.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with isolated_settings(_env_overrides(config, work_dir)):
            settings = get_settings()
            client = llm or OllamaClient(settings)
            reset_llm(client)
            get_embedder(settings)
            reachable, _ = await client.probe()
            header = {
                "type": "run",
                "started_at": _now(),
                "app_version": __version__,
                "git": git_commit(Path(__file__).resolve().parent),
                "package": {
                    "name": package.name,
                    "version": package.version,
                    "status": package.status,
                    "frozen_at": package.manifest.get("frozen_at"),
                    "manifest_sha256": package.manifest_sha256(),
                    "package_type": "cases",
                },
                "model": client.model_name,
                "ollama": {
                    "base_url": client.base_url,
                    "reachable": reachable,
                    "version": await client.version() if reachable else None,
                },
                "num_ctx": client.num_ctx,
                "temperature": client.temperature,
                "top_k": settings.verify_top_k,
                "summary_top_k": settings.summarize_top_k,
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "embedding_backend": get_embedding_backend(),
                "embedding_model": settings.embedding_model,
                "prompt_version": PROMPT_VERSION,
                "prompt_versions": {
                    "bg": get_prompt_version("bg"),
                    "en": get_prompt_version("en"),
                },
                "model_routing": settings.model_routing,
                "stub_on_unavailable": client.stub_on_unavailable,
                "repeats": config.repeats,
                "cases": [c.case_id for c in package.cases],
            }
            out_path = config.out_dir / run_filename(
                client.model_name, client.num_ctx, settings.verify_top_k
            )
            counters = {"stubbed": 0, "errors": 0}
            with out_path.open("w", encoding="utf-8") as fh:
                writer = RunWriter(fh)
                writer.write(header)
                for repeat in range(1, config.repeats + 1):
                    for case in package.cases:
                        await _run_case(package, case, repeat, writer, counters)
                writer.write(
                    {
                        "type": "run_end",
                        "finished_at": _now(),
                        "stubbed_outputs": counters["stubbed"],
                        "errors": counters["errors"],
                        "embedding_stubbed": get_embedding_backend() == "hash_stub",
                        "harness_peak_rss_bytes": peak_rss_bytes(),
                        "ollama_loaded_models": await client.running_models(),
                    }
                )
            return out_path
    finally:
        if config.work_dir is None and not config.keep_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.run_cases",
        description="Run a case-level evaluation package end to end.",
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, dest="out_dir")
    parser.add_argument("--model", help="Ollama model tag")
    parser.add_argument("--num-ctx", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--summary-top-k", type=int)
    parser.add_argument("--embedding-backend")
    parser.add_argument("--embedding-model")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--no-stub", action="store_true")
    parser.add_argument(
        "--routing",
        choices=["off", "language"],
        default=None,
        help="Model routing mode (default: off)",
    )
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--keep-work-dir", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = RunConfig(
        package=args.package,
        out_dir=args.out_dir,
        model=args.model,
        num_ctx=args.num_ctx,
        temperature=args.temperature,
        top_k=args.top_k,
        summary_top_k=args.summary_top_k,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        repeats=max(1, args.repeats),
        allow_stub=not args.no_stub,
        work_dir=args.work_dir,
        keep_work_dir=args.keep_work_dir,
        routing=args.routing,
    )
    out_path = asyncio.run(run_case_evaluation(config))
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
