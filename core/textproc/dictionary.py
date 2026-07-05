"""User dictionary replacement (C17)."""

from __future__ import annotations

import logging
import re
from typing import Callable

from core.store.models import DictionaryEntry
from core.textproc.rules import compile_word_pattern, is_ascii_word_term, sort_entries_by_priority

logger = logging.getLogger(__name__)


def _replace_vocab_term(text: str, entry: DictionaryEntry) -> tuple[str, bool]:
    term = entry.term
    replacement = entry.replacement
    if not term:
        return text, False
    if is_ascii_word_term(term):
        try:
            pattern = compile_word_pattern(term, case_insensitive=True)
            new_text, count = pattern.subn(replacement, text)
            return (new_text, count > 0)
        except re.error as exc:
            logger.warning("Skipping dictionary rule %s: %s", entry.id, exc)
            return text, False
    if term not in text:
        return text, False
    return text.replace(term, replacement), True


def apply_dictionary(
    text: str,
    entries: list[DictionaryEntry],
    *,
    on_applied: Callable[[str], None] | None = None,
) -> str:
    """Replace vocabulary terms longest-first with Latin word boundaries."""
    result = text
    for entry in sort_entries_by_priority(entries):
        try:
            new_result, applied = _replace_vocab_term(result, entry)
            if applied:
                result = new_result
                if on_applied is not None:
                    on_applied(f"vocab:{entry.term}")
        except Exception as exc:  # noqa: BLE001 — skip single rule only
            logger.warning("Skipping dictionary rule %s: %s", entry.id, exc)
    return result
