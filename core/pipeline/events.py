"""Pipeline event callbacks (C4)."""

from __future__ import annotations

from collections.abc import Callable

from core.pipeline.types import PipelineRun, StageArtifact

StageCallback = Callable[[int], None]
StageCompletedCallback = Callable[[int, StageArtifact], None]
InjectRequestedCallback = Callable[[StageArtifact], None]
PipelineErrorCallback = Callable[[int, Exception], None]
PipelineFinishedCallback = Callable[[PipelineRun], None]
