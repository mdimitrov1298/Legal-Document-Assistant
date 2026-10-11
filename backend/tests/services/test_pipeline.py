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


HIT_OTHER = {
    "chunk_id": "doc2:0",
    "text": "Der Vertrag wird am 1. Januar 2024 unterzeichnet.",
    "metadata": {
        "document_id": "doc2",
        "document_filename": "vertrag.txt",
        "chunk_index": 0,
        "language": "other",
    },
    "relevance": 0.70,
}


@pytest.fixture
def rag_env_other(monkeypatch: pytest.MonkeyPatch):
    """Env where all chunks are detected as 'other' language."""
    case = {"id": "case-2", "title": "Deutsch", "documents": [], "status": "ingested"}
    store = MagicMock()
    store.get_case.return_value = case
    store.require_case.return_value = case
    vs = MagicMock()
    vs.query.return_value = [HIT_OTHER]
    monkeypatch.setattr(pipeline, "get_store", lambda: store)
    monkeypatch.setattr(pipeline, "get_vectorstore", lambda: vs)
    return store, vs


async def test_other_language_uses_bg_prompts_and_warns(rag_env_other, install_llm):
    install_llm(_down)
    result = await pipeline.verify_claim("case-2", "Der Vertrag ist gültig")
    assert result.answer_language == "bg"
    assert result.language_warning is not None
    assert "неподдържан" in result.language_warning


async def test_other_language_summarize_warns(rag_env_other, install_llm):
    install_llm(_down)
    result = await pipeline.summarize_case("case-2")
    assert result.answer_language == "bg"
    assert result.language_warning is not None


async def test_bg_language_no_warning(rag_env, install_llm):
    install_llm(_down)
    result = await pipeline.verify_claim("case-1", "Нещо")
    assert result.answer_language == "bg"
    assert result.language_warning is None


# ---------------------------------------------------------------------------
# ask_question tests
# ---------------------------------------------------------------------------


async def test_ask_returns_answer_with_citation(rag_env, install_llm):
    install_llm(
        _respond(
            {
                "answer": "Възнаграждението е 4500 лв.",
                "status": "answered",
                "evidence": [{"index": 1, "quote": "4500 лв."}],
            }
        )
    )
    result = await pipeline.ask_question("case-1", "Какво е възнаграждението?")
    assert result.stubbed is False
    assert result.answer_status == "answered"
    assert "4500" in result.answer
    assert len(result.citations) >= 1
    assert result.model == "qwen2.5:7b"


async def test_ask_not_found(rag_env, install_llm):
    install_llm(
        _respond(
            {
                "answer": "Не е намерена информация в документите.",
                "status": "not_found",
                "evidence": [],
            }
        )
    )
    result = await pipeline.ask_question("case-1", "Колко е данъкът?")
    assert result.answer_status == "not_found"
    assert result.citations == []


async def test_ask_stub(rag_env, install_llm):
    install_llm(_down)
    result = await pipeline.ask_question("case-1", "Какъв е срокът?")
    assert result.stubbed is True
    assert result.answer_status == "not_found"
    assert len(result.retrieved_quotes) == 2


async def test_ask_prompt_selection_bg(rag_env, install_llm):
    """BG chunks get Bulgarian ask prompt."""
    install_llm(_down)
    result = await pipeline.ask_question("case-1", "Какъв е срокът?")
    assert result.answer_language == "bg"
    assert result.prompt_version == "bg-v1"


def test_parse_json_object_handles_markdown_code_block():
    from app.services.pipeline import _parse_json_object

    raw = '```json\n{\n  "verdict": "supported",\n  "rationale": "ok"\n}\n```'
    assert _parse_json_object(raw) == {"verdict": "supported", "rationale": "ok"}


def test_parse_json_object_handles_unterminated_code_block():
    from app.services.pipeline import _parse_json_object

    raw = '```JSON\n{"verdict": "denied", "rationale": "x"}'
    assert _parse_json_object(raw)["verdict"] == "denied"


def test_verdict_regex_recovers_from_truncated_json():
    # C24 case from run 20261004T073507Z: fenced JSON cut off mid-field
    from app.services.pipeline import _VERDICT_FIELD, _parse_json_object

    raw = (
        '```json\n{\n  "verdict": "supported",\n  "rationale": "т",\n  "supporting_quo'
    )
    assert _parse_json_object(raw) == {}
    m = _VERDICT_FIELD.search(raw)
    assert m and m.group(1) == "supported"


# ---------------------------------------------------------------------------
# Language-based model routing tests (W8)
# ---------------------------------------------------------------------------


HIT_EN = {
    "chunk_id": "doc3:0",
    "text": "The contract was signed by John Smith on 15 January 2024.",
    "metadata": {
        "document_id": "doc3",
        "document_filename": "contract.txt",
        "chunk_index": 0,
        "language": "en",
    },
    "relevance": 0.88,
}


@pytest.fixture
def rag_env_en(monkeypatch: pytest.MonkeyPatch):
    """Env where all chunks are English."""
    case = {"id": "case-en", "title": "English", "documents": [], "status": "ingested"}
    store = MagicMock()
    store.get_case.return_value = case
    store.require_case.return_value = case
    vs = MagicMock()
    vs.query.return_value = [HIT_EN]
    monkeypatch.setattr(pipeline, "get_store", lambda: store)
    monkeypatch.setattr(pipeline, "get_vectorstore", lambda: vs)
    return store, vs


async def test_routing_off_uses_default_model(rag_env, install_llm, monkeypatch):
    """With routing=off, the default OLLAMA_MODEL is used."""
    monkeypatch.setenv("MODEL_ROUTING", "off")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    install_llm(_down)
    result = await pipeline.verify_claim("case-1", "Нещо")
    assert result.routed is False
    assert result.model == "qwen2.5:7b"


async def test_routing_language_bg_uses_bg_model(rag_env, install_llm, monkeypatch):
    """With routing=language, BG chunks → OLLAMA_MODEL_BG."""
    monkeypatch.setenv("MODEL_ROUTING", "language")
    monkeypatch.setenv("OLLAMA_MODEL_BG", "bggpt-test:latest")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    install_llm(_down)
    result = await pipeline.verify_claim("case-1", "Нещо")
    assert result.routed is True
    assert result.model == "bggpt-test:latest"


async def test_routing_language_en_uses_en_model(rag_env_en, install_llm, monkeypatch):
    """With routing=language, EN chunks → OLLAMA_MODEL_EN."""
    monkeypatch.setenv("MODEL_ROUTING", "language")
    monkeypatch.setenv("OLLAMA_MODEL_EN", "qwen-test:latest")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    install_llm(_down)
    result = await pipeline.verify_claim("case-en", "Something")
    assert result.routed is True
    assert result.model == "qwen-test:latest"


async def test_routing_language_summarize(rag_env, install_llm, monkeypatch):
    """Summarize respects routing too."""
    monkeypatch.setenv("MODEL_ROUTING", "language")
    monkeypatch.setenv("OLLAMA_MODEL_BG", "bggpt-test:latest")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    install_llm(_down)
    result = await pipeline.summarize_case("case-1")
    assert result.routed is True
    assert result.model == "bggpt-test:latest"


async def test_routing_language_ask(rag_env_en, install_llm, monkeypatch):
    """Ask respects routing too."""
    monkeypatch.setenv("MODEL_ROUTING", "language")
    monkeypatch.setenv("OLLAMA_MODEL_EN", "qwen-test:latest")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    install_llm(_down)
    result = await pipeline.ask_question("case-en", "What is the contract?")
    assert result.routed is True
    assert result.model == "qwen-test:latest"


async def test_routing_off_response_has_routed_false(rag_env, install_llm):
    """Default (routing=off) responses have routed=False."""
    install_llm(_down)
    summary = await pipeline.summarize_case("case-1")
    assert summary.routed is False
    verify = await pipeline.verify_claim("case-1", "Нещо")
    assert verify.routed is False
    ask = await pipeline.ask_question("case-1", "Какъв е срокът?")
    assert ask.routed is False
