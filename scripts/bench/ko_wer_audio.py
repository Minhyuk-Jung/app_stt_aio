"""Live audio WER benchmark via STTProvider (C2 §10)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.regression.ko_wer.wer_utils import (  # noqa: E402
    FIXTURES_DIR,
    audio_cases,
    load_audio_buffer,
    load_baseline,
    wer,
    write_silence_wav,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Korean audio WER benchmark")
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--models-dir", default="")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        print("status=skip")
        print("reason=faster_whisper not installed")
        return 0

    from core.audio.resample import build_audio_buffer
    from core.models.store_paths import resolve_models_dir
    from core.stt.faster_whisper_local import FasterWhisperLocalProvider

    models_dir = resolve_models_dir(
        default_dir=Path(tempfile.gettempdir()) / "stt-aio-models",
        custom_path=args.models_dir,
    )
    provider = FasterWhisperLocalProvider(
        models_dir=models_dir,
        model_id=args.model,
        device="cpu",
        compute_type="int8",
    )

    payload = load_baseline()
    default_max = float(payload.get("max_wer", 0.0))
    cases = audio_cases(payload)
    if not cases:
        print("status=skip")
        print("reason=no audio cases in baseline.json")
        return 0

    all_ok = True
    try:
        for case in cases:
            wav_path = FIXTURES_DIR / case["audio_file"]
            if not wav_path.is_file() and case["audio_file"] == "silence_200ms.wav":
                write_silence_wav(wav_path)
            audio = load_audio_buffer(case)
            audio = build_audio_buffer(
                audio.pcm_bytes,
                sample_rate=audio.sample_rate,
                channels=audio.channels,
            )
            try:
                result = provider.transcribe(audio)
            except Exception as exc:  # noqa: BLE001
                print(f"case={case['id']} status=error reason={exc}")
                all_ok = False
                continue
            hypothesis = result.text.strip()
            reference = case["reference"]
            score = wer(reference, hypothesis)
            limit = float(case.get("max_wer", default_max))
            ok = score <= limit
            all_ok = all_ok and ok
            print(f"case={case['id']} wer={score:.3f} max={limit} pass={ok}")
    finally:
        provider.close()

    print(f"pass={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
