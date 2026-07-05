"""Shared STT data types (C2 contract)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class CostType(str, Enum):
    FREE = "free"
    LOCAL = "local"
    PAID = "paid"


class ProviderState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    BUSY = "busy"


@dataclass(frozen=True)
class STTCapabilities:
    supports_streaming: bool
    languages: tuple[str, ...]
    max_audio_sec: int
    needs_network: bool
    cost_type: CostType
    gpu_optional: bool


@dataclass
class STTOptions:
    language: str = "ko"
    initial_prompt: str = ""
    hotwords: tuple[str, ...] = ()
    beam_size: int = 5
    temperature: float = 0.0
    task: str = "transcribe"


@dataclass(frozen=True)
class STTSegmentResult:
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class STTSegment:
    text: str
    is_final: bool
    start_ms: int
    end_ms: int


@dataclass
class STTResult:
    text: str
    language: str
    segments: list[STTSegmentResult] = field(default_factory=list)
    duration_ms: int = 0
    provider_id: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


STTChunkIterator = Iterator[bytes]
