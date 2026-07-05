"""Shared helpers for Korean WER regression (README §12)."""

from __future__ import annotations

import json
import wave
from io import BytesIO
from pathlib import Path

from core.audio.format import AudioBuffer

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "ko_wer"
BASELINE = FIXTURES_DIR / "baseline.json"


def wer(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    hyp = hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    rows = len(ref) + 1
    cols = len(hyp) + 1
    dist = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        dist[i][0] = i
    for j in range(cols):
        dist[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dist[i][j] = min(
                dist[i - 1][j] + 1,
                dist[i][j - 1] + 1,
                dist[i - 1][j - 1] + cost,
            )
    return dist[rows - 1][cols - 1] / len(ref)


def load_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def audio_cases(payload: dict | None = None) -> list[dict]:
    data = payload if payload is not None else load_baseline()
    return [case for case in data.get("cases", []) if case.get("audio_file")]


def load_audio_buffer(case: dict) -> AudioBuffer:
    path = FIXTURES_DIR / str(case["audio_file"])
    with wave.open(str(path), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        return AudioBuffer(
            pcm_bytes=pcm,
            sample_rate=wf.getframerate(),
            channels=wf.getnchannels(),
        )


def write_silence_wav(path: Path, *, duration_sec: float = 0.2) -> None:
    frames = int(16000 * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)
