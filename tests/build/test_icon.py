"""C16 icon generation tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generate_icon_writes_valid_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_icon import write_icon  # noqa: WPS433

        target = tmp_path / "icon.ico"
        write_icon(target)
        data = target.read_bytes()
        assert data[:2] == b"\x00\x00" or data[:4] == b"\x00\x00\x01\x00"
        assert len(data) > 100
    finally:
        sys.path.pop(0)
