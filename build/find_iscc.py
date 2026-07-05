"""Locate Inno Setup compiler (ISCC) on Windows (C16 §6.2)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_iscc() -> Path | None:
    """Return ISCC executable path, or None if not installed."""
    for name in ("ISCC", "iscc"):
        found = shutil.which(name)
        if found:
            return Path(found)

    program_files = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
    candidates = (
        local_programs,
        Path(program_files) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None
