"""Simple overlapping character chunker (Bulgarian case text; encoding-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    text: str
    index: int


def chunk_text(
    text: str,
    *,
    doc_id: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[Chunk]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    n = len(cleaned)
    while start < n:
        end = min(start + chunk_size, n)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}:{idx}",
                    text=piece,
                    index=idx,
                )
            )
            idx += 1
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks
