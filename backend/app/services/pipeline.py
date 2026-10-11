"""Ingest, summarize and verify pipeline (RAG with persistent Chroma)."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import CaseNotIngestedError, IngestFailedError, NoDocumentsError
from app.schemas.rag import (
    IngestResponse,
    SummarizeResponse,
    Verdict,
    VerifyResponse,
)
from app.services import prompts
from app.services.chunking import Chunk, chunk_text
from app.services.citations import citation_from_hit, citations_from_model
from app.services.embeddings import get_embedder, get_embedding_backend
from app.services.extraction import extract_text
from app.services.language import Language, detect_language, majority_language
from app.services.llm import get_llm
from app.services.storage import STATUS_INGESTED, STATUS_STALE, get_store
from app.services.vector_store import get_vectorstore

logger = logging.getLogger(__name__)

QUERYABLE_STATUSES = {STATUS_INGESTED, STATUS_STALE}
SUMMARY_FALLBACK_QUERY = "страни дати суми срокове задължения"
SUMMARY_FALLBACK_QUERY_EN = "parties dates amounts deadlines obligations"


def _resolve_language(
    hits: list[dict[str, Any]],
    answer_language: str = "auto",
) -> Language:
    """Determine the prompt language from retrieved chunks or an explicit override."""
    if answer_language in ("bg", "en"):
        return answer_language  # type: ignore[return-value]
    langs: list[Language] = [h.get("metadata", {}).get("language", "bg") for h in hits]
    return majority_language(langs)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


_CODE_FENCE = re.compile(r"```(?:json|JSON)?\s*([\s\S]*?)(?:```|$)")
_VERDICT_FIELD = re.compile(r'"verdict"\s*:\s*"([A-Za-z_]+)"')


def _strip_code_fence(raw: str) -> str:
    """Return the body of a markdown code block if the reply is wrapped in one."""
    m = _CODE_FENCE.search(raw)
    return m.group(1).strip() if m else raw


def _parse_json_object(raw: str) -> dict:
    raw = _strip_code_fence(raw.strip())
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _require_queryable_case(case_id: str) -> dict:
    case = get_store().require_case(case_id)
    if case.get("status") not in QUERYABLE_STATUSES:
        raise CaseNotIngestedError(
            details={"case_id": case_id, "status": case.get("status")}
        )
    return case


async def ingest_case(case_id: str) -> IngestResponse:
    """Extract, chunk and embed every document; rebuilds the case collection."""
    started = time.perf_counter()
    store = get_store()
    settings = get_settings()
    case = store.require_case(case_id)
    if not case["documents"]:
        raise NoDocumentsError(details={"case_id": case_id})

    # Initialise the embedder first so the reported backend label is accurate
    get_embedder(settings)
    vs = get_vectorstore()

    per_doc: list[tuple[dict, list[Chunk], Language]] = []
    for doc in case["documents"]:
        path = Path(doc["path"])
        if not path.exists():
            logger.warning("Missing file for doc %s", doc["id"])
            continue
        try:
            text = extract_text(path, doc.get("content_type"))
        except Exception as exc:  # noqa: BLE001
            raise IngestFailedError(
                f"Could not extract text from {doc['filename']}",
                details={"document_id": doc["id"], "filename": doc["filename"]},
            ) from exc
        lang = detect_language(text)
        if lang == "other":
            logger.warning(
                "Document %s detected as '%s'; treating as English for prompts",
                doc["id"],
                lang,
            )
        chunks = chunk_text(
            text,
            doc_id=doc["id"],
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        if chunks:
            per_doc.append((doc, chunks, lang))

    total_chunks = sum(len(chunks) for _, chunks, _ in per_doc)
    if total_chunks == 0:
        raise IngestFailedError(
            "No extractable text found in the case documents",
            details={"case_id": case_id, "documents": len(case["documents"])},
        )

    vs.reset_case(case_id)
    for doc, chunks, lang in per_doc:
        vs.upsert_chunks(
            case_id,
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "document_id": doc["id"],
                    "document_filename": doc["filename"],
                    "chunk_index": c.index,
                    "language": lang,
                }
                for c in chunks
            ],
        )

    persisted_count = vs.count(case_id)
    backend = get_embedding_backend()
    store.mark_ingested(
        case_id,
        persisted_count,
        embedding_backend=backend,
        embedding_model=settings.embedding_model,
    )
    return IngestResponse(
        case_id=case_id,
        documents_processed=len(per_doc),
        chunks_indexed=total_chunks,
        embedding_backend=backend,
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        vector_store_path=vs.persist_path,
        persisted=(persisted_count == total_chunks),
        duration_ms=_elapsed_ms(started),
    )


async def summarize_case(
    case_id: str,
    top_k: int | None = None,
    answer_language: str = "auto",
) -> SummarizeResponse:
    started = time.perf_counter()
    top_k = top_k or get_settings().summarize_top_k
    case = _require_queryable_case(case_id)
    vs = get_vectorstore()
    llm = get_llm()

    retrieval_started = time.perf_counter()
    hits = vs.query(case_id, case.get("title") or SUMMARY_FALLBACK_QUERY, top_k=top_k)
    if not hits:
        hits = vs.query(case_id, SUMMARY_FALLBACK_QUERY, top_k=top_k)
    retrieval_ms = _elapsed_ms(retrieval_started)

    lang = _resolve_language(hits, answer_language)
    system_prompt = prompts.get_summarize_system(lang)
    prompt = prompts.build_summarize_prompt(case.get("title"), hits, language=lang)
    generation_started = time.perf_counter()
    raw, stubbed = await llm.generate(prompt, system=system_prompt)
    generation_ms = _elapsed_ms(generation_started)
    parsed = _parse_json_object(raw)

    if parsed.get("summary"):
        summary_text = str(parsed["summary"]).strip()
        cite_idx = parsed.get("citation_indices")
        if not cite_idx and not parsed.get("citations"):
            cite_idx = list(range(len(hits)))
    else:
        summary_text = raw.strip()
        if stubbed and hits:
            # Build a citation-backed stub summary from retrieved chunks
            bullets = [f"- {h['text'][:180]}" for h in hits[:5]]
            summary_text = (
                "[STUB SUMMARY: Ollama unreachable; facts below are direct "
                "from retrieved chunks]\n" + "\n".join(bullets)
            )
        cite_idx = list(range(len(hits)))

    citations = citations_from_model(hits, parsed.get("citations"), cite_idx)
    if not citations and hits:
        citations = [citation_from_hit(h) for h in hits]

    return SummarizeResponse(
        case_id=case_id,
        summary=summary_text,
        citations=citations,
        model=llm.model_name,
        stubbed=stubbed,
        chunks_used=len(hits),
        duration_ms=_elapsed_ms(started),
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        answer_language=lang,
        prompt_version=prompts.get_prompt_version(lang),
    )


async def verify_claim(
    case_id: str,
    claim: str,
    top_k: int | None = None,
    answer_language: str = "auto",
) -> VerifyResponse:
    started = time.perf_counter()
    top_k = top_k or get_settings().verify_top_k
    _require_queryable_case(case_id)
    vs = get_vectorstore()
    llm = get_llm()

    retrieval_started = time.perf_counter()
    hits = vs.query(case_id, claim, top_k=top_k)
    retrieved = [citation_from_hit(h) for h in hits]
    retrieval_ms = _elapsed_ms(retrieval_started)

    lang = _resolve_language(hits, answer_language)
    system_prompt = prompts.get_verify_system(lang)
    prompt = prompts.build_verify_prompt(claim, hits, language=lang)
    generation_started = time.perf_counter()
    raw, stubbed = await llm.generate(prompt, system=system_prompt)
    generation_ms = _elapsed_ms(generation_started)
    parsed = _parse_json_object(raw)

    if not parsed:
        # Truncated or otherwise invalid JSON: still recover an explicit verdict.
        m = _VERDICT_FIELD.search(raw)
        parsed = {
            "verdict": m.group(1) if m else "inconclusive",
            "rationale": raw[:500] or "Could not parse model response.",
        }

    verdict_raw = str(parsed.get("verdict", "inconclusive")).strip().lower()
    try:
        verdict = Verdict(verdict_raw)
    except ValueError:
        verdict = Verdict.inconclusive

    supporting = citations_from_model(
        hits, parsed.get("supporting_quotes"), parsed.get("supporting_quote_indices")
    )
    denying = citations_from_model(
        hits, parsed.get("denying_quotes"), parsed.get("denying_quote_indices")
    )

    # Always surface retrieved evidence when the model omitted indices
    if not supporting and not denying and hits:
        if verdict == Verdict.denied:
            denying = [retrieved[0]]
        else:
            supporting = [retrieved[0]]

    rationale = str(parsed.get("rationale", ""))
    if stubbed and hits and not rationale.startswith("[STUB]"):
        rationale = (
            "[STUB] Ollama unreachable, showing top retrieved quote(s) as "
            "evidence. " + rationale
        )

    return VerifyResponse(
        case_id=case_id,
        claim=claim,
        verdict=verdict,
        rationale=rationale,
        supporting_quotes=supporting,
        denying_quotes=denying,
        retrieved_quotes=retrieved,
        model=llm.model_name,
        stubbed=stubbed,
        duration_ms=_elapsed_ms(started),
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        answer_language=lang,
        prompt_version=prompts.get_prompt_version(lang),
    )
