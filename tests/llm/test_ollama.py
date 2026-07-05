"""Tests for Ollama provider with mocked HTTP."""

from __future__ import annotations

from unittest.mock import patch

from core.llm import LLMRequest, OllamaLocalProvider


def test_ollama_complete_parses_chat_response() -> None:
    provider = OllamaLocalProvider(model="llama3")
    with patch("core.llm.ollama_local.request_json") as mock_json:
        mock_json.return_value = {
            "message": {"content": "다듬어진 문장"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        result = provider.complete(LLMRequest(system_prompt="교정", user_text="원문"))

    assert result.text == "다듬어진 문장"
    assert result.usage is not None
    assert result.usage.completion_tokens == 5


def test_ollama_list_models() -> None:
    provider = OllamaLocalProvider()
    with patch("core.llm.ollama_local.request_json") as mock_json:
        mock_json.return_value = {"models": [{"name": "llama3", "size": 100}]}
        models = provider.list_models()

    assert models[0].id == "llama3"
