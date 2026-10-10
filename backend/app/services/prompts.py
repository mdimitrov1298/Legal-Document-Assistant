"""Bulgarian and English prompts for summarize and verify, plus chat template handling.

The system prompts are identical for every model so A/B runs stay comparable.
The only model-specific difference is the legacy BgGPT instruction template:
BgGPT-7B-Instruct v0.x is Mistral-based and expects `[INST] ... [/INST]`. A GGUF
imported with a bare Modelfile has no template, so the prompt is rendered here
and sent raw. BgGPT v1.0 is Gemma 2 based; its Ollama builds (for example
`s_emanuilov/BgGPT-v1.0:9b`) ship the Gemma chat template, so it is left to
Ollama like every other model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROMPT_VERSION_BG = "bg-v1"
PROMPT_VERSION_EN = "en-v1"
# Legacy alias kept for the eval runner header (always reports bg-v1 when BG).
PROMPT_VERSION = PROMPT_VERSION_BG

# ---------------------------------------------------------------------------
# Bulgarian system prompts (unchanged)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# English system prompts (same JSON contract and labels)
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_EN = (
    "You are summarising case documents for a research prototype. "
    "Use ONLY the numbered excerpts. Do not add facts, names, dates or amounts "
    "that are not present in the excerpts. Do not give legal advice, conclusions, "
    "qualifications or interpretations. Write in English, in 5 to 8 sentences. "
    'Reply with JSON only: {"summary": "...", "citation_indices": [int, ...]}, '
    "where citation_indices are the numbers of the excerpts you used."
)

VERIFY_SYSTEM_EN = (
    "You are checking whether a CLAIM is supported or denied by the given "
    "CITATIONS from case documents. Use only these citations as evidence; do "
    "not use external knowledge and do not invent text. If the citations do not "
    "contain enough information, return inconclusive. Do not give legal conclusions. "
    "Write the rationale in English. "
    'Reply with JSON only: {"verdict": "supported"|"denied"|"inconclusive", '
    '"rationale": "...", '
    '"supporting_quotes": [{"index": int, "quote": "..."}], '
    '"denying_quotes": [{"index": int, "quote": "..."}]}, '
    "where index is the number of the CITATION and quote is a passage copied "
    "verbatim from it."
)

NO_EXCERPTS_EN = "(No indexed excerpts.)"


def get_summarize_system(language: str = "bg") -> str:
    """Return the summarize system prompt for the given language."""
    return SUMMARIZE_SYSTEM_EN if language == "en" else SUMMARIZE_SYSTEM


def get_verify_system(language: str = "bg") -> str:
    """Return the verify system prompt for the given language."""
    return VERIFY_SYSTEM_EN if language == "en" else VERIFY_SYSTEM


def get_prompt_version(language: str = "bg") -> str:
    """Return the prompt version string for the given language."""
    return PROMPT_VERSION_EN if language == "en" else PROMPT_VERSION_BG


def format_excerpts(hits: list[dict[str, Any]], *, language: str = "bg") -> str:
    if not hits:
        return NO_EXCERPTS_EN if language == "en" else NO_EXCERPTS
    if language == "en":
        return "\n\n".join(
            f"[{i}] document={h.get('metadata', {}).get('document_filename')} "
            f"chunk={h.get('chunk_id')}\n{h.get('text', '')}"
            for i, h in enumerate(hits)
        )
    return "\n\n".join(
        f"[{i}] документ={h.get('metadata', {}).get('document_filename')} "
        f"фрагмент={h.get('chunk_id')}\n{h.get('text', '')}"
        for i, h in enumerate(hits)
    )


def build_summarize_prompt(
    title: str | None,
    hits: list[dict[str, Any]],
    *,
    language: str = "bg",
) -> str:
    if language == "en":
        return (
            f"Case title: {title or '-'}\n\n"
            f"EXCERPTS:\n{format_excerpts(hits, language='en')}\n\n"
            "JSON:"
        )
    return (
        f"Заглавие на делото: {title or '-'}\n\n"
        f"ОТКЪСИ:\n{format_excerpts(hits)}\n\n"
        "JSON:"
    )


def build_verify_prompt(
    claim: str,
    hits: list[dict[str, Any]],
    *,
    language: str = "bg",
) -> str:
    if language == "en":
        return (
            f"CLAIM:\n{claim}\n\n"
            f"CITATIONS:\n{format_excerpts(hits, language='en')}\n\n"
            "JSON:"
        )
    return f"ТВЪРДЕНИЕ:\n{claim}\n\nЦИТАТИ:\n{format_excerpts(hits)}\n\nJSON:"


_GEMMA_BGGPT_MARKERS = ("v1.0", "v1-0", "gemma")


def is_bggpt(model: str) -> bool:
    return "bggpt" in model.lower()


def needs_inst_template(model: str) -> bool:
    """True only for the Mistral-based BgGPT v0.x, not Gemma-based BgGPT v1.0."""
    name = model.lower()
    return is_bggpt(name) and not any(m in name for m in _GEMMA_BGGPT_MARKERS)


@dataclass(frozen=True)
class RenderedPrompt:
    prompt: str
    system: str | None
    raw: bool


def render_for_model(model: str, prompt: str, system: str | None) -> RenderedPrompt:
    """Apply the model's chat template when Ollama cannot be relied on for it."""
    if needs_inst_template(model):
        body = f"{system}\n\n{prompt}" if system else prompt
        return RenderedPrompt(prompt=f"[INST] {body} [/INST]", system=None, raw=True)
    return RenderedPrompt(prompt=prompt, system=system, raw=False)
