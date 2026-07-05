"""Convert arbitrary PCM input to 16 kHz mono 16-bit PCM."""

from __future__ import annotations

import numpy as np

from core.audio.errors import ResampleError
from core.audio.format import (
    STANDARD_CHANNELS,
    STANDARD_SAMPLE_RATE,
    STANDARD_SAMPLE_WIDTH,
    AudioBuffer,
)


def to_standard_pcm(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
    sample_width: int = STANDARD_SAMPLE_WIDTH,
) -> bytes:
    if sample_rate <= 0 or channels <= 0 or sample_width <= 0:
        raise ResampleError("invalid source audio parameters")
    if not pcm_bytes:
        return b""

    frame_bytes = sample_width * channels
    if len(pcm_bytes) % frame_bytes != 0:
        raise ResampleError("pcm_bytes length is not aligned to frame size")

    if sample_width != STANDARD_SAMPLE_WIDTH:
        raise ResampleError(f"unsupported sample_width: {sample_width}")

    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

    if sample_rate == STANDARD_SAMPLE_RATE:
        return samples.tobytes()

    target_len = int(round(len(samples) * STANDARD_SAMPLE_RATE / sample_rate))
    if target_len <= 0:
        return b""

    source_indices = np.arange(len(samples), dtype=np.float64)
    target_indices = np.linspace(0, len(samples) - 1, target_len)
    resampled = np.interp(target_indices, source_indices, samples.astype(np.float64))
    return resampled.astype(np.int16).tobytes()


def build_audio_buffer(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
    sample_width: int = STANDARD_SAMPLE_WIDTH,
) -> AudioBuffer:
    standard_pcm = to_standard_pcm(
        pcm_bytes,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
    )
    buffer = AudioBuffer(pcm_bytes=standard_pcm)
    buffer.validate()
    return buffer
