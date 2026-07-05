"""Pipeline event dispatch helpers (C4)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from core.pipeline.events import (
    InjectRequestedCallback,
    PipelineErrorCallback,
    PipelineFinishedCallback,
    StageCallback,
    StageCompletedCallback,
)
from core.pipeline.types import PipelineRun, StageArtifact

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PipelineEventBus:
    """Collect and emit pipeline lifecycle callbacks."""

    def __init__(self) -> None:
        self._stage_started: list[StageCallback] = []
        self._stage_completed: list[StageCompletedCallback] = []
        self._inject_requested: list[InjectRequestedCallback] = []
        self._pipeline_error: list[PipelineErrorCallback] = []
        self._pipeline_finished: list[PipelineFinishedCallback] = []

    def on_stage_started(self, callback: StageCallback) -> None:
        self._stage_started.append(callback)

    def on_stage_completed(self, callback: StageCompletedCallback) -> None:
        self._stage_completed.append(callback)

    def on_inject_requested(self, callback: InjectRequestedCallback) -> None:
        self._inject_requested.append(callback)

    def on_pipeline_error(self, callback: PipelineErrorCallback) -> None:
        self._pipeline_error.append(callback)

    def on_pipeline_finished(self, callback: PipelineFinishedCallback) -> None:
        self._pipeline_finished.append(callback)

    def emit_stage_started(self, stage: int) -> None:
        self._emit_all(self._stage_started, stage)

    def emit_stage_completed(self, stage: int, artifact: StageArtifact) -> None:
        self._emit_all(self._stage_completed, stage, artifact)

    def emit_inject_requested(self, artifact: StageArtifact) -> None:
        self._emit_all(self._inject_requested, artifact)

    def emit_pipeline_error(self, stage: int, error: Exception) -> None:
        self._emit_all(self._pipeline_error, stage, error)

    def emit_pipeline_finished(self, run: PipelineRun) -> None:
        self._emit_all(self._pipeline_finished, run)

    @staticmethod
    def _emit_all(callbacks: list[Callable[..., None]], *args) -> None:
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:
                logger.exception("Pipeline callback failed")
