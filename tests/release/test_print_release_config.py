"""Tests for scripts/release/print_release_config.py."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_print_release_config_outputs_manifest_url(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "1.2.0"}), encoding="utf-8")
    (tmp_path / "STT-AIO-Setup-1.2.0.exe").write_bytes(b"x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/stt-aio")
    if str(ROOT) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(ROOT))
    from scripts.release.print_release_config import main  # noqa: WPS433

    assert main(["--build-manifest", str(manifest), "--tag", "v1.2.0"]) == 0
    out = capsys.readouterr().out
    assert "manifest_url=https://github.com/acme/stt-aio/releases/download/v1.2.0/update-manifest.json" in out
    assert "update.manifest_url=" in out


def test_print_release_config_fails_on_tag_mismatch(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (tmp_path / "STT-AIO-Setup-1.0.0.exe").write_bytes(b"x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/stt-aio")
    if str(ROOT) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(ROOT))
    from scripts.release.print_release_config import main  # noqa: WPS433

    assert main(["--build-manifest", str(manifest), "--tag", "v9.9.9"]) == 1
