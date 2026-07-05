"""Display labels for workbench UI."""

from __future__ import annotations

from core.store.models import SessionSource, SessionStatus

SESSION_STATUS_LABELS: dict[SessionStatus, str] = {
    SessionStatus.RECORDING: "녹음 중",
    SessionStatus.PROCESSING: "처리 중",
    SessionStatus.DONE: "완료",
    SessionStatus.ERROR: "오류",
    SessionStatus.CANCELED: "취소",
}

SESSION_SOURCE_LABELS: dict[SessionSource, str] = {
    SessionSource.BATCH: "일괄",
    SessionSource.REALTIME: "실시간",
    SessionSource.REMOTE: "원격",
}


def format_session_status(status: SessionStatus) -> str:
    return SESSION_STATUS_LABELS.get(status, status.value)
