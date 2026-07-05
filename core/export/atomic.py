"""Atomic file writes for export (C8)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


def atomic_write(dest_path: Path, writer: Callable[[Path], None]) -> None:
    """Write to a temp file in the same directory, then replace dest atomically."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_name(f".{dest_path.name}.{os.getpid()}.exporting")
    try:
        if temp_path.exists():
            temp_path.unlink()
        writer(temp_path)
        os.replace(temp_path, dest_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
