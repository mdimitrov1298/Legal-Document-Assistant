"""Unit tests for keyword matching, highlights and search service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services import search
from app.services.search import (
    SearchResponse,
    _find_highlights,
    _reciprocal_rank_fusion,
    search_case,
)

# ---------------------------------------------------------------------------
# Highlight offset tests
# ---------------------------------------------------------------------------


def test_highlight_exact():
    h = _find_highlights("The fee is 4500 BGN.", "4500")
    assert len(h) == 1
    assert h[0].start == 11
    assert h[0].end == 15
    assert "The fee is 4500 BGN."[h[0].start : h[0].end] == "4500"


def test_highlight_case_insensitive():
    h = _find_highlights("Contract signed in Plovdiv.", "plovdiv")
    assert len(h) == 1
    assert h[0].start == 19
    assert h[0].end == 26


def test_highlight_multiple():
    h = _find_highlights("abc abc abc", "abc")
    assert len(h) == 3


def test_highlight_empty_query():
    assert _find_highlights("some text", "") == []


def test_highlight_no_match():
    assert _find_highlights("some text", "xyz") == []


def test_highlight_special_chars():
    h = _find_highlights("Price is $100.00 per item.", "$100.00")
    assert len(h) == 1
    assert h[0].start == 9
    assert h[0].end == 16


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

HIT_A = {
    "chunk_id": "d1:0",
    "text": "Възнаграждението от 4500 лв. се плаща в срок от 30 дни.",
    "metadata": {
        "document_id": "d1",
        "document_filename": "dogovor.txt",
        "chunk_index": 0,
        "language": "bg",
    },
    "relevance": 0.9,
}

HIT_B = {
    "chunk_id": "d1:1",
    "text": "Договорът е подписан в гр. Пловдив на 15.01.2024 г.",
    "metadata": {
        "document_id": "d1",
        "document_filename": "dogovor.txt",
        "chunk_index": 1,
        "language": "bg",
    },
    "relevance": 0.7,
}


# ---------------------------------------------------------------------------
# Reciprocal rank fusion
# ---------------------------------------------------------------------------


def test_rrf_merges_and_ranks():
    fused = _reciprocal_rank_fusion([HIT_A, HIT_B], [HIT_B, HIT_A], top_k=10)
    ids = [h["chunk_id"] for h, _ in fused]
    assert set(ids) == {"d1:0", "d1:1"}
    assert len(fused) == 2
    # Both appear in both lists so scores should be positive
    assert all(score > 0 for _, score in fused)


def test_rrf_respects_top_k():
    fused = _reciprocal_rank_fusion([HIT_A, HIT_B], [HIT_B], top_k=1)
    assert len(fused) == 1


# ---------------------------------------------------------------------------
# search_case integration (mocked store / vs)
# ---------------------------------------------------------------------------


@pytest.fixture
def search_env(monkeypatch: pytest.MonkeyPatch):
    case = {"id": "c1", "title": "Demo", "documents": [], "status": "ingested"}
    store = MagicMock()
    store.require_case.return_value = case

    # Mock a Chroma collection
    coll = MagicMock()
    coll.count.return_value = 2
    coll.get.return_value = {
        "ids": ["d1:0", "d1:1"],
        "documents": [HIT_A["text"], HIT_B["text"]],
        "metadatas": [HIT_A["metadata"], HIT_B["metadata"]],
    }

    vs = MagicMock()
    vs.query.return_value = [HIT_A, HIT_B]
    vs.collection_name.return_value = "case_c1"
    vs._client.get_collection.return_value = coll

    monkeypatch.setattr(search, "get_store", lambda: store)
    monkeypatch.setattr(search, "get_vectorstore", lambda: vs)
    return store, vs


def test_keyword_search(search_env):
    result = search_case("c1", "4500", top_k=10, mode="keyword")
    assert isinstance(result, SearchResponse)
    assert result.mode == "keyword"
    assert len(result.results) == 1
    assert result.results[0].chunk_id == "d1:0"
    assert result.results[0].highlights[0].start == 20
    assert result.results[0].highlights[0].end == 24


def test_semantic_search(search_env):
    result = search_case("c1", "възнаграждение", top_k=10, mode="semantic")
    assert result.mode == "semantic"
    assert len(result.results) == 2


def test_hybrid_search(search_env):
    result = search_case("c1", "4500", top_k=10, mode="hybrid")
    assert result.mode == "hybrid"
    assert len(result.results) >= 1
    # The keyword-matching chunk should rank well
    ids = [r.chunk_id for r in result.results]
    assert "d1:0" in ids


def test_empty_query_raises(search_env):
    """SearchRequest validation catches empty query before it reaches service."""
    from pydantic import ValidationError

    from app.schemas.rag import SearchRequest

    with pytest.raises(ValidationError):
        SearchRequest(query="", top_k=10, mode="keyword")


def test_not_ingested_case_raises(monkeypatch: pytest.MonkeyPatch):
    case = {"id": "c2", "title": "New", "documents": [], "status": "uploaded"}
    store = MagicMock()
    store.require_case.return_value = case
    monkeypatch.setattr(search, "get_store", lambda: store)
    from app.core.errors import CaseNotIngestedError

    with pytest.raises(CaseNotIngestedError):
        search_case("c2", "test")
