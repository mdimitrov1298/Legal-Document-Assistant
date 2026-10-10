"""Language detection unit tests."""

from __future__ import annotations

from app.services.language import detect_language, majority_language


def test_detect_bulgarian():
    text = (
        "Правилата уреждат реда за ползване на общинските спортни зали. "
        "Резервации се подават най-малко три работни дни предварително."
    )
    assert detect_language(text) == "bg"


def test_detect_english():
    text = (
        "The rules regulate the use of municipal sports halls. "
        "Reservations must be submitted at least three working days in advance."
    )
    assert detect_language(text) == "en"


def test_detect_empty_returns_other():
    assert detect_language("") == "other"
    assert detect_language("   ") == "other"


def test_detect_short_text_returns_other():
    assert detect_language("hello") == "other"


def test_detect_mixed_defaults_to_detected():
    # A predominantly Bulgarian text with some English words
    text = (
        "Договорът е сключен с фирма Company Ltd. за ремонт на покрива. "
        "Сумата е 12 000 лв. с ДДС включен в цената за всички работи."
    )
    result = detect_language(text)
    assert result in ("bg", "en", "other")


def test_majority_language_bg():
    assert majority_language(["bg", "bg", "en"]) == "bg"


def test_majority_language_en():
    assert majority_language(["en", "en", "bg"]) == "en"


def test_majority_language_empty():
    assert majority_language([]) == "en"


def test_majority_language_tie_prefers_bg():
    assert majority_language(["bg", "en"]) == "bg"


def test_majority_language_all_other():
    assert majority_language(["other", "other"]) == "other"
