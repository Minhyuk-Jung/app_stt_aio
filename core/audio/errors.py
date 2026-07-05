"""Audio capture error types."""

from __future__ import annotations


class AudioError(Exception):
    """Base error for audio capture operations."""


class DeviceNotFoundError(AudioError):
    """Requested input device does not exist."""


class DeviceAccessError(AudioError):
    """Microphone access was denied or the device is unavailable."""


class CaptureBusyError(AudioError):
    """Another capture session is already active."""


class CaptureStateError(AudioError):
    """Operation is invalid for the current capture state."""


class ResampleError(AudioError):
    """Failed to convert audio to the standard format."""


class MaxDurationExceededError(AudioError):
    """Batch recording exceeded configured maximum duration."""
