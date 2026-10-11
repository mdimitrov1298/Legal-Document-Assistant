"""Ingest, index stats, summarize and verify endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import AppError, IngestFailedError
from app.schemas.common import error_responses
from app.schemas.rag import (
    AskRequest,
    AskResponse,
    IndexStatsResponse,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SummarizeRequest,
    SummarizeResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services import pipeline
from app.services.search import search_case
from app.services.storage import get_store
from app.services.vector_store import VectorStore, get_vectorstore

router = APIRouter(prefix="/cases/{case_id}", tags=["rag"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses=error_responses(404, 409, 500),
)
async def ingest_case(case_id: str) -> IngestResponse:
    """Extract, chunk and embed all documents. Re-ingest rebuilds the collection."""
    try:
        return await pipeline.ingest_case(case_id)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IngestFailedError(f"Ingest failed: {exc}") from exc


@router.get("/index", response_model=IndexStatsResponse, responses=error_responses(404))
async def get_index_stats(case_id: str) -> IndexStatsResponse:
    case = get_store().require_case(case_id)
    return IndexStatsResponse(
        case_id=case_id,
        collection=VectorStore.collection_name(case_id),
        chunk_count=get_vectorstore().count(case_id),
        embedding_backend=case.get("embedding_backend"),
        embedding_model=case.get("embedding_model"),
        ingested_at=case.get("ingested_at"),
    )


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    responses=error_responses(404, 409, 422, 503),
)
async def summarize_case(
    case_id: str, body: SummarizeRequest | None = None
) -> SummarizeResponse:
    top_k = body.top_k if body else None
    answer_language = body.answer_language if body else "auto"
    return await pipeline.summarize_case(
        case_id, top_k=top_k, answer_language=answer_language
    )


@router.post(
    "/verify",
    response_model=VerifyResponse,
    responses=error_responses(404, 409, 422, 503),
)
async def verify_claim(case_id: str, body: VerifyRequest) -> VerifyResponse:
    return await pipeline.verify_claim(
        case_id, body.claim, top_k=body.top_k, answer_language=body.answer_language
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    responses=error_responses(404, 409, 422),
)
async def search(case_id: str, body: SearchRequest) -> SearchResponse:
    """Interactive search over indexed case documents. No LLM call required."""
    return search_case(case_id, body.query, top_k=body.top_k, mode=body.mode)


@router.post(
    "/ask",
    response_model=AskResponse,
    responses=error_responses(404, 409, 422, 503),
)
async def ask(case_id: str, body: AskRequest) -> AskResponse:
    """Answer a free-form question about the case documents with citations."""
    return await pipeline.ask_question(
        case_id,
        body.question,
        top_k=body.top_k,
        answer_language=body.answer_language,
    )
