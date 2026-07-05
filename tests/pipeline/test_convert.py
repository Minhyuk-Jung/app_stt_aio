"""Tests for pipeline convert helpers."""

from __future__ import annotations

import pytest

from core.inject.types import InjectMethod, InjectResult
from core.pipeline.convert import (
    require_stage1,
    stage_to_session_artifact,
    stage_to_stt_result,
)
from core.pipeline.types import PipelineRun, PipelineStatus, StageArtifact


def test_stage_to_session_artifact_maps_fields() -> None:
    inject = InjectResult(success=True, method_used=InjectMethod.UNICODE, chars_injected=3)
    stage = StageArtifact(
        session_id="sid",
        stage=1,
        text="hello",
        language="ko",
        provider="mock",
        inject_result=inject,
    )

    artifact = stage_to_session_artifact(stage)

    assert artifact.session_id == "sid"
    assert artifact.text == "hello"
    assert artifact.inject_result is inject


def test_stage_to_stt_result_uses_provider_id() -> None:
    stage = StageArtifact(
        session_id="sid",
        stage=1,
        text="안녕",
        language="ko",
        provider="faster_whisper_local",
    )

    result = stage_to_stt_result(stage)

    assert result.text == "안녕"
    assert result.provider_id == "faster_whisper_local"


def test_require_stage1_raises_when_missing() -> None:
    run = PipelineRun(session_id="sid", status=PipelineStatus.ERROR, error="boom")

    with pytest.raises(RuntimeError, match="boom"):
        require_stage1(run)
