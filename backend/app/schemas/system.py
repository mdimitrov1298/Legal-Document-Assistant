"""System, health and model status models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    service: str
    version: str
    docs: str


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class OllamaStatus(BaseModel):
    reachable: bool
    base_url: str
    model: str
    model_present: bool | None = Field(
        None, description="Whether OLLAMA_MODEL is pulled; null if unreachable"
    )
    models_installed: list[str] = Field(default_factory=list)


class EmbeddingStatus(BaseModel):
    backend: str = Field(..., description="Backend actually in use")
    backend_configured: str = Field(..., description="EMBEDDING_BACKEND setting")
    model: str
    device: str


class VectorStoreStatus(BaseModel):
    path: str


class ChunkingStatus(BaseModel):
    size: int
    overlap: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = Field(
        ..., description="degraded when Ollama is unreachable or the model is missing"
    )
    version: str
    ollama: OllamaStatus
    embeddings: EmbeddingStatus
    vector_store: VectorStoreStatus
    chunking: ChunkingStatus


class ModelsResponse(BaseModel):
    active: str
    reachable: bool
    installed: list[str] = Field(default_factory=list)
