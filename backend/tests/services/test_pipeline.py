"""Summarize and verify use the LLM client; stubbed flag and citations propagate."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.services import pipeline

HIT_SIGNED = {
    "chunk_id": "doc1:0",
    "text": "Договорът е подписан от Иван Петров и Мария Георгиева на 15.01.2024 г.",
    "metadata": {
        "document_id": "doc1",
        "document_filename": "dogovor.txt",
        "chunk_index": 0,
    },
    "relevance": 0.91,
}
HIT_PAYMENT = {
    "chunk_id": "doc1:1",
    "text": "Възнаграждението от 4500 лв. се плаща в срок от 30 дни.",
    "metadata": {
        "document_id": "doc1",
        "document_filename": "dogovor.txt",
        "chunk_index": 1,
    },
    "relevance": 0.80,
}


@pytest.fixture
def rag_env(monkeypatch: pytest.MonkeyPatch):
    case = {"id": "case-1", "title": "Демо", "documents": [], "status": "ingested"}
    store = MagicMock()
    store.get_case.return_value = case
    store.require_case.return_value = case
    vs = MagicMock()
    vs.query.return_value = [HIT_SIGNED, HIT_PAYMENT]
    monkeypatch.setattr(pipeline, "get_store", lambda: store)
    monkeypatch.setattr(pipeline, "get_vectorstore", lambda: vs)
    return store, vs


def _respond(payload) -> callable:
    text = payload if isinstance(payload, str) else json.dumps(payload)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": text})

    return handler


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


async def test_summarize_plain_text_response(rag_env, install_llm):
    install_llm(_respond("- Иван Петров и Мария Георгиева подписват договора."))
    result = await pipeline.summarize_case("case-1")
    assert result.stubbed is False
    assert "Иван Петров" in result.summary
    assert result.model == "qwen2.5:7b"
    assert result.chunks_used == 2


async def test_summarize_returns_rag_citations(rag_env, install_llm):
    install_llm(
        _respond({"summary": "Договор за 4500 лв.", "citation_indices": [0, 1]})
    )
    result = await pipeline.summarize_case("case-1")
    assert result.stubbed is False
    assert [c.chunk_id for c in result.citations] == ["doc1:0", "doc1:1"]
    assert "подписан" in result.citations[0].quote


async def test_summarize_stub_still_returns_citations(rag_env, install_llm):
    install_llm(_down)
    result = await pipeline.summarize_case("case-1")
    assert result.stubbed is True
    assert "STUB SUMMARY" in result.summary
    assert len(result.citations) == 2


async def test_verify_uses_model_json(rag_env, install_llm):
    install_llm(
        _respond(
            {
                "verdict": "supported",
                "rationale": "Цитат [1] посочва 4500 лв.",
                "supporting_quote_indices": [1],
                "denying_quote_indices": [],
            }
        )
    )
    result = await pipeline.verify_claim("case-1", "Възнаграждението е 4500 лв.")
    assert result.stubbed is False
    assert result.verdict.value == "supported"
    assert [q.chunk_id for q in result.supporting_quotes] == ["doc1:1"]
    assert len(result.retrieved_quotes) == 2


async def test_verify_stub_surfaces_retrieved_quote(rag_env, install_llm):
    install_llm(_down)
    result = await pipeline.verify_claim("case-1", "Плащането е в срок от 30 дни")
    assert result.stubbed is True
    assert result.verdict.value == "inconclusive"
    assert "[STUB]" in result.rationale
    assert len(result.retrieved_quotes) == 2
    assert len(result.supporting_quotes) + len(result.denying_quotes) >= 1


async def test_verify_flags_non_verbatim_model_quotes(rag_env, install_llm):
    install_llm(
        _respond(
            {
                "verdict": "denied",
                "rationale": "Сумата е друга.",
                "supporting_quotes": [],
                "denying_quotes": [
                    {"index": 1, "quote": "Възнаграждението   от 4500 лв."},
                    {"index": 1, "quote": "Възнаграждението е 5000 лв."},
                ],
            }
        )
    )
    result = await pipeline.verify_claim("case-1", "Възнаграждението е 5000 лв.")
    assert result.verdict.value == "denied"
    assert [q.verbatim for q in result.denying_quotes] == [True, False]
    assert result.denying_quotes[0].chunk_index == 1
    assert all(q.verbatim for q in result.retrieved_quotes)


async def test_summarize_stub_citations_are_verbatim(rag_env, install_llm):
    install_llm(_down)
    result = await pipeline.summarize_case("case-1")
    assert all(c.verbatim for c in result.citations)
    assert [c.chunk_index for c in result.citations] == [0, 1]


async def test_verify_unknown_verdict_becomes_inconclusive(rag_env, install_llm):
    install_llm(_respond({"verdict": "maybe", "rationale": "?"}))
    result = await pipeline.verify_claim("case-1", "Нещо неясно")
    assert result.verdict.value == "inconclusive"
