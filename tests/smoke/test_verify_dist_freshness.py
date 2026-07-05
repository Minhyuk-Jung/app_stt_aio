"""Tests for scripts/smoke/verify_dist_freshness.py."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from scripts.smoke.verify_dist_freshness import verify_dist_freshness, write_build_stamp


def test_verify_dist_freshness_warns_when_exe_older_than_pyproject(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist" / "STT-AIO"
    dist.mkdir(parents=True)
    exe = dist / "STT-AIO.exe"
    exe.write_bytes(b"x")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nversion='9.9.9'\n", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.smoke.verify_dist_freshness.VERSION_SOURCES",
        (pyproject,),
    )

    past = time.time() - 3600
    os.utime(exe, (past, past))
    pyproject.touch()

    issues = verify_dist_freshness(exe=exe, strict=False)
    assert issues
    assert any("older than" in issue for issue in issues)


def test_verify_dist_freshness_passes_with_stamp(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist" / "STT-AIO"
    installer = tmp_path / "dist" / "installer"
    dist.mkdir(parents=True)
    installer.mkdir(parents=True)
    exe = dist / "STT-AIO.exe"
    exe.write_bytes(b"x")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nversion='0.1.0'\n", encoding="utf-8")
    manifest = installer / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")

    monkeypatch.setattr("scripts.smoke.verify_dist_freshness.ROOT", tmp_path)
    monkeypatch.setattr("scripts.smoke.verify_dist_freshness.DEFAULT_EXE", exe)
    monkeypatch.setattr("scripts.smoke.verify_dist_freshness.DEFAULT_MANIFEST", manifest)
    monkeypatch.setattr("scripts.smoke.verify_dist_freshness.STAMP_PATH", installer / "build-stamp.json")
    monkeypatch.setattr(
        "scripts.smoke.verify_dist_freshness.VERSION_SOURCES",
        (pyproject,),
    )

    write_build_stamp(version="0.1.0", portable=True, installer=True)
    os.utime(exe, None)
    assert verify_dist_freshness(exe=exe, strict=False) == []
