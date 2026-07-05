"""Tests for pipeline stage executors."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import Config
from core.audio.format import AudioBuffer
from core.pipeline.stages import post_process_stage1_text, run_stage1
from core.stt.types import STTResult


@pytest.fixture
def config(tmp_path: Path) -> Config:
    cfg = Config.open(tmp_path / "stages.db", migrate_backup=False)
    cfg.bind_text_processor()
    yield cfg
    cfg.close()


def test_post_process_stage1_text_normalizes(config: Config) -> None:
    assert post_process_stage1_text(config, "  hello  ") == "hello"


def test_run_stage1_transcribes_and_builds_artifact(config: Config) -> None:
    config._stt_session = MagicMock()
    config._stt_session.transcribe_segment.return_value = STTResult(
        text="테스트",
        language="ko",
        provider_id="mock-provider",
    )
    config.get_stt_options = MagicMock()

    _stt, artifact = run_stage1(config, AudioBuffer(pcm_bytes=b"\x00\x01"), "sid-1")

    assert artifact.session_id == "sid-1"
    assert artifact.stage == 1
    assert artifact.text == "테스트"
    assert artifact.language == "ko"
    assert artifact.provider == "mock-provider"
    config._stt_session.transcribe_segment.assert_called_once()
