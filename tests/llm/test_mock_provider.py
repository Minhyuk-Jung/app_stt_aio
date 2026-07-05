"""Tests for mock LLM provider."""

from __future__ import annotations

from core.llm import LLMRequest, MockLLMProvider


def test_mock_complete_returns_user_text() -> None:
    provider = MockLLMProvider(prefix="[ok] ")
    result = provider.complete(
        LLMRequest(system_prompt="교정", user_text="안녕")
    )
    assert result.text == "[ok] 안녕"
    assert result.provider_id == "mock"


def test_mock_test_connection_succeeds() -> None:
    provider = MockLLMProvider()
    conn = provider.test_connection()
    assert conn.success is True
    assert conn.models


def test_mock_complete_empty_user_with_system_still_runs() -> None:
    provider = MockLLMProvider()
    result = provider.complete(
        LLMRequest(system_prompt="지시만", user_text="   ")
    )
    assert "지시만" in result.text
