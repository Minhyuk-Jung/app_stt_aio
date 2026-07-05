"""Frozen/packaged runtime helpers (C16 plan §7)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path | None:
    if not is_frozen():
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass)


def startup_failure_message(error: BaseException) -> str:
    """User-facing hint when packaged app fails to start (plan §7)."""
    from core.paths import get_app_data_root

    logs_dir = get_app_data_root() / "logs"
    lines = [
        f"STT-AIO 시작에 실패했습니다: {error}",
        f"로그 폴더: {logs_dir}",
    ]
    if is_frozen():
        lines.append(
            "설치본 실행 중 오류입니다. 최신 설치 프로그램으로 재설치하거나 "
            "진단 패키지(설정 > 프라이버시)를 보내 주세요."
        )
    else:
        lines.append('개발 환경에서는 pip install -e ".[ui,stt,export]" 를 확인하세요.')
    return "\n".join(lines)
