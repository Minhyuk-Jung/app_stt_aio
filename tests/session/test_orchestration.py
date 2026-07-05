"""Tests for orchestration -> pipeline bridge."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.session.orchestration import run_batch_pipeline
from app.session.types import SessionArtifact
from core.audio.format import AudioBuffer
from core.pipeline.errors import PipelineCanceledError
from core.pipeline.types import PipelineRun, PipelineStatus, StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource


def test_run_batch_pipeline_raises_on_cancel(tmp_path) -> None:
    config = Config.open(tmp_path / "orch_cancel.db", migrate_backup=False)
    config.bind_pipeline()
    session = config._store.sessions.create(source=SessionSource.BATCH)

    canceled_run = PipelineRun(session_id=session.id, status=PipelineStatus.CANCELED)

    with patch.object(config.pipeline, "run", return_value=canceled_run):
        with pytest.raises(PipelineCanceledError):
            run_batch_pipeline(config, session.id, AudioBuffer(pcm_bytes=b"\x00\x01"))

    config.close()


def test_run_batch_pipeline_passes_press_enter(tmp_path) -> None:
    config = Config.open(tmp_path / "orch_enter.db", migrate_backup=False)
    config.bind_pipeline()
    session = config._store.sessions.create(source=SessionSource.BATCH)

    finished = PipelineRun(
        session_id=session.id,
        status=PipelineStatus.FINISHED,
        artifacts={
            1: StageArtifact(
                session_id=session.id,
                stage=1,
                text="ok",
                language="ko",
            )
        },
    )

    with patch.object(config.pipeline, "run", return_value=finished) as mock_run:
        stt, artifact = run_batch_pipeline(
            config,
            session.id,
            AudioBuffer(pcm_bytes=b"\x00\x01"),
            press_enter=True,
        )

    assert stt.text == "ok"
    assert artifact.text == "ok"
    assert mock_run.call_args.kwargs["is_canceled"] is None
    pipeline_input = mock_run.call_args.args[0]
    assert pipeline_input.press_enter is True

    config.close()


def test_run_batch_pipeline_raises_on_error_without_stage1(tmp_path) -> None:
    config = Config.open(tmp_path / "orch_error.db", migrate_backup=False)
    config.bind_pipeline()
    session = config._store.sessions.create(source=SessionSource.BATCH)

    failed = PipelineRun(
        session_id=session.id,
        status=PipelineStatus.ERROR,
        error="stt failed",
    )

    with patch.object(config.pipeline, "run", return_value=failed):
        with pytest.raises(RuntimeError, match="stt failed"):
            run_batch_pipeline(config, session.id, AudioBuffer(pcm_bytes=b"\x00\x01"))

    config.close()


def test_run_batch_pipeline_forwards_cancel_check(tmp_path) -> None:
    config = Config.open(tmp_path / "orch_forward.db", migrate_backup=False)
    config.bind_pipeline()
    session = config._store.sessions.create(source=SessionSource.BATCH)

    canceled_run = PipelineRun(session_id=session.id, status=PipelineStatus.CANCELED)
    cancel_check = lambda: True

    with patch.object(config.pipeline, "run", return_value=canceled_run) as mock_run:
        with pytest.raises(PipelineCanceledError):
            run_batch_pipeline(
                config,
                session.id,
                AudioBuffer(pcm_bytes=b"\x00\x01"),
                is_canceled=cancel_check,
            )

    assert mock_run.call_args.kwargs["is_canceled"] is cancel_check

    config.close()
