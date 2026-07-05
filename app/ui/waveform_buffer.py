"""Ring buffer for waveform level samples (C12, Qt-free)."""

from __future__ import annotations

from collections import deque


class WaveformBuffer:
    """Store recent normalized RMS levels for overlay rendering."""

    def __init__(self, capacity: int = 60) -> None:
        self._capacity = max(1, capacity)
        self._samples: deque[float] = deque(maxlen=self._capacity)

    def push(self, level: float) -> None:
        clamped = max(0.0, min(1.0, float(level)))
        self._samples.append(clamped)

    def clear(self) -> None:
        self._samples.clear()

    def values(self) -> list[float]:
        return list(self._samples)

    @property
    def capacity(self) -> int:
        return self._capacity
