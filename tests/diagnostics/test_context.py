"""Tests for log context (C20)."""

from __future__ import annotations

from core.diagnostics.context import bind_context, clear_context, format_context_suffix, log_context


def test_bind_and_format_context() -> None:
    clear_context()
    bind_context(session_id="abc", component="stt")
    suffix = format_context_suffix()
    assert "session_id=abc" in suffix
    assert "component=stt" in suffix


def test_log_context_manager_restores() -> None:
    clear_context()
    bind_context(session_id="outer")
    with log_context(stage=2):
        suffix = format_context_suffix()
        assert "stage=2" in suffix
        assert "session_id=outer" in suffix
    assert "stage=2" not in format_context_suffix()
    assert "session_id=outer" in format_context_suffix()
    clear_context()
