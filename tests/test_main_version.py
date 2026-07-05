"""CLI entry tests."""

from __future__ import annotations

from unittest.mock import patch

from app.main import main


def test_main_version_flag() -> None:
    with patch("sys.argv", ["stt-aio", "--version"]):
        assert main() == 0
