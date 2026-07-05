"""Tests for OpenAI-compatible provider."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.llm import AuthenticationError, LLMRequest, OpenAICompatProvider


def test_openai_complete_parses_response() -> None:
    provider = OpenAICompatProvider(
        base_url="https://api.example.com",
        model="gpt-test",
        api_key="secret",
    )
    with patch("core.llm.openai_compat.request_json") as mock_json:
        mock_json.return_value = {
            "model": "gpt-test",
            "choices": [{"message": {"content": "완료"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        result = provider.complete(LLMRequest(system_prompt="s", user_text="u"))

    assert result.text == "완료"
    assert result.usage is not None


def test_openai_requires_api_key() -> None:
    provider = OpenAICompatProvider(
        base_url="https://api.example.com",
        model="gpt-test",
        api_key="",
    )
    with pytest.raises(AuthenticationError):
        provider.complete(LLMRequest(system_prompt="s", user_text="u"))
