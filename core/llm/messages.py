"""Prompt/message helpers for LLM providers."""

from __future__ import annotations

from core.llm.types import LLMRequest
from core.modes.prompts import PROMPT_TEXT_PLACEHOLDER, format_prompt


def build_messages(request: LLMRequest) -> list[dict[str, str]]:
    """Map an LLMRequest to chat messages (system/user split)."""
    system = request.system_prompt.strip()
    user = request.user_text.strip()

    if system and PROMPT_TEXT_PLACEHOLDER in system:
        merged = format_prompt(system, user)
        return [{"role": "user", "content": merged}]

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    if user:
        messages.append({"role": "user", "content": user})
    elif not messages:
        messages.append({"role": "user", "content": ""})
    return messages
