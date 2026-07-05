"""Tests for tray/overlay bridge."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.controller import TrayOverlayBridge
from app.ui.state_view import OverlayDisplayState
from core.store.models import SessionStatus


def test_bridge_updates_display_state() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    states: list[OverlayDisplayState] = []
    bridge.on_display_state(lambda state, _label: states.append(state))

    bridge._on_session_state("sid", SessionStatus.RECORDING)
    bridge._on_session_state("sid", SessionStatus.PROCESSING)
    bridge._on_session_state("sid", SessionStatus.DONE)

    assert states == [
        OverlayDisplayState.RECORDING,
        OverlayDisplayState.PROCESSING,
        OverlayDisplayState.IDLE,
    ]


def test_bridge_collects_waveform_levels() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    bridge._on_session_state("sid", SessionStatus.RECORDING)
    bridge._on_level(0.5, 0.25)
    bridge._on_level(0.8, 0.4)

    assert bridge.waveform.values() == [0.25, 0.4]
