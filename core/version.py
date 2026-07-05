"""Application version (C16 — synced with pyproject.toml / build/version.py)."""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

APP_NAME = "STT-AIO"


@lru_cache(maxsize=1)
def get_version() -> str:
    from core.runtime import is_frozen

    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        version_file = exe_dir / "VERSION.txt"
        if version_file.is_file():
            text = version_file.read_text(encoding="utf-8").strip()
            if text:
                return text
    try:
        from importlib.metadata import version

        return version("stt-aio")
    except Exception:  # noqa: BLE001
        pass
    root = Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        if match:
            return match.group(1)
    return "0.0.0-dev"


__version__ = get_version()
