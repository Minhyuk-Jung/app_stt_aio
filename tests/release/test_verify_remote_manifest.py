"""Tests for scripts/release/verify_remote_manifest.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.release.verify_remote_manifest import verify_remote_manifest


def test_verify_remote_manifest_validates_payload(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "version": "1.0.0",
        "download_url": "https://github.com/acme/stt/releases/download/v1.0.0/STT-AIO-Setup-1.0.0.exe",
        "checksum_sha256": "a" * 64,
        "release_notes": "notes",
    }
    local = tmp_path / "manifest.json"
    local.write_text(json.dumps(payload), encoding="utf-8")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return local.read_bytes()

    monkeypatch.setattr(
        "scripts.release.verify_remote_manifest.urllib.request.urlopen",
        lambda *a, **k: _Response(),
    )
    assert verify_remote_manifest("https://example.com/manifest.json") == []


def test_verify_remote_manifest_detects_version_mismatch(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "version": "1.0.0",
        "download_url": "https://github.com/acme/stt/releases/download/v1.0.0/STT-AIO-Setup-1.0.0.exe",
        "checksum_sha256": "b" * 64,
    }
    local = tmp_path / "manifest.json"
    local.write_text(json.dumps(payload), encoding="utf-8")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return local.read_bytes()

    monkeypatch.setattr(
        "scripts.release.verify_remote_manifest.urllib.request.urlopen",
        lambda *a, **k: _Response(),
    )
    failures = verify_remote_manifest(
        "https://example.com/manifest.json",
        expected_version="2.0.0",
    )
    assert failures
    assert any("expected" in f for f in failures)
