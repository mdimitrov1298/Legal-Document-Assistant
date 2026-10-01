"""Shared response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(..., description="Stable snake_case error code")
    message: str = Field(..., description="Human-readable message")
    details: dict[str, Any] | None = Field(None, description="Optional context")


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str = Field(..., description="Same value as the X-Request-ID header")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "case_not_found",
                    "message": "Case not found",
                    "details": None,
                },
                "request_id": "5f0c6f7e-8c1b-4d0e-9f59-0c7d1b1f2a3b",
            }
        }
    }


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting the error envelope."""
    return {status: {"model": ErrorResponse} for status in statuses}
