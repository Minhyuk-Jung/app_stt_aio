"""Tests for prompt placeholder formatting."""

from __future__ import annotations

from core.modes import PROMPT_TEXT_PLACEHOLDER, format_prompt
from core.modes.defaults import DEFAULT_CORRECTION_PROMPT


def test_format_prompt_replaces_placeholder() -> None:
    result = format_prompt(DEFAULT_CORRECTION_PROMPT, "안녕하세요")
    assert PROMPT_TEXT_PLACEHOLDER not in result
    assert "안녕하세요" in result


def test_format_prompt_appends_text_without_placeholder() -> None:
    result = format_prompt("지시문", "본문")
    assert result.endswith("본문")
    assert result.startswith("지시문")
