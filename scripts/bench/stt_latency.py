"""P0 spike: local STT end-to-end latency benchmark (C2).

Uses faster-whisper when installed; otherwise reports skip status.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audio.format import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE


def _write_sine_wav(path: Path, *, duration_sec: float = 1.5) -> None:
    frames = int(STANDARD_SAMPLE_RATE * duration_sec)
    t = np.linspace(0, duration_sec, frames, endpoint=False, dtype=np.float32)
    audio = (np.sin(2 * np.pi * 220 * t) * 0.3 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(STANDARD_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(STANDARD_SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def bench_transcribe(model_id: str, language: str) -> dict[str, float | str | bool]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"status": "skip", "reason": "faster_whisper not installed"}

    wav = Path(tempfile.mkdtemp()) / "sample.wav"
    _write_sine_wav(wav)
    started = time.perf_counter()
    model = WhisperModel(model_id, device="cpu", compute_type="int8")
    load_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    segments, _info = model.transcribe(str(wav), language=language, beam_size=1)
    text = "".join(segment.text for segment in segments).strip()
    transcribe_ms = (time.perf_counter() - started) * 1000
    target_ms = 2000
    return {
        "status": "ok",
        "model": model_id,
        "load_ms": round(load_ms, 1),
        "transcribe_ms": round(transcribe_ms, 1),
        "text_len": len(text),
        "pass": transcribe_ms < target_ms,
        "target_ms": target_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="STT latency benchmark (P0)")
    parser.add_argument("--model", default="tiny", help="Whisper model id")
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()

    result = bench_transcribe(args.model, args.language)
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
