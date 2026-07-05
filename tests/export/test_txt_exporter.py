"""Tests for minimal text/markdown export."""

from __future__ import annotations

from core.export import export_markdown_file, export_text_file, render_session_markdown


def test_export_text_file_writes_utf8(tmp_path) -> None:
    dest = tmp_path / "nested" / "note.txt"
    result = export_text_file(dest, "한글 테스트")
    assert result.success is True
    assert dest.read_text(encoding="utf-8") == "한글 테스트"


def test_export_markdown_file_writes_utf8(tmp_path) -> None:
    dest = tmp_path / "note.md"
    result = export_markdown_file(dest, "본문", title="제목")
    assert result.success is True
    content = dest.read_text(encoding="utf-8")
    assert content.startswith("# 제목")
    assert "본문" in content


def test_render_session_markdown_includes_meta_and_stages() -> None:
    body = render_session_markdown(
        session_id="abc",
        mode_name="빠른 받아쓰기",
        created_at="2026-01-01 12:00",
        stages={1: "1차", 2: "2차"},
        include_meta=True,
    )
    assert "abc" in body
    assert "## 1차" in body
    assert "## 2차" in body
