"""Pipeline stage artifacts to C8 export E2E (C4 §10, README P2)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.config import Config
from core.audio.format import AudioBuffer
from core.export import ExportPayload, ExportTarget, docx_dependency_available, export_session
from core.inject.types import InjectMethod, InjectResult
from core.pipeline import Pipeline, PipelineInput, PipelineStatus, StageArtifact
from core.pipeline.mode_resolve import resolve_mode_for_session
from core.stt.types import STTResult
from core.store.models import SessionSource


def _bind_mock_llm(config: Config) -> None:
    from core.llm import MockLLMProvider

    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()


@pytest.fixture
def pipeline_env(tmp_path):
    config = Config.open(tmp_path / "export_e2e.db", migrate_backup=False)
    config.bind_stt_session()
    config.bind_injector()
    session = config._store.sessions.create(source=SessionSource.BATCH)
    pipeline = Pipeline(config)
    yield config, pipeline, session.id
    config.close()


def test_pipeline_stage1_export_txt_and_md(pipeline_env, tmp_path) -> None:
    """Audio -> stage1 pipeline -> persisted artifact -> txt/md export."""
    config, pipeline, session_id = pipeline_env
    stored_session = config._store.sessions.get(session_id)
    assert stored_session is not None

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="안녕하세요", language="ko", provider_id="mock-stt"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="안녕하세요",
                language="ko",
                provider="mock-stt",
            ),
        )
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=5,
            )
            run = pipeline.run(
                PipelineInput(
                    source=SessionSource.BATCH,
                    audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                    session_id=session_id,
                )
            )

    assert run.status is PipelineStatus.FINISHED
    artifact = config._store.artifacts.latest_by_stage(session_id, 1)
    assert artifact is not None
    assert artifact.text == "안녕하세요"

    payload = ExportPayload(
        session_id=session_id,
        mode_name="",
        created_at=stored_session.created_at or datetime.now(timezone.utc),
        stages={1: artifact.text},
        providers={1: artifact.provider or "mock-stt"},
    )
    target = ExportTarget(session_id=session_id, stages=(1,), include_meta=False)

    txt_dest = tmp_path / "session.txt"
    txt_result = export_session(payload, target, txt_dest, "txt")
    assert txt_result.success is True
    assert "안녕하세요" in txt_dest.read_text(encoding="utf-8-sig")

    md_dest = tmp_path / "session.md"
    md_result = export_session(payload, target, md_dest, "md")
    assert md_result.success is True
    assert "안녕하세요" in md_dest.read_text(encoding="utf-8")


@pytest.mark.skipif(not docx_dependency_available(), reason="python-docx not installed")
def test_pipeline_meeting_mode_export_docx(pipeline_env, tmp_path) -> None:
    """Meeting mode 1→2→3 pipeline -> persisted artifacts -> docx export (C4/C8)."""
    config, pipeline, _session_id = pipeline_env
    _bind_mock_llm(config)

    session = config._store.sessions.create(
        source=SessionSource.BATCH,
        mode_id="meeting",
    )
    mode = resolve_mode_for_session(config, session.id)
    stored_session = config._store.sessions.get(session.id)
    assert stored_session is not None
    assert mode.target_stage == 3

    with patch("core.pipeline.pipeline.run_stage1") as mock_stage1:
        mock_stage1.return_value = (
            STTResult(text="회의 시작", language="ko", provider_id="mock-stt"),
            StageArtifact(
                session_id=session.id,
                stage=1,
                text="회의 시작",
                language="ko",
                provider="mock-stt",
            ),
        )
        with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
            mock_stage2.return_value = (
                StageArtifact(
                    session_id=session.id,
                    stage=2,
                    text="교정된 회의 시작",
                    language="ko",
                    provider="mock-llm",
                ),
                "prompt-2",
            )
            with patch("core.pipeline.pipeline.run_stage3") as mock_stage3:
                mock_stage3.return_value = (
                    StageArtifact(
                        session_id=session.id,
                        stage=3,
                        text="회의록 요약 본문",
                        language="ko",
                        provider="mock-llm",
                    ),
                    "prompt-3",
                )
                with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
                    mock_inject.return_value = InjectResult(
                        success=True,
                        method_used=InjectMethod.UNICODE,
                        chars_injected=0,
                    )
                    run = pipeline.run(
                        PipelineInput(
                            source=SessionSource.BATCH,
                            audio=AudioBuffer(pcm_bytes=b"\x00\x01"),
                            session_id=session.id,
                        ),
                        mode,
                    )

    assert run.status is PipelineStatus.FINISHED
    artifacts = {
        stage: config._store.artifacts.latest_by_stage(session.id, stage)
        for stage in (1, 2, 3)
    }
    assert all(artifacts[s] is not None for s in artifacts)

    payload = ExportPayload(
        session_id=session.id,
        mode_name="회의",
        created_at=stored_session.created_at or datetime.now(timezone.utc),
        stages={stage: artifacts[stage].text for stage in artifacts},
        providers={stage: artifacts[stage].provider or "mock" for stage in artifacts},
    )
    target = ExportTarget(
        session_id=session.id,
        stages=(1, 2, 3),
        include_meta=True,
        template="meeting",
    )
    docx_dest = tmp_path / "meeting.docx"
    result = export_session(payload, target, docx_dest, "docx")
    assert result.success is True
    assert docx_dest.stat().st_size > 0

    from docx import Document

    document = Document(str(docx_dest))
    body = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "회의 시작" in body or "교정된 회의 시작" in body
    assert "회의록 요약 본문" in body
