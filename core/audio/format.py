"""Standard internal audio format definitions."""

from __future__ import annotations

from dataclasses import dataclass

STANDARD_SAMPLE_RATE = 16000
STANDARD_CHANNELS = 1
STANDARD_SAMPLE_WIDTH = 2  # 16-bit PCM


@dataclass(frozen=True)
class AudioBuffer:
    pcm_bytes: bytes
    sample_rate: int = STANDARD_SAMPLE_RATE
    channels: int = STANDARD_CHANNELS
    sample_width: int = STANDARD_SAMPLE_WIDTH

    @property
    def is_empty(self) -> bool:
        return len(self.pcm_bytes) == 0

    @property
    def duration_ms(self) -> int:
        if self.sample_width <= 0 or self.channels <= 0 or self.sample_rate <= 0:
            return 0
        frame_bytes = self.sample_width * self.channels
        if frame_bytes == 0:
            return 0
        frames = len(self.pcm_bytes) // frame_bytes
        return int(frames * 1000 / self.sample_rate)

    def validate(self) -> None:
        if self.sample_rate != STANDARD_SAMPLE_RATE:
            raise ValueError(f"unexpected sample_rate: {self.sample_rate}")
        if self.channels != STANDARD_CHANNELS:
            raise ValueError(f"unexpected channels: {self.channels}")
        if self.sample_width != STANDARD_SAMPLE_WIDTH:
            raise ValueError(f"unexpected sample_width: {self.sample_width}")
        if len(self.pcm_bytes) % (self.sample_width * self.channels) != 0:
            raise ValueError("pcm_bytes length is not aligned to frame size")
