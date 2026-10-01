"""Build citations from retrieved chunks and flag whether quotes are verbatim.

A quote is verbatim when, after Unicode NFC normalisation, collapsing all
whitespace to single spaces and stripping enclosing quotation marks, it occurs
as an exact (case-sensitive) substring of the stored chunk text.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from app.schemas.rag import Citation

MAX_QUOTE_CHARS = 500
_ENCLOSING_QUOTES = "\"'„“”«»‘’`"


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalize_quote(quote: str) -> str:
    return normalize_text(quote).strip(_ENCLOSING_QUOTES).strip()


def is_verbatim(quote: str, chunk_text: str) -> bool:
    q = normalize_quote(quote)
    return bool(q) and q in normalize_text(chunk_text)


def _chunk_index(hit: dict[str, Any]) -> int | None:
    meta = hit.get("metadata") or {}
    value = meta.get("chunk_index")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    suffix = str(hit.get("chunk_id", "")).rsplit(":", 1)[-1]
    return int(suffix) if suffix.isdigit() else None


def citation_from_hit(hit: dict[str, Any], quote: str | None = None) -> Citation:
    """Citation for a retrieved chunk; without a quote the chunk excerpt is used."""
    meta = hit.get("metadata") or {}
    chunk_text = str(hit.get("text", ""))
    text = chunk_text[:MAX_QUOTE_CHARS] if quote is None else quote.strip()
    return Citation(
        document_id=str(meta.get("document_id", "")),
        document_filename=str(meta.get("document_filename", "")),
        chunk_id=str(hit.get("chunk_id", "")),
        chunk_index=_chunk_index(hit),
        quote=text,
        relevance=hit.get("relevance"),
        verbatim=is_verbatim(text, chunk_text),
    )


def find_hit_for_quote(hits: list[dict[str, Any]], quote: str) -> int | None:
    for i, hit in enumerate(hits):
        if is_verbatim(quote, str(hit.get("text", ""))):
            return i
    return None


def _as_index(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def citations_from_model(
    hits: list[dict[str, Any]], items: Any, indices: Any = None
) -> list[Citation]:
    """Map model output to citations.

    `items` is a list of `{"index": int, "quote": str}` objects (or bare
    indices); `indices` is the older list-of-ints form. Quotes that do not
    occur in the referenced chunk are kept with `verbatim=False`; a quote
    with an invalid index is attributed to the chunk that contains it, or
    dropped when no chunk does.
    """
    out: list[Citation] = []
    seen: set[tuple[str, str]] = set()

    def add(citation: Citation) -> None:
        key = (citation.chunk_id, normalize_quote(citation.quote))
        if key not in seen:
            seen.add(key)
            out.append(citation)

    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            idx = _as_index(item.get("index"))
            quote = item.get("quote")
            quote = str(quote) if isinstance(quote, str) and quote.strip() else None
        else:
            idx, quote = _as_index(item), None
        if idx is None or not 0 <= idx < len(hits):
            idx = find_hit_for_quote(hits, quote) if quote else None
            if idx is None:
                continue
        add(citation_from_hit(hits[idx], quote))

    for value in indices if isinstance(indices, list) else []:
        idx = _as_index(value)
        if idx is not None and 0 <= idx < len(hits):
            add(citation_from_hit(hits[idx]))
    return out
