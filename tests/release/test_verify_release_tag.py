"""Tests for scripts/release/verify_release_tag.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.release.verify_release_tag import tag_to_version, verify_release_tag


def test_tag_to_version() -> None:
    assert tag_to_version("v0.2.0") == "0.2.0"
    assert tag_to_version("0.2.0") == "0.2.0"


def test_verify_release_tag_passes_when_aligned(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "1.2.3", "artifacts": []}), encoding="utf-8")
    (tmp_path / "STT-AIO-Setup-1.2.3.exe").write_bytes(b"x")
    assert verify_release_tag("v1.2.3", manifest) == []


def test_verify_release_tag_fails_on_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (tmp_path / "STT-AIO-Setup-1.0.0.exe").write_bytes(b"x")
    failures = verify_release_tag("v2.0.0", manifest)
    assert failures
    assert any("does not match" in f for f in failures)


def test_verify_release_tag_requires_installer_exe(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    failures = verify_release_tag("v1.0.0", manifest)
    assert any("installer" in f.lower() for f in failures)
