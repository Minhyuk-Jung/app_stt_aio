"""Audio capture (C1)."""

from core.audio.audio_capture import AudioCapture, CaptureState, RecordingHandle
from core.audio.device import DeviceInfo
from core.audio.errors import (
    AudioError,
    CaptureBusyError,
    CaptureStateError,
    DeviceAccessError,
    DeviceNotFoundError,
    MaxDurationExceededError,
    ResampleError,
)
from core.audio.format import STANDARD_SAMPLE_RATE, AudioBuffer
from core.audio.settings import AudioSettings

__all__ = [
    "STANDARD_SAMPLE_RATE",
    "AudioBuffer",
    "AudioCapture",
    "AudioError",
    "AudioSettings",
    "CaptureBusyError",
    "CaptureState",
    "CaptureStateError",
    "DeviceAccessError",
    "DeviceInfo",
    "DeviceNotFoundError",
    "MaxDurationExceededError",
    "RecordingHandle",
    "ResampleError",
]
