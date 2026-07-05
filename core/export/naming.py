"""Export filename rules (C8)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


_FORMAT_SUFFIX = {
    "txt": ".txt",
    "md": ".md",
    "docx": ".docx",
}


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", value.strip())
    return cleaned.replace(" ", "_") or "session"


def validate_filename_pattern(pattern: str) -> str | None:
    stripped = pattern.strip()
    if not stripped:
        return "파일명 패턴이 비어 있습니다."
    if any(ch in stripped for ch in '<>:"/\\|?*'):
        return '파일명 패턴에 사용할 수 없는 문자(<>:\"/\\|?*)가 있습니다.'
    return None


def build_export_filename(
    pattern: str,
    *,
    mode_name: str,
    stage: int | str,
    export_format: str,
    when: datetime | None = None,
) -> str:
    moment = when or datetime.now()
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    date_str = moment.strftime("%Y%m%d")
    time_str = moment.strftime("%H%M")
    mode_part = sanitize_filename_part(mode_name)
    stage_part = str(stage)
    filename = (
        pattern.replace("{date}", date_str)
        .replace("{time}", time_str)
        .replace("{mode}", mode_part)
        .replace("{stage}", stage_part)
    )
    suffix = _FORMAT_SUFFIX.get(export_format, f".{export_format}")
    if not filename.lower().endswith(suffix):
        filename = f"{filename}{suffix}"
    return filename


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
