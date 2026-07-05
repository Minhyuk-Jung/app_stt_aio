"""Convert WebM/Opus browser recordings to 16kHz mono PCM (C15)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from core.audio.format import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE, AudioBuffer


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def webm_to_pcm(
    data: bytes,
    *,
    sample_rate: int = STANDARD_SAMPLE_RATE,
    channels: int = STANDARD_CHANNELS,
) -> AudioBuffer:
    """Decode WebM bytes to PCM using ffmpeg on PATH."""
    if not data:
        raise ValueError("empty audio")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError(
            "WebM 오디오는 ffmpeg가 필요합니다. "
            "https://ffmpeg.org 에서 설치하거나 WAV로 업로드하세요."
        )

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.webm"
        dst = Path(tmp) / "output.pcm"
        src.write_bytes(data)
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            str(dst),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=120.0,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:500]
            raise ValueError(f"WebM 변환 실패: {stderr or exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("WebM 변환 시간 초과") from exc

        pcm = dst.read_bytes()
        if not pcm:
            raise ValueError("WebM 변환 결과가 비어 있습니다")
        return AudioBuffer(
            pcm_bytes=pcm,
            sample_rate=sample_rate,
            channels=channels,
        )
