"""Ingest chunks, embeds and persists to Chroma across client reopen."""

from __future__ import annotations

from pathlib import Path

from app.core.config import clear_settings_cache, get_settings
from app.services.embeddings import get_embedding_backend, reset_embedder
from app.services.pipeline import ingest_case
from app.services.storage import CaseStore, reset_store
from app.services.vector_store import VectorStore, reset_vectorstore


async def test_ingest_persists_in_chroma(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "80")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")
    clear_settings_cache()
    settings = get_settings()
    store = CaseStore(settings)
    reset_store(store)
    vs = VectorStore(settings)
    reset_vectorstore(vs)

    case = store.create_case("Persist demo")
    text = (
        "Страна А се задължава да плати на Страна Б десет хиляди лева в срок от "
        "тридесет дни. Договорът е подписан в София на 15 януари 2024 г. от "
        "Иван Петров и Мария Георгиева. Задълженията за поверителност остават "
        "в сила две години след прекратяването."
    )
    store.add_document(case["id"], "dogovor.txt", "text/plain", text.encode("utf-8"))

    result = await ingest_case(case["id"])
    assert result.documents_processed == 1
    assert result.chunks_indexed >= 2
    assert result.persisted is True
    assert result.embedding_backend == "hash_stub"
    assert Path(result.vector_store_path).exists()
    assert vs.count(case["id"]) == result.chunks_indexed

    # A fresh PersistentClient on the same path must still see the data
    reset_vectorstore(None)
    reset_embedder()
    vs2 = VectorStore(settings)
    assert vs2.count(case["id"]) == result.chunks_indexed
    hits = vs2.query(case["id"], "подписан в София", top_k=3)
    assert len(hits) >= 1
    assert all(h["metadata"]["document_filename"] == "dogovor.txt" for h in hits)
    assert get_embedding_backend() == "hash_stub"
