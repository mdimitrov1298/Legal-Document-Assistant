"""HTTP routers. Versioned endpoints live under /api/v1."""

from fastapi import APIRouter

from app.routes import cases, documents, rag, system

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(system.router)
api_router.include_router(cases.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)

public_router = system.public_router

__all__ = ["API_PREFIX", "api_router", "public_router"]
