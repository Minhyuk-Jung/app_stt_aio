"""Tray + overlay application shell (C12)."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.services.dictation_runtime import DictationRuntime
from app.services.remote_gateway_service import RemoteGatewayService
from app.session.errors import SessionBusyError, SessionStateError
from app.ui.controller import TrayOverlayBridge, UiActionHandlers
from app.ui.overlay import OverlayWindow
from app.ui.qt_dispatcher import QtUiDispatcher
from app.ui.session_actions import resolve_cancel_session_id
from app.ui.settings.workers import SettingsTaskRunner
from app.ui.state_view import OverlayDisplayState
from app.ui.tray import TrayController
from app.ui.update_check import run_update_check_dialog, run_update_check_on_startup
from core.audio.errors import AudioError
from core.store.models import SessionSource

logger = logging.getLogger(__name__)


def start_hotkey_safe(hotkey, tray) -> bool:
    """Start global hotkeys; degrade gracefully on registration failure.

    Returns True if hotkeys registered, False if unavailable.
    """
    from app.hotkey.errors import HotkeyRegistrationError

    try:
        hotkey.start()
        return True
    except HotkeyRegistrationError as exc:
        logger.error("Global hotkey unavailable: %s", exc)
        tray.show_message(
            "STT-AIO",
            "전역 핫키를 등록하지 못했습니다. 트레이 아이콘 → 녹음 시작/정지를 사용하세요.",
        )
        return False


class TrayOverlayApp:
    """P1 desktop shell: tray menu + status overlay."""

    def __init__(self, runtime: DictationRuntime) -> None:
        self._runtime = runtime
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._dispatcher = QtUiDispatcher()
        self._bridge = TrayOverlayBridge(runtime)
        self._overlay = OverlayWindow()
        self._tray = TrayController(self._bridge)
        self._manual_session_id: str | None = None
        self._settings_window = None
        self._workbench_window = None
        self._workbench_controller = None
        self._onboarding_controller = None
        self._update_tasks = SettingsTaskRunner()
        self._remote_gateway = RemoteGatewayService(runtime.sessions)

        self._wire_thread_safe_events()
        self._bridge.bind_actions(
            UiActionHandlers(
                request_record_toggle=self._toggle_recording,
                request_cancel=self._cancel_active,
                open_settings=self._open_settings,
                open_workbench=self._open_workbench,
                open_onboarding=self._open_onboarding,
                open_remote_settings=self._open_remote_settings,
                check_updates=self._check_updates,
                quit_app=self._quit,
            )
        )
        self._runtime.capture.set_error_callback(self._on_capture_error)
        self._runtime.config.bind_pipeline()
        self._bridge.bind_pipeline(self._runtime.config.pipeline)

    def _wire_thread_safe_events(self) -> None:
        self._bridge.on_display_state(
            lambda state, label: self._dispatcher.display_state_changed.emit(state, label)
        )
        self._bridge.on_waveform(
            lambda samples: self._dispatcher.waveform_changed.emit(samples)
        )
        self._bridge.on_pipeline_error(
            lambda title, message: self._dispatcher.error_notice.emit(title, message)
        )
        self._bridge.on_inject_feedback(self._on_inject_feedback)

        self._dispatcher.display_state_changed.connect(self._overlay.set_display_state)
        self._dispatcher.display_state_changed.connect(self._tray.update_for_display_state)
        self._dispatcher.waveform_changed.connect(self._overlay.queue_waveform)
        self._dispatcher.error_notice.connect(self._tray.show_message)
        self._dispatcher.inject_feedback.connect(self._on_inject_feedback_main)
        self._dispatcher.workbench_refresh.connect(self._on_workbench_refresh)
        self._dispatcher.workbench_stage_completed.connect(self._on_workbench_stage_completed)

        self._overlay.set_render_error_callback(
            lambda message: self._tray.show_message("STT-AIO", message)
        )
        self._overlay.set_error_dismiss_callback(self._dismiss_overlay_error)

    def run(self) -> int:
        self._bridge._emit_display_state(OverlayDisplayState.IDLE)
        self._tray.show()
        start_hotkey_safe(self._runtime.hotkey, self._tray)
        from app.ui.onboarding import is_completed

        if not is_completed(self._runtime.config):
            self._open_onboarding()
        if bool(self._runtime.config.get("update.auto_check")):
            manifest_url = str(self._runtime.config.get("update.manifest_url"))
            if manifest_url.strip():
                run_update_check_on_startup(self._update_tasks, manifest_url, None)
        logger.info("STT-AIO tray app started")
        return self._app.exec()

    def _on_inject_feedback(self, session_id: str, success: bool) -> None:
        self._dispatcher.inject_feedback.emit(session_id, success)

    def _on_inject_feedback_main(self, session_id: str, success: bool) -> None:
        del session_id, success  # inject feedback reserved for future UI (C13)

    def _dismiss_overlay_error(self) -> None:
        self._bridge.dismiss_display_error()

    def _on_capture_error(self, error: AudioError) -> None:
        logger.warning("Audio capture error: %s", error)
        self._bridge.notify_pipeline_error(f"오디오 오류: {error}")

    def _toggle_recording(self) -> None:
        sessions = self._runtime.sessions
        if sessions.recording_session_id is not None:
            session_id = sessions.recording_session_id
            try:
                sessions.stop(session_id)
            except (SessionStateError, SessionBusyError) as exc:
                logger.warning("Manual stop failed: %s", exc)
            return

        try:
            self._manual_session_id = sessions.begin(SessionSource.BATCH)
        except SessionBusyError as exc:
            logger.info("Manual begin ignored: %s", exc)

    def _cancel_active(self) -> None:
        sessions = self._runtime.sessions
        session_id = resolve_cancel_session_id(sessions, self._manual_session_id)
        if session_id is None:
            return
        try:
            sessions.cancel(session_id)
        except (SessionStateError, SessionBusyError) as exc:
            logger.warning("Manual cancel failed: %s", exc)
        finally:
            self._manual_session_id = None

    def _open_settings(self) -> None:
        from app.ui.settings import SettingsController
        from app.ui.settings.settings_window import SettingsWindow

        if self._settings_window is None:
            self._settings_window = SettingsWindow(
                SettingsController(
                    self._runtime.config,
                    hotkey_manager=self._runtime.hotkey,
                    capture=self._runtime.capture,
                    gateway_service=self._remote_gateway,
                ),
                gateway_service=self._remote_gateway,
                on_active_mode_changed=self._on_settings_active_mode_changed,
                on_modes_changed=self._on_settings_modes_updated,
            )
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _open_remote_settings(self) -> None:
        self._open_settings()
        if self._settings_window is not None:
            self._settings_window.select_tab("원격 녹음")

    def _check_updates(self) -> None:
        manifest_url = str(self._runtime.config.get("update.manifest_url"))
        run_update_check_dialog(self._update_tasks, manifest_url, None)

    def _on_settings_active_mode_changed(self, mode_id: str, _mode_name: str) -> None:
        self._bridge.change_mode(mode_id)

    def _on_settings_modes_updated(self) -> None:
        self._bridge.notify_modes_updated()
        self._tray.refresh_mode_menu()

    def _on_workbench_refresh(self, session_id: str) -> None:
        if self._workbench_window is not None and self._workbench_window.isVisible():
            if session_id:
                self._workbench_window.refresh_if_viewing(session_id)
            else:
                self._workbench_window.reload(preserve_selection=True)

    def _on_workbench_stage_completed(self, session_id: str, stage: int) -> None:
        if self._workbench_window is not None and self._workbench_window.isVisible():
            self._workbench_window.refresh_after_stage(session_id, stage)

    def _open_workbench(self) -> None:
        from app.ui.workbench import WorkbenchController
        from app.ui.workbench.workbench_window import WorkbenchWindow

        if self._workbench_controller is None:
            self._workbench_controller = WorkbenchController(
                self._runtime.config,
                session_manager=self._runtime.sessions,
            )
            if self._runtime.config._pipeline is None:
                self._runtime.config.bind_pipeline()
            self._workbench_controller.bind_pipeline(self._runtime.config.pipeline)
            self._workbench_controller.on_session_state(
                lambda sid, _status: self._dispatcher.workbench_refresh.emit(sid)
            )
            self._workbench_controller.on_stage_completed(
                lambda sid, stage: self._dispatcher.workbench_stage_completed.emit(
                    sid, stage
                )
            )
        if self._workbench_window is None:
            self._workbench_window = WorkbenchWindow(self._workbench_controller)
        self._workbench_window.show()
        self._workbench_window.raise_()
        self._workbench_window.activateWindow()

    def _open_onboarding(self) -> None:
        from app.ui.onboarding import start_onboarding
        from app.ui.settings.controller import SettingsController

        if self._onboarding_controller is None:
            self._onboarding_controller = SettingsController(
                self._runtime.config,
                hotkey_manager=self._runtime.hotkey,
                capture=self._runtime.capture,
                gateway_service=self._remote_gateway,
            )
        start_onboarding(
            self._onboarding_controller,
            parent=None,
            blocking=True,
            on_completed=self._on_onboarding_completed,
        )

    def _on_onboarding_completed(self) -> None:
        logger.info("Onboarding completed")

    def _quit(self) -> None:
        self._remote_gateway.stop()
        self._runtime.hotkey.close()
        self._runtime.sessions.close()
        self._runtime.config.close()
        self._app.quit()


def create_tray_overlay_app(runtime: DictationRuntime) -> TrayOverlayApp:
    return TrayOverlayApp(runtime)
