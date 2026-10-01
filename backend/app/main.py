"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import __version__
from app.core.config import Settings, get_settings
from app.core.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.routes import api_router, public_router

DESCRIPTION = (
    "Diploma prototype: upload, ingest, summarize, verify. "
    "Local Ollama only; no cloud LLM APIs for case document data. "
    "Case documents: Bulgarian PDF/TXT only. "
    "Out of scope: legal interpretation, timelines, classification, "
    "legal conclusions."
)


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """Use route function names as OpenAPI operation IDs for simpler clients.

    Must be called after all routes have been added.
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    for path in (settings.data_dir, settings.upload_dir, settings.chroma_path):
        path.mkdir(parents=True, exist_ok=True)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Legal Document Assistant API",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(public_router)
    app.include_router(api_router)

    use_route_names_as_operation_ids(app)
    return app


app = create_app()
