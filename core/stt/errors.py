"""STT provider error types."""

from __future__ import annotations

__all__ = [
    "AudioFormatError",
    "AuthenticationError",
    "ModelLoadError",
    "ModelNotFoundError",
    "NetworkError",
    "ProviderBusyError",
    "ProviderNotFoundError",
    "STTError",
    "TranscriptionError",
]


class STTError(Exception):
    """Base error for STT operations."""


class ProviderNotFoundError(STTError):
    """Unknown or unsupported provider id."""


class ModelNotFoundError(STTError):
    """Local model path does not exist."""


class ModelLoadError(STTError):
    """Failed to load STT model."""


class AudioFormatError(STTError):
    """Audio buffer is not in a supported format."""


class AuthenticationError(STTError):
    """Cloud provider rejected credentials (no retry)."""


class NetworkError(STTError):
    """Network or timeout error talking to a cloud provider."""


class TranscriptionError(STTError):
    """Transcription failed at runtime."""


class ProviderBusyError(STTError):
    """Provider is already transcribing."""
