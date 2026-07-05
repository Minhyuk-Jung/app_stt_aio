"""Bridge Application events to Qt signals (C12)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app.ui.state_view import OverlayDisplayState, map_session_status
from app.ui.waveform_buffer import WaveformBuffer
from core.store.models import SessionStatus

if TYPE_CHECKING:
    from app.services.dictation_runtime import DictationRuntime

logger = logging.getLogger(__name__)

UserActionCallback = Callable[[], None]


@dataclass
class UiActionHandlers:
    request_record_toggle: UserActionCallback | None = None
    request_cancel: UserActionCallback | None = None
    open_settings: UserActionCallback | None = None
    open_workbench: UserActionCallback | None = None
    open_onboarding: UserActionCallback | None = None
    open_remote_settings: UserActionCallback | None = None
    check_updates: UserActionCallback | None = None
    quit_app: UserActionCallback | None = None


class TrayOverlayBridge:
    """Qt-free event bridge; UI layer attaches signal emitters to callbacks."""

    def __init__(self, runtime: DictationRuntime) -> None:
        self._runtime = runtime
        self._display_state = OverlayDisplayState.IDLE
        self._waveform = WaveformBuffer()
        self._active_session_id: str | None = None
        self._state_listeners: list[Callable[[OverlayDisplayState, str], None]] = []
        self._session_state_listeners: list[Callable[[str, SessionStatus], None]] = []
        self._level_listeners: list[Callable[[list[float]], None]] = []
        self._raw_level_listeners: list[Callable[[float, float], None]] = []
        self._error_listeners: list[Callable[[str, str], None]] = []
        self._inject_listeners: list[Callable[[str, bool], None]] = []
        self._actions = UiActionHandlers()
        self._pending_error_message: str | None = None
        self._mode_listeners: list[Callable[[str, str], None]] = []
        self._active_mode_name = runtime.config.get_active_mode().name
        self._processing_stage: int | None = None

        runtime.sessions.on_session_state(self._on_session_state)
        runtime.sessions.on_level(self._on_level)
        runtime.sessions.on_inject(self._on_inject)

    @property
    def display_state(self) -> OverlayDisplayState:
        return self._display_state

    @property
    def waveform(self) -> WaveformBuffer:
        return self._waveform

    @property
    def actions(self) -> UiActionHandlers:
        return self._actions

    def on_display_state(self, callback: Callable[[OverlayDisplayState, str], None]) -> None:
        self._state_listeners.append(callback)

    def on_session_state(self, callback: Callable[[str, SessionStatus], None]) -> None:
        """Plan section 3: raw session status subscription."""
        self._session_state_listeners.append(callback)

    def on_waveform(self, callback: Callable[[list[float]], None]) -> None:
        self._level_listeners.append(callback)

    def on_level(self, callback: Callable[[float, float], None]) -> None:
        """Plan section 3: peak/rms level subscription."""
        self._raw_level_listeners.append(callback)

    def on_error_notice(self, callback: Callable[[str, str], None]) -> None:
        self._error_listeners.append(callback)

    def on_inject_feedback(self, callback: Callable[[str, bool], None]) -> None:
        self._inject_listeners.append(callback)

    def on_inject(self, callback: Callable[[str, bool], None]) -> None:
        """Plan section 3 alias for inject feedback."""
        self.on_inject_feedback(callback)

    def on_pipeline_error(self, callback: Callable[[str, str], None]) -> None:
        """Alias for pipeline/session processing errors (plan 3)."""
        self._error_listeners.append(callback)

    def change_mode(self, mode_id: str) -> None:
        config = self._runtime.config
        try:
            config.set_active_mode_id(mode_id)
        except (ValueError, Exception) as exc:
            logger.warning("Mode change to %s failed: %s", mode_id, exc)
            return
        mode = config.get_active_mode()
        for callback in self._mode_listeners:
            callback(mode.id, mode.name)
        self._active_mode_name = mode.name
        if self._display_state is OverlayDisplayState.IDLE:
            self._emit_display_state(OverlayDisplayState.IDLE)
        logger.info("Active mode changed to %s (%s)", mode.id, mode.name)

    def notify_modes_updated(self) -> None:
        """Refresh UI subscribers after mode list/metadata changes (C14)."""
        mode = self._runtime.config.get_active_mode()
        for callback in self._mode_listeners:
            callback(mode.id, mode.name)

    def list_enabled_modes(self) -> list[tuple[str, str]]:
        """Return (id, name) pairs for enabled modes (C12 quick switch)."""
        return [
            (mode.id, mode.name)
            for mode in self._runtime.config.mode_manager.list_modes(enabled_only=True)
        ]

    def get_active_mode_label(self) -> str:
        return self._runtime.config.get_active_mode().name

    def on_mode_changed(self, callback: Callable[[str, str], None]) -> None:
        """Subscribe to active mode changes (mode_id, display name)."""
        self._mode_listeners.append(callback)

    def bind_pipeline(self, pipeline) -> None:
        """Subscribe to pipeline stage events for overlay detail (C12 P2)."""
        pipeline.on_stage_started(self._on_pipeline_stage_started)
        pipeline.on_pipeline_finished(lambda _run: self._clear_processing_stage())

    def _on_pipeline_stage_started(self, stage: int) -> None:
        self._processing_stage = stage
        if self._display_state is OverlayDisplayState.PROCESSING:
            self._emit_display_state(self._display_state)

    def _clear_processing_stage(self) -> None:
        self._processing_stage = None

    def bind_actions(self, handlers: UiActionHandlers) -> None:
        self._actions = handlers

    def request_record_toggle(self) -> None:
        if self._actions.request_record_toggle is not None:
            self._actions.request_record_toggle()

    def request_cancel(self) -> None:
        if self._actions.request_cancel is not None:
            self._actions.request_cancel()

    def open_settings(self) -> None:
        if self._actions.open_settings is not None:
            self._actions.open_settings()

    def open_workbench(self) -> None:
        if self._actions.open_workbench is not None:
            self._actions.open_workbench()

    def open_onboarding(self) -> None:
        if self._actions.open_onboarding is not None:
            self._actions.open_onboarding()

    def open_remote_settings(self) -> None:
        if self._actions.open_remote_settings is not None:
            self._actions.open_remote_settings()

    def check_updates(self) -> None:
        if self._actions.check_updates is not None:
            self._actions.check_updates()

    def quit_app(self) -> None:
        if self._actions.quit_app is not None:
            self._actions.quit_app()

    def _on_session_state(self, session_id: str, status: SessionStatus) -> None:
        self._active_session_id = session_id
        for callback in self._session_state_listeners:
            callback(session_id, status)

        self._display_state = map_session_status(status)
        if self._display_state is not OverlayDisplayState.RECORDING:
            self._waveform.clear()
        self._emit_display_state(self._display_state)
        if self._display_state is OverlayDisplayState.ERROR:
            message = self._pending_error_message or f"세션 오류 ({session_id[:8]})"
            self._pending_error_message = None
            for callback in self._error_listeners:
                callback("STT-AIO", message)

    def _on_level(self, peak: float, rms: float) -> None:
        for callback in self._raw_level_listeners:
            callback(peak, rms)
        if self._display_state is not OverlayDisplayState.RECORDING:
            return
        self._waveform.push(rms)
        samples = self._waveform.values()
        for callback in self._level_listeners:
            callback(samples)

    def dismiss_display_error(self) -> None:
        """Sync bridge state after overlay auto-dismisses an error."""
        if self._display_state is not OverlayDisplayState.ERROR:
            return
        self._emit_display_state(OverlayDisplayState.IDLE)

    def _emit_display_state(self, state: OverlayDisplayState) -> None:
        from app.ui.state_view import overlay_status_text

        self._display_state = state
        label = overlay_status_text(
            state,
            mode_name=self._active_mode_name,
            processing_stage=self._processing_stage,
        )
        for callback in self._state_listeners:
            callback(state, label)

    def _on_inject(self, artifact) -> None:
        success = artifact.inject_result.success if artifact.inject_result else True
        for callback in self._inject_listeners:
            callback(artifact.session_id, success)
        if not success:
            self._pending_error_message = f"주입 실패 ({artifact.session_id[:8]})"

    def notify_pipeline_error(self, message: str) -> None:
        """Explicit pipeline error hook for non-session failures."""
        self._emit_display_state(OverlayDisplayState.ERROR)
        for callback in self._error_listeners:
            callback("STT-AIO", message)
