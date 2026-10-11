"""Service info, liveness, dependency health and model status."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.schemas.system import (
    ChunkingStatus,
    EmbeddingStatus,
    HealthResponse,
    LivenessResponse,
    ModelsResponse,
    OllamaStatus,
    RootResponse,
    RoutingStatus,
    VectorStoreStatus,
)
from app.services.embeddings import get_embedder, get_embedding_backend
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

public_router = APIRouter(tags=["system"])
router = APIRouter(tags=["system"])


@public_router.get("/", response_model=RootResponse)
async def read_root() -> RootResponse:
    return RootResponse(
        service="Legal Document Assistant API", version=__version__, docs="/docs"
    )


@public_router.get("/health", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Liveness only: no dependency checks."""
    return LivenessResponse()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Ollama reachability and model presence, embeddings, vector store, chunking."""
    settings = get_settings()
    llm = get_llm()
    reachable, installed = await llm.probe()
    model_present = llm.is_model_installed(installed) if reachable else None
    # Initialise the embedder so the backend label reflects any fallback
    try:
        get_embedder(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedder initialisation failed: %s", exc)
    degraded = not reachable or not model_present
    return HealthResponse(
        status="degraded" if degraded else "ok",
        version=__version__,
        ollama=OllamaStatus(
            reachable=reachable,
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            model_present=model_present,
            models_installed=installed,
        ),
        embeddings=EmbeddingStatus(
            backend=get_embedding_backend(),
            backend_configured=settings.embedding_backend,
            model=settings.embedding_model,
            device=settings.embedding_device,
        ),
        vector_store=VectorStoreStatus(path=str(settings.chroma_path)),
        chunking=ChunkingStatus(
            size=settings.chunk_size, overlap=settings.chunk_overlap
        ),
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """Active OLLAMA_MODEL, installed models and model routing state."""
    settings = get_settings()
    llm = get_llm()
    reachable, installed = await llm.probe()
    routing = RoutingStatus(
        mode=settings.model_routing,
        model_bg=settings.ollama_model_bg,
        model_en=settings.ollama_model_en,
    )
    return ModelsResponse(
        active=llm.model_name,
        reachable=reachable,
        installed=installed,
        routing=routing,
    )
