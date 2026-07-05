"""Stage label helpers for export renderers (C8)."""

from __future__ import annotations

_STAGE_LABELS: dict[int, str] = {
    1: "1차",
    2: "2차",
    3: "3차 리포트",
}

_MEETING_LABELS: dict[int, str] = {
    1: "원문 기록",
    2: "정리본",
    3: "요약/결론",
}

_REPORT_LABELS: dict[int, str] = {
    1: "배경/원문",
    2: "본문",
    3: "결론",
}


def stage_heading(stage: int) -> str:
    return _STAGE_LABELS.get(stage, f"{stage}차")


def meeting_stage_heading(stage: int) -> str:
    return _MEETING_LABELS.get(stage, f"{stage}차")


def report_stage_heading(stage: int) -> str:
    return _REPORT_LABELS.get(stage, f"{stage}차")
