"""Integration tests for batch dictation service."""

from __future__ import annotations

from unittest.mock import patch

from app.config import Config
from app.services.batch_dictation import transcribe_and_inject
from core.audio.format import AudioBuffer
from core.inject.types import InjectMethod, InjectResult
from core.pipeline.types import StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionStatus


def test_transcribe_and_inject_ephemeral_session_persists_done(tmp_path) -> None:
    config = Config.open(tmp_path / "batch_int.db", migrate_backup=False)
    config.bind_stt_session()
    config.bind_injector()
    config.bind_pipeline()

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        def stage1_side_effect(_config, _audio, session_id: str):
            return (
                STTResult(text="배치", language="ko", provider_id="mock"),
                StageArtifact(
                    session_id=session_id,
                    stage=1,
                    text="배치",
                    language="ko",
                    provider="mock",
                ),
            )

        mock_stage1.side_effect = stage1_side_effect
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=2,
            )

            result = transcribe_and_inject(config, AudioBuffer(pcm_bytes=b"\x00\x01"))

    stored = config._store.sessions.get(result.session_id)
    assert stored is not None
    assert stored.status is SessionStatus.DONE
    assert result.stt.text == "배치"
    assert result.inject is not None
    assert config._store.artifacts.latest_by_stage(result.session_id, 1) is not None

    config.close()
