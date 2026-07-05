"""Headless end-to-end: trigger record toggle via real Qt app shell."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.config import Config
from app.services.dictation_runtime import DictationRuntime
from app.ui.app_shell import TrayOverlayApp
from core.store.models import SessionSource


def test_manual_record_toggle_runs_pipeline(qtbot, tmp_path):
    config = Config.open(tmp_path / "e2e.db", migrate_backup=False)
    runtime = DictationRuntime(
        config=config,
        capture=MagicMock(),
        hotkey=MagicMock(),
        sessions=MagicMock(),
    )
    runtime.sessions.recording_session_id = None
    app = TrayOverlayApp(runtime)

    app._toggle_recording()
    runtime.sessions.begin.assert_called_once_with(SessionSource.BATCH)

    config.close()
