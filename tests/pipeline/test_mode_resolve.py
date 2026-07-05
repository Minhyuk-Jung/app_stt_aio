"""Tests for mode resolution with C7."""

from __future__ import annotations

from app.config import Config
from core.pipeline.mode_resolve import resolve_mode_for_session
from core.store.models import SessionSource


def test_resolve_mode_unknown_session_returns_default_mode(tmp_path) -> None:
    config = Config.open(tmp_path / "mode.db", migrate_backup=False)
    try:
        mode = resolve_mode_for_session(config, "missing")
        assert mode.id == "quick-dictation"
        assert mode.target_stage == 1
        assert mode.inject_stage == 1
    finally:
        config.close()


def test_resolve_mode_without_mode_id_uses_default(tmp_path) -> None:
    config = Config.open(tmp_path / "mode2.db", migrate_backup=False)
    try:
        session = config._store.sessions.create(source=SessionSource.BATCH)
        mode = resolve_mode_for_session(config, session.id)
        assert mode.id == "quick-dictation"
    finally:
        config.close()


def test_resolve_mode_uses_session_mode_stages(tmp_path) -> None:
    config = Config.open(tmp_path / "mode3.db", migrate_backup=False)
    try:
        session = config._store.sessions.create(
            source=SessionSource.BATCH,
            mode_id="polish",
        )
        mode = resolve_mode_for_session(config, session.id)
        assert mode.id == "polish"
        assert mode.target_stage == 2
        assert mode.inject_stage == 2
    finally:
        config.close()


def test_resolve_mode_falls_back_when_mode_disabled(tmp_path) -> None:
    config = Config.open(tmp_path / "mode4.db", migrate_backup=False)
    try:
        config.mode_manager.disable_mode("polish")
        session = config._store.sessions.create(
            source=SessionSource.BATCH,
            mode_id="polish",
        )
        mode = resolve_mode_for_session(config, session.id)
        assert mode.id == "quick-dictation"
    finally:
        config.close()
