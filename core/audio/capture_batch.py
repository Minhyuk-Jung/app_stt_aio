"""Non-blocking batch (push-to-talk) microphone capture."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import sounddevice as sd

from core.audio.device import open_input_stream_kwargs, validate_device
from core.audio.errors import (
    CaptureStateError,
    DeviceAccessError,
    MaxDurationExceededError,
    ResampleError,
)
from core.audio.format import AudioBuffer
from core.audio.level import compute_peak_rms
from core.audio.resample import build_audio_buffer

ErrorCallback = Callable[[Exception], None]
LevelCallback = Callable[[float, float], None]


@dataclass
class BatchRecording:
    handle_id: int
    device_id: int | None
    stream_channels: int
    sample_rate: int
    max_duration_ms: int | None = None
    _chunks: list[bytes] = field(default_factory=list)
    _stream: sd.InputStream | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _closed: bool = False
    _duration_exceeded: bool = False

    def append_chunk(self, chunk: bytes) -> bool:
        with self._lock:
            if self._closed:
                return False
            if self._duration_exceeded:
                return False
            self._chunks.append(chunk)
            if self.max_duration_ms is not None and self._current_duration_ms() > self.max_duration_ms:
                self._duration_exceeded = True
                return False
            return True

    def _current_duration_ms(self) -> int:
        frame_bytes = 2 * self.stream_channels
        if frame_bytes <= 0:
            return 0
        frames = sum(len(chunk) // frame_bytes for chunk in self._chunks)
        return int(frames * 1000 / self.sample_rate)

    @property
    def duration_exceeded(self) -> bool:
        with self._lock:
            return self._duration_exceeded

    def discard(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._closed = True

    def finalize(self) -> AudioBuffer:
        with self._lock:
            if self._closed:
                raise CaptureStateError("recording already finalized")
            self._closed = True
            pcm = b"".join(self._chunks)
            self._chunks.clear()
        try:
            return build_audio_buffer(
                pcm,
                sample_rate=self.sample_rate,
                channels=self.stream_channels,
            )
        except ResampleError as exc:
            raise CaptureStateError(str(exc)) from exc


class BatchCapture:
    """Accumulates microphone frames until stop_batch or cancel."""

    def __init__(self, on_error: ErrorCallback | None = None) -> None:
        self._on_error = on_error
        self._next_handle_id = 1
        self._active: BatchRecording | None = None

    @property
    def is_active(self) -> bool:
        return self._active is not None

    def start(
        self,
        device_id: int | None,
        *,
        max_duration_ms: int | None = None,
        on_level: LevelCallback | None = None,
    ) -> BatchRecording:
        if self._active is not None:
            raise CaptureStateError("batch capture already active")

        resolved = validate_device(device_id)
        try:
            stream_kwargs = open_input_stream_kwargs(resolved)
        except (DeviceAccessError, CaptureStateError):
            raise
        except Exception as exc:
            raise DeviceAccessError(str(exc)) from exc

        recording = BatchRecording(
            handle_id=self._next_handle_id,
            device_id=resolved,
            stream_channels=stream_kwargs["channels"],
            sample_rate=stream_kwargs["samplerate"],
            max_duration_ms=max_duration_ms,
        )
        self._next_handle_id += 1

        def callback(indata, frames, time_info, status) -> None:  # noqa: ANN001, ARG001
            if status:
                self._emit_error(DeviceAccessError(str(status)))
            if on_level is not None:
                peak, rms = compute_peak_rms(indata.tobytes())
                on_level(peak, rms)
            if not recording.append_chunk(indata.copy().tobytes()):
                if recording.duration_exceeded:
                    self._emit_error(
                        MaxDurationExceededError(
                            f"batch recording exceeded {max_duration_ms}ms limit"
                        )
                    )
                    self._close_stream(recording)

        try:
            stream = sd.InputStream(callback=callback, **stream_kwargs)
            stream.start()
        except sd.PortAudioError as exc:
            raise DeviceAccessError(str(exc)) from exc

        recording._stream = stream
        self._active = recording
        return recording

    def stop(self, handle: BatchRecording) -> AudioBuffer:
        recording = self._require_handle(handle)
        self._close_stream(recording)
        self._active = None
        return recording.finalize()

    def cancel(self, handle: BatchRecording) -> None:
        recording = self._require_handle(handle)
        self._close_stream(recording)
        recording.discard()
        self._active = None

    def force_reset(self) -> None:
        """Discard any active recording without requiring a valid facade state."""
        if self._active is None:
            return
        recording = self._active
        self._close_stream(recording)
        recording.discard()
        self._active = None

    def _require_handle(self, handle: BatchRecording) -> BatchRecording:
        if self._active is None or self._active.handle_id != handle.handle_id:
            raise CaptureStateError("unknown or inactive recording handle")
        return self._active

    def _close_stream(self, recording: BatchRecording) -> None:
        stream = recording._stream
        if stream is None:
            return
        try:
            stream.stop()
        finally:
            stream.close()
            recording._stream = None

    def _emit_error(self, error: Exception) -> None:
        if self._on_error:
            self._on_error(error)


def generate_test_tone(
    *,
    frequency_hz: float = 440.0,
    duration_ms: int = 500,
    sample_rate: int = 48000,
    channels: int = 1,
) -> bytes:
    """Synthesize PCM for unit tests without a microphone."""
    frame_count = int(sample_rate * duration_ms / 1000)
    time_axis = np.arange(frame_count, dtype=np.float64) / sample_rate
    wave = (0.5 * np.sin(2 * np.pi * frequency_hz * time_axis) * np.iinfo(np.int16).max)
    samples = wave.astype(np.int16)
    if channels > 1:
        samples = np.column_stack([samples] * channels).reshape(-1)
    return samples.tobytes()
