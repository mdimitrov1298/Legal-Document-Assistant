"""Ollama LLM client: real local generate with graceful stub fallback.

Primary path: POST {OLLAMA_BASE_URL}/api/generate with model from OLLAMA_MODEL
(default s_emanuilov/BgGPT-v1.0:9b, fallback qwen2.5:7b) and options
num_ctx / temperature from settings. On connect
errors, timeouts, HTTP errors or empty responses it falls back to deterministic
stubs when OLLAMA_STUB_ON_UNAVAILABLE=true, so summarize/verify still return
structured API responses. With the fallback disabled it raises
LLMUnavailableError (HTTP 503).
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailableError
from app.services.prompts import render_for_model

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Stable interface used by the summarize and verify pipelines."""

    @property
    def model_name(self) -> str: ...

    async def is_reachable(self) -> bool: ...

    async def list_model_names(self) -> list[str]: ...

    async def configured_model_present(self) -> bool | None: ...

    async def generate(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, bool]:
        """Return (text, stubbed). stubbed=True means Ollama was not used."""
        ...


def model_matches(installed: str, target: str) -> bool:
    """`qwen2.5:7b` matches itself; an untagged `bggpt-7b` matches `:latest`."""
    if installed == target or installed.startswith(f"{target}-"):
        return True
    return ":" not in target and installed == f"{target}:latest"


class OllamaClient:
    """Calls local Ollama `/api/generate`; falls back to stubs if configured."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_model
        self.stub_on_unavailable = self.settings.ollama_stub_on_unavailable
        self.health_timeout = self.settings.ollama_health_timeout
        self.generate_timeout = self.settings.ollama_generate_timeout
        self.num_ctx = self.settings.ollama_num_ctx
        self.temperature = self.settings.ollama_temperature
        self._transport = transport

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def options(self) -> dict[str, float | int]:
        return {"num_ctx": self.num_ctx, "temperature": self.temperature}

    def _client(self, timeout: float) -> httpx.AsyncClient:
        kwargs: dict = {"timeout": timeout, "base_url": self.base_url}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def probe(self) -> tuple[bool, list[str]]:
        """One `/api/tags` call: (reachable, installed model names)."""
        try:
            async with self._client(self.health_timeout) as client:
                r = await client.get("/api/tags")
                r.raise_for_status()
                models = r.json().get("models") or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama probe failed: %s", exc)
            return False, []
        names = [str(m.get("name") or m.get("model")) for m in models]
        return True, [n for n in names if n and n != "None"]

    async def is_reachable(self) -> bool:
        reachable, _ = await self.probe()
        return reachable

    async def list_model_names(self) -> list[str]:
        """Installed Ollama model names (empty if unreachable)."""
        _, names = await self.probe()
        return names

    def is_model_installed(self, names: list[str]) -> bool:
        return any(model_matches(n, self.model) for n in names)

    async def configured_model_present(self) -> bool | None:
        """True/False when Ollama is up; None if unreachable."""
        reachable, names = await self.probe()
        if not reachable:
            return None
        return self.is_model_installed(names)

    async def running_models(self) -> list[dict]:
        """Loaded models from `/api/ps` (size and size_vram in bytes); [] if down."""
        try:
            async with self._client(self.health_timeout) as client:
                r = await client.get("/api/ps")
                r.raise_for_status()
                models = r.json().get("models") or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama ps failed: %s", exc)
            return []
        return [
            {
                "name": m.get("name") or m.get("model"),
                "size_bytes": m.get("size"),
                "size_vram_bytes": m.get("size_vram"),
            }
            for m in models
            if isinstance(m, dict)
        ]

    async def version(self) -> str | None:
        try:
            async with self._client(self.health_timeout) as client:
                r = await client.get("/api/version")
                r.raise_for_status()
                return str(r.json().get("version") or "") or None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama version check failed: %s", exc)
            return None

    def build_payload(self, prompt: str, system: str | None) -> dict:
        rendered = render_for_model(self.model, prompt, system)
        payload: dict = {
            "model": self.model,
            "prompt": rendered.prompt,
            "stream": False,
            "options": self.options,
        }
        if rendered.system:
            payload["system"] = rendered.system
        if rendered.raw:
            payload["raw"] = True
        return payload

    async def generate(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, bool]:
        """Call Ollama /api/generate. Returns (text, stubbed)."""
        payload = self.build_payload(prompt, system)
        try:
            text = await self._generate_real(payload)
            logger.info("Ollama generate ok model=%s chars=%d", self.model, len(text))
            return text, False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ollama generate failed (model=%s url=%s): %s",
                self.model,
                self.base_url,
                exc,
            )
            if not self.stub_on_unavailable:
                raise LLMUnavailableError(
                    f"Ollama generate failed for model {self.model}",
                    details={"model": self.model, "base_url": self.base_url},
                ) from exc
            return self._stub(prompt, system), True

    async def _generate_real(self, payload: dict) -> str:
        async with self._client(self.generate_timeout) as client:
            r = await client.post("/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()
            text = str(data.get("response", "")).strip()
            if not text:
                raise RuntimeError("Ollama returned empty response")
            return text

    def _stub(self, prompt: str, system: str | None) -> str:
        """Deterministic stub for offline/dev when Ollama is down."""
        lower = ((system or "") + "\n" + prompt).lower()
        if "claim" in lower or "verdict" in lower or "quotes" in lower:
            return json.dumps(
                {
                    "verdict": "inconclusive",
                    "rationale": (
                        "[STUB] Ollama unreachable. Cannot verify claim against "
                        "retrieved quotes. Run `ollama serve` and "
                        f"`ollama pull {self.model}`, then retry."
                    ),
                    "supporting_quote_indices": [],
                    "denying_quote_indices": [],
                }
            )
        return (
            "[STUB SUMMARY] Ollama is unreachable. This is a placeholder summary. "
            f"Run `ollama serve` and `ollama pull {self.model}`, then retry. "
            f"(Configured model: {self.model}, base: {self.base_url})"
        )


_client: OllamaClient | None = None


def get_llm() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def reset_llm(client: OllamaClient | None = None) -> None:
    """Replace or clear the process-wide LLM singleton (for tests)."""
    global _client
    _client = client
