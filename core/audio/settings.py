"""Audio capture parameters (from C11 Config or defaults)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioSettings:
    device_id: str = ""
    vad_engine: str = "energy"
    vad_threshold: float = 0.5
    min_speech_ms: int = 250
    hangover_ms: int = 500
    max_segment_ms: int = 30000
