"""Case models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CaseStatus(StrEnum):
    empty = "empty"
    uploaded = "uploaded"
    ingested = "ingested"
    stale = "stale"


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class CaseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class CaseResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    status: CaseStatus
    chunk_count: int = 0
    ingested_at: datetime | None = None
