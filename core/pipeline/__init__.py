"""Pipeline orchestration package (C4)."""

from core.pipeline.errors import (
    PipelineCanceledError,
    PipelineError,
    PipelineNotImplementedError,
)
from core.pipeline.event_bus import PipelineEventBus
from core.pipeline.pipeline import Pipeline
from core.pipeline.queue import PipelineQueue
from core.pipeline.types import (
    DEFAULT_BATCH_MODE,
    Mode,
    PipelineInput,
    PipelineMode,
    PipelineRun,
    PipelineStatus,
    StageArtifact,
)

__all__ = [
    "DEFAULT_BATCH_MODE",
    "Mode",
    "Pipeline",
    "PipelineCanceledError",
    "PipelineError",
    "PipelineEventBus",
    "PipelineInput",
    "PipelineMode",
    "PipelineNotImplementedError",
    "PipelineQueue",
    "PipelineRun",
    "PipelineStatus",
    "StageArtifact",
]
