"""Tests for Config LLM bindings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Config
from core.llm import MockLLMProvider


def test_llm_session_property_requires_bind(tmp_path) -> None:
    config = Config.open(tmp_path / "llm_prop.db", migrate_backup=False)
    try:
        try:
            _ = config.llm_session
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
        bound = config.bind_llm_session()
        assert config.llm_session is bound
    finally:
        config.close()


def test_test_llm_connection_delegates(tmp_path) -> None:
    config = Config.open(tmp_path / "llm_conn.db", migrate_backup=False)
    try:
        config.bind_llm_session()
        mock_provider = MagicMock()
        mock_provider.test_connection.return_value = MagicMock(success=True, message="ok")
        config._llm_session._providers["ollama"] = mock_provider

        result = config.test_llm_connection()
        assert result.success is True
        mock_provider.test_connection.assert_called_once()
    finally:
        config.close()


def test_list_llm_models_delegates(tmp_path) -> None:
    config = Config.open(tmp_path / "llm_models.db", migrate_backup=False)
    try:
        config.bind_llm_session()
        mock_provider = MockLLMProvider()
        config._llm_session._providers["ollama"] = mock_provider

        models = config.list_llm_models()
        assert models[0].id == "mock"
    finally:
        config.close()
