"""Remote audio ingest → standard buffer (C15 §6.3)."""

from __future__ import annotations

from core.audio.format import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE, AudioBuffer
from core.audio.resample import build_audio_buffer


def ingest_upload(data: bytes, *, content_type: str = "") -> AudioBuffer:
    """Wrap uploaded bytes as 16 kHz mono AudioBuffer (PCM/WAV/WebM)."""
    if not data:
        raise ValueError("empty audio")
    lowered = (content_type or "").lower()
    if lowered.startswith("audio/wav") or data[:4] == b"RIFF":
        return _from_wav(data)
    if lowered.startswith("audio/webm") or data[:4] == b"\x1a\x45\xdf\xa3":
        from core.audio.webm_convert import webm_to_pcm

        buffer = webm_to_pcm(data)
        buffer.validate()
        return buffer
    return build_audio_buffer(
        data,
        sample_rate=STANDARD_SAMPLE_RATE,
        channels=STANDARD_CHANNELS,
    )


def _from_wav(data: bytes) -> AudioBuffer:
    import wave
    from io import BytesIO

    with wave.open(BytesIO(data), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        return build_audio_buffer(
            pcm,
            sample_rate=wf.getframerate(),
            channels=wf.getnchannels(),
            sample_width=wf.getsampwidth(),
        )
