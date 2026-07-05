"""Cloud STT provider contract tests (C2)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.audio.capture_batch import generate_test_tone
from core.audio.format import AudioBuffer
from core.stt.deepgram_transcribe import DeepgramTranscribeProvider
from core.stt.errors import AuthenticationError
from core.stt.groq_transcribe import GroqTranscribeProvider
from core.stt.types import CostType


@pytest.fixture
def sample_audio() -> AudioBuffer:
    return AudioBuffer(pcm_bytes=generate_test_tone(duration_ms=400))


def test_groq_provider_id() -> None:
    provider = GroqTranscribeProvider(api_key="test")
    assert provider.provider_id == "groq_transcribe"
    assert provider.capabilities().needs_network is True
    assert provider.capabilities().cost_type == CostType.PAID


def test_deepgram_provider_id() -> None:
    provider = DeepgramTranscribeProvider(api_key="test")
    assert provider.provider_id == "deepgram_transcribe"


def test_deepgram_requires_api_key(sample_audio: AudioBuffer) -> None:
    provider = DeepgramTranscribeProvider(api_key=None)
    with pytest.raises(AuthenticationError):
        provider.transcribe(sample_audio)


@patch("core.stt.deepgram_transcribe.request_bytes")
def test_deepgram_transcribe_parses_response(
    mock_request: MagicMock,
    sample_audio: AudioBuffer,
) -> None:
    payload = {
        "results": {
            "channels": [
                {"alternatives": [{"transcript": "안녕하세요 반갑습니다"}]},
            ],
        },
    }
    mock_request.return_value = json.dumps(payload).encode("utf-8")
    provider = DeepgramTranscribeProvider(api_key="dg-test")
    result = provider.transcribe(sample_audio)
    assert result.text == "안녕하세요 반갑습니다"
    assert result.provider_id == "deepgram_transcribe"


def test_config_create_groq_provider(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "groq.db", migrate_backup=False) as config:
        config.set("stt.provider", "groq_transcribe")
        config.set("stt.cloud_model", "whisper-large-v3")
        with patch.object(config, "get_stt_api_key", return_value="gk-test"):
            provider = config.create_stt_provider()
        assert provider.provider_id == "groq_transcribe"


def test_config_create_deepgram_provider(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "dg.db", migrate_backup=False) as config:
        config.set("stt.provider", "deepgram_transcribe")
        with patch.object(config, "get_stt_api_key", return_value="dg-test"):
            provider = config.create_stt_provider()
        assert provider.provider_id == "deepgram_transcribe"


@patch("core.stt.openai_transcribe.request_multipart_json")
def test_openai_transcribe_retries_via_http_util(
    mock_request: MagicMock,
    sample_audio: AudioBuffer,
) -> None:
    from core.stt.openai_transcribe import OpenAITranscribeProvider

    mock_request.return_value = {"text": "안녕", "language": "ko"}
    provider = OpenAITranscribeProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
    )
    result = provider.transcribe(sample_audio)
    assert result.text == "안녕"
    mock_request.assert_called_once()
