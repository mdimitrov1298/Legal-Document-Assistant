"""Shared fixtures: isolated data dirs, hash_stub embeddings, mocked Ollama."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, clear_settings_cache, get_settings
from app.services.embeddings import reset_embedder
from app.services.llm import OllamaClient, reset_llm
from app.services.storage import reset_store
from app.services.vector_store import reset_vectorstore

OLLAMA_TEST_URL = "http://ollama.test"

Handler = Callable[[httpx.Request], httpx.Response]


def ollama_down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def _reset_all() -> None:
    clear_settings_cache()
    reset_llm(None)
    reset_store(None)
    reset_vectorstore(None)
    reset_embedder()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point every setting at a temp dir and use offline-friendly backends."""
    data = tmp_path / "data"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("CHROMA_PATH", str(data / "chroma"))
    monkeypatch.setenv("UPLOAD_DIR", str(data / "uploads"))
    monkeypatch.setenv("EMBEDDING_BACKEND", "hash_stub")
    monkeypatch.setenv("EMBEDDING_MODEL", "hash_stub")
    monkeypatch.setenv("OLLAMA_BASE_URL", OLLAMA_TEST_URL)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    _reset_all()
    reset_llm(OllamaClient(get_settings(), transport=httpx.MockTransport(ollama_down)))
    yield data
    _reset_all()


@pytest.fixture
def install_llm() -> Callable[..., OllamaClient]:
    """Replace the process LLM with one backed by an httpx mock handler."""

    def _install(handler: Handler, **overrides) -> OllamaClient:
        settings = get_settings().model_copy(update=overrides)
        client = OllamaClient(settings, transport=httpx.MockTransport(handler))
        reset_llm(client)
        return client

    return _install


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
