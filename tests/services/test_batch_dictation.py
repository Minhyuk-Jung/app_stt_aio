"""Tests for P1 batch dictation service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.audio.format import AudioBuffer
from core.inject.types import InjectMethod, InjectResult
from core.stt.types import STTResult


def test_transcribe_and_inject_empty_transcript() -> None:
    from app.services import transcribe_and_inject
    from app.session.types import SessionArtifact

    config = MagicMock()
    config._pipeline = MagicMock()
    config._store.sessions.create.return_value = MagicMock(id="sess-1")

    stt = STTResult(text="", language="ko", provider_id="mock")
    artifact = SessionArtifact(
        session_id="sess-1",
        stage=1,
        text="",
        language="ko",
        inject_result=InjectResult(
            success=True,
            method_used=InjectMethod.UNICODE,
            chars_injected=0,
        ),
    )

    with patch(
        "app.services.batch_dictation.run_batch_pipeline",
        return_value=(stt, artifact),
    ):
        result = transcribe_and_inject(config, AudioBuffer(pcm_bytes=b""))

    assert result.stt.is_empty
    assert result.inject is not None
    assert result.inject.success is True
    assert result.session_id == "sess-1"


def test_transcribe_and_inject_with_text() -> None:
    from app.services import transcribe_and_inject
    from app.session.types import SessionArtifact

    config = MagicMock()
    config._pipeline = MagicMock()

    stt = STTResult(text="안녕하세요", language="ko", provider_id="mock")
    artifact = SessionArtifact(
        session_id="provided-session",
        stage=1,
        text="안녕하세요",
        language="ko",
        inject_result=InjectResult(
            success=True,
            method_used=InjectMethod.UNICODE,
            chars_injected=5,
        ),
    )

    with patch(
        "app.services.batch_dictation.run_batch_pipeline",
        return_value=(stt, artifact),
    ) as mock_pipeline:
        result = transcribe_and_inject(
            config,
            AudioBuffer(pcm_bytes=b"\x00" * 100),
            session_id="provided-session",
        )

    assert result.stt.text == "안녕하세요"
    assert result.inject is not None
    assert result.inject.success is True
    assert result.session_id == "provided-session"
    mock_pipeline.assert_called_once()
