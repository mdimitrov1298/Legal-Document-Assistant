"""Document endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Response, UploadFile, status

from app.core.config import get_settings
from app.core.errors import PayloadTooLargeError
from app.schemas.common import error_responses
from app.schemas.documents import DocumentResponse
from app.services.extraction import validate_upload
from app.services.storage import STATUS_EMPTY, get_store
from app.services.vector_store import get_vectorstore

router = APIRouter(prefix="/cases/{case_id}/documents", tags=["documents"])


def to_document_response(doc: dict) -> DocumentResponse:
    return DocumentResponse(
        id=doc["id"],
        case_id=doc["case_id"],
        filename=doc["filename"],
        content_type=doc["content_type"],
        size_bytes=doc["size_bytes"],
        sha256=doc.get("sha256"),
        uploaded_at=doc["uploaded_at"],
    )


@router.get("", response_model=list[DocumentResponse], responses=error_responses(404))
async def list_documents(case_id: str) -> list[DocumentResponse]:
    return [to_document_response(d) for d in get_store().list_documents(case_id)]


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 404, 413, 415, 422),
)
async def upload_document(
    case_id: str, file: UploadFile = File(...)
) -> DocumentResponse:
    """Upload a Bulgarian PDF or TXT document (max MAX_UPLOAD_MB)."""
    store = get_store()
    store.require_case(case_id)
    settings = get_settings()

    filename = file.filename or "upload.bin"
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"File exceeds the {settings.max_upload_mb} MB upload limit",
            details={"filename": filename, "max_upload_mb": settings.max_upload_mb},
        )
    content_type = validate_upload(filename, file.content_type, data)

    doc = store.add_document(case_id, filename, content_type, data)
    return to_document_response(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=error_responses(404),
)
async def delete_document(case_id: str, document_id: str) -> Response:
    """Delete a document and its indexed chunks; the case becomes stale."""
    store = get_store()
    store.require_document(case_id, document_id)
    vs = get_vectorstore()
    remaining = vs.delete_document_chunks(case_id, document_id)
    case = store.delete_document(case_id, document_id, remaining_chunks=remaining)
    if case["status"] == STATUS_EMPTY:
        vs.reset_case(case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
