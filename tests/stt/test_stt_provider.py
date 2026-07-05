"""Tests for C2 STT provider (P1 local batch)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.audio.capture_batch import generate_test_tone
from core.audio.format import AudioBuffer
from core.models.errors import ModelNotFoundError as ResolverModelNotFound
from core.models.resolver import resolve_whisper_model_path
from core.stt import (
    FasterWhisperLocalProvider,
    ProviderNotFoundError,
    STTOptions,
    create_provider,
    registered_provider_ids,
    resolve_provider_id,
)
from core.stt.audio_adapter import audio_buffer_to_float32
from core.stt.errors import ModelNotFoundError, ProviderBusyError, STTError, TranscriptionError
from core.stt.types import CostType, ProviderState


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    path = tmp_path / "models"
    path.mkdir()
    return path


@pytest.fixture
def sample_audio() -> AudioBuffer:
    pcm = generate_test_tone(duration_ms=500, sample_rate=16000, channels=1)
    return AudioBuffer(pcm_bytes=pcm)


def test_registered_providers() -> None:
    assert "faster_whisper_local" in registered_provider_ids()


def test_resolve_provider_aliases() -> None:
    assert resolve_provider_id("local") == "faster_whisper_local"
    assert resolve_provider_id("groq") == "groq_transcribe"
    assert resolve_provider_id("deepgram") == "deepgram_transcribe"
    with pytest.raises(ProviderNotFoundError):
        resolve_provider_id("unknown_provider")


def test_create_provider(models_dir: Path) -> None:
    provider = create_provider(
        "faster_whisper_local",
        models_dir=models_dir,
        model_id="base",
    )
    assert provider.provider_id == "faster_whisper_local"


def test_resolve_whisper_model_path_builtin(models_dir: Path) -> None:
    assert resolve_whisper_model_path(models_dir, "base") == "base"


def test_resolve_whisper_model_path_custom(models_dir: Path) -> None:
    custom = models_dir / "my-model"
    custom.mkdir(parents=True)
    (custom / "model.bin").write_bytes(b"x")
    assert resolve_whisper_model_path(models_dir, "my-model") == str(custom)


def test_resolve_whisper_model_path_missing(models_dir: Path) -> None:
    with pytest.raises(ResolverModelNotFound):
        resolve_whisper_model_path(models_dir, "missing-model")


def test_audio_buffer_to_float32(sample_audio: AudioBuffer) -> None:
    samples = audio_buffer_to_float32(sample_audio)
    assert samples.dtype == np.float32
    assert samples.size > 0
    assert float(np.max(np.abs(samples))) <= 1.0


def test_capabilities(models_dir: Path) -> None:
    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    caps = provider.capabilities()
    assert caps.supports_streaming is True
    assert caps.needs_network is False
    assert caps.cost_type == CostType.LOCAL
    assert caps.gpu_optional is True
    assert "ko" in caps.languages


def test_transcribe_empty_audio(models_dir: Path) -> None:
    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    result = provider.transcribe(AudioBuffer(pcm_bytes=b""))
    assert result.is_empty
    assert result.provider_id == "faster_whisper_local"


def test_transcribe_silent_audio(models_dir: Path) -> None:
    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    silent = AudioBuffer(pcm_bytes=b"\x00\x00" * 1600)
    result = provider.transcribe(silent)
    assert result.is_empty


@patch("core.stt.faster_whisper_local._import_whisper_model")
def test_stream_yields_final_segments(
    mock_import: MagicMock,
    models_dir: Path,
    sample_audio: AudioBuffer,
) -> None:
    mock_segment = SimpleNamespace(
        text=" 안녕",
        start=0.0,
        end=0.4,
        avg_logprob=-0.1,
    )
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = lambda *args, **kwargs: (
        iter([mock_segment]),
        SimpleNamespace(language="ko"),
    )
    mock_import.return_value = MagicMock(return_value=mock_model)

    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    pcm = sample_audio.pcm_bytes
    segments = list(provider.stream(iter([pcm, pcm]), STTOptions(language="ko")))

    assert len(segments) == 2
    assert all(seg.is_final for seg in segments)
    assert segments[0].text == "안녕"
    assert mock_model.transcribe.call_count == 2


@patch("core.stt.faster_whisper_local._import_whisper_model")
def test_transcribe_with_mock_model(
    mock_import: MagicMock,
    models_dir: Path,
    sample_audio: AudioBuffer,
) -> None:
    mock_segment = SimpleNamespace(
        text=" 안녕하세요",
        start=0.0,
        end=0.5,
        avg_logprob=-0.2,
    )
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        iter([mock_segment]),
        SimpleNamespace(language="ko"),
    )
    mock_import.return_value = MagicMock(return_value=mock_model)

    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    result = provider.transcribe(
        sample_audio,
        STTOptions(language="ko", initial_prompt="회의", hotwords=("STT-AIO",)),
    )

    assert result.text == "안녕하세요"
    assert result.language == "ko"
    assert len(result.segments) == 1
    assert result.segments[0].start_ms == 0
    assert result.segments[0].end_ms == 500
    mock_model.transcribe.assert_called_once()
    call_kwargs = mock_model.transcribe.call_args.kwargs
    assert call_kwargs["language"] == "ko"
    assert "회의" in call_kwargs["initial_prompt"]
    assert call_kwargs["task"] == "transcribe"


@patch("core.stt.faster_whisper_local._import_whisper_model")
def test_transcribe_rejects_oversized_audio(
    mock_import: MagicMock,
    models_dir: Path,
) -> None:
    mock_import.return_value = MagicMock()
    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    long_pcm = generate_test_tone(duration_ms=601_000, sample_rate=16000)
    audio = AudioBuffer(pcm_bytes=long_pcm)
    with pytest.raises(TranscriptionError):
        provider.transcribe(audio)


@patch("core.stt.faster_whisper_local._import_whisper_model")
def test_transcribe_failure_keeps_model_ready(
    mock_import: MagicMock,
    models_dir: Path,
    sample_audio: AudioBuffer,
) -> None:
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("engine failed")
    mock_import.return_value = MagicMock(return_value=mock_model)

    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    provider.warmup()
    assert provider.state == ProviderState.READY

    with pytest.raises(TranscriptionError):
        provider.transcribe(sample_audio)

    assert provider.state == ProviderState.READY
    assert provider._model is not None


@patch("core.stt.faster_whisper_local._import_whisper_model")
def test_provider_busy_rejects_parallel_transcribe(
    mock_import: MagicMock,
    models_dir: Path,
    sample_audio: AudioBuffer,
) -> None:
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter([]), SimpleNamespace(language="ko"))
    mock_import.return_value = MagicMock(return_value=mock_model)

    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="base")
    provider._state = ProviderState.BUSY
    with pytest.raises(ProviderBusyError):
        provider.transcribe(sample_audio)


def test_model_not_found_is_stt_error(models_dir: Path) -> None:
    provider = FasterWhisperLocalProvider(models_dir=models_dir, model_id="missing")
    with pytest.raises(ModelNotFoundError) as exc_info:
        provider.warmup()
    assert isinstance(exc_info.value, STTError)


def test_config_create_stt_provider(tmp_path: Path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "stt.db", migrate_backup=False) as config:
        provider = config.create_stt_provider()
        assert provider.provider_id == "faster_whisper_local"


def test_config_bind_stt_session_refreshes_on_change(tmp_path: Path) -> None:
    from app.config import Config
    from app.stt import STTProviderSession

    with Config.open(tmp_path / "stt_session.db", migrate_backup=False) as config:
        session = config.bind_stt_session()
        assert isinstance(session, STTProviderSession)
        first = session.provider
        config.set("stt.model", "small")
        second = session.provider
        assert first is not second
