"""Language detection for uploaded documents.

Uses langdetect (Google's language-detection library ported to Python) to
classify text as Bulgarian, English or other.  The result is stored on the
document record and propagated to chunk metadata so that the correct prompts
are selected at query time.
"""

from __future__ import annotations

import logging
from typing import Literal

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

logger = logging.getLogger(__name__)

# Make langdetect deterministic (it uses random sampling internally).
DetectorFactory.seed = 0

Language = Literal["bg", "en", "other"]


def detect_language(text: str) -> Language:
    """Return ``"bg"``, ``"en"`` or ``"other"`` for the given text.

    Returns ``"other"`` for empty / very short text or when detection fails.
    """
    if not text or len(text.strip()) < 20:
        return "other"
    try:
        code = detect(text)
    except LangDetectException:
        return "other"
    if code == "bg":
        return "bg"
    if code == "en":
        return "en"
    return "other"


def majority_language(languages: list[Language]) -> Language:
    """Return the most common language in *languages*, defaulting to ``"en"``."""
    if not languages:
        return "en"
    from collections import Counter

    counts = Counter(languages)
    # Resolve ties: prefer bg, then en, then other
    for lang in ("bg", "en", "other"):
        if lang in counts:
            if counts[lang] == counts.most_common(1)[0][1]:
                return lang  # type: ignore[return-value]
    return counts.most_common(1)[0][0]  # type: ignore[return-value]
