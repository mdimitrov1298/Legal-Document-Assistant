"""Root, liveness, dependency health and model endpoints."""

from __future__ import annotations

import httpx

from app import __version__


def _tags(*names: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": n} for n in names]})
        return httpx.Response(404)

    return handler


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {
        "service": "Legal Document Assistant API",
        "version": __version__,
        "docs": "/docs",
    }


def test_liveness(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ok_when_model_present(client, install_llm):
    install_llm(_tags("qwen2.5:7b", "nomic-embed-text"))
    data = client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert data["ollama"] == {
        "reachable": True,
        "base_url": "http://ollama.test",
        "model": "qwen2.5:7b",
        "model_present": True,
        "models_installed": ["qwen2.5:7b", "nomic-embed-text"],
    }
    assert data["embeddings"]["backend"] == "hash_stub"
    assert data["embeddings"]["backend_configured"] == "hash_stub"
    assert data["embeddings"]["device"] == "cpu"
    assert data["vector_store"]["path"].endswith("chroma")
    assert data["chunking"] == {"size": 800, "overlap": 120}


def test_health_degraded_when_model_missing(client, install_llm):
    install_llm(_tags("llama3.1:8b"))
    data = client.get("/api/v1/health").json()
    assert data["status"] == "degraded"
    assert data["ollama"]["model_present"] is False


def test_health_degraded_when_ollama_down(client):
    data = client.get("/api/v1/health").json()
    assert data["status"] == "degraded"
    assert data["ollama"]["reachable"] is False
    assert data["ollama"]["model_present"] is None


def test_models(client, install_llm):
    install_llm(_tags("qwen2.5:7b", "bggpt-7b:latest"))
    assert client.get("/api/v1/models").json() == {
        "active": "qwen2.5:7b",
        "reachable": True,
        "installed": ["qwen2.5:7b", "bggpt-7b:latest"],
    }


def test_models_when_down(client):
    assert client.get("/api/v1/models").json() == {
        "active": "qwen2.5:7b",
        "reachable": False,
        "installed": [],
    }


def test_operation_ids_use_route_names(client):
    spec = client.get("/openapi.json").json()
    op_ids = {
        op["operationId"] for path in spec["paths"].values() for op in path.values()
    }
    assert {
        "create_case",
        "upload_document",
        "ingest_case",
        "get_index_stats",
        "verify_claim",
        "list_models",
    } <= op_ids
