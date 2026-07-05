"""AudioCapture facade: device selection and batch capture (P1)."""

from __future__ import annotations

from enum import Enum
from typing import Callable

from core.audio.capture_batch import BatchCapture, BatchRecording
from core.audio.device import DeviceInfo, list_devices, resolve_device_id, validate_device
from core.audio.errors import AudioError, CaptureBusyError, CaptureStateError, DeviceAccessError, MaxDurationExceededError
from core.audio.format import AudioBuffer
from core.audio.settings import AudioSettings

ErrorCallback = Callable[[AudioError], None]
LevelCallback = Callable[[float, float], None]
SegmentCallback = Callable[[AudioBuffer, bool], None]


class CaptureState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STREAMING = "streaming"
    ERROR = "error"


RecordingHandle = BatchRecording
StreamHandle = object


class AudioCapture:
    """Microphone capture facade for batch mode (P1)."""

    def __init__(self, on_error: ErrorCallback | None = None) -> None:
        self._on_error = on_error
        self._device_id: int | None = None
        self._max_batch_duration_ms: int | None = None
        self._state = CaptureState.IDLE
        self._batch = BatchCapture(on_error=self._forward_error)
        self._level_callback: LevelCallback | None = None
        self._stream_capture = None
        self._stream_handle = None
        self._audio_settings = AudioSettings()

    @property
    def state(self) -> CaptureState:
        return self._state

    def list_devices(self) -> list[DeviceInfo]:
        return list_devices()

    def select_device(self, device_id: str | int | None) -> int | None:
        resolved = resolve_device_id(device_id)
        self._device_id = validate_device(resolved)
        return self._device_id

    def apply_settings(self, settings: AudioSettings) -> None:
        if self._state == CaptureState.RECORDING:
            raise CaptureStateError("cannot change audio settings while recording")
        self._audio_settings = settings
        self.select_device(settings.device_id or None)
        self._max_batch_duration_ms = settings.max_segment_ms

    def set_level_callback(self, callback: LevelCallback | None) -> None:
        self._level_callback = callback

    def set_error_callback(self, callback: ErrorCallback | None) -> None:
        self._on_error = callback

    def reset(self) -> None:
        """Recover from error state back to idle (plan: error → idle)."""
        self._batch.force_reset()
        self._state = CaptureState.IDLE

    def start_batch(self) -> RecordingHandle:
        if self._state == CaptureState.ERROR:
            raise CaptureStateError(
                "capture is in error state; call reset() before starting again"
            )
        if self._state != CaptureState.IDLE:
            raise CaptureBusyError(f"cannot start batch capture in state: {self._state}")
        try:
            handle = self._batch.start(
                self._device_id,
                max_duration_ms=self._max_batch_duration_ms,
                on_level=self._level_callback,
            )
        except AudioError:
            self._state = CaptureState.ERROR
            raise
        self._state = CaptureState.RECORDING
        return handle

    def stop_batch(self, handle: RecordingHandle) -> AudioBuffer:
        if self._state == CaptureState.ERROR and self._batch.is_active:
            try:
                buffer = self._batch.stop(handle)
            except AudioError:
                raise
            self._state = CaptureState.IDLE
            return buffer
        if self._state != CaptureState.RECORDING:
            raise CaptureStateError(f"cannot stop batch capture in state: {self._state}")
        try:
            buffer = self._batch.stop(handle)
        except AudioError:
            self._state = CaptureState.ERROR
            raise
        self._state = CaptureState.IDLE
        return buffer

    def cancel(self, handle: RecordingHandle) -> None:
        if self._state == CaptureState.ERROR and self._batch.is_active:
            self._batch.cancel(handle)
            self._state = CaptureState.IDLE
            return
        if self._state not in (CaptureState.RECORDING, CaptureState.STREAMING):
            raise CaptureStateError(f"cannot cancel capture in state: {self._state}")
        self._batch.cancel(handle)
        self._state = CaptureState.IDLE

    def start_stream(
        self,
        on_segment: SegmentCallback,
        on_level: LevelCallback | None = None,
    ) -> StreamHandle:
        if self._state == CaptureState.ERROR:
            raise CaptureStateError(
                "capture is in error state; call reset() before starting again"
            )
        if self._state != CaptureState.IDLE:
            raise CaptureBusyError(f"cannot start stream capture in state: {self._state}")
        from core.audio.stream_capture import StreamCapture

        self._stream_capture = StreamCapture(
            device_id=self._device_id,
            vad_engine=self._audio_settings.vad_engine,
            vad_threshold=self._audio_settings.vad_threshold,
            min_speech_ms=self._audio_settings.min_speech_ms,
            hangover_ms=self._audio_settings.hangover_ms,
            max_segment_ms=self._audio_settings.max_segment_ms,
            on_segment=on_segment,
            on_level=on_level or self._level_callback,
            on_error=self._forward_error,
        )
        self._stream_handle = self._stream_capture.start()
        self._state = CaptureState.STREAMING
        return self._stream_handle

    def stop_stream(self, handle: StreamHandle) -> None:
        if self._state != CaptureState.STREAMING:
            raise CaptureStateError(f"cannot stop stream capture in state: {self._state}")
        if self._stream_capture is None or self._stream_handle is None:
            raise CaptureStateError("no active stream handle")
        if getattr(handle, "stream_id", None) != getattr(self._stream_handle, "stream_id", None):
            raise CaptureStateError("unknown stream handle")
        self._stream_capture.stop(handle)
        self._stream_capture = None
        self._stream_handle = None
        self._state = CaptureState.IDLE

    def _forward_error(self, error: Exception) -> None:
        if isinstance(error, MaxDurationExceededError):
            if self._on_error:
                self._on_error(error)
            return
        self._state = CaptureState.ERROR
        if not self._on_error:
            return
        if isinstance(error, AudioError):
            self._on_error(error)
        else:
            self._on_error(DeviceAccessError(str(error)))
