"""Input level helpers for UI waveform display."""

from __future__ import annotations

import numpy as np


def compute_peak_rms(pcm_bytes: bytes, sample_width: int = 2) -> tuple[float, float]:
    """Return normalized peak and RMS in range 0.0..1.0."""
    if not pcm_bytes or sample_width != 2:
        return 0.0, 0.0
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(samples)) / np.iinfo(np.int16).max)
    rms = float(np.sqrt(np.mean(samples ** 2)) / np.iinfo(np.int16).max)
    return min(peak, 1.0), min(rms, 1.0)
