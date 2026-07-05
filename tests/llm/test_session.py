"""Tests for LLM provider session."""

from __future__ import annotations

from app.config import Config
from core.llm import LLMRequest


def test_session_skips_provider_on_fully_empty_request(tmp_path) -> None:
    config = Config.open(tmp_path / "llm_sess.db", migrate_backup=False)
    try:
        session = config.bind_llm_session()
        result = session.complete(LLMRequest(system_prompt="", user_text="   "))
        assert result.text == ""
        assert result.provider_id == "skipped"
    finally:
        config.close()
