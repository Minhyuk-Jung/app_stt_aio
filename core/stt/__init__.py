"""Speech-to-text providers (C2)."""

from core.stt.base import STTProvider
from core.stt.errors import (
    AudioFormatError,
    AuthenticationError,
    ModelLoadError,
    ModelNotFoundError,
    NetworkError,
    ProviderBusyError,
    ProviderNotFoundError,
    STTError,
    TranscriptionError,
)
from core.stt.faster_whisper_local import FasterWhisperLocalProvider
from core.stt.registry import create_provider, registered_provider_ids, resolve_provider_id
from core.stt.types import (
    CostType,
    ProviderState,
    STTCapabilities,
    STTOptions,
    STTResult,
    STTSegment,
    STTSegmentResult,
)

__all__ = [
    "AudioFormatError",
    "AuthenticationError",
    "CostType",
    "FasterWhisperLocalProvider",
    "ModelLoadError",
    "ModelNotFoundError",
    "NetworkError",
    "ProviderBusyError",
    "ProviderNotFoundError",
    "ProviderState",
    "STTCapabilities",
    "STTError",
    "STTOptions",
    "STTProvider",
    "STTResult",
    "STTSegment",
    "STTSegmentResult",
    "TranscriptionError",
    "create_provider",
    "registered_provider_ids",
    "resolve_provider_id",
]
