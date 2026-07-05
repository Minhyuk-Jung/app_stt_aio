"""Pipeline stage2/3 integration tests."""

from __future__ import annotations

from unittest.mock import patch

from app.config import Config
from core.audio.format import AudioBuffer
from core.inject.types import InjectMethod, InjectResult
from core.llm import MockLLMProvider
from core.pipeline import Pipeline, PipelineInput, PipelineMode, PipelineStatus, StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource


def _bind_mock_llm(config: Config) -> None:
    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()


def _stage1_artifact(session_id: str, text: str = "원문") -> StageArtifact:
    return StageArtifact(
        session_id=session_id,
        stage=1,
        text=text,
        language="ko",
        provider="mock-stt",
    )


def test_pipeline_runs_stage2_and_injects_at_stage2(tmp_path) -> None:
    config = Config.open(tmp_path / "p2.db", migrate_backup=False)
    _bind_mock_llm(config)
    session = config._store.sessions.create(source=SessionSource.BATCH, mode_id="polish")
    pipeline = Pipeline(config)

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="원문", language="ko", provider_id="mock-stt"),
            _stage1_artifact(session.id),
        )
        with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
            mock_stage2.return_value = (
                StageArtifact(
                    session_id=session.id,
                    stage=2,
                    text="다듬어진 문장",
                    language="ko",
                    provider="mock",
                ),
                "prompt-snapshot",
            )
            with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
                mock_inject.return_value = InjectResult(
                    success=True,
                    method_used=InjectMethod.UNICODE,
                    chars_injected=6,
                )
                run = pipeline.run(
                    PipelineInput(
                        source=SessionSource.BATCH,
                        audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                        session_id=session.id,
                    ),
                    PipelineMode(id="polish", target_stage=2, inject_stage=2),
                )

    assert run.status is PipelineStatus.FINISHED
    mock_inject.assert_called_once()
    assert run.artifacts[2].text == "다듬어진 문장"
    config.close()


def test_pipeline_stage2_failure_preserves_stage1(tmp_path) -> None:
    config = Config.open(tmp_path / "p2_fail.db", migrate_backup=False)
    _bind_mock_llm(config)
    session = config._store.sessions.create(source=SessionSource.BATCH)
    pipeline = Pipeline(config)

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="원문", language="ko", provider_id="mock-stt"),
            _stage1_artifact(session.id),
        )
        with patch("core.pipeline.pipeline.run_stage2", side_effect=RuntimeError("llm down")):
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                    session_id=session.id,
                ),
                PipelineMode(id="polish", target_stage=2, inject_stage=2),
            )

    assert run.status is PipelineStatus.ERROR
    assert run.error_stage == 2
    assert config._store.artifacts.latest_by_stage(session.id, 1) is not None
    config.close()


def test_run_stage2_uses_mock_llm(tmp_path) -> None:
    config = Config.open(tmp_path / "stage2.db", migrate_backup=False)
    _bind_mock_llm(config)
    session = config._store.sessions.create(
        source=SessionSource.BATCH,
        mode_id="polish",
    )

    from core.pipeline.stages import run_stage2

    artifact, snapshot = run_stage2(config, session.id, "원문")
    assert "원문" in artifact.text
    assert snapshot
    config.close()


def test_run_stage2_skips_llm_on_empty_text(tmp_path) -> None:
    config = Config.open(tmp_path / "stage2_empty.db", migrate_backup=False)
    _bind_mock_llm(config)
    session = config._store.sessions.create(
        source=SessionSource.BATCH,
        mode_id="polish",
    )

    from core.pipeline.stages import run_stage2

    with patch.object(config.llm_session, "complete") as mock_complete:
        artifact, _snapshot = run_stage2(config, session.id, "   ")

    mock_complete.assert_not_called()
    assert artifact.provider is None
    config.close()
