"""Tests for active mode selection."""

from __future__ import annotations

import pytest

from app.config import Config
from app.session import SessionManager
from unittest.mock import MagicMock


def test_get_active_mode_id_uses_setting(tmp_path) -> None:
    config = Config.open(tmp_path / "active_mode.db", migrate_backup=False)
    try:
        assert config.get("mode.active_id") == "quick-dictation"
        config.set("mode.active_id", "polish")
        assert config.get_active_mode_id() == "polish"
    finally:
        config.close()


def test_get_active_mode_id_falls_back_to_default(tmp_path) -> None:
    config = Config.open(tmp_path / "active_fallback.db", migrate_backup=False)
    try:
        config.set("mode.active_id", "missing")
        assert config.get_active_mode_id() == "quick-dictation"
    finally:
        config.close()


def test_session_begin_uses_active_mode(tmp_path) -> None:
    config = Config.open(tmp_path / "session_mode.db", migrate_backup=False)
    capture = MagicMock()
    manager = SessionManager(config, capture)
    try:
        config.set("mode.active_id", "meeting")
        session_id = manager.begin("batch")
        stored = config._store.sessions.get(session_id)
        assert stored is not None
        assert stored.mode_id == "meeting"
    finally:
        manager.close()
        config.close()


def test_set_active_mode_id_persists(tmp_path) -> None:
    config = Config.open(tmp_path / "set_active.db", migrate_backup=False)
    try:
        assert config.set_active_mode_id("report") == "report"
        assert config.get("mode.active_id") == "report"
        assert config.get_active_mode().name == "보고서"
    finally:
        config.close()


def test_set_active_mode_id_rejects_disabled(tmp_path) -> None:
    config = Config.open(tmp_path / "set_active_disabled.db", migrate_backup=False)
    try:
        config.mode_manager.disable_mode("polish")
        with pytest.raises(ValueError, match="disabled"):
            config.set_active_mode_id("polish")
    finally:
        config.close()
