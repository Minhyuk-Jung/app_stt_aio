"""Tests for Qt-free UI session action helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.session_actions import resolve_cancel_session_id


def test_resolve_cancel_session_id_includes_processing() -> None:
    sessions = MagicMock()
    sessions.recording_session_id = None
    sessions.processing_session_id = "proc-123"

    assert resolve_cancel_session_id(sessions, None) == "proc-123"


def test_resolve_cancel_session_id_prefers_recording() -> None:
    sessions = MagicMock()
    sessions.recording_session_id = "rec-456"
    sessions.processing_session_id = "proc-123"

    assert resolve_cancel_session_id(sessions, None) == "rec-456"


def test_resolve_cancel_session_id_falls_back_to_manual() -> None:
    sessions = MagicMock()
    sessions.recording_session_id = None
    sessions.processing_session_id = None

    assert resolve_cancel_session_id(sessions, "manual-1") == "manual-1"
