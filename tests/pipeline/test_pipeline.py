"""Tests for C4 Pipeline (P1 stage1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import Config
from core.audio.format import AudioBuffer
from core.inject.types import InjectMethod, InjectResult
from core.pipeline import (
    DEFAULT_BATCH_MODE,
    Pipeline,
    PipelineInput,
    PipelineNotImplementedError,
    PipelineStatus,
    StageArtifact,
)
from core.stt.types import STTResult
from core.store.models import SessionSource


def _bind_mock_llm(config) -> None:
    from core.llm import MockLLMProvider

    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()


@pytest.fixture
def pipeline_env(tmp_path):
    config = Config.open(tmp_path / "pipeline.db", migrate_backup=False)
    session = config._store.sessions.create(source=SessionSource.BATCH)
    pipeline = Pipeline(config)
    yield config, pipeline, session.id
    config.close()


def test_run_stage1_transcribes_injects_and_persists(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    events: list[str] = []
    pipeline.on_stage_started(lambda stage: events.append(f"start:{stage}"))
    pipeline.on_stage_completed(lambda stage, _artifact: events.append(f"done:{stage}"))
    pipeline.on_inject_requested(lambda _artifact: events.append("inject"))
    pipeline.on_pipeline_finished(lambda run: events.append(f"finish:{run.status.value}"))

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="안녕", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="안녕",
                language="ko",
                provider="mock",
            ),
        )
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=2,
            )
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                    session_id=session_id,
                ),
                DEFAULT_BATCH_MODE,
            )

    assert run.status is PipelineStatus.FINISHED
    assert run.artifacts[1].text == "안녕"
    assert run.artifacts[1].inject_result is not None
    assert events == ["start:1", "done:1", "inject", "finish:finished"]

    stored = config._store.artifacts.latest_by_stage(session_id, 1)
    assert stored is not None
    assert stored.text == "안녕"


def test_run_empty_transcript_skips_inject_chars(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="  ", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="  ",
                language="ko",
                provider="mock",
            ),
        )
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b""),
                    session_id=session_id,
                )
            )

    assert run.status is PipelineStatus.FINISHED
    mock_inject.assert_not_called()
    assert run.artifacts[1].inject_result.chars_injected == 0


def test_run_honors_cancel_check(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    canceled = {"value": False}

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="취소", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="취소",
                language="ko",
                provider="mock",
            ),
        )

        def cancel_after_stage1() -> bool:
            if mock_stage1.called:
                canceled["value"] = True
            return canceled["value"]

        inject_calls: list[str] = []
        pipeline.on_inject_requested(
            lambda artifact: inject_calls.append(artifact.text)
        )

        run = pipeline.run(
            PipelineInput(
                source=SessionSource.BATCH,
                audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                session_id=session_id,
            ),
            is_canceled=cancel_after_stage1,
        )

    assert run.status is PipelineStatus.CANCELED
    assert inject_calls == []


def test_run_emits_pipeline_error_on_stage_failure(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    errors: list[tuple[int, str]] = []
    pipeline.on_pipeline_error(
        lambda stage, error: errors.append((stage, str(error)))
    )

    with patch("core.pipeline.pipeline.run_stage1", side_effect=RuntimeError("stt down")):
        run = pipeline.run(
            PipelineInput(
                source=SessionSource.BATCH,
                audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                session_id=session_id,
            )
        )

    assert run.status is PipelineStatus.ERROR
    assert errors == [(1, "stt down")]
    assert config._store.artifacts.get_by_session(session_id) == []


def test_reprocess_from_stage2(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    from core.pipeline.types import PipelineMode

    _bind_mock_llm(config)
    config._store.artifacts.add(session_id, 1, "원문", provider="mock")

    with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
        mock_stage2.return_value = (
            StageArtifact(
                session_id=session_id,
                stage=2,
                text="교정됨",
                language="ko",
                provider="mock",
            ),
            "prompt",
        )
        run = pipeline.reprocess(session_id, from_stage=2, mode=PipelineMode(id="m", target_stage=2))

    assert run.status is PipelineStatus.FINISHED
    assert run.artifacts[2].text == "교정됨"


def test_reprocess_from_stage1_requires_audio(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    config._store.artifacts.add(session_id, 1, "원문", provider="mock")
    run = pipeline.reprocess(session_id, from_stage=1)
    assert run.status is PipelineStatus.ERROR


def test_target_stage_two_runs_stage2(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    from core.pipeline.types import PipelineMode

    _bind_mock_llm(config)

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="안녕", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="안녕",
                language="ko",
                provider="mock",
            ),
        )
        with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
            mock_stage2.return_value = (
                StageArtifact(
                    session_id=session_id,
                    stage=2,
                    text="다듬임",
                    language="ko",
                    provider="mock",
                ),
                "prompt",
            )
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                    session_id=session_id,
                ),
                PipelineMode(id="mode", target_stage=2, inject_stage=1),
            )

    assert run.status is PipelineStatus.FINISHED
    assert run.artifacts[2].text == "다듬임"
    stored = config._store.artifacts.latest_by_stage(session_id, 1)
    assert stored is not None


def test_inject_stage_not_one_skips_inject(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    from core.pipeline.types import PipelineMode

    inject_events: list[str] = []
    pipeline.on_inject_requested(lambda artifact: inject_events.append(artifact.text))

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="안녕", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="안녕",
                language="ko",
                provider="mock",
            ),
        )
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                    session_id=session_id,
                ),
                PipelineMode(id="mode", target_stage=1, inject_stage=2),
            )

    assert run.status is PipelineStatus.FINISHED
    mock_inject.assert_not_called()
    assert inject_events == []
    assert run.artifacts[1].inject_result is None


def test_shared_queue_serializes_concurrent_runs(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env
    from core.pipeline.queue import PipelineQueue

    order: list[str] = []
    gate = __import__("threading").Event()

    def stage1_side_effect(_config, _audio, sid: str):
        order.append(f"start:{sid}")
        gate.wait(timeout=2.0)
        order.append(f"end:{sid}")
        return (
            STTResult(text="ok", language="ko", provider_id="mock"),
            StageArtifact(session_id=sid, stage=1, text="ok", language="ko"),
        )

    second = config._store.sessions.create(source=SessionSource.BATCH)
    with patch("core.pipeline.pipeline.run_stage1", side_effect=stage1_side_effect):
        import threading

        results: list = []

        def run_one(sid: str) -> None:
            results.append(
                pipeline.run(
                    PipelineInput(
                        source=SessionSource.BATCH,
                        audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                        session_id=sid,
                    )
                ).status
            )

        first_thread = threading.Thread(target=run_one, args=(session_id,))
        second_thread = threading.Thread(target=run_one, args=(second.id,))

        first_thread.start()
        __import__("time").sleep(0.05)
        second_thread.start()
        __import__("time").sleep(0.05)
        gate.set()
        first_thread.join(timeout=3.0)
        gate.set()
        second_thread.join(timeout=3.0)

    assert order.index(f"end:{session_id}") < order.index(f"start:{second.id}")
    assert results == [PipelineStatus.FINISHED, PipelineStatus.FINISHED]


def test_config_bind_pipeline_reuses_queue(tmp_path) -> None:
    config = Config.open(tmp_path / "bind_pipeline.db", migrate_backup=False)
    first = config.bind_pipeline()
    second = config.bind_pipeline()
    assert first is second
    assert first.queue is second.queue
    config.close()


def test_cancel_before_stage1_skips_persist(pipeline_env) -> None:
    config, pipeline, session_id = pipeline_env

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        run = pipeline.run(
            PipelineInput(
                source=SessionSource.BATCH,
                audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                session_id=session_id,
            ),
            is_canceled=lambda: True,
        )

    mock_stage1.assert_not_called()
    assert run.status is PipelineStatus.CANCELED
    assert config._store.artifacts.get_by_session(session_id) == []


def test_resolve_mode_uses_session_mode_id(pipeline_env) -> None:
    config, _pipeline, session_id = pipeline_env
    from core.pipeline.mode_resolve import resolve_mode_for_session

    config._store.sessions.update_mode_id(session_id, "polish")
    mode = resolve_mode_for_session(config, session_id)

    assert mode.id == "polish"
    assert mode.target_stage == 2
    assert mode.inject_stage == 2
