"""Pipeline domain types (C4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from core.audio.format import AudioBuffer
from core.inject.types import InjectResult
from core.store.models import SessionSource

if TYPE_CHECKING:
    pass


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass(frozen=True)
class PipelineMode:
    """Mode routing contract (P1 default: stage1 only)."""

    id: str | None
    target_stage: int = 1
    inject_stage: int = 1


DEFAULT_BATCH_MODE = PipelineMode(id=None, target_stage=1, inject_stage=1)

# Plan section 3 public contract alias.
Mode = PipelineMode


@dataclass(frozen=True)
class PipelineInput:
    source: SessionSource
    audio: AudioBuffer | None = None
    seed_text: str | None = None
    session_id: str | None = None
    press_enter: bool = False
    inject_method: str | None = None


@dataclass
class StageArtifact:
    session_id: str
    stage: int
    text: str
    language: str
    provider: str | None = None
    inject_result: InjectResult | None = None


@dataclass
class PipelineRun:
    session_id: str
    artifacts: dict[int, StageArtifact] = field(default_factory=dict)
    status: PipelineStatus = PipelineStatus.PENDING
    error_stage: int | None = None
    error: str | None = None
