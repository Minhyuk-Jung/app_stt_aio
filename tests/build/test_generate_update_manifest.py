"""Tests for build/generate_update_manifest.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_update_manifest_from_installer_artifact() -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import build_update_manifest  # noqa: WPS433
    finally:
        sys.path.pop(0)

    build = {
        "product": "STT-AIO",
        "version": "0.2.0",
        "artifacts": [
            {
                "type": "installer",
                "path": "dist/installer/STT-AIO-Setup-0.2.0.exe",
                "sha256": "a" * 64,
            }
        ],
    }
    update = build_update_manifest(
        build,
        download_url="https://example.com/STT-AIO-Setup-0.2.0.exe",
        release_notes="test",
    )
    assert update["version"] == "0.2.0"
    assert update["checksum_sha256"] == "a" * 64
    assert update["download_url"].endswith("0.2.0.exe")


def test_generate_update_manifest_cli(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "product": "STT-AIO",
                "version": "1.0.0",
                "artifacts": [
                    {"type": "installer", "path": "x.exe", "sha256": "b" * 64},
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "update-manifest.json"
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import main  # noqa: WPS433
    finally:
        sys.path.pop(0)

    code = main(
        [
            "--build-manifest",
            str(manifest),
            "--output",
            str(out),
            "--download-url",
            "https://cdn.example/setup.exe",
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["checksum_sha256"] == "b" * 64


def test_verify_update_manifest_rejects_placeholder(tmp_path: Path) -> None:
    manifest = tmp_path / "update-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "download_url": "https://example.com/setup.exe",
                "checksum_sha256": "c" * 64,
            }
        ),
        encoding="utf-8",
    )
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import verify_update_manifest  # noqa: WPS433
    finally:
        sys.path.pop(0)

    failures = verify_update_manifest(manifest, allow_placeholder=False)
    assert failures
    assert any("placeholder" in f.lower() for f in failures)
    assert verify_update_manifest(manifest, allow_placeholder=True) == []


def test_generate_update_manifest_fails_without_real_url(tmp_path: Path) -> None:
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "artifacts": [{"type": "installer", "path": "x.exe", "sha256": "d" * 64}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "update-manifest.json"
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import main  # noqa: WPS433
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
            "https://releases.example.com/STT-AIO-Setup-1.0.0.exe",
        ]
    ) == 0


def test_verify_only_mode(tmp_path: Path) -> None:
    out = tmp_path / "update-manifest.json"
    out.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "download_url": "https://example.com/setup.exe",
                "checksum_sha256": "e" * 64,
            }
        ),
        encoding="utf-8",
    )
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import main  # noqa: WPS433
    finally:
        sys.path.pop(0)

    assert main(["--verify-only", "--output", str(out)]) == 1
    assert main(["--verify-only", "--output", str(out), "--allow-placeholder"]) == 0

