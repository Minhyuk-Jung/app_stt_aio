"""Additional C10 gap coverage tests."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.session.errors import SessionBusyError
from app.session.types import SessionArtifact
from core.audio.errors import CaptureBusyError
from core.stt.types import STTResult
from core.store.models import SessionSource, SessionStatus


def test_capture_error_on_begin_marks_error(session_env) -> None:
    _config, capture, manager, _handle = session_env
    capture.start_batch.side_effect = CaptureBusyError("busy")
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    with pytest.raises(CaptureBusyError):
        manager.begin(SessionSource.BATCH)

    assert states == [SessionStatus.ERROR]


def test_cancel_during_processing_keeps_canceled(session_env) -> None:
    _config, _capture, manager, handle = session_env
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    session_id = manager.begin(SessionSource.BATCH)
    artifact = SessionArtifact(session_id=session_id, stage=1, text="x", language="ko")

    def slow_pipeline(*_args, **_kwargs):
        time.sleep(0.15)
        return STTResult(text="x", language="ko"), artifact

    with patch("app.session.session_manager.run_batch_pipeline", side_effect=slow_pipeline):
        manager.stop(session_id)
        time.sleep(0.02)
        manager.cancel(session_id)
        time.sleep(0.3)

    assert SessionStatus.CANCELED in states
    assert SessionStatus.DONE not in states


def test_cancel_policy_cancels_processing_before_new_begin(session_env) -> None:
    config, capture, manager, _handle = session_env
    config.set("session.queue_policy", "cancel")

    first_id = manager.begin(SessionSource.BATCH)
    manager._recording_session_id = None
    manager._processing_session_id = first_id

    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    second_id = manager.begin(SessionSource.BATCH)

    assert SessionStatus.CANCELED in states
    assert second_id != first_id
    assert capture.start_batch.call_count == 2


def test_queue_drains_after_processing_completes(session_env) -> None:
    config, capture, manager, _handle = session_env
    config.set("session.queue_policy", "queue")

    first_id = manager.begin(SessionSource.BATCH)
    artifact = SessionArtifact(session_id=first_id, stage=1, text="done", language="ko")

    with patch(
        "app.session.session_manager.run_batch_pipeline",
        return_value=(STTResult(text="done", language="ko"), artifact),
    ):
        manager.stop(first_id)
        with pytest.raises(SessionBusyError, match="queued"):
            manager.begin(SessionSource.BATCH)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if capture.start_batch.call_count >= 2:
                break
            time.sleep(0.02)

    assert capture.start_batch.call_count == 2


def test_cancel_policy_cancels_active_recording_before_new_begin(session_env) -> None:
    config, capture, manager, _handle = session_env
    config.set("session.queue_policy", "cancel")

    first_id = manager.begin(SessionSource.BATCH)
    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    second_id = manager.begin(SessionSource.BATCH)

    assert first_id != second_id
    assert SessionStatus.CANCELED in states
    assert capture.start_batch.call_count == 2
    assert manager.recording_session_id == second_id


def test_session_forwards_capture_levels(session_env) -> None:
    _config, capture, manager, _handle = session_env
    levels: list[tuple[float, float]] = []
    manager.on_level(lambda peak, rms: levels.append((peak, rms)))

    manager.begin(SessionSource.BATCH)

    assert capture.set_level_callback.call_count >= 1
    callback = capture.set_level_callback.call_args_list[-1][0][0]
    callback(0.6, 0.3)

    assert levels == [(0.6, 0.3)]


def test_cancel_during_processing_skips_inject_via_pipeline(session_env) -> None:
    config, capture, manager, _handle = session_env
    config.bind_stt_session()
    config.bind_injector()
    config.bind_pipeline()

    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    def slow_stage1(_cfg, _audio, session_id: str):
        time.sleep(0.2)
        return (
            STTResult(text="늦음", language="ko", provider_id="mock"),
            SessionArtifact(session_id=session_id, stage=1, text="늦음", language="ko"),
        )

    with patch("core.pipeline.pipeline.run_stage1", side_effect=slow_stage1):
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            session_id = manager.begin(SessionSource.BATCH)
            manager.stop(session_id)
            time.sleep(0.05)
            manager.cancel(session_id)
            time.sleep(0.35)

    mock_inject.assert_not_called()
    assert SessionStatus.CANCELED in states
    assert SessionStatus.DONE not in states
