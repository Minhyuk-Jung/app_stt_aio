"""WebM ingest tests (C15)."""

from __future__ import annotations

import wave
from io import BytesIO
from unittest.mock import patch

import pytest

from core.audio.webm_convert import ffmpeg_available, webm_to_pcm
from remote.gateway.ingest import ingest_upload


def test_ingest_webm_without_ffmpeg_raises() -> None:
    with patch("core.audio.webm_convert.shutil.which", return_value=None):
        with pytest.raises(ValueError, match="ffmpeg"):
            ingest_upload(b"\x1a\x45\xdf\xa3fake", content_type="audio/webm")


def test_webm_to_pcm_with_mock_ffmpeg() -> None:
    pcm = b"\x00\x01" * 800

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        out_path = cmd[-1]
        with open(out_path, "wb") as fh:
            fh.write(pcm)
        return type("R", (), {"returncode": 0})()

    with patch("core.audio.webm_convert.shutil.which", return_value="ffmpeg"):
        with patch("core.audio.webm_convert.subprocess.run", side_effect=fake_run):
            buffer = webm_to_pcm(b"\x1a\x45\xdf\xa3data")
    assert buffer.pcm_bytes == pcm


def test_ffmpeg_available_is_bool() -> None:
    assert isinstance(ffmpeg_available(), bool)
