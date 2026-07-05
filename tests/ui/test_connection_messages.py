"""Tests for settings connection messages."""

from __future__ import annotations

from app.ui.settings.connection_messages import format_connection_result
from core.llm.types import ConnResult


def test_format_connection_success() -> None:
    text = format_connection_result(ConnResult(success=True, message="connected"))
    assert "연결 성공" in text


def test_format_connection_auth_failure() -> None:
    text = format_connection_result(ConnResult(success=False, message="401 Unauthorized"))
    assert "인증 실패" in text


def test_format_connection_network_failure() -> None:
    text = format_connection_result(ConnResult(success=False, message="Connection refused"))
    assert "네트워크 오류" in text
