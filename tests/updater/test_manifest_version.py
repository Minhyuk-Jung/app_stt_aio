"""Tests for C22 manifest and version helpers."""

from __future__ import annotations

from core.updater.manifest import get_release_notes, parse_manifest
from core.updater.version import is_newer_version, parse_version


def test_parse_version_numeric_parts() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v0.10.0") == (0, 10, 0)
    assert parse_version("0.1.0-beta") == (0, 1, 0)


def test_is_newer_version_semantics() -> None:
    assert is_newer_version("0.2.0", "0.1.0")
    assert is_newer_version("1.0.0", "0.9.9")
    assert not is_newer_version("0.1.0", "0.1.0")
    assert not is_newer_version("0.1.0", "0.2.0")


def test_parse_manifest_notes_by_version() -> None:
    manifest = parse_manifest(
        {
            "version": "1.0.0",
            "release_notes": "default notes",
            "notes_by_version": {"1.0.0": "specific notes"},
        }
    )
    assert get_release_notes(manifest) == "specific notes"
    assert get_release_notes(manifest, "0.9.0") == "default notes"
