"""Rule ordering and matching helpers (C17)."""

from __future__ import annotations

import re
from typing import TypeVar

from core.store.models import DictionaryEntry

T = TypeVar("T", bound=DictionaryEntry)

# Pipeline step identifiers (plan 6.2).
STEP_BASIC_NORMALIZE = "normalize:basic"
STEP_DICTIONARY = "dictionary"
STEP_SNIPPETS = "snippets"
STEP_KO_PUNCT = "normalize:ko_punct"
STEP_KO_NUMBER = "normalize:ko_number"

_ASCII_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]*$")


def sort_entries_by_priority(entries: list[T]) -> list[T]:
    """Longest term first, then lexicographic — resolves overlap conflicts."""
    return sorted(entries, key=lambda entry: (-len(entry.term), entry.term))


def is_ascii_word_term(term: str) -> bool:
    """True when term should use Latin word-boundary matching."""
    return bool(term) and _ASCII_WORD.fullmatch(term) is not None


def compile_word_pattern(term: str, *, case_insensitive: bool = True) -> re.Pattern[str]:
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
        flags,
    )
