"""Tests for LLM message mapping."""

from __future__ import annotations

from core.llm.messages import build_messages
from core.llm.types import LLMRequest
from core.modes.defaults import DEFAULT_CORRECTION_PROMPT


def test_build_messages_splits_system_and_user() -> None:
    messages = build_messages(
        LLMRequest(system_prompt="시스템", user_text="본문")
    )
    assert messages == [
        {"role": "system", "content": "시스템"},
        {"role": "user", "content": "본문"},
    ]


def test_build_messages_merges_placeholder_template() -> None:
    messages = build_messages(
        LLMRequest(system_prompt=DEFAULT_CORRECTION_PROMPT, user_text="원문")
    )
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "원문" in messages[0]["content"]
