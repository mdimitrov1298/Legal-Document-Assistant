"""Document models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str | None = None
    uploaded_at: datetime
