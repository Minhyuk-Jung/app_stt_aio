"""Tests for LLM provider registry."""

from __future__ import annotations

import pytest

from core.llm import MockLLMProvider, ProviderNotFoundError, create_provider, resolve_provider_id


def test_resolve_provider_aliases() -> None:
    assert resolve_provider_id("local") == "ollama"
    assert resolve_provider_id("openai") == "openai_compat"


def test_create_mock_provider() -> None:
    provider = create_provider("mock")
    assert isinstance(provider, MockLLMProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ProviderNotFoundError):
        create_provider("unknown-llm")
