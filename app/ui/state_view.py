"""Overlay display state mapping (C12, Qt-free)."""

from __future__ import annotations

from enum import Enum

from core.store.models import SessionStatus


class OverlayDisplayState(str, Enum):
    HIDDEN = "hidden"
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


_STATUS_TO_OVERLAY: dict[SessionStatus, OverlayDisplayState] = {
    SessionStatus.RECORDING: OverlayDisplayState.RECORDING,
    SessionStatus.PROCESSING: OverlayDisplayState.PROCESSING,
    SessionStatus.DONE: OverlayDisplayState.IDLE,
    SessionStatus.ERROR: OverlayDisplayState.ERROR,
    SessionStatus.CANCELED: OverlayDisplayState.IDLE,
}


def map_session_status(status: SessionStatus) -> OverlayDisplayState:
    return _STATUS_TO_OVERLAY.get(status, OverlayDisplayState.IDLE)


def overlay_status_text(
    state: OverlayDisplayState,
    *,
    mode_name: str | None = None,
    processing_stage: int | None = None,
) -> str:
    labels = {
        OverlayDisplayState.HIDDEN: "",
        OverlayDisplayState.IDLE: "대기",
        OverlayDisplayState.RECORDING: "녹음 중",
        OverlayDisplayState.PROCESSING: "처리 중",
        OverlayDisplayState.ERROR: "오류",
    }
    text = labels.get(state, "")
    if state is OverlayDisplayState.PROCESSING and processing_stage:
        stage_labels = {1: "1차 STT", 2: "2차 교정", 3: "3차 리포트"}
        text = f"처리 중 · {stage_labels.get(processing_stage, f'{processing_stage}차')}"
    if state is OverlayDisplayState.IDLE and mode_name:
        return f"{text} · {mode_name}"
    return text
