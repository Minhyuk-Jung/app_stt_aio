"""Tests for config LLM API key resolution."""

from __future__ import annotations

from app.config import Config
from core.secrets import LLM_API_KEY_SECRET, reset_default_store
from core.secrets.mock_store import MemorySecretStore


def test_get_llm_api_key_prefers_secret_store(tmp_path) -> None:
    store = MemorySecretStore()
    reset_default_store(store)
    store.set_secret(LLM_API_KEY_SECRET, "from-store")
    config = Config.open(tmp_path / "apikey.db", migrate_backup=False)
    try:
        assert config.get_llm_api_key() == "from-store"
        assert config.has_llm_api_key() is True
        assert config.delete_llm_api_key() is True
        assert config.has_llm_api_key() is False
    finally:
        config.close()
        reset_default_store(None)


def test_set_llm_api_key_refreshes_session(tmp_path) -> None:
    store = MemorySecretStore()
    reset_default_store(store)
    config = Config.open(tmp_path / "refresh.db", migrate_backup=False)
    from core.llm import MockLLMProvider

    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()
    config.set_llm_api_key("sk-test-key")
    assert config.get_llm_api_key() == "sk-test-key"
    config.close()
    reset_default_store(None)
