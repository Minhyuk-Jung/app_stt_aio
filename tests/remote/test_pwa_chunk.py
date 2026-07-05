"""PWA static asset checks."""

from __future__ import annotations

from pathlib import Path

PWA = Path(__file__).resolve().parents[2] / "remote" / "gateway" / "pwa" / "index.html"


def test_pwa_supports_chunk_upload() -> None:
    text = PWA.read_text(encoding="utf-8")
    assert "transcribe/chunks/init" in text
    assert "transcribe/chunk" in text
    assert "CHUNK_THRESHOLD" in text
    assert "uploadBlobChunked" in text
    assert "uploadOneChunk" in text
    assert "buildChunkForm" in text
    assert "MAX_OUTER_RETRY" in text
    assert "while (index < total)" in text
