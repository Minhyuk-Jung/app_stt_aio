"""Tests for overlay state mapping."""

from __future__ import annotations

from app.ui.state_view import OverlayDisplayState, map_session_status, overlay_status_text
from core.store.models import SessionStatus


def test_map_session_status_recording() -> None:
    assert map_session_status(SessionStatus.RECORDING) is OverlayDisplayState.RECORDING


def test_map_session_status_processing() -> None:
    assert map_session_status(SessionStatus.PROCESSING) is OverlayDisplayState.PROCESSING


def test_map_session_status_done_returns_idle() -> None:
    assert map_session_status(SessionStatus.DONE) is OverlayDisplayState.IDLE


def test_overlay_status_text_korean() -> None:
    assert overlay_status_text(OverlayDisplayState.RECORDING) == "녹음 중"


def test_overlay_idle_includes_mode_name() -> None:
    assert overlay_status_text(OverlayDisplayState.IDLE, mode_name="빠른 받아쓰기") == (
        "대기 · 빠른 받아쓰기"
    )
