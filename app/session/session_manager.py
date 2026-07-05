"""Session lifecycle orchestration (C10)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from collections.abc import Callable

from app.session.errors import (
    SessionBusyError,
    SessionNotFoundError,
    SessionNotImplementedError,
    SessionStateError,
)
from app.session.orchestration import run_batch_pipeline
from core.pipeline.errors import PipelineCanceledError
from app.session.queue_policy import QueueAction, resolve_begin_action
from app.session.types import (
    InjectCallback,
    PendingBegin,
    SessionArtifact,
    SessionStateCallback,
)
from core.audio.errors import AudioError
from core.audio.format import AudioBuffer
from core.store.models import SessionSource, SessionStatus

if TYPE_CHECKING:
    from app.config.config import Config
    from app.hotkey.hotkey_manager import HotkeyManager
    from core.audio.audio_capture import AudioCapture, RecordingHandle

logger = logging.getLogger(__name__)


@dataclass
class _RuntimeSession:
    session_id: str
    source: SessionSource
    mode_id: str | None
    capture_handle: RecordingHandle | None = None


class SessionManager:
    """Coordinate batch dictation sessions across capture, STT, and inject."""

    def __init__(self, config: Config, capture: AudioCapture) -> None:
        self._config = config
        self._capture = capture
        self._sessions: dict[str, _RuntimeSession] = {}
        self._recording_session_id: str | None = None
        self._processing_session_id: str | None = None
        self._pending_begins: list[PendingBegin] = []
        self._hotkey_session_id: str | None = None
        self._canceled_sessions: set[str] = set()
        self._worker_lock = threading.Lock()
        self._store_lock = threading.Lock()
        self._active_workers = 0
        self._state_callbacks: list[SessionStateCallback] = []
        self._inject_callbacks: list[InjectCallback] = []
        self._level_callbacks: list[Callable[[float, float], None]] = []

    @property
    def recording_session_id(self) -> str | None:
        return self._recording_session_id

    @property
    def processing_session_id(self) -> str | None:
        return self._processing_session_id

    def on_session_state(self, callback: SessionStateCallback) -> None:
        self._state_callbacks.append(callback)

    def on_inject(self, callback: InjectCallback) -> None:
        self._inject_callbacks.append(callback)

    def on_level(self, callback: Callable[[float, float], None]) -> None:
        self._level_callbacks.append(callback)

    def begin(
        self,
        source: SessionSource | str,
        mode_id: str | None = None,
    ) -> str:
        normalized = SessionSource(source)
        if normalized is SessionSource.REALTIME:
            return self._begin_realtime(mode_id)
        if normalized is SessionSource.REMOTE:
            raise SessionNotImplementedError(
                "remote sessions require C15 RemoteGateway; use submit_remote()"
            )

        action = resolve_begin_action(
            self._config.get("session.queue_policy"),
            is_recording=self._recording_session_id is not None,
            is_processing=self._processing_session_id is not None,
        )
        if action is QueueAction.IGNORE:
            raise SessionBusyError("session manager is busy (ignore policy)")
        if action is QueueAction.QUEUE:
            self._pending_begins.append(PendingBegin(source=normalized, mode_id=mode_id))
            logger.info("Queued batch session request (mode=%s)", mode_id)
            raise SessionBusyError("session request queued")
        if action is QueueAction.CANCEL_CURRENT:
            self._cancel_current_unlocked()

        return self._begin_batch(mode_id)

    def stop(self, session_id: str, *, press_enter: bool = False) -> None:
        runtime = self._require_runtime(session_id)
        if runtime.source is SessionSource.REALTIME:
            if self._recording_session_id != session_id:
                raise SessionStateError(f"session {session_id} is not in realtime recording")
            if runtime.capture_handle is not None:
                self._capture.stop_stream(runtime.capture_handle)
                runtime.capture_handle = None
            self._recording_session_id = None
            self._capture.set_level_callback(None)
            self._set_status(session_id, SessionStatus.DONE)
            self._sessions.pop(session_id, None)
            return
        if runtime.source is not SessionSource.BATCH:
            raise SessionNotImplementedError(f"stop not supported for {runtime.source}")
        if self._recording_session_id != session_id:
            raise SessionStateError(f"session {session_id} is not recording")

        handle = runtime.capture_handle
        if handle is None:
            raise SessionStateError(f"session {session_id} has no active capture handle")

        try:
            audio = self._capture.stop_batch(handle)
        except AudioError:
            runtime.capture_handle = None
            self._recording_session_id = None
            self._sessions.pop(session_id, None)
            self._set_status(session_id, SessionStatus.ERROR)
            raise

        runtime.capture_handle = None
        self._recording_session_id = None
        self._capture.set_level_callback(None)
        self._start_processing(session_id, audio, press_enter=press_enter)

    def cancel(self, session_id: str) -> None:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            with self._store_lock:
                stored = self._config._store.sessions.get(session_id)
            if stored is None:
                raise SessionNotFoundError(session_id)
            if stored.status is SessionStatus.CANCELED:
                return
            raise SessionStateError(f"cannot cancel session {session_id} in state {stored.status}")

        if self._recording_session_id == session_id:
            if runtime.capture_handle is not None:
                if runtime.source is SessionSource.REALTIME:
                    self._capture.stop_stream(runtime.capture_handle)
                else:
                    self._capture.cancel(runtime.capture_handle)
                runtime.capture_handle = None
            self._recording_session_id = None
            self._capture.set_level_callback(None)
            self._set_status(session_id, SessionStatus.CANCELED)
            self._sessions.pop(session_id, None)
            return

        if self._processing_session_id == session_id:
            self._canceled_sessions.add(session_id)
            self._processing_session_id = None
            self._set_status(session_id, SessionStatus.CANCELED)
            self._sessions.pop(session_id, None)
            return

        raise SessionStateError(f"cannot cancel session {session_id} in current runtime state")

    def submit_remote(
        self,
        audio: AudioBuffer,
        mode_id: str | None = None,
    ) -> str:
        """Accept audio from C15 RemoteGateway and run batch pipeline."""
        if mode_id is None:
            mode_id = self._config.get_active_mode_id()
        with self._store_lock:
            stored = self._config._store.sessions.create(
                source=SessionSource.REMOTE,
                mode_id=mode_id,
                status=SessionStatus.PROCESSING,
            )
        self._start_processing(stored.id, audio)
        return stored.id

    def wire_hotkey(self, hotkey: HotkeyManager) -> None:
        """Connect C9 hotkey events to batch session lifecycle."""

        def on_record_start() -> None:
            try:
                self._hotkey_session_id = self.begin(SessionSource.BATCH)
            except SessionBusyError as exc:
                if "queued" not in str(exc).lower():
                    logger.debug("Ignored hotkey record start: %s", exc)
            except AudioError as exc:
                logger.warning("Hotkey record start failed: %s", exc)

        def on_record_stop() -> None:
            self._hotkey_stop(press_enter=False)

        def on_auto_send() -> None:
            self._hotkey_stop(press_enter=True)

        def on_cancel() -> None:
            session_id = (
                self._hotkey_session_id
                or self._recording_session_id
                or self._processing_session_id
            )
            if session_id is None:
                return
            try:
                self.cancel(session_id)
            except (SessionNotFoundError, SessionStateError) as exc:
                logger.warning("Hotkey cancel failed for %s: %s", session_id, exc)
            finally:
                self._hotkey_session_id = None

        hotkey.on_record_start(on_record_start)
        hotkey.on_record_stop(on_record_stop)
        hotkey.on_auto_send(on_auto_send)
        hotkey.on_cancel(on_cancel)

    def _hotkey_stop(self, *, press_enter: bool) -> None:
        session_id = self._hotkey_session_id
        if session_id is None:
            return
        try:
            self.stop(session_id, press_enter=press_enter)
        except (SessionNotFoundError, SessionStateError, AudioError) as exc:
            logger.warning("Hotkey record stop failed for %s: %s", session_id, exc)
        finally:
            self._hotkey_session_id = None

    def close(self) -> None:
        if self._processing_session_id is not None:
            self._canceled_sessions.add(self._processing_session_id)
        if self._recording_session_id is not None:
            try:
                self.cancel(self._recording_session_id)
            except (SessionNotFoundError, SessionStateError):
                pass
        self._pending_begins.clear()
        self._hotkey_session_id = None
        self._wait_for_workers(timeout_sec=2.0)

    def _wait_for_workers(self, *, timeout_sec: float) -> None:
        deadline = time.monotonic() + timeout_sec
        while self._active_workers > 0 and time.monotonic() < deadline:
            time.sleep(0.02)

    def _begin_batch(self, mode_id: str | None) -> str:
        if mode_id is None:
            mode_id = self._config.get_active_mode_id()
        with self._store_lock:
            stored = self._config._store.sessions.create(
                source=SessionSource.BATCH,
                mode_id=mode_id,
                status=SessionStatus.RECORDING,
            )
        try:
            handle = self._capture.start_batch()
        except AudioError:
            self._set_status(stored.id, SessionStatus.ERROR)
            raise

        self._capture.set_level_callback(self._forward_level)

        runtime = _RuntimeSession(
            session_id=stored.id,
            source=SessionSource.BATCH,
            mode_id=mode_id,
            capture_handle=handle,
        )
        self._sessions[stored.id] = runtime
        self._recording_session_id = stored.id
        self._set_status(stored.id, SessionStatus.RECORDING)
        return stored.id

    def _begin_realtime(self, mode_id: str | None) -> str:
        if mode_id is None:
            mode_id = self._config.get_active_mode_id()
        with self._store_lock:
            stored = self._config._store.sessions.create(
                source=SessionSource.REALTIME,
                mode_id=mode_id,
                status=SessionStatus.RECORDING,
            )
        session_id = stored.id
        from core.inject.realtime import RealtimeInjector

        realtime_injector = RealtimeInjector(
            injector=self._config.injector,
            options=self._config.get_inject_options(),
        )

        def on_segment(buffer: AudioBuffer, _is_final: bool) -> None:
            if session_id in self._canceled_sessions:
                return
            try:
                from core.pipeline.stages import run_stage1

                _result, artifact = run_stage1(self._config, buffer, session_id)
                realtime_injector.inject_partial(artifact.text, is_final=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Realtime segment failed for %s: %s", session_id, exc)

        try:
            handle = self._capture.start_stream(
                on_segment,
                on_level=self._forward_level,
            )
        except AudioError:
            self._set_status(session_id, SessionStatus.ERROR)
            raise

        self._capture.set_level_callback(self._forward_level)
        runtime = _RuntimeSession(
            session_id=session_id,
            source=SessionSource.REALTIME,
            mode_id=mode_id,
            capture_handle=handle,
        )
        self._sessions[session_id] = runtime
        self._recording_session_id = session_id
        self._set_status(session_id, SessionStatus.RECORDING)
        return session_id

    def _start_processing(
        self,
        session_id: str,
        audio: AudioBuffer,
        *,
        press_enter: bool = False,
    ) -> None:
        self._set_status(session_id, SessionStatus.PROCESSING)
        self._processing_session_id = session_id

        with self._worker_lock:
            self._active_workers += 1

        def work() -> None:
            from core.diagnostics import bind_context, clear_context, report_error

            bind_context(session_id=session_id)
            try:
                if session_id in self._canceled_sessions:
                    return
                _result, artifact = run_batch_pipeline(
                    self._config,
                    session_id,
                    audio,
                    press_enter=press_enter,
                    is_canceled=lambda: session_id in self._canceled_sessions,
                )
                if session_id in self._canceled_sessions:
                    return
                self._emit_inject(artifact)
                if artifact.inject_result is not None and not artifact.inject_result.success:
                    self._set_status(session_id, SessionStatus.ERROR)
                else:
                    self._set_status(session_id, SessionStatus.DONE)
            except PipelineCanceledError:
                return
            except Exception as exc:
                if session_id not in self._canceled_sessions:
                    report_error(exc, context={"session_id": session_id})
                    self._set_status(session_id, SessionStatus.ERROR)
            finally:
                clear_context()
                with self._worker_lock:
                    self._active_workers = max(0, self._active_workers - 1)
                    self._canceled_sessions.discard(session_id)
                    if self._processing_session_id == session_id:
                        self._processing_session_id = None
                    self._sessions.pop(session_id, None)
                    self._drain_pending_begins()

        threading.Thread(
            target=work,
            name=f"session-worker-{session_id[:8]}",
            daemon=True,
        ).start()

    def _cancel_current_unlocked(self) -> None:
        if self._recording_session_id is not None:
            recording_id = self._recording_session_id
            try:
                self.cancel(recording_id)
            except (SessionNotFoundError, SessionStateError):
                logger.warning("Failed to cancel recording session %s", recording_id)
        self._cancel_processing_unlocked()

    def _cancel_processing_unlocked(self) -> None:
        session_id = self._processing_session_id
        if session_id is None:
            return
        self._canceled_sessions.add(session_id)
        self._processing_session_id = None
        self._set_status(session_id, SessionStatus.CANCELED)
        self._sessions.pop(session_id, None)

    def _drain_pending_begins(self) -> None:
        if self._recording_session_id is not None or self._processing_session_id is not None:
            return
        if not self._pending_begins:
            return
        pending = self._pending_begins.pop(0)
        try:
            self._begin_batch(pending.mode_id)
        except Exception as exc:
            from core.diagnostics import report_error

            report_error(exc, context={"component": "session_manager", "action": "drain_pending"})
            logger.exception("Failed to start queued session")

    def _require_runtime(self, session_id: str) -> _RuntimeSession:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            raise SessionNotFoundError(session_id)
        return runtime

    def _set_status(self, session_id: str, status: SessionStatus) -> None:
        with self._store_lock:
            self._config._store.sessions.update_status(session_id, status)
        self._emit_state(session_id, status)

    def _emit_state(self, session_id: str, status: SessionStatus) -> None:
        for callback in self._state_callbacks:
            try:
                callback(session_id, status)
            except Exception:
                logger.exception("Session state callback failed for %s", session_id)

    def _emit_inject(self, artifact: SessionArtifact) -> None:
        for callback in self._inject_callbacks:
            try:
                callback(artifact)
            except Exception:
                logger.exception("Session inject callback failed for %s", artifact.session_id)

    def _forward_level(self, peak: float, rms: float) -> None:
        for callback in self._level_callbacks:
            try:
                callback(peak, rms)
            except Exception:
                logger.exception("Session level callback failed")
