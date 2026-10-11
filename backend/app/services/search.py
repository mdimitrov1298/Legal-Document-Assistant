"""Interactive search over indexed case chunks.

Three modes:
- **semantic**: vector similarity via the existing Chroma collection.
- **keyword**: case-insensitive substring match over stored chunk texts.
- **hybrid**: reciprocal rank fusion of semantic and keyword results.

No LLM call — works without Ollama.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.schemas.rag import SearchHighlight, SearchResponse, SearchResult
from app.services.storage import STATUS_INGESTED, STATUS_STALE, get_store
from app.services.vector_store import get_vectorstore

QUERYABLE_STATUSES = {STATUS_INGESTED, STATUS_STALE}

# RRF constant (standard value from Cormack et al.)
_RRF_K = 60


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _find_highlights(text: str, query: str) -> list[SearchHighlight]:
    """Find all case-insensitive occurrences of *query* in *text*."""
    highlights: list[SearchHighlight] = []
    if not query:
        return highlights
    pattern = re.escape(query)
    for m in re.finditer(pattern, text, re.IGNORECASE):
        highlights.append(SearchHighlight(start=m.start(), end=m.end()))
    return highlights


def _result_from_hit(hit: dict[str, Any], score: float, query: str) -> SearchResult:
    meta = hit.get("metadata") or {}
    text = str(hit.get("text", ""))
    chunk_index = meta.get("chunk_index")
    if isinstance(chunk_index, bool):
        chunk_index = None
    return SearchResult(
        document_id=str(meta.get("document_id", "")),
        document_filename=str(meta.get("document_filename", "")),
        chunk_id=str(hit.get("chunk_id", "")),
        chunk_index=chunk_index,
        text=text,
        score=round(score, 6),
        highlights=_find_highlights(text, query),
        language=str(meta.get("language", "bg")),
    )


def _semantic_search(case_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    """Return ranked hits from Chroma vector similarity."""
    vs = get_vectorstore()
    return vs.query(case_id, query, top_k=top_k)


def _keyword_search(case_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    """Case-insensitive substring match over all chunks in the collection.

    Chroma's ``$contains`` is limited, so we fetch all chunks and filter
    in Python for reliable case-insensitive matching.
    """
    vs = get_vectorstore()
    name = vs.collection_name(case_id)
    try:
        coll = vs._client.get_collection(name)
    except Exception:  # noqa: BLE001
        return []
    n = coll.count()
    if n == 0:
        return []
    result = coll.get(include=["documents", "metadatas"])
    if not result or not result.get("ids"):
        return []

    query_lower = query.lower()
    hits: list[dict[str, Any]] = []
    for i, chunk_id in enumerate(result["ids"]):
        doc_text = result["documents"][i] if result.get("documents") else ""
        if query_lower not in doc_text.lower():
            continue
        meta = result["metadatas"][i] if result.get("metadatas") else {}
        hits.append(
            {
                "chunk_id": chunk_id,
                "text": doc_text,
                "metadata": meta or {},
                "relevance": 1.0,
            }
        )
    return hits[:top_k]


def _reciprocal_rank_fusion(
    semantic_hits: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    top_k: int,
) -> list[tuple[dict[str, Any], float]]:
    """Merge two ranked lists using reciprocal rank fusion."""
    scores: dict[str, float] = {}
    by_id: dict[str, dict[str, Any]] = {}

    for rank, hit in enumerate(semantic_hits):
        cid = hit["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        by_id[cid] = hit

    for rank, hit in enumerate(keyword_hits):
        cid = hit["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        by_id.setdefault(cid, hit)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(by_id[cid], score) for cid, score in ranked[:top_k]]


def search_case(
    case_id: str,
    query: str,
    top_k: int = 10,
    mode: str = "hybrid",
) -> SearchResponse:
    """Execute an interactive search over an indexed case."""
    started = time.perf_counter()

    # Validate case exists and is indexed
    store = get_store()
    case = store.require_case(case_id)
    from app.core.errors import CaseNotIngestedError

    if case.get("status") not in QUERYABLE_STATUSES:
        raise CaseNotIngestedError(
            details={"case_id": case_id, "status": case.get("status")}
        )

    results: list[SearchResult] = []

    if mode == "semantic":
        hits = _semantic_search(case_id, query, top_k)
        for hit in hits:
            score = hit.get("relevance") or 0.0
            results.append(_result_from_hit(hit, score, query))

    elif mode == "keyword":
        hits = _keyword_search(case_id, query, top_k)
        for hit in hits:
            results.append(_result_from_hit(hit, 1.0, query))

    else:  # hybrid
        sem_hits = _semantic_search(case_id, query, top_k)
        kw_hits = _keyword_search(case_id, query, top_k)
        fused = _reciprocal_rank_fusion(sem_hits, kw_hits, top_k)
        for hit, score in fused:
            results.append(_result_from_hit(hit, score, query))

    return SearchResponse(
        query=query,
        results=results,
        duration_ms=_elapsed_ms(started),
        mode=mode,
    )
