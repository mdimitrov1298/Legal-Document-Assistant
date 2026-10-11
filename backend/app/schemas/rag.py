"""Ingest, index, summarize and verify models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    case_id: str
    documents_processed: int
    chunks_indexed: int
    embedding_backend: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    vector_store_path: str
    persisted: bool = Field(..., description="Chroma count equals chunks_indexed")
    duration_ms: float


class IndexStatsResponse(BaseModel):
    case_id: str
    collection: str
    chunk_count: int
    embedding_backend: str | None = None
    embedding_model: str | None = None
    ingested_at: datetime | None = None


class Citation(BaseModel):
    document_id: str
    document_filename: str
    chunk_id: str
    chunk_index: int | None = None
    quote: str
    relevance: float | None = None
    verbatim: bool = Field(
        ...,
        description=(
            "True when the quote occurs exactly (after whitespace normalisation) "
            "in the stored chunk text"
        ),
    )


class SummarizeRequest(BaseModel):
    top_k: int | None = Field(
        None, ge=1, le=20, description="Defaults to SUMMARIZE_TOP_K (8)"
    )
    answer_language: str = Field(
        "auto",
        pattern=r"^(auto|bg|en)$",
        description="Language for the answer: auto (from chunks), bg or en",
    )


class SummarizeResponse(BaseModel):
    case_id: str
    summary: str
    citations: list[Citation] = Field(default_factory=list)
    model: str
    stubbed: bool = False
    chunks_used: int = 0
    duration_ms: float = 0.0
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    answer_language: str = "bg"
    prompt_version: str = ""


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=1000)
    top_k: int | None = Field(
        None, ge=1, le=20, description="Defaults to VERIFY_TOP_K (5)"
    )
    answer_language: str = Field(
        "auto",
        pattern=r"^(auto|bg|en)$",
        description="Language for the answer: auto (from chunks), bg or en",
    )


class Verdict(StrEnum):
    supported = "supported"
    denied = "denied"
    inconclusive = "inconclusive"


class VerifyResponse(BaseModel):
    case_id: str
    claim: str
    verdict: Verdict
    rationale: str
    supporting_quotes: list[Citation] = Field(default_factory=list)
    denying_quotes: list[Citation] = Field(default_factory=list)
    retrieved_quotes: list[Citation] = Field(
        default_factory=list,
        description="All retrieved chunks used as evidence (always from Chroma).",
    )
    model: str
    stubbed: bool = False
    duration_ms: float = 0.0
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    answer_language: str = "bg"
    prompt_version: str = ""
