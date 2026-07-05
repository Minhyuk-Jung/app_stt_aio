"""STTProvider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from core.audio.format import AudioBuffer
from core.stt.types import (
    ProviderState,
    STTChunkIterator,
    STTCapabilities,
    STTOptions,
    STTResult,
    STTSegment,
)


class STTProvider(ABC):
    """Replaceable speech-to-text provider contract (C2)."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable provider identifier."""

    @property
    def state(self) -> ProviderState:
        """Provider lifecycle state (unloaded/loading/ready/busy)."""
        return ProviderState.READY

    @abstractmethod
    def capabilities(self) -> STTCapabilities:
        """Return supported features and constraints."""

    @abstractmethod
    def transcribe(
        self,
        audio: AudioBuffer,
        options: STTOptions | None = None,
    ) -> STTResult:
        """Batch transcription for a complete audio buffer."""

    def stream(
        self,
        audio_chunks: STTChunkIterator,
        options: STTOptions | None = None,
    ) -> Iterator[STTSegment]:
        raise NotImplementedError(
            f"{self.provider_id} does not support streaming transcription"
        )

    def warmup(self) -> None:
        """Pre-load models to reduce first-use latency."""

    def close(self) -> None:
        """Release provider resources."""

    def __enter__(self) -> STTProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
