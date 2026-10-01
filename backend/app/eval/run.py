"""Run an evaluation package through ingest, summarize and verify.

Usage (from backend/):

    python -m app.eval.run --package ../eval/eval-v0.1 --model qwen2.5:7b \
        --num-ctx 4096 --top-k 5 --out ../eval/runs

For every runnable passage a temporary case is created in an isolated work
directory, the passage (plus its companion passages) is ingested, summarized
once, and every claim of that passage is verified. Results are written as
JSONL: a `run` header with metadata, one record per step, and a `run_end`
footer. Nothing is written to the regular case store.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from app import __version__
from app.core.config import clear_settings_cache, get_settings
from app.core.errors import AppError
from app.eval.manifest import VERDICT_TO_LABEL, Package, load_package
from app.services import pipeline
from app.services.embeddings import (
    get_embedder,
    get_embedding_backend,
    reset_embedder,
)
from app.services.llm import OllamaClient, reset_llm
from app.services.prompts import PROMPT_VERSION
from app.services.storage import get_store, reset_store
from app.services.vector_store import reset_vectorstore


@dataclass
class RunConfig:
    package: Path
    out_dir: Path
    model: str | None = None
    num_ctx: int | None = None
    temperature: float | None = None
    top_k: int | None = None
    summary_top_k: int | None = None
    embedding_backend: str | None = None
    embedding_model: str | None = None
    repeats: int = 1
    allow_stub: bool = True
    work_dir: Path | None = None
    keep_work_dir: bool = False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def git_commit(cwd: Path) -> dict[str, Any]:
    """Current commit and dirty flag, or nulls when git is unavailable."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return {"commit": commit or None, "dirty": bool(dirty)}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


@contextmanager
def isolated_settings(overrides: dict[str, str]) -> Iterator[None]:
    """Temporarily set env vars, reset cached settings and service singletons."""
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    _reset_services()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset_services()


def _reset_services() -> None:
    clear_settings_cache()
    reset_llm(None)
    reset_store(None)
    reset_vectorstore(None)
    reset_embedder()


def _env_overrides(config: RunConfig, work_dir: Path) -> dict[str, str]:
    env = {
        "DATA_DIR": str(work_dir / "data"),
        "CHROMA_PATH": str(work_dir / "data" / "chroma"),
        "UPLOAD_DIR": str(work_dir / "data" / "uploads"),
        "OLLAMA_STUB_ON_UNAVAILABLE": "true" if config.allow_stub else "false",
    }
    optional = {
        "OLLAMA_MODEL": config.model,
        "OLLAMA_NUM_CTX": config.num_ctx,
        "OLLAMA_TEMPERATURE": config.temperature,
        "VERIFY_TOP_K": config.top_k,
        "SUMMARIZE_TOP_K": config.summary_top_k,
        "EMBEDDING_BACKEND": config.embedding_backend,
        "EMBEDDING_MODEL": config.embedding_model,
    }
    env.update({k: str(v) for k, v in optional.items() if v is not None})
    return env


def run_filename(model: str, num_ctx: int, top_k: int) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", model)
    return f"{stamp}_{safe_model}_ctx{num_ctx}_k{top_k}.jsonl"


class RunWriter:
    def __init__(self, fh: TextIO) -> None:
        self.fh = fh

    def write(self, record: dict[str, Any]) -> None:
        self.fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.fh.flush()


def _citations(items: list[Any]) -> list[dict[str, Any]]:
    return [c.model_dump() for c in items]


async def _run_passage(
    package: Package,
    passage_id: str,
    repeat: int,
    writer: RunWriter,
    counters: dict[str, int],
) -> None:
    passage = package.passages[passage_id]
    store = get_store()
    case = store.create_case(f"{package.name} {passage_id} r{repeat}")
    doc_ids = [passage_id, *passage.companion_passages]
    for doc_pid in doc_ids:
        data = package.passage_path(doc_pid).read_bytes()
        store.add_document(case["id"], f"{doc_pid}.txt", "text/plain", data)

    base = {"passage_id": passage_id, "repeat": repeat, "case_id": case["id"]}

    started = time.perf_counter()
    try:
        ingest = await pipeline.ingest_case(case["id"])
    except AppError as exc:
        counters["errors"] += 1
        writer.write({"type": "ingest", **base, "error": exc.code, "message": str(exc)})
        return
    writer.write(
        {
            "type": "ingest",
            **base,
            "documents": doc_ids,
            "chunks_indexed": ingest.chunks_indexed,
            "embedding_backend": ingest.embedding_backend,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    )

    started = time.perf_counter()
    try:
        summary = await pipeline.summarize_case(case["id"])
        counters["stubbed"] += int(summary.stubbed)
        writer.write(
            {
                "type": "summary",
                **base,
                "summary": summary.summary,
                "citations": _citations(summary.citations),
                "chunks_used": summary.chunks_used,
                "model": summary.model,
                "stubbed": summary.stubbed,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    except AppError as exc:
        counters["errors"] += 1
        writer.write(
            {"type": "summary", **base, "error": exc.code, "message": str(exc)}
        )

    for claim in package.claims_for(passage_id):
        record = {
            "type": "verify",
            **base,
            "claim_id": claim.claim_id,
            "scenario": claim.scenario,
            "trap_type": claim.trap_type,
            "claim_text": claim.claim_text,
            "gold_label": claim.gold_label,
        }
        started = time.perf_counter()
        try:
            result = await pipeline.verify_claim(case["id"], claim.claim_text)
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
                "model": result.model,
                "stubbed": result.stubbed,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )


async def run_evaluation(config: RunConfig, *, llm: OllamaClient | None = None) -> Path:
    """Execute the package and return the path of the JSONL run file."""
    package = load_package(config.package)
    work_dir = config.work_dir or Path(tempfile.mkdtemp(prefix="eval-run-"))
    config.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with isolated_settings(_env_overrides(config, work_dir)):
            settings = get_settings()
            client = llm or OllamaClient(settings)
            reset_llm(client)
            # Resolve the embedding backend actually used (fallbacks included)
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
                "embedding_backend_configured": settings.embedding_backend,
                "embedding_model": settings.embedding_model,
                "prompt_version": PROMPT_VERSION,
                "stub_on_unavailable": client.stub_on_unavailable,
                "repeats": config.repeats,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            }
            out_path = config.out_dir / run_filename(
                client.model_name, client.num_ctx, settings.verify_top_k
            )
            counters = {"stubbed": 0, "errors": 0}
            with out_path.open("w", encoding="utf-8") as fh:
                writer = RunWriter(fh)
                writer.write(header)
                for repeat in range(1, config.repeats + 1):
                    for passage in package.runnable_passages():
                        await _run_passage(
                            package, passage.id, repeat, writer, counters
                        )
                writer.write(
                    {
                        "type": "run_end",
                        "finished_at": _now(),
                        "stubbed_outputs": counters["stubbed"],
                        "errors": counters["errors"],
                        "embedding_stubbed": get_embedding_backend() == "hash_stub",
                    }
                )
            return out_path
    finally:
        if config.work_dir is None and not config.keep_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.run", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, dest="out_dir")
    parser.add_argument("--model", help="Ollama model tag (default OLLAMA_MODEL)")
    parser.add_argument("--num-ctx", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-k", type=int, help="Verify top-k (default VERIFY_TOP_K)")
    parser.add_argument("--summary-top-k", type=int)
    parser.add_argument("--embedding-backend")
    parser.add_argument("--embedding-model")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--no-stub",
        action="store_true",
        help="Fail calls instead of stubbing when Ollama is unavailable",
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
    )
    out_path = asyncio.run(run_evaluation(config))
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
