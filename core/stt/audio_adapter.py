"""Convert C1 AudioBuffer to formats STT engines consume."""

from __future__ import annotations

import numpy as np

from core.audio.format import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE, AudioBuffer
from core.stt.errors import AudioFormatError


def audio_buffer_to_float32(audio: AudioBuffer) -> np.ndarray:
    audio.validate()
    if audio.is_empty:
        return np.array([], dtype=np.float32)
    if audio.sample_rate != STANDARD_SAMPLE_RATE or audio.channels != STANDARD_CHANNELS:
        raise AudioFormatError(
            f"expected {STANDARD_SAMPLE_RATE}Hz mono PCM, got "
            f"{audio.sample_rate}Hz {audio.channels}ch"
        )
    samples = np.frombuffer(audio.pcm_bytes, dtype=np.int16).astype(np.float32)
    return samples / np.iinfo(np.int16).max


def audio_buffer_to_wav_bytes(audio: AudioBuffer) -> bytes:
    """Encode mono PCM int16 buffer as a minimal WAV file."""
    import struct
    import wave
    from io import BytesIO

    audio.validate()
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(audio.channels or STANDARD_CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(audio.sample_rate or STANDARD_SAMPLE_RATE)
        wav_file.writeframes(audio.pcm_bytes)
    return buffer.getvalue()
