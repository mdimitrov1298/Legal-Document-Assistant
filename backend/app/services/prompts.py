"""Bulgarian prompts for summarize and verify, plus chat template handling.

The system prompts are identical for every model so A/B runs stay comparable.
The only model-specific difference is the BgGPT instruction template: BgGPT is
Mistral-based and expects `[INST] ... [/INST]`. A GGUF imported with a bare
Modelfile has no template, so the prompt is rendered here and sent raw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROMPT_VERSION = "bg-v1"

SUMMARIZE_SYSTEM = (
    "Ти обобщаваш документи по дело за изследователски прототип. "
    "Използвай САМО номерираните откъси. Не добавяй факти, имена, дати или суми, "
    "които не присъстват в откъсите. Не давай правни съвети, изводи, "
    "квалификации или тълкувания. Пиши на български език, в 5 до 8 изречения. "
    'Отговори само с JSON: {"summary": "...", "citation_indices": [int, ...]}, '
    "където citation_indices са номерата на откъсите, които си използвал."
)

VERIFY_SYSTEM = (
    "Проверяваш дали ТВЪРДЕНИЕ се подкрепя или опровергава от дадените ЦИТАТИ "
    "от документи по дело. Използвай само тези цитати като доказателство; не "
    "използвай външни знания и не измисляй текст. Ако цитатите не съдържат "
    "достатъчно информация, върни inconclusive. Не давай правни изводи. "
    "Обосновката пиши на български. "
    'Отговори само с JSON: {"verdict": "supported"|"denied"|"inconclusive", '
    '"rationale": "...", '
    '"supporting_quotes": [{"index": int, "quote": "..."}], '
    '"denying_quotes": [{"index": int, "quote": "..."}]}, '
    "където index е номерът на ЦИТАТА, а quote е откъс, копиран дословно от него."
)

NO_EXCERPTS = "(Няма индексирани откъси.)"


def format_excerpts(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return NO_EXCERPTS
    return "\n\n".join(
        f"[{i}] документ={h.get('metadata', {}).get('document_filename')} "
        f"фрагмент={h.get('chunk_id')}\n{h.get('text', '')}"
        for i, h in enumerate(hits)
    )


def build_summarize_prompt(title: str | None, hits: list[dict[str, Any]]) -> str:
    return (
        f"Заглавие на делото: {title or '-'}\n\n"
        f"ОТКЪСИ:\n{format_excerpts(hits)}\n\n"
        "JSON:"
    )


def build_verify_prompt(claim: str, hits: list[dict[str, Any]]) -> str:
    return f"ТВЪРДЕНИЕ:\n{claim}\n\nЦИТАТИ:\n{format_excerpts(hits)}\n\nJSON:"


def is_bggpt(model: str) -> bool:
    return "bggpt" in model.lower()


@dataclass(frozen=True)
class RenderedPrompt:
    prompt: str
    system: str | None
    raw: bool


def render_for_model(model: str, prompt: str, system: str | None) -> RenderedPrompt:
    """Apply the model's chat template when Ollama cannot be relied on for it."""
    if is_bggpt(model):
        body = f"{system}\n\n{prompt}" if system else prompt
        return RenderedPrompt(prompt=f"[INST] {body} [/INST]", system=None, raw=True)
    return RenderedPrompt(prompt=prompt, system=system, raw=False)
