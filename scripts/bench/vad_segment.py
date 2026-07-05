"""P0 spike: VAD segment-end latency benchmark (C1).

Uses SegmentTracker + energy threshold (same path as StreamCapture).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audio.format import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE
from core.audio.level import compute_peak_rms
from core.audio.vad import SegmentTracker, _energy_threshold


def _pcm_chunk(rms_level: float, *, frame_ms: int = 30) -> bytes:
    frames = int(STANDARD_SAMPLE_RATE * frame_ms / 1000)
    amplitude = min(0.95, max(0.0, rms_level))
    t = np.arange(frames, dtype=np.float32) / STANDARD_SAMPLE_RATE
    wave = (np.sin(2 * np.pi * 440 * t) * amplitude * 32767).astype(np.int16)
    if STANDARD_CHANNELS > 1:
        wave = np.column_stack([wave] * STANDARD_CHANNELS)
    return wave.tobytes()


def simulate_segment_end_ms(
    *,
    vad_threshold: float | None = None,
    hangover_ms: int = 500,
    min_speech_ms: int = 60,
    speech_frames: int = 20,
    silence_after_speech: int = 30,
    frame_ms: int = 30,
) -> float:
    """Return ms from last speech frame to segment emit."""
    threshold = vad_threshold if vad_threshold is not None else _energy_threshold(0.5)
    tracker = SegmentTracker(
        min_speech_ms=min_speech_ms,
        hangover_ms=hangover_ms,
        frame_ms=frame_ms,
    )
    last_speech_frame_idx = -1
    emit_frame_idx: int | None = None
    total_frames = speech_frames + silence_after_speech

    for frame_idx in range(total_frames):
        rms_level = 0.15 if frame_idx < speech_frames else 0.0
        chunk = _pcm_chunk(rms_level, frame_ms=frame_ms)
        _peak, rms = compute_peak_rms(chunk)
        is_speech = rms >= threshold
        if is_speech:
            last_speech_frame_idx = frame_idx
        if tracker.feed(chunk, is_speech) is not None:
            emit_frame_idx = frame_idx
            break

    if emit_frame_idx is None:
        emit_frame_idx = total_frames - 1
    if last_speech_frame_idx < 0:
        return float(hangover_ms)
    return max(0.0, (emit_frame_idx - last_speech_frame_idx) * frame_ms)


def main() -> None:
    frame_ms = 30
    hangover_ms = 500
    started = time.perf_counter()
    latency_ms = simulate_segment_end_ms(hangover_ms=hangover_ms, frame_ms=frame_ms)
    elapsed = (time.perf_counter() - started) * 1000
    target_ms = hangover_ms + frame_ms
    ok = latency_ms <= target_ms
    print(f"vad_segment_end_ms={latency_ms:.1f}")
    print(f"target_ms={target_ms}")
    print(f"pass={ok}")
    print(f"bench_overhead_ms={elapsed:.2f}")


if __name__ == "__main__":
    main()
