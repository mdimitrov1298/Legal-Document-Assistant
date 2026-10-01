"""Case endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.schemas.cases import CaseCreate, CaseResponse, CaseUpdate
from app.schemas.common import error_responses
from app.services.storage import get_store
from app.services.vector_store import get_vectorstore

router = APIRouter(prefix="/cases", tags=["cases"])


def to_case_response(case: dict) -> CaseResponse:
    return CaseResponse(
        id=case["id"],
        title=case["title"],
        description=case.get("description"),
        created_at=case["created_at"],
        updated_at=case["updated_at"],
        document_count=len(case.get("documents") or []),
        status=case["status"],
        chunk_count=case.get("chunk_count", 0),
        ingested_at=case.get("ingested_at"),
    )


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(422),
)
async def create_case(body: CaseCreate) -> CaseResponse:
    case = get_store().create_case(body.title, body.description)
    return to_case_response(case)


@router.get("", response_model=list[CaseResponse], responses=error_responses(422))
async def list_cases(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)
) -> list[CaseResponse]:
    """Cases ordered newest first."""
    return [to_case_response(c) for c in get_store().list_cases(skip, limit)]


@router.get("/{case_id}", response_model=CaseResponse, responses=error_responses(404))
async def get_case(case_id: str) -> CaseResponse:
    return to_case_response(get_store().require_case(case_id))


@router.patch(
    "/{case_id}", response_model=CaseResponse, responses=error_responses(404, 422)
)
async def update_case(case_id: str, body: CaseUpdate) -> CaseResponse:
    changes: dict = {}
    if body.title is not None:
        changes["title"] = body.title
    if "description" in body.model_fields_set:
        changes["description"] = body.description
    case = get_store().update_case(case_id, **changes)
    return to_case_response(case)


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=error_responses(404),
)
async def delete_case(case_id: str) -> Response:
    """Delete the case, its uploads and its Chroma collection."""
    store = get_store()
    store.require_case(case_id)
    get_vectorstore().reset_case(case_id)
    store.delete_case(case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
