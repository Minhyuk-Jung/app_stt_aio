"""Tests for pipeline prompt bridge."""

from __future__ import annotations

from app.config import Config
from core.pipeline.mode_prompts import get_prompt_for_session
from core.store.models import SessionSource


def test_get_prompt_for_session_uses_mode_correction(tmp_path) -> None:
    config = Config.open(tmp_path / "prompt.db", migrate_backup=False)
    try:
        session = config._store.sessions.create(
            source=SessionSource.BATCH,
            mode_id="polish",
        )
        prompt = get_prompt_for_session(config, session.id, 2)
        assert "교정" in prompt.system_prompt
    finally:
        config.close()
