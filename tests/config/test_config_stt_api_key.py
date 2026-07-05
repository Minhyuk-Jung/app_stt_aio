"""Tests for cloud STT API key resolution (C19)."""

from __future__ import annotations

from unittest.mock import patch

from app.config import Config
from core.secrets import STT_API_KEY_SECRET, reset_default_store
from core.secrets.mock_store import MemorySecretStore


def test_get_stt_api_key_prefers_dedicated_secret(tmp_path) -> None:
    store = MemorySecretStore()
    reset_default_store(store)
    store.set_secret(STT_API_KEY_SECRET, "stt-only")
    config = Config.open(tmp_path / "sttkey.db", migrate_backup=False)
    try:
        assert config.get_stt_api_key() == "stt-only"
        assert config.delete_stt_api_key() is True
        assert config.get_stt_api_key() is None
    finally:
        config.close()
        reset_default_store(None)


def test_get_stt_api_key_falls_back_to_llm(tmp_path) -> None:
    config = Config.open(tmp_path / "fallback.db", migrate_backup=False)
    try:
        with patch.object(config, "get_llm_api_key", return_value="llm-shared"):
            assert config.get_stt_api_key() == "llm-shared"
    finally:
        config.close()


def test_set_stt_provider_alias_normalizes(tmp_path) -> None:
    config = Config.open(tmp_path / "alias.db", migrate_backup=False)
    try:
        config.set("stt.provider", "groq")
        assert config.get("stt.provider") == "groq_transcribe"
        config.set("stt.provider", "deepgram")
        assert config.get("stt.provider") == "deepgram_transcribe"
    finally:
        config.close()


def test_create_stt_provider_uses_stt_api_key(tmp_path) -> None:
    config = Config.open(tmp_path / "create.db", migrate_backup=False)
    try:
        config.set("stt.provider", "groq_transcribe")
        with patch.object(config, "get_stt_api_key", return_value="gk-test") as mock_key:
            provider = config.create_stt_provider()
        assert provider.provider_id == "groq_transcribe"
        mock_key.assert_called()
    finally:
        config.close()
