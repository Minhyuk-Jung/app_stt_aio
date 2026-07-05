"""VAD unit tests (C1)."""

from __future__ import annotations

import numpy as np
import pytest

from core.audio.vad import (
    EnergySpeechDetector,
    SegmentTracker,
    _energy_threshold,
    create_speech_detector,
)


def _pcm_chunk(amplitude: float, *, frames: int = 480) -> bytes:
    wave = (np.sin(np.linspace(0, 4 * np.pi, frames)) * amplitude * 32767).astype(np.int16)
    return wave.tobytes()


def test_segment_tracker_emits_after_hangover() -> None:
    tracker = SegmentTracker(min_speech_ms=60, hangover_ms=90, frame_ms=30)
    speech = _pcm_chunk(0.3)
    silence = _pcm_chunk(0.0)
    assert tracker.feed(speech, True) is None
    assert tracker.feed(speech, True) is None
    completed = tracker.feed(silence, False)
    assert completed is None
    completed = tracker.feed(silence, False)
    assert completed is None
    completed = tracker.feed(silence, False)
    assert completed is not None
    assert len(completed) > 0


def test_energy_detector() -> None:
    detector = EnergySpeechDetector(threshold=0.02)
    assert detector.is_speech(_pcm_chunk(0.3)) is True
    assert detector.is_speech(_pcm_chunk(0.0)) is False


def test_create_speech_detector_falls_back_on_silero_failure(monkeypatch) -> None:
    class _Boom:
        def __init__(self, **kwargs) -> None:
            raise RuntimeError("no silero")

    monkeypatch.setattr("core.audio.vad.SileroSpeechDetector", _Boom)
    detector = create_speech_detector("silero", threshold=0.5)
    assert isinstance(detector, EnergySpeechDetector)


def test_energy_threshold_mapping() -> None:
    assert _energy_threshold(0.5) == pytest.approx(0.02, abs=0.001)


def test_short_segment_discarded_on_hangover() -> None:
    tracker = SegmentTracker(min_speech_ms=90, hangover_ms=90, frame_ms=30)
    speech = _pcm_chunk(0.3)
    silence = _pcm_chunk(0.0)
    tracker.feed(speech, True)
    tracker.feed(speech, True)
    for _ in range(3):
        assert tracker.feed(silence, False) is None
    assert tracker.flush() is None


def test_max_segment_forces_emit() -> None:
    tracker = SegmentTracker(min_speech_ms=30, max_segment_ms=60, frame_ms=30)
    speech = _pcm_chunk(0.3)
    assert tracker.feed(speech, True) is None
    completed = tracker.feed(speech, True)
    assert completed is not None
    assert len(completed) > 0
