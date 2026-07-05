"""StreamCapture resample/VAD integration tests (C1)."""

from __future__ import annotations

import numpy as np
import pytest

from core.audio.format import STANDARD_SAMPLE_RATE
from core.audio.stream_capture import StreamCapture, StreamRecording


class _FakeInputStream:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def close(self) -> None:
        return


def _chunk_48k(*, amplitude: float, frame_ms: int = 30) -> np.ndarray:
    frames = int(48_000 * frame_ms / 1000)
    t = np.arange(frames, dtype=np.float32) / 48_000
    wave = (np.sin(2 * np.pi * 440 * t) * amplitude * 32767).astype(np.int16)
    return wave.reshape(-1, 1)


def test_stream_callback_resamples_and_emits_segment(monkeypatch) -> None:
    emitted: list = []

    monkeypatch.setattr("core.audio.stream_capture.validate_device", lambda device_id: device_id)
    monkeypatch.setattr(
        "core.audio.stream_capture.open_input_stream_kwargs",
        lambda device_id: {
            "device": device_id,
            "channels": 1,
            "samplerate": 48_000,
            "dtype": "int16",
        },
    )
    monkeypatch.setattr("core.audio.stream_capture.sd.InputStream", _FakeInputStream)

    capture = StreamCapture(
        device_id=0,
        vad_threshold=0.5,
        min_speech_ms=60,
        hangover_ms=90,
        on_segment=lambda buffer, _final: emitted.append(buffer),
    )
    handle = capture.start()
    speech = _chunk_48k(amplitude=0.35)
    silence = _chunk_48k(amplitude=0.0)
    for _ in range(4):
        capture._callback(speech, speech.shape[0], None, None)
    for _ in range(4):
        capture._callback(silence, silence.shape[0], None, None)
    capture.stop(handle)

    assert len(emitted) == 1
    buffer = emitted[0]
    assert buffer.sample_rate == STANDARD_SAMPLE_RATE
    assert buffer.channels == 1
    assert len(buffer.pcm_bytes) > 0
