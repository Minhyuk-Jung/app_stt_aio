"""Tests for C13 WorkbenchController."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Config
from app.ui.workbench.controller import (
    DEFAULT_PAGE_SIZE,
    WorkbenchController,
    WorkbenchNotImplementedError,
)
from core.export import ExportTarget
from core.store.models import SessionSource, SessionStatus


@pytest.fixture
def workbench(tmp_path):
    config = Config.open(tmp_path / "wb.db", migrate_backup=False)
    controller = WorkbenchController(config)
    yield controller, config
    config.close()


def test_list_sessions_empty(workbench) -> None:
    controller, _config = workbench
    assert controller.list_sessions() == []
    assert controller.count_sessions() == 0


def test_session_detail_with_artifacts(workbench) -> None:
    controller, config = workbench
    session = config._store.sessions.create(
        source=SessionSource.BATCH,
        status=SessionStatus.DONE,
        mode_id="quick-dictation",
    )
    config._store.artifacts.add(session.id, 1, "1차 텍스트", provider="stt")
    config._store.artifacts.add(session.id, 2, "2차 텍스트", provider="llm")

    summaries = controller.list_sessions()
    assert len(summaries) == 1
    assert summaries[0].preview_text == "1차 텍스트"

    detail = controller.get_session_detail(session.id)
    assert detail is not None
    assert detail.artifacts[1].text == "1차 텍스트"
    assert detail.artifacts[2].text == "2차 텍스트"
    assert detail.mode_name == "빠른 받아쓰기"


def test_update_artifact_text(workbench) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    artifact = config._store.artifacts.add(session.id, 1, "원문", provider="stt")

    updated = controller.update_artifact_text(artifact.id, "수정본")
    assert updated is not None
    assert updated.text == "수정본"


def test_resolve_default_export_path_uses_session_time(workbench) -> None:
    from datetime import datetime, timezone

    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.sessions.update_status(session.id, SessionStatus.DONE)
    fetched = config._store.sessions.get(session.id)
    assert fetched is not None

    path = controller.resolve_default_export_path(session.id, 1, export_format="txt", unique=False)
    local = fetched.created_at.astimezone()
    assert local.strftime("%Y%m%d") in path.name
    assert local.strftime("%H%M") in path.name


def test_request_export_txt(workbench, tmp_path) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "보낼 내용", provider="stt")

    dest = tmp_path / "out.txt"
    result = controller.request_export(session.id, 1, dest)
    assert result.success is True
    assert dest.read_text(encoding="utf-8-sig") == "보낼 내용"


def test_request_export_uses_text_override(workbench, tmp_path) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "DB 내용", provider="stt")

    dest = tmp_path / "edited.txt"
    result = controller.request_export(
        session.id,
        1,
        dest,
        text_override="편집 중 내용",
    )
    assert result.success is True
    assert dest.read_text(encoding="utf-8-sig") == "편집 중 내용"


def test_request_export_md(workbench, tmp_path) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "md 본문", provider="stt")

    dest = tmp_path / "out.md"
    result = controller.request_export(session.id, 1, dest, export_format="md")
    assert result.success is True
    content = dest.read_text(encoding="utf-8")
    assert "md 본문" in content


def test_request_export_target_all_stages_md(workbench, tmp_path) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "1차", provider="stt")
    config._store.artifacts.add(session.id, 2, "2차", provider="llm")

    dest = tmp_path / "all.md"
    target = ExportTarget(session_id=session.id, stages=(1, 2), include_meta=True)
    result = controller.request_export_target(target, dest, export_format="md")
    assert result.success is True
    content = dest.read_text(encoding="utf-8")
    assert "1차" in content
    assert "2차" in content
    assert session.id in content


def test_list_sessions_pagination_and_status_filter(workbench) -> None:
    controller, config = workbench
    for status in (SessionStatus.DONE, SessionStatus.ERROR, SessionStatus.DONE):
        config._store.sessions.create(source=SessionSource.BATCH, status=status)

    assert controller.count_sessions() == 3
    assert controller.count_sessions(status=SessionStatus.DONE) == 2
    page = controller.list_sessions(limit=DEFAULT_PAGE_SIZE, offset=0, status=SessionStatus.DONE)
    assert len(page) == 2


def test_search_sessions_matches_artifact_text(workbench) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH, status=SessionStatus.DONE)
    config._store.artifacts.add(session.id, 1, "고유키워드ABC", provider="stt")
    config._store.sessions.create(source=SessionSource.BATCH, status=SessionStatus.DONE)

    results = controller.list_sessions(query="고유키워드ABC")
    assert len(results) == 1
    assert results[0].id == session.id
    assert controller.count_sessions(query="고유키워드ABC") == 1


def test_list_sessions_mode_filter(workbench) -> None:
    controller, config = workbench
    config._store.sessions.create(
        source=SessionSource.BATCH,
        status=SessionStatus.DONE,
        mode_id="quick-dictation",
    )
    config._store.sessions.create(
        source=SessionSource.BATCH,
        status=SessionStatus.DONE,
        mode_id="meeting",
    )

    assert controller.count_sessions(mode_id="meeting") == 1
    listed = controller.list_sessions(mode_id="meeting")
    assert len(listed) == 1


def test_get_focus_session_id_prefers_processing(workbench) -> None:
    controller, config = workbench
    done = config._store.sessions.create(source=SessionSource.BATCH, status=SessionStatus.DONE)
    processing = config._store.sessions.create(
        source=SessionSource.BATCH,
        status=SessionStatus.PROCESSING,
    )

    class _FakeSessions:
        processing_session_id = processing.id
        recording_session_id = None

        def on_session_state(self, _callback) -> None:
            return None

    controller_with_sessions = WorkbenchController(config, session_manager=_FakeSessions())  # type: ignore[arg-type]
    assert controller_with_sessions.get_focus_session_id() == processing.id

    controller_latest = WorkbenchController(config)
    assert controller_latest.get_focus_session_id() == processing.id


def test_bind_pipeline_emits_stage_completed(workbench) -> None:
    controller, config = workbench
    config.bind_pipeline()

    events: list[tuple[str, int]] = []
    controller.bind_pipeline(config.pipeline)
    controller.on_stage_completed(lambda sid, stage: events.append((sid, stage)))

    from core.pipeline.types import StageArtifact

    artifact = StageArtifact(session_id="sess-1", stage=2, text="x", language="ko")
    config.pipeline._events.emit_stage_completed(2, artifact)
    assert events == [("sess-1", 2)]


def test_request_reprocess_runs_pipeline(workbench) -> None:
    controller, config = workbench
    from core.llm import MockLLMProvider

    config.bind_llm_session()
    config._llm_session._providers["ollama"] = MockLLMProvider()
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "원문", provider="stt")

    with patch("core.pipeline.pipeline.run_stage2") as mock_stage2:
        from core.pipeline.types import StageArtifact

        mock_stage2.return_value = (
            StageArtifact(session_id=session.id, stage=2, text="교정", language="ko"),
            "prompt",
        )
        result = controller.request_reprocess(session.id, 2)

    assert result.success is True
    assert 2 in result.stages_completed


def test_unsupported_export_format_suggests_alternatives(workbench, tmp_path) -> None:
    controller, config = workbench
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "x", provider="stt")

    result = controller.request_export(
        session.id,
        1,
        Path(tmp_path / "out.pdf"),
        export_format="pdf",
    )
    assert result.success is False
    assert result.suggestion is not None


@pytest.mark.skipif(
    __import__("core.export", fromlist=["docx_dependency_available"]).docx_dependency_available()
    is False,
    reason="python-docx not installed",
)
def test_request_export_docx_uses_config_default_template(workbench, tmp_path) -> None:
    controller, config = workbench
    config.set("export.default_docx_template", "meeting")
    session = config._store.sessions.create(source=SessionSource.BATCH)
    config._store.artifacts.add(session.id, 1, "회의 내용", provider="stt")

    dest = tmp_path / "out.docx"
    result = controller.request_export(session.id, 1, dest, export_format="docx")
    assert result.success is True

    from docx import Document

    doc = Document(str(dest))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "회의록" in text
