"""Capture -> Pipeline bridge (C10/C4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.audio.format import AudioBuffer
from core.pipeline import PipelineInput, PipelineStatus
from core.pipeline.convert import (
    require_stage1,
    stage_to_session_artifact,
    stage_to_stt_result,
)
from core.pipeline.errors import PipelineCanceledError
from core.pipeline.mode_resolve import resolve_mode_for_session
from core.store.models import SessionSource

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.config.config import Config
    from app.session.types import SessionArtifact
    from core.stt.types import STTResult

    CancelCheck = Callable[[], bool]


def run_batch_pipeline(
    config: Config,
    session_id: str,
    audio: AudioBuffer,
    *,
    press_enter: bool = False,
    inject_method: str | None = None,
    is_canceled: CancelCheck | None = None,
) -> tuple[STTResult, SessionArtifact]:
    """Run P1 batch path via bound C4 Pipeline (compat wrapper for C10)."""
    if config._pipeline is None:
        config.bind_pipeline()

    mode = resolve_mode_for_session(config, session_id)
    run = config.pipeline.run(
        PipelineInput(
            source=SessionSource.BATCH,
            audio=audio,
            session_id=session_id,
            press_enter=press_enter,
            inject_method=inject_method,
        ),
        mode,
        is_canceled=is_canceled,
    )

    if run.status is PipelineStatus.CANCELED:
        raise PipelineCanceledError(f"session {session_id} canceled")
    if run.status is PipelineStatus.ERROR:
        raise RuntimeError(run.error or "pipeline failed")

    stage = require_stage1(run)
    return stage_to_stt_result(stage), stage_to_session_artifact(stage)
