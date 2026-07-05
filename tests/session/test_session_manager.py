"""Tests for SessionManager lifecycle."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.session.errors import (
    SessionBusyError,
    SessionNotFoundError,
    SessionNotImplementedError,
    SessionStateError,
)
from app.session.types import SessionArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource, SessionStatus


def test_begin_batch_creates_recording_session(session_env) -> None:
    config, capture, manager, handle = session_env
    states: list[tuple[str, SessionStatus]] = []
    manager.on_session_state(lambda sid, status: states.append((sid, status)))

    session_id = manager.begin(SessionSource.BATCH)

    capture.start_batch.assert_called_once()
    stored = config._store.sessions.get(session_id)
    assert stored is not None
    assert stored.status is SessionStatus.RECORDING
    assert manager.recording_session_id == session_id
    assert states == [(session_id, SessionStatus.RECORDING)]


def test_stop_runs_pipeline_and_marks_done(session_env) -> None:
    config, capture, manager, handle = session_env
    states: list[SessionStatus] = []
    artifacts: list[str] = []
    manager.on_session_state(lambda _sid, status: states.append(status))
    manager.on_inject(lambda artifact: artifacts.append(artifact.text))

    session_id = manager.begin(SessionSource.BATCH)
    artifact = SessionArtifact(
        session_id=session_id,
        stage=1,
        text="안녕",
        language="ko",
        inject_result=MagicMock(success=True),
    )

    with patch(
        "app.session.session_manager.run_batch_pipeline",
        return_value=(STTResult(text="안녕", language="ko"), artifact),
    ):
        manager.stop(session_id)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if SessionStatus.DONE in states:
                break
            time.sleep(0.02)

    capture.stop_batch.assert_called_once_with(handle)
    assert SessionStatus.PROCESSING in states
    assert SessionStatus.DONE in states
    assert artifacts == ["안녕"]


def test_stop_marks_error_on_inject_failure(session_env) -> None:
    config, capture, manager, handle = session_env
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    session_id = manager.begin(SessionSource.BATCH)
    artifact = SessionArtifact(
        session_id=session_id,
        stage=1,
        text="실패",
        language="ko",
        inject_result=MagicMock(success=False),
    )

    with patch(
        "app.session.session_manager.run_batch_pipeline",
        return_value=(STTResult(text="실패", language="ko"), artifact),
    ):
        manager.stop(session_id)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if SessionStatus.ERROR in states:
                break
            time.sleep(0.02)

    assert SessionStatus.ERROR in states
    assert SessionStatus.DONE not in states


def test_cancel_during_recording(session_env) -> None:
    config, capture, manager, _handle = session_env
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    session_id = manager.begin(SessionSource.BATCH)
    manager.cancel(session_id)

    capture.cancel.assert_called_once()
    capture.stop_batch.assert_not_called()
    assert states[-1] is SessionStatus.CANCELED
    assert manager.recording_session_id is None


def test_begin_realtime_starts_stream(session_env) -> None:
    config, capture, manager, _handle = session_env
    config.bind_injector()
    stream_handle = MagicMock()
    capture.start_stream.return_value = stream_handle
    session_id = manager.begin(SessionSource.REALTIME)
    assert manager.recording_session_id == session_id
    capture.start_stream.assert_called_once()


def test_stop_unknown_session_raises(session_env) -> None:
    _config, _capture, manager, _handle = session_env
    with pytest.raises(SessionNotFoundError):
        manager.stop("missing")


def test_ignore_policy_rejects_while_processing(session_env) -> None:
    config, capture, manager, handle = session_env
    config.set("session.queue_policy", "ignore")

    session_id = manager.begin(SessionSource.BATCH)
    manager._recording_session_id = None
    manager._processing_session_id = session_id

    with pytest.raises(SessionBusyError):
        manager.begin(SessionSource.BATCH)

    capture.start_batch.assert_called_once()


def test_queue_policy_enqueues_second_begin(session_env) -> None:
    config, _capture, manager, _handle = session_env
    config.set("session.queue_policy", "queue")

    first_id = manager.begin(SessionSource.BATCH)
    manager._recording_session_id = None
    manager._processing_session_id = first_id

    with pytest.raises(SessionBusyError, match="queued"):
        manager.begin(SessionSource.BATCH)


def test_close_waits_for_background_worker(session_env) -> None:
    config, capture, manager, _handle = session_env
    started = threading.Event()
    release_worker = threading.Event()

    def slow_pipeline(*_args, **_kwargs):
        started.set()
        release_worker.wait(timeout=2.0)
        artifact = SessionArtifact(
            session_id="worker-test",
            stage=1,
            text="done",
            language="ko",
            inject_result=MagicMock(success=True),
        )
        return STTResult(text="done", language="ko"), artifact

    session_id = manager.begin(SessionSource.BATCH)
    with patch(
        "app.session.session_manager.run_batch_pipeline",
        side_effect=slow_pipeline,
    ):
        manager.stop(session_id)
        assert started.wait(timeout=2.0)

        def release_worker_later() -> None:
            release_worker.set()

        threading.Thread(target=release_worker_later, daemon=True).start()
        manager.close()

    assert manager._active_workers == 0


def test_close_cancels_active_recording(session_env) -> None:
    _config, capture, manager, _handle = session_env
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    session_id = manager.begin(SessionSource.BATCH)
    manager.close()

    capture.cancel.assert_called_once()
    assert SessionStatus.CANCELED in states
    assert manager.recording_session_id is None
