"""Tests for app.packaged_smoke (invoked via STT-AIO.exe --smoke in CI)."""

from __future__ import annotations

from app.packaged_smoke import run_packaged_smoke


def test_run_packaged_smoke_passes() -> None:
    assert run_packaged_smoke() == 0
