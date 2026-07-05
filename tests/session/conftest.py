"""Shared fixtures for session tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.session import SessionManager
from core.audio.format import AudioBuffer


@pytest.fixture
def session_env(tmp_path):
    config = Config.open(tmp_path / "session.db", migrate_backup=False)
    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle
    capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01\x02")
    manager = SessionManager(config, capture)
    yield config, capture, manager, handle
    manager.close()
    config.close()
