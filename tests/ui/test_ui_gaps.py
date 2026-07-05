"""Tests for bridge user action dispatch and error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.controller import TrayOverlayBridge, UiActionHandlers
from app.ui.state_view import OverlayDisplayState
from core.store.models import SessionStatus


def test_bridge_change_mode_updates_config(tmp_path) -> None:
    from app.config import Config
    from app.ui.controller import TrayOverlayBridge
    from app.ui.state_view import OverlayDisplayState

    config = Config.open(tmp_path / "bridge_mode.db", migrate_backup=False)
    runtime = MagicMock()
    runtime.config = config
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    changes: list[tuple[str, str]] = []
    labels: list[str] = []
    bridge.on_mode_changed(lambda mode_id, name: changes.append((mode_id, name)))
    bridge.on_display_state(lambda _state, label: labels.append(label))

    bridge.change_mode("polish")

    assert config.get_active_mode_id() == "polish"
    assert changes == [("polish", "문장 다듬기")]
    assert labels[-1] == "대기 · 문장 다듬기"
    config.close()


def test_bridge_dispatches_user_actions() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    events: list[str] = []
    bridge.bind_actions(
        UiActionHandlers(
            request_record_toggle=lambda: events.append("toggle"),
            request_cancel=lambda: events.append("cancel"),
            quit_app=lambda: events.append("quit"),
        )
    )
    bridge.request_record_toggle()
    bridge.request_cancel()
    bridge.quit_app()
    assert events == ["toggle", "cancel", "quit"]


def test_bridge_notify_pipeline_error_sets_error_state() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    states: list[OverlayDisplayState] = []
    errors: list[tuple[str, str]] = []
    bridge.on_display_state(lambda state, _label: states.append(state))
    bridge.on_pipeline_error(lambda title, msg: errors.append((title, msg)))

    bridge.notify_pipeline_error("테스트 오류")

    assert states == [OverlayDisplayState.ERROR]
    assert errors == [("STT-AIO", "테스트 오류")]


def test_bridge_inject_failure_uses_pending_message_on_session_error() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    errors: list[tuple[str, str]] = []
    bridge.on_pipeline_error(lambda title, msg: errors.append((title, msg)))

    artifact = MagicMock()
    artifact.session_id = "abcd-1234"
    artifact.inject_result = MagicMock(success=False)

    bridge._on_inject(artifact)
    bridge._on_session_state("abcd-1234", SessionStatus.ERROR)

    assert errors == [("STT-AIO", "주입 실패 (abcd-123)")]


def test_bridge_session_error_without_pending_uses_generic_message() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    errors: list[tuple[str, str]] = []
    bridge.on_pipeline_error(lambda title, msg: errors.append((title, msg)))

    bridge._on_session_state("session-xyz", SessionStatus.ERROR)

    assert errors == [("STT-AIO", "세션 오류 (session-)")]


def test_bridge_ignores_stale_level_events_after_recording() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    bridge._on_session_state("sid", SessionStatus.RECORDING)
    bridge._on_level(0.5, 0.25)
    bridge._on_session_state("sid", SessionStatus.PROCESSING)
    bridge._on_level(0.9, 0.8)

    assert bridge.waveform.values() == []


def test_bridge_on_session_state_alias_receives_raw_status() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    events: list[tuple[str, SessionStatus]] = []
    bridge.on_session_state(lambda sid, status: events.append((sid, status)))

    bridge._on_session_state("abc", SessionStatus.PROCESSING)

    assert events == [("abc", SessionStatus.PROCESSING)]


def test_bridge_on_level_alias_receives_peak_rms() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    levels: list[tuple[float, float]] = []
    bridge.on_level(lambda peak, rms: levels.append((peak, rms)))

    bridge._on_session_state("sid", SessionStatus.RECORDING)
    bridge._on_level(0.7, 0.35)

    assert levels == [(0.7, 0.35)]


def test_bridge_dismiss_display_error_resets_state() -> None:
    runtime = MagicMock()
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)

    states: list[OverlayDisplayState] = []
    bridge.on_display_state(lambda state, _label: states.append(state))
    bridge.notify_pipeline_error("오류")

    bridge.dismiss_display_error()

    assert states == [OverlayDisplayState.ERROR, OverlayDisplayState.IDLE]
    assert bridge.display_state is OverlayDisplayState.IDLE

