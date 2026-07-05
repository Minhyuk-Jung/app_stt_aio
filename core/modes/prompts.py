"""Prompt placeholder formatting (C7 section 6.4)."""

from __future__ import annotations

PROMPT_TEXT_PLACEHOLDER = "{{text}}"


def format_prompt(template: str, text: str) -> str:
    """Substitute user text into a mode prompt template."""
    if PROMPT_TEXT_PLACEHOLDER in template:
        return template.replace(PROMPT_TEXT_PLACEHOLDER, text)
    return f"{template.rstrip()}\n\n{text}"
