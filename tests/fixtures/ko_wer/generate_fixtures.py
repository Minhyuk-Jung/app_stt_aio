"""Generate WAV fixtures for ko_wer regression (README §12).

Uses Windows SAPI TTS when available; always writes silence_200ms.wav.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
BASELINE = OUT / "baseline.json"

TTS_CASES = (
    ("greeting.wav", "안녕하세요 반갑습니다"),
    ("meeting.wav", "오늘 회의 내용을 정리합니다"),
)


def write_silence_wav(path: Path, *, duration_sec: float = 0.2) -> None:
    frames = int(16000 * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)


def _synthesize_windows_sapi(text: str, path: Path) -> bool:
    if sys.platform != "win32":
        return False
    escaped = text.replace('"', '`"')
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($voice in $synth.GetInstalledVoices()) {{
  if ($voice.VoiceInfo.Culture.Name -like 'ko*') {{
    $synth.SelectVoice($voice.VoiceInfo.Name)
    break
  }}
}}
$synth.SetOutputToWaveFile('{path}')
$synth.Speak("{escaped}")
$synth.Dispose()
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and path.is_file()


def _resample_to_16k_mono(src: Path, dest: Path) -> None:
    from core.audio.resample import to_standard_pcm

    with wave.open(str(src), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        rate = wf.getframerate()
        channels = wf.getnchannels()
    standard = to_standard_pcm(pcm, sample_rate=rate, channels=channels)
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(standard)


def synthesize_fixture(filename: str, text: str) -> bool:
    target = OUT / filename
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        if not _synthesize_windows_sapi(text, raw):
            return False
        _resample_to_16k_mono(raw, target)
    return target.is_file()


def _patch_baseline_audio_files() -> None:
    if not BASELINE.is_file():
        return
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in payload.get("cases", [])}
    mapping = {
        "greeting": "greeting.wav",
        "meeting": "meeting.wav",
        "silence_200ms": "silence_200ms.wav",
    }
    for case_id, audio_file in mapping.items():
        case = by_id.get(case_id)
        if case is None:
            continue
        case["audio_file"] = audio_file
        if case_id in ("greeting", "meeting"):
            case.setdefault("max_wer", 0.65)
    BASELINE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    write_silence_wav(OUT / "silence_200ms.wav")
    print(f"wrote {OUT / 'silence_200ms.wav'}")

    ok = 0
    for filename, text in TTS_CASES:
        if synthesize_fixture(filename, text):
            print(f"wrote {OUT / filename}")
            ok += 1
        else:
            print(f"skip {filename} (SAPI TTS unavailable)")

    _patch_baseline_audio_files()
    print(f"updated {BASELINE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())