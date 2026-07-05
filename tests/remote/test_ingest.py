"""C15 ingest tests."""

from __future__ import annotations

import wave
from io import BytesIO

import pytest

from remote.gateway.ingest import ingest_upload


def _wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 160)
    return buf.getvalue()


def test_ingest_wav() -> None:
    buffer = ingest_upload(_wav_bytes(), content_type="audio/wav")
    assert buffer.sample_rate == 16000
    assert len(buffer.pcm_bytes) > 0


def test_ingest_wav_resamples_non_16k() -> None:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x00\x00" * 480)
    buffer = ingest_upload(buf.getvalue(), content_type="audio/wav")
    assert buffer.sample_rate == 16000
    assert len(buffer.pcm_bytes) == 160 * 2


def test_ingest_empty_rejected() -> None:
    with pytest.raises(ValueError):
        ingest_upload(b"")
