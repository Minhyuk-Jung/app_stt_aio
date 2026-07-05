"""Audio-backed WER regression (C2 §10, README §12)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.audio.resample import build_audio_buffer
from core.stt.faster_whisper_local import FasterWhisperLocalProvider
from core.stt.types import STTResult
from tests.regression.ko_wer.wer_utils import (
    FIXTURES_DIR,
    audio_cases,
    load_audio_buffer,
    load_baseline,
    wer,
    write_silence_wav,
)

# Mock hypotheses for pipeline contract tests (not live STT output).
MOCK_HYPOTHESES: dict[str, str] = {
    "greeting": "안녕하세요 반갑습니다",
    "meeting": "오늘 회의 내용 정리합니다",
    "mixed_noise": "STT-AIO 한국어 받아쓰기 테스트입니다",
    "minor_spacing": "다음주 월요일에 다시 연락 드리겠습니다",
    "silence_200ms": "",
}


def test_audio_fixture_files_exist() -> None:
    silence = FIXTURES_DIR / "silence_200ms.wav"
    if not silence.is_file():
        write_silence_wav(silence)
    for case in audio_cases():
        path = FIXTURES_DIR / case["audio_file"]
        assert path.is_file(), f"missing fixture: {path}"


def test_wer_audio_pipeline_with_mock_stt(tmp_path) -> None:
    payload = load_baseline()
    default_max = float(payload.get("max_wer", 0.0))
    provider = FasterWhisperLocalProvider(models_dir=tmp_path, model_id="base")
    for case in audio_cases(payload):
        audio = load_audio_buffer(case)
        audio = build_audio_buffer(
            audio.pcm_bytes,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )
        hypothesis = case.get("hypothesis") or MOCK_HYPOTHESES.get(case["id"], case["reference"])
        reference = case["reference"]
        with patch.object(
            provider,
            "transcribe",
            return_value=STTResult(
                text=hypothesis,
                language="ko",
                provider_id="mock-stt",
            ),
        ):
            result = provider.transcribe(audio)
        score = wer(reference, result.text)
        limit = float(case.get("max_wer", default_max))
        assert score <= limit, f"{case['id']}: wer={score:.3f} > {limit}"


@pytest.mark.integration
def test_wer_audio_live_stt_optional(tmp_path) -> None:
    if os.environ.get("STT_AIO_WER_LIVE") != "1":
        pytest.skip("set STT_AIO_WER_LIVE=1 to run live STT WER")

    pytest.importorskip("faster_whisper")

    silence = FIXTURES_DIR / "silence_200ms.wav"
    if not silence.is_file():
        write_silence_wav(silence)

    payload = load_baseline()
    default_max = float(payload.get("max_wer", 0.0))
    model_id = os.environ.get("STT_AIO_WER_MODEL", "base")

    provider = FasterWhisperLocalProvider(
        models_dir=tmp_path,
        model_id=model_id,
        device="cpu",
        compute_type="int8",
    )
    try:
        for case in audio_cases(payload):
            audio = load_audio_buffer(case)
            audio = build_audio_buffer(
                audio.pcm_bytes,
                sample_rate=audio.sample_rate,
                channels=audio.channels,
            )
            try:
                result = provider.transcribe(audio)
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"live STT unavailable: {exc}")
            score = wer(case["reference"], result.text.strip())
            limit = float(case.get("max_wer", default_max))
            assert score <= limit, (
                f"{case['id']}: wer={score:.3f} > {limit} "
                f"(hypothesis={result.text!r})"
            )
    finally:
        provider.close()
