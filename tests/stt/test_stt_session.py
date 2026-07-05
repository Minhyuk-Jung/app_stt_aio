"""STTProviderSession behavior tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.stt.session import STTProviderSession
from core.audio.format import AudioBuffer
from core.stt.types import STTCapabilities, CostType, STTResult, STTSegment


@pytest.fixture
def config(tmp_path):
    cfg = Config.open(tmp_path / "stt_sess.db", migrate_backup=False)
    yield cfg
    cfg.close()


def test_transcribe_segment_uses_stream_when_supported(config: Config) -> None:
    session = STTProviderSession(config)
    mock_provider = MagicMock()
    mock_provider.provider_id = "faster_whisper_local"
    mock_provider.capabilities.return_value = STTCapabilities(
        supports_streaming=True,
        languages=("ko",),
        max_audio_sec=600,
        needs_network=False,
        cost_type=CostType.LOCAL,
        gpu_optional=True,
    )
    mock_provider.stream.return_value = iter(
        [STTSegment(text="안녕", is_final=True, start_ms=0, end_ms=400)]
    )
    session._provider = mock_provider

    audio = AudioBuffer(pcm_bytes=b"\x00\x01" * 100)
    result = session.transcribe_segment(audio)

    assert result.text == "안녕"
    assert result.provider_id == "faster_whisper_local"
    mock_provider.stream.assert_called_once()
    mock_provider.transcribe.assert_not_called()


def test_transcribe_uses_batch_path(config: Config) -> None:
    session = STTProviderSession(config)
    mock_provider = MagicMock()
    mock_provider.provider_id = "openai_transcribe"
    mock_provider.capabilities.return_value = STTCapabilities(
        supports_streaming=False,
        languages=("ko",),
        max_audio_sec=1800,
        needs_network=True,
        cost_type=CostType.PAID,
        gpu_optional=True,
    )
    mock_provider.transcribe.return_value = STTResult(
        text="배치",
        language="ko",
        provider_id="openai_transcribe",
    )
    session._provider = mock_provider

    audio = AudioBuffer(pcm_bytes=b"\x00\x01")
    result = session.transcribe(audio)

    assert result.text == "배치"
    mock_provider.transcribe.assert_called_once()
    mock_provider.stream.assert_not_called()
