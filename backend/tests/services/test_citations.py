"""Verbatim citation checks, including Cyrillic text."""

from __future__ import annotations

import unicodedata

from app.services.citations import (
    citation_from_hit,
    citations_from_model,
    is_verbatim,
    normalize_text,
)

CHUNK = (
    "Възложителят заплаща на изпълнителя\nвъзнаграждение в размер на 4500 лв.  "
    "без ДДС. Срокът за изпълнение е 30 дни."
)
HITS = [
    {
        "chunk_id": "doc1:3",
        "text": CHUNK,
        "metadata": {
            "document_id": "doc1",
            "document_filename": "dogovor.txt",
            "chunk_index": 3,
        },
        "relevance": 0.7,
    },
    {
        "chunk_id": "doc2:0",
        "text": "Приемо-предавателният протокол е подписан на 12.03.2025 г.",
        "metadata": {"document_id": "doc2", "document_filename": "protokol.txt"},
        "relevance": 0.5,
    },
]


def test_whitespace_is_normalised():
    assert is_verbatim("възнаграждение   в размер\tна 4500 лв. без ДДС", CHUNK)
    assert normalize_text(" а \n б ") == "а б"


def test_changed_amount_is_not_verbatim():
    assert not is_verbatim("възнаграждение в размер на 4800 лв.", CHUNK)


def test_case_sensitive_and_empty():
    assert not is_verbatim("ВЪЗЛОЖИТЕЛЯТ заплаща", CHUNK)
    assert not is_verbatim("   ", CHUNK)


def test_enclosing_quotes_are_ignored():
    assert is_verbatim("„Срокът за изпълнение е 30 дни.“", CHUNK)
    assert is_verbatim('"Срокът за изпълнение е 30 дни."', CHUNK)


def test_nfc_normalisation_for_decomposed_cyrillic():
    text = unicodedata.normalize("NFD", "Изпълнителят й дължи неустойка.")
    assert "й" not in text
    assert is_verbatim("й дължи неустойка", text)


def test_citation_from_hit_defaults_to_chunk_excerpt():
    c = citation_from_hit(HITS[0])
    assert c.verbatim is True
    assert c.chunk_index == 3
    assert c.quote == CHUNK


def test_chunk_index_parsed_from_chunk_id_when_missing():
    assert citation_from_hit(HITS[1]).chunk_index == 0


def test_model_quotes_are_flagged_and_kept():
    items = [
        {"index": 0, "quote": "възнаграждение в размер на 4500 лв."},
        {"index": 0, "quote": "възнаграждение от около пет хиляди лева"},
        {"index": 9, "quote": "подписан на 12.03.2025 г."},
        {"index": 9, "quote": "текст, който го няма"},
        1,
    ]
    cites = citations_from_model(HITS, items)
    assert [(c.chunk_id, c.verbatim) for c in cites] == [
        ("doc1:3", True),
        ("doc1:3", False),
        ("doc2:0", True),
        ("doc2:0", True),
    ]


def test_legacy_indices_and_dedupe():
    cites = citations_from_model(HITS, None, [0, "1", 0, "x", 5])
    assert [c.chunk_id for c in cites] == ["doc1:3", "doc2:0"]
    assert all(c.verbatim for c in cites)
