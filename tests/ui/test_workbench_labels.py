"""Tests for workbench display labels."""

from core.store.models import SessionStatus
from app.ui.workbench.labels import format_session_status


def test_format_session_status_korean() -> None:
    assert format_session_status(SessionStatus.DONE) == "완료"
    assert format_session_status(SessionStatus.PROCESSING) == "처리 중"
