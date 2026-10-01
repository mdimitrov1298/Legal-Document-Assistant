"""Application errors and exception handlers producing a uniform error envelope.

Every non-2xx response has the shape
`{"error": {"code", "message", "details"}, "request_id"}`.
"""

from __future__ import annotations

import logging
import uuid
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    code: str = "internal_error"
    status_code: int = 500
    message: str = "Internal server error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class CaseNotFoundError(AppError):
    code = "case_not_found"
    status_code = 404
    message = "Case not found"


class DocumentNotFoundError(AppError):
    code = "document_not_found"
    status_code = 404
    message = "Document not found"


class EmptyFileError(AppError):
    code = "empty_file"
    status_code = 400
    message = "Uploaded file is empty"


class PayloadTooLargeError(AppError):
    code = "payload_too_large"
    status_code = 413
    message = "Uploaded file is too large"


class UnsupportedMediaTypeError(AppError):
    code = "unsupported_media_type"
    status_code = 415
    message = "Only PDF and TXT uploads are supported"


class NoDocumentsError(AppError):
    code = "no_documents"
    status_code = 409
    message = "Case has no documents to ingest"


class CaseNotIngestedError(AppError):
    code = "case_not_ingested"
    status_code = 409
    message = "Case has not been ingested yet"


class IngestFailedError(AppError):
    code = "ingest_failed"
    status_code = 500
    message = "Ingest failed"


class LLMUnavailableError(AppError):
    code = "llm_unavailable"
    status_code = 503
    message = "Local LLM is unavailable"


_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    500: "internal_error",
    503: "service_unavailable",
}


def get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None) or request_id_var.get()
    return rid or str(uuid.uuid4())


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = {
        "error": {"code": code, "message": message, "details": details},
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("%s: %s", exc.code, exc.message)
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "loc": list(err.get("loc", ())),
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        }
        for err in exc.errors()
    ]
    return error_response(
        request,
        422,
        "validation_error",
        "Request validation failed",
        {"errors": errors},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    if isinstance(exc.detail, str):
        message, details = exc.detail, None
    else:
        message = HTTPStatus(exc.status_code).phrase
        details = {"detail": exc.detail} if exc.detail is not None else None
    return error_response(
        request,
        exc.status_code,
        code,
        message,
        details,
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(request, 500, "internal_error", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
