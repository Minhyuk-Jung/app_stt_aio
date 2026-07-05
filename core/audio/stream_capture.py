"""Energy / Silero streaming capture with VAD (C1 P2)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

import sounddevice as sd

from core.audio.device import open_input_stream_kwargs, validate_device
from core.audio.errors import DeviceAccessError
from core.audio.format import AudioBuffer
from core.audio.level import compute_peak_rms
from core.audio.resample import to_standard_pcm
from core.audio.vad import SegmentTracker, create_speech_detector

SegmentCallback = Callable[[AudioBuffer, bool], None]
LevelCallback = Callable[[float, float], None]


@dataclass
class StreamRecording:
    stream_id: int


class StreamCapture:
    """Streaming capture with pluggable VAD (energy or Silero)."""

    def __init__(
        self,
        *,
        device_id: int | None,
        vad_engine: str = "energy",
        vad_threshold: float = 0.5,
        min_speech_ms: int = 250,
        hangover_ms: int = 500,
        max_segment_ms: int = 0,
        on_segment: SegmentCallback,
        on_level: LevelCallback | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._device_id = device_id
        self._on_segment = on_segment
        self._on_level = on_level
        self._on_error = on_error
        self._stream: sd.InputStream | None = None
        self._stop = threading.Event()
        self._stream_id = 0
        self._frame_ms = 30
        self._source_sample_rate = 16_000
        self._source_channels = 1
        self._detector = create_speech_detector(vad_engine, threshold=vad_threshold)
        self._tracker = SegmentTracker(
            min_speech_ms=min_speech_ms,
            hangover_ms=hangover_ms,
            max_segment_ms=max_segment_ms,
            frame_ms=self._frame_ms,
        )

    def start(self) -> StreamRecording:
        self._stream_id += 1
        self._stop.clear()
        self._detector.reset()
        self._tracker.reset()
        resolved = validate_device(self._device_id)
        try:
            stream_kwargs = open_input_stream_kwargs(resolved)
            self._source_sample_rate = int(stream_kwargs["samplerate"])
            self._source_channels = int(stream_kwargs["channels"])
            blocksize = max(1, int(self._source_sample_rate * self._frame_ms / 1000))
            self._stream = sd.InputStream(
                callback=self._callback,
                blocksize=blocksize,
                **stream_kwargs,
            )
            self._stream.start()
        except sd.PortAudioError as exc:
            raise DeviceAccessError(str(exc)) from exc
        return StreamRecording(stream_id=self._stream_id)

    def stop(self, handle: StreamRecording) -> None:
        del handle
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
            finally:
                self._stream.close()
                self._stream = None
        self._flush_segment(force=True)

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001, ARG001
        if self._stop.is_set():
            return
        chunk = indata.copy().tobytes()
        try:
            standard_pcm = to_standard_pcm(
                chunk,
                sample_rate=self._source_sample_rate,
                channels=self._source_channels,
            )
        except Exception as exc:  # noqa: BLE001
            if self._on_error is not None:
                self._on_error(exc)
            return
        peak, rms = compute_peak_rms(standard_pcm)
        if self._on_level is not None:
            self._on_level(peak, rms)
        is_speech = self._detector.is_speech(standard_pcm)
        completed = self._tracker.feed(standard_pcm, is_speech)
        if completed:
            self._emit_pcm(completed)

    def _flush_segment(self, *, force: bool = False) -> None:
        completed = self._tracker.flush(force=force)
        if completed:
            self._emit_pcm(completed)

    def _emit_pcm(self, pcm: bytes) -> None:
        if not pcm:
            return
        buffer = AudioBuffer(pcm_bytes=pcm)
        try:
            buffer.validate()
        except ValueError as exc:
            if self._on_error is not None:
                self._on_error(exc)
            return
        try:
            self._on_segment(buffer, True)
        except Exception as exc:  # noqa: BLE001
            if self._on_error is not None:
                self._on_error(exc)
