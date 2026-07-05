"""Tests for C8 Exporter."""

from __future__ import annotations

from datetime import datetime, timezone

from pathlib import Path

import pytest

from core.export import (
    ExportPayload,
    ExportTarget,
    available_templates,
    build_export_filename,
    docx_dependency_available,
    ensure_unique_path,
    export,
    export_session,
    render_session_markdown,
)
from core.export.atomic import atomic_write
from core.export.naming import sanitize_filename_part, validate_filename_pattern
from core.export.stages import stage_heading


@pytest.fixture
def payload() -> ExportPayload:
    return ExportPayload(
        session_id="sess-1",
        mode_name="빠른 받아쓰기",
        created_at=datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
        stages={1: "1차 본문", 2: "2차 정리"},
        providers={1: "stt", 2: "llm"},
    )


def test_build_export_filename_adds_suffix() -> None:
    name = build_export_filename(
        "{date}-{time}_{mode}_{stage}",
        mode_name="빠른 받아쓰기",
        stage=1,
        export_format="docx",
        when=datetime(2026, 7, 4, 9, 15),
    )
    assert name.endswith(".docx")
    assert "20260704-0915" in name


def test_stage_heading_for_report_stage() -> None:
    assert stage_heading(3) == "3차 리포트"


def test_atomic_write_preserves_existing_dest(tmp_path) -> None:
    dest = tmp_path / "out.txt"
    dest.write_text("original", encoding="utf-8")

    def boom(temp: Path) -> None:
        temp.write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    with pytest.raises(OSError):
        atomic_write(dest, boom)
    assert dest.read_text(encoding="utf-8") == "original"
    leftovers = list(tmp_path.glob("*.exporting"))
    assert leftovers == []


def test_export_alias_matches_export_session(tmp_path, payload) -> None:
    dest = tmp_path / "alias.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))
    result = export(target, dest, "txt", payload)
    assert result.success is True
    assert dest.read_text(encoding="utf-8-sig") == "1차 본문"


def test_export_session_unicode_and_emoji(tmp_path, payload) -> None:
    rich = ExportPayload(
        session_id=payload.session_id,
        mode_name=payload.mode_name,
        created_at=payload.created_at,
        stages={1: "한글 🎤 <특수> \"인용\""},
    )
    dest = tmp_path / "unicode.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))
    result = export_session(rich, target, dest, "txt")
    assert result.success is True
    assert "🎤" in dest.read_text(encoding="utf-8")


def test_export_session_long_text(tmp_path, payload) -> None:
    long_text = "가" * 50_000
    large = ExportPayload(
        session_id=payload.session_id,
        mode_name=payload.mode_name,
        created_at=payload.created_at,
        stages={1: long_text},
    )
    dest = tmp_path / "long.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))
    result = export_session(large, target, dest, "txt")
    assert result.success is True
    assert len(dest.read_text(encoding="utf-8-sig")) == 50_000


def test_sanitize_filename_part() -> None:
    assert sanitize_filename_part('bad<>name') == "bad__name"


def test_validate_filename_pattern_rejects_invalid() -> None:
    assert validate_filename_pattern("") is not None
    assert validate_filename_pattern('bad|pattern') is not None
    assert validate_filename_pattern("{date}_{mode}") is None


def test_build_export_filename_uses_local_session_time() -> None:
    from datetime import timezone

    utc = datetime(2026, 7, 4, 3, 30, tzinfo=timezone.utc)
    name = build_export_filename(
        "{date}-{time}_{mode}_{stage}",
        mode_name="test",
        stage=1,
        export_format="txt",
        when=utc,
    )
    local = utc.astimezone()
    assert local.strftime("%Y%m%d") in name
    assert local.strftime("%H%M") in name


def test_ensure_unique_path(tmp_path) -> None:
    base = tmp_path / "note.txt"
    base.write_text("a", encoding="utf-8")
    unique = ensure_unique_path(base)
    assert unique.name == "note (1).txt"


def test_export_session_txt(tmp_path, payload) -> None:
    dest = tmp_path / "out.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))
    result = export_session(payload, target, dest, "txt")
    assert result.success is True
    assert dest.read_text(encoding="utf-8-sig") == "1차 본문"


def test_export_session_md_with_meta(tmp_path, payload) -> None:
    dest = tmp_path / "out.md"
    target = ExportTarget(session_id="sess-1", stages=(1, 2), include_meta=True)
    result = export_session(payload, target, dest, "md")
    assert result.success is True
    content = dest.read_text(encoding="utf-8")
    assert "sess-1" in content
    assert "## 1차" in content
    assert "2차 정리" in content


def test_export_session_rejects_empty_text(tmp_path, payload) -> None:
    empty = ExportPayload(
        session_id="sess-1",
        mode_name="m",
        created_at=payload.created_at,
        stages={1: "   "},
    )
    dest = tmp_path / "empty.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))
    result = export_session(empty, target, dest, "txt")
    assert result.success is False
    assert not dest.exists()


def test_export_session_atomic_on_failure(tmp_path, payload, monkeypatch) -> None:
    dest = tmp_path / "out.txt"
    target = ExportTarget(session_id="sess-1", stages=(1,))

    def boom(_path):
        raise OSError("disk full")

    monkeypatch.setattr("core.export.exporter.atomic_write", boom)
    result = export_session(payload, target, dest, "txt")
    assert result.success is False
    assert result.suggestion is not None


@pytest.mark.skipif(not docx_dependency_available(), reason="python-docx not installed")
def test_export_session_docx(tmp_path, payload) -> None:
    dest = tmp_path / "out.docx"
    target = ExportTarget(session_id="sess-1", stages=(1, 2), template="meeting", include_meta=True)
    result = export_session(payload, target, dest, "docx")
    assert result.success is True
    assert dest.stat().st_size > 0

    from docx import Document

    doc = Document(str(dest))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "회의록" in text
    assert "1차 본문" in text


def test_available_templates_docx() -> None:
    templates = available_templates("docx")
    assert {item.id for item in templates} >= {"basic", "meeting", "report"}


def test_render_session_markdown_compat() -> None:
    body = render_session_markdown(
        session_id="abc",
        mode_name="모드",
        created_at="2026-07-04 12:00",
        stages={1: "본문"},
        include_meta=True,
    )
    assert "abc" in body
    assert "본문" in body
