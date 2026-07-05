"""Tests for scripts/release/prepare_release_manifest.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prepare_release_manifest_requires_real_url(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "artifacts": [{"type": "installer", "path": "x.exe", "sha256": "f" * 64}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "update-manifest.json"
    sys.path.insert(0, str(ROOT / "scripts" / "release"))
    try:
        from prepare_release_manifest import main  # noqa: WPS433
    finally:
        sys.path.pop(0)

    assert main(["--build-manifest", str(manifest), "--output", str(out)]) == 1
    assert main(
        [
            "--build-manifest",
            str(manifest),
            "--output",
            str(out),
            "--download-url",
            "https://github.com/org/repo/releases/download/v2.0.0/STT-AIO-Setup-2.0.0.exe",
        ]
    ) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["version"] == "2.0.0"
    assert "github.com" in payload["download_url"]


def test_prepare_release_manifest_rejects_tag_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "artifacts": [{"type": "installer", "path": "x.exe", "sha256": "a" * 64}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "STT-AIO-Setup-1.0.0.exe").write_bytes(b"x")
    out = tmp_path / "update-manifest.json"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.release.prepare_release_manifest import main  # noqa: WPS433

    assert (
        main(
            [
                "--build-manifest",
                str(manifest),
                "--output",
                str(out),
                "--github-release",
                "--tag",
                "v2.0.0",
            ]
        )
        == 1
    )


def test_prepare_release_manifest_github_release(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.5.0",
                "artifacts": [{"type": "installer", "path": "x.exe", "sha256": "a" * 64}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "STT-AIO-Setup-1.5.0.exe").write_bytes(b"x")
    out = tmp_path / "update-manifest.json"
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/stt-aio")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.release.prepare_release_manifest import main  # noqa: WPS433

    assert main(
        [
            "--build-manifest",
            str(manifest),
            "--output",
            str(out),
            "--github-release",
            "--tag",
            "v1.5.0",
        ]
    ) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "github.com/acme/stt-aio/releases/download/v1.5.0/" in payload["download_url"]
