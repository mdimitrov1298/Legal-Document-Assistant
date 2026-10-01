"""Embeddings for ~16GB machines.

Backends (EMBEDDING_BACKEND):
  - sentence-transformers (default): all-MiniLM-L6-v2 on CPU, offline after download
  - ollama: POST /api/embeddings (e.g. nomic-embed-text), needs Ollama running
  - hash_stub: deterministic local stub for CI / offline fallback

EMBEDDING_MODEL selects the model id for the chosen backend.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

EmbedFn = Callable[[Sequence[str]], list[list[float]]]

_model: EmbedFn | None = None
_model_name: str | None = None
_backend: str = "uninitialized"


def get_embedding_backend() -> str:
    return _backend


def reset_embedder() -> None:
    global _model, _model_name, _backend
    _model = None
    _model_name = None
    _backend = "uninitialized"


def get_embedder(settings: Settings | None = None) -> EmbedFn:
    global _model, _model_name, _backend
    settings = settings or get_settings()
    name = settings.embedding_model
    backend_pref = (
        (settings.embedding_backend or "sentence-transformers").strip().lower()
    )

    cache_key = f"{backend_pref}:{name}"
    if _model is not None and _model_name == cache_key:
        return _model

    if (
        backend_pref in {"hash", "hash_stub"}
        or name.startswith("__")
        or name in {"hash", "hash_stub"}
    ):
        _model = _hash_embedder
        _model_name = cache_key
        _backend = "hash_stub"
        logger.info("Using hash stub embeddings")
        return _model

    if backend_pref == "ollama":
        try:
            encode = _make_ollama_embedder(settings, name)
            _model = encode
            _model_name = cache_key
            _backend = "ollama"
            logger.info("Using Ollama embeddings model=%s", name)
            return _model
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ollama embeddings unavailable (%s); falling back to hash stub",
                exc,
            )
            _model = _hash_embedder
            _model_name = cache_key
            _backend = "hash_stub"
            return _model

    # Default: sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model %s on %s", name, settings.embedding_device)
        st = SentenceTransformer(name, device=settings.embedding_device)

        def encode(texts: Sequence[str]) -> list[list[float]]:
            vectors = st.encode(list(texts), show_progress_bar=False)
            return [v.tolist() for v in vectors]

        _model = encode
        _model_name = cache_key
        _backend = "sentence-transformers"
        return _model
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sentence-transformers unavailable (%s); using hash stub embeddings",
            exc,
        )
        _model = _hash_embedder
        _model_name = cache_key
        _backend = "hash_stub"
        return _model


def _make_ollama_embedder(settings: Settings, model: str) -> EmbedFn:
    base = settings.ollama_base_url.rstrip("/")
    timeout = max(30.0, float(settings.ollama_generate_timeout))

    # Probe once
    with httpx.Client(timeout=settings.ollama_health_timeout) as client:
        r = client.get(f"{base}/api/tags")
        r.raise_for_status()

    def encode(texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        with httpx.Client(timeout=timeout) as client:
            for t in texts:
                r = client.post(
                    f"{base}/api/embeddings",
                    json={"model": model, "prompt": t},
                )
                r.raise_for_status()
                data = r.json()
                emb = data.get("embedding")
                if not emb:
                    raise RuntimeError(f"Ollama embeddings empty for model={model}")
                out.append([float(x) for x in emb])
        return out

    return encode


def _hash_embedder(texts: Sequence[str]) -> list[list[float]]:
    dim = 384
    out: list[list[float]] = []
    for t in texts:
        vec = [0.0] * dim
        for i, ch in enumerate(t.encode("utf-8", errors="ignore")[:4096]):
            vec[i % dim] += (ch % 31) / 31.0
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        out.append([x / norm for x in vec])
    return out
