"""Convert pipeline artifacts to session-layer types."""

from __future__ import annotations

from app.session.types import SessionArtifact
from core.pipeline.types import PipelineRun, StageArtifact
from core.stt.types import STTResult


def stage_to_session_artifact(stage: StageArtifact) -> SessionArtifact:
    return SessionArtifact(
        session_id=stage.session_id,
        stage=stage.stage,
        text=stage.text,
        language=stage.language,
        inject_result=stage.inject_result,
    )


def stage_to_stt_result(stage: StageArtifact) -> STTResult:
    return STTResult(
        text=stage.text,
        language=stage.language,
        provider_id=stage.provider or "",
    )


def require_stage1(run: PipelineRun) -> StageArtifact:
    stage = run.artifacts.get(1)
    if stage is None:
        raise RuntimeError(run.error or "pipeline stage1 artifact missing")
    return stage
