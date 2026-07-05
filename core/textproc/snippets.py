"""Snippet expansion for shorthand triggers (C17)."""

from __future__ import annotations

import logging
import re
from typing import Callable

from core.store.models import DictionaryEntry
from core.textproc.rules import sort_entries_by_priority

logger = logging.getLogger(__name__)

# STT often mis-hears slash commands as Korean syllables.
_STT_SLASH_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"슬래시\s*"), "/"),
    (re.compile(r"슬러시\s*"), "/"),
)


def normalize_snippet_triggers(text: str) -> str:
    """Normalize common STT variants of slash-style snippet triggers."""
    result = text
    for pattern, replacement in _STT_SLASH_ALIASES:
        result = pattern.sub(replacement, result)
    return result


def expand_snippets(
    text: str,
    entries: list[DictionaryEntry],
    *,
    on_applied: Callable[[str], None] | None = None,
) -> str:
    """Expand snippet triggers longest-first."""
    result = normalize_snippet_triggers(text)
    for entry in sort_entries_by_priority(entries):
        if not entry.term:
            continue
        try:
            if entry.term not in result:
                continue
            new_result = result.replace(entry.term, entry.replacement)
            if new_result == result:
                continue
            result = new_result
            if on_applied is not None:
                on_applied(f"snippet:{entry.term}")
        except Exception as exc:  # noqa: BLE001 — skip single rule only
            logger.warning("Skipping snippet rule %s: %s", entry.id, exc)
    return result
