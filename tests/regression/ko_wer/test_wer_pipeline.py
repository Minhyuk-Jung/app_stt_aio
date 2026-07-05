"""Pipeline-integrated WER regression for audio fixtures."""

from __future__ import annotations

from unittest.mock import patch

from app.config import Config
from app.session.orchestration import run_batch_pipeline
from core.audio.resample import build_audio_buffer
from core.inject.types import InjectMethod, InjectResult
from core.pipeline.types import StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource
from tests.regression.ko_wer.wer_utils import audio_cases, load_audio_buffer, load_baseline, wer


def test_wer_audio_through_batch_pipeline(tmp_path) -> None:
    """Audio fixture -> run_batch_pipeline -> WER on stage1 text (mock STT)."""
    config = Config.open(tmp_path / "wer_pipeline.db", migrate_backup=False)
    config.bind_injector()
    config.bind_pipeline()
    payload = load_baseline()
    default_max = float(payload.get("max_wer", 0.0))

    try:
        for case in audio_cases(payload):
            audio = load_audio_buffer(case)
            audio = build_audio_buffer(
                audio.pcm_bytes,
                sample_rate=audio.sample_rate,
                channels=audio.channels,
            )
            reference = case["reference"]
            hypothesis = case.get("hypothesis", reference)
            session = config._store.sessions.create(
                source=SessionSource.BATCH,
                mode_id=config.get_active_mode_id(),
            )
            stage = StageArtifact(
                session_id=session.id,
                stage=1,
                text=hypothesis,
                language="ko",
                provider="mock-stt",
            )
            with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
                mock_stage1.return_value = (
                    STTResult(text=hypothesis, language="ko", provider_id="mock-stt"),
                    stage,
                )
                with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
                    mock_inject.return_value = InjectResult(
                        success=True,
                        method_used=InjectMethod.UNICODE,
                        chars_injected=len(hypothesis),
                    )
                    _stt, artifact = run_batch_pipeline(config, session.id, audio)

            score = wer(reference, artifact.text)
            limit = float(case.get("max_wer", default_max))
            assert score <= limit, f"{case['id']}: wer={score:.3f} > {limit}"
            stored = config._store.artifacts.latest_by_stage(session.id, 1)
            assert stored is not None
            assert stored.text == hypothesis
    finally:
        config.close()
