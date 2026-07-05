"""Integration tests for P1 MVP dictation flow."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding
from app.session import SessionManager
from app.session.orchestration import run_batch_pipeline
from app.services.dictation_runtime import create_dictation_runtime
from core.audio.format import AudioBuffer
from core.inject.types import InjectMethod, InjectResult
from core.pipeline.types import StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource, SessionStatus
from tests.hotkey.helpers import VK_CTRL, VK_SPACE, press, release


def test_orchestration_runs_bound_pipeline_with_artifact_persist(tmp_path) -> None:
    config = Config.open(tmp_path / "orch.db", migrate_backup=False)
    config.bind_stt_session()
    config.bind_injector()
    config.bind_pipeline()

    session = config._store.sessions.create(source=SessionSource.BATCH)
    stage = StageArtifact(
        session_id=session.id,
        stage=1,
        text="통합 테스트",
        language="ko",
        provider="mock-stt",
    )

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="통합 테스트", language="ko", provider_id="mock-stt"),
            stage,
        )
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=5,
            )
            stt, artifact = run_batch_pipeline(
                config,
                session.id,
                AudioBuffer(pcm_bytes=b"\x00\x01"),
            )

    assert stt.text == "통합 테스트"
    assert artifact.inject_result is not None
    assert artifact.inject_result.success is True
    stored = config._store.artifacts.latest_by_stage(session.id, 1)
    assert stored is not None
    assert stored.text == "통합 테스트"
    config.close()


def test_dictation_runtime_end_to_end_hotkey_session(tmp_path) -> None:
    backend = MockKeyboardBackend()

    with patch("core.audio.AudioCapture") as mock_capture_cls:
        with patch(
            "app.hotkey.hotkey_manager.create_keyboard_backend",
            return_value=backend,
        ):
            capture = MagicMock()
            handle = MagicMock()
            capture.start_batch.return_value = handle
            capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01\x02")
            mock_capture_cls.return_value = capture

            config = Config.open(tmp_path / "e2e.db", migrate_backup=False)
            config.set("hotkey.record_binding", "ctrl+space")
            runtime = create_dictation_runtime(config)
            runtime.hotkey.start()

            states: list[SessionStatus] = []
            runtime.sessions.on_session_state(lambda _sid, status: states.append(status))

            def pipeline_side_effect(cfg, sid, audio, **kwargs):
                from app.session.types import SessionArtifact

                artifact = SessionArtifact(
                    session_id=sid,
                    stage=1,
                    text="E2E",
                    language="ko",
                    inject_result=InjectResult(
                        success=True,
                        method_used=InjectMethod.UNICODE,
                        chars_injected=2,
                    ),
                )
                return STTResult(text="E2E", language="ko", provider_id="mock"), artifact

            with patch(
                "app.session.session_manager.run_batch_pipeline",
                side_effect=pipeline_side_effect,
            ):
                press(backend, VK_CTRL)
                press(backend, VK_SPACE)
                release(backend, VK_SPACE)

                deadline = time.time() + 2.0
                while time.time() < deadline:
                    if SessionStatus.DONE in states:
                        break
                    time.sleep(0.02)

            assert SessionStatus.RECORDING in states
            assert SessionStatus.PROCESSING in states
            assert SessionStatus.DONE in states

            runtime.hotkey.close()
            runtime.sessions.close()
            config.close()


def test_hotkey_cancel_during_processing(tmp_path) -> None:
    config = Config.open(tmp_path / "cancel_proc.db", migrate_backup=False)
    backend = MockKeyboardBackend()
    hotkey = HotkeyManager(backend=backend)
    hotkey.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    hotkey.register(
        HotkeyBinding(id="cancel", keys="escape", action=HotkeyAction.CANCEL)
    )
    hotkey.start()

    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle
    capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01")

    manager = SessionManager(config, capture)
    manager.wire_hotkey(hotkey)

    states: list[SessionStatus] = []
    manager.on_session_state(lambda _sid, status: states.append(status))

    started = __import__("threading").Event()

    def slow_pipeline(*_args, **_kwargs):
        started.set()
        time.sleep(0.2)
        from app.session.types import SessionArtifact

        sid = _args[1]
        artifact = SessionArtifact(session_id=sid, stage=1, text="x", language="ko")
        return STTResult(text="x", language="ko"), artifact

    with patch("app.session.session_manager.run_batch_pipeline", side_effect=slow_pipeline):
        press(backend, VK_CTRL)
        press(backend, VK_SPACE)
        release(backend, VK_SPACE)

        assert started.wait(timeout=2.0)
        press(backend, 0x1B)  # escape
        time.sleep(0.35)

    assert SessionStatus.CANCELED in states
    assert SessionStatus.DONE not in states

    hotkey.close()
    manager.close()
    config.close()
