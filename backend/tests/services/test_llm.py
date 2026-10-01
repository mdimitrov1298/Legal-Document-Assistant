"""Unit tests for OllamaClient with mocked HTTP; optional live check."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import LLMUnavailableError
from app.services.llm import OllamaClient, model_matches


def _settings(**kwargs) -> Settings:
    defaults = dict(
        ollama_base_url="http://ollama.test",
        ollama_model="qwen2.5:7b",
        ollama_stub_on_unavailable=True,
        ollama_health_timeout=2.0,
        ollama_generate_timeout=5.0,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_generate_success_uses_real_ollama():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = json.loads(request.content.decode())
        assert body["model"] == "qwen2.5:7b"
        assert body["stream"] is False
        assert body["prompt"] == "Summarize this."
        assert body["system"] == "Be brief."
        return httpx.Response(200, json={"response": "  Real summary from Ollama.  "})

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    text, stubbed = await client.generate("Summarize this.", system="Be brief.")
    assert stubbed is False
    assert text == "Real summary from Ollama."


@pytest.mark.asyncio
async def test_generate_connection_error_falls_back_to_stub():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    text, stubbed = await client.generate("Make a summary of the documents.")
    assert stubbed is True
    assert "[STUB SUMMARY]" in text
    assert "qwen2.5:7b" in text


@pytest.mark.asyncio
async def test_generate_timeout_falls_back_to_stub():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    text, stubbed = await client.generate(
        "CLAIM:\nx\n\nQUOTES:\n[0] ...\n\nJSON:",
        system="Reply with verdict JSON for the claim.",
    )
    assert stubbed is True
    data = json.loads(text)
    assert data["verdict"] == "inconclusive"
    assert "[STUB]" in data["rationale"]


@pytest.mark.asyncio
async def test_generate_http_error_falls_back_to_stub():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    text, stubbed = await client.generate("summary please")
    assert stubbed is True
    assert "[STUB SUMMARY]" in text


@pytest.mark.asyncio
async def test_generate_empty_response_falls_back_to_stub():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "   "})

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    text, stubbed = await client.generate("summary please")
    assert stubbed is True


@pytest.mark.asyncio
async def test_generate_raises_when_stub_disabled():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client = OllamaClient(
        _settings(ollama_stub_on_unavailable=False),
        transport=_mock_transport(handler),
    )
    with pytest.raises(LLMUnavailableError) as info:
        await client.generate("hi")
    assert info.value.status_code == 503
    assert info.value.code == "llm_unavailable"


@pytest.mark.asyncio
async def test_generate_sends_num_ctx_and_temperature():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["options"] == {"num_ctx": 8192, "temperature": 0.0}
        assert "raw" not in body
        return httpx.Response(200, json={"response": "ok"})

    client = OllamaClient(
        _settings(ollama_num_ctx=8192, ollama_temperature=0.0),
        transport=_mock_transport(handler),
    )
    assert await client.generate("hi", system="sys") == ("ok", False)


@pytest.mark.asyncio
async def test_bggpt_uses_inst_template_in_raw_mode():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["raw"] is True
        assert "system" not in body
        assert body["prompt"] == "[INST] Системна инструкция\n\nВъпрос [/INST]"
        return httpx.Response(200, json={"response": "отговор"})

    client = OllamaClient(
        _settings(ollama_model="bggpt-7b"), transport=_mock_transport(handler)
    )
    text, stubbed = await client.generate("Въпрос", system="Системна инструкция")
    assert (text, stubbed) == ("отговор", False)


@pytest.mark.asyncio
async def test_probe_and_untagged_model_presence():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"models": [{"name": "bggpt-7b:latest"}, {"model": "x:1"}]}
        )

    client = OllamaClient(
        _settings(ollama_model="bggpt-7b"), transport=_mock_transport(handler)
    )
    assert await client.probe() == (True, ["bggpt-7b:latest", "x:1"])
    assert await client.configured_model_present() is True


def test_model_matches():
    assert model_matches("qwen2.5:7b", "qwen2.5:7b")
    assert model_matches("bggpt-7b:latest", "bggpt-7b")
    assert not model_matches("qwen2.5:14b", "qwen2.5:7b")
    assert not model_matches("llama3.1:8b", "bggpt-7b")


@pytest.mark.asyncio
async def test_version():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/version"
        return httpx.Response(200, json={"version": "0.12.3"})

    client = OllamaClient(_settings(), transport=_mock_transport(handler))
    assert await client.version() == "0.12.3"
    down = OllamaClient(
        _settings(),
        transport=_mock_transport(
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("x", request=r))
        ),
    )
    assert await down.version() is None


@pytest.mark.asyncio
async def test_is_reachable_true_and_false():
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    client = OllamaClient(_settings(), transport=_mock_transport(ok))
    assert await client.is_reachable() is True

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client2 = OllamaClient(_settings(), transport=_mock_transport(fail))
    assert await client2.is_reachable() is False


@pytest.mark.asyncio
async def test_model_from_settings_is_configurable():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "llama3.1:8b"
        return httpx.Response(200, json={"response": "ok"})

    client = OllamaClient(
        _settings(ollama_model="llama3.1:8b"),
        transport=_mock_transport(handler),
    )
    text, stubbed = await client.generate("hi")
    assert stubbed is False
    assert text == "ok"
    assert client.model_name == "llama3.1:8b"


@pytest.mark.asyncio
async def test_live_ollama_generate_or_skip():
    """Optional live check, skipped when Ollama is not running locally."""
    live = OllamaClient(
        Settings(
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="qwen2.5:7b",
            ollama_stub_on_unavailable=False,
            ollama_health_timeout=2.0,
            ollama_generate_timeout=30.0,
        )
    )
    if not await live.is_reachable():
        pytest.skip("Ollama not reachable at 127.0.0.1:11434")

    text, stubbed = await live.generate(
        "Reply with exactly: pong",
        system="You are a ping test. Reply with one word only.",
    )
    assert stubbed is False
    assert len(text) > 0
