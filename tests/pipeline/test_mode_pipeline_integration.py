"""Pipeline integration for mode routing (C7/C4)."""

from __future__ import annotations

from unittest.mock import patch

from app.config import Config
from core.audio.format import AudioBuffer
from core.pipeline.mode_resolve import resolve_mode_for_session
from core.pipeline.pipeline import Pipeline
from core.pipeline.types import PipelineInput, PipelineStatus, StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource


def _bind_mock_llm(config: Config) -> None:
    from core.llm import MockLLMProvider

    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()


def test_meeting_mode_runs_three_stages_without_inject(tmp_path) -> None:
    config = Config.open(tmp_path / "meeting_pipe.db", migrate_backup=False)
    config.bind_stt_session()
    config.bind_injector()
    _bind_mock_llm(config)
    pipeline = Pipeline(config)

    session = config._store.sessions.create(
        source=SessionSource.BATCH,
        mode_id="meeting",
    )
    mode = resolve_mode_for_session(config, session.id)
    assert mode.inject_stage == 0
    assert mode.target_stage == 3

    inject_events: list[str] = []
    pipeline.on_inject_requested(lambda artifact: inject_events.append(artifact.text))

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="회의", language="ko", provider_id="mock"),
            StageArtifact(
                session_id=session.id,
                stage=1,
                text="회의",
                language="ko",
                provider="mock",
            ),
        )
        with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
            mock_stage2.return_value = (
                StageArtifact(
                    session_id=session.id,
                    stage=2,
                    text="교정본",
                    language="ko",
                    provider="mock",
                ),
                "p2",
            )
            with patch("core.pipeline.pipeline.run_stage3") as mock_stage3:
                mock_stage3.return_value = (
                    StageArtifact(
                        session_id=session.id,
                        stage=3,
                        text="회의록",
                        language="ko",
                        provider="mock",
                    ),
                    "p3",
                )
                with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
                    run = pipeline.run(
                        PipelineInput(
                            source=SessionSource.BATCH,
                            audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                            session_id=session.id,
                        ),
                        mode,
                    )

    assert run.status is PipelineStatus.FINISHED
    mock_inject.assert_not_called()
    assert inject_events == []
    assert run.artifacts[3].text == "회의록"
    config.close()
