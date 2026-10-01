"""Chroma local persistent vector store per case.

Uses chromadb.PersistentClient under CHROMA_PATH so collections survive process
restarts. Embeddings are computed by our embedder (sentence-transformers or hash stub)
and stored with the chunks, so ingest does not require Ollama.
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import Settings, get_settings
from app.services.embeddings import get_embedder

logger = logging.getLogger(__name__)


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma only accepts str/int/float/bool metadata values."""
    out: dict[str, str | int | float | bool] = {}
    for k, v in meta.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, int) and not isinstance(v, bool):
            out[k] = v
        elif isinstance(v, float):
            out[k] = v
        elif v is None:
            continue
        else:
            out[k] = str(v)
    return out


class VectorStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        path = str(self.settings.chroma_path)
        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embed = get_embedder(self.settings)
        logger.info("Chroma PersistentClient at %s", path)

    @property
    def persist_path(self) -> str:
        return str(self.settings.chroma_path)

    @staticmethod
    def collection_name(case_id: str) -> str:
        safe = case_id.replace("-", "")
        return f"case_{safe}"

    def reset_case(self, case_id: str) -> None:
        name = self.collection_name(case_id)
        try:
            self._client.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass

    def delete_document_chunks(self, case_id: str, document_id: str) -> int:
        """Remove one document's chunks; returns the remaining chunk count."""
        try:
            coll = self._client.get_collection(self.collection_name(case_id))
        except Exception:  # noqa: BLE001
            return 0
        coll.delete(where={"document_id": document_id})
        return int(coll.count())

    def count(self, case_id: str) -> int:
        name = self.collection_name(case_id)
        try:
            return int(self._client.get_collection(name).count())
        except Exception:  # noqa: BLE001
            return 0

    def upsert_chunks(
        self,
        case_id: str,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        if not ids:
            return 0
        coll = self._client.get_or_create_collection(
            name=self.collection_name(case_id),
            metadata={"hnsw:space": "cosine"},
        )
        embeddings = self._embed(documents)
        clean_meta = [_sanitize_metadata(m) for m in metadatas]
        # Batch to keep memory bounded on 16GB machines
        batch = 64
        for i in range(0, len(ids), batch):
            sl = slice(i, i + batch)
            coll.upsert(
                ids=ids[sl],
                documents=documents[sl],
                metadatas=clean_meta[sl],
                embeddings=embeddings[sl],
            )
        return len(ids)

    def query(
        self,
        case_id: str,
        query_text: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        name = self.collection_name(case_id)
        try:
            coll = self._client.get_collection(name)
        except Exception:  # noqa: BLE001
            return []
        n = coll.count()
        if n == 0:
            return []
        q_emb = self._embed([query_text])[0]
        result = coll.query(
            query_embeddings=[q_emb],
            n_results=min(top_k, n),
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        if not result or not result.get("ids") or not result["ids"][0]:
            return hits
        for i, chunk_id in enumerate(result["ids"][0]):
            dist = None
            if result.get("distances"):
                dist = result["distances"][0][i]
            meta = result["metadatas"][0][i] if result.get("metadatas") else {}
            doc = result["documents"][0][i] if result.get("documents") else ""
            relevance = None if dist is None else max(0.0, 1.0 - float(dist))
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc,
                    "metadata": meta or {},
                    "relevance": relevance,
                }
            )
        return hits


_vs: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    global _vs
    if _vs is None:
        _vs = VectorStore()
    return _vs


def reset_vectorstore(store: VectorStore | None = None) -> None:
    global _vs
    _vs = store
