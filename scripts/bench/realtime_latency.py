"""P0 spike: realtime path latency (VAD segment end -> STT) (README P0 DoD ④).

Simulates segment emission then batch-transcribes the segment buffer.
Target: segment end -> text within 1000 ms (NFR realtime, short utterance).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audio.format import AudioBuffer, STANDARD_CHANNELS, STANDARD_SAMPLE_RATE
from core.audio.level import compute_peak_rms
from core.audio.vad import SegmentTracker, _energy_threshold
from scripts.bench import vad_segment as vad_bench


def _build_segment_pcm(
    *,
    speech_frames: int = 12,
    silence_after: int = 20,
    frame_ms: int = 30,
    hangover_ms: int = 500,
) -> tuple[AudioBuffer, float]:
    """Return emitted segment audio and VAD end-detection latency (ms)."""
    threshold = _energy_threshold(0.5)
    tracker = SegmentTracker(
        min_speech_ms=60,
        hangover_ms=hangover_ms,
        frame_ms=frame_ms,
    )
    vad_end_ms = vad_bench.simulate_segment_end_ms(
        hangover_ms=hangover_ms,
        frame_ms=frame_ms,
        speech_frames=speech_frames,
        silence_after_speech=silence_after,
    )

    pcm: bytes | None = None
    total_frames = speech_frames + silence_after
    for frame_idx in range(total_frames):
        rms_level = 0.15 if frame_idx < speech_frames else 0.0
        chunk = vad_bench._pcm_chunk(rms_level, frame_ms=frame_ms)
        _peak, rms = compute_peak_rms(chunk)
        is_speech = rms >= threshold
        emitted = tracker.feed(chunk, is_speech)
        if emitted is not None:
            pcm = emitted
            break

    if pcm is None:
        frames = speech_frames * int(STANDARD_SAMPLE_RATE * frame_ms / 1000)
        wave = (np.sin(2 * np.pi * 440 * np.arange(frames) / STANDARD_SAMPLE_RATE) * 0.2 * 32767)
        pcm = wave.astype(np.int16).tobytes()

    audio = AudioBuffer(
        pcm_bytes=pcm,
        sample_rate=STANDARD_SAMPLE_RATE,
        channels=STANDARD_CHANNELS,
    )
    return audio, vad_end_ms


def bench_realtime(model_id: str, language: str) -> dict[str, float | str | bool]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"status": "skip", "reason": "faster_whisper not installed"}

    audio, vad_end_ms = _build_segment_pcm()
    started = time.perf_counter()
    model = WhisperModel(model_id, device="cpu", compute_type="int8")
    load_ms = (time.perf_counter() - started) * 1000

    wav = Path(tempfile.mkdtemp()) / "segment.wav"
    import wave

    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(STANDARD_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(STANDARD_SAMPLE_RATE)
        wf.writeframes(audio.pcm_bytes)

    started = time.perf_counter()
    segments, _info = model.transcribe(str(wav), language=language, beam_size=1)
    text = "".join(segment.text for segment in segments).strip()
    stt_ms = (time.perf_counter() - started) * 1000
    total_ms = vad_end_ms + stt_ms
    target_ms = 1000
    return {
        "status": "ok",
        "model": model_id,
        "vad_end_ms": round(vad_end_ms, 1),
        "stt_ms": round(stt_ms, 1),
        "load_ms": round(load_ms, 1),
        "total_ms": round(total_ms, 1),
        "text_len": len(text),
        "pass": total_ms < target_ms,
        "target_ms": target_ms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Realtime path latency (P0)")
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()

    result = bench_realtime(args.model, args.language)
    for key, value in result.items():
        print(f"{key}={value}")
    if result.get("status") == "skip":
        return 0
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
