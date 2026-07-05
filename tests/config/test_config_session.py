"""Tests for Config <-> SessionManager binding."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_bind_session_manager(tmp_path) -> None:
    from app.config import Config
    from app.session import SessionManager

    capture = MagicMock()
    with Config.open(tmp_path / "bind_session.db", migrate_backup=False) as config:
        manager = config.bind_session_manager(capture)
        assert isinstance(manager, SessionManager)
        assert config.session_manager is manager


def test_session_manager_property_requires_bind(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "bind_session2.db", migrate_backup=False) as config:
        try:
            _ = config.session_manager
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass


def test_bind_pipeline_from_config(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "bind_pipeline_session.db", migrate_backup=False) as config:
        pipeline = config.bind_pipeline()
        assert config.pipeline is pipeline
        assert config.bind_pipeline() is pipeline
