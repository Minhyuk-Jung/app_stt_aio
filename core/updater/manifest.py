"""Remote update manifest parsing (C22 §6.1 manifest.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    download_url: str | None
    release_notes: str
    checksum_sha256: str | None
    mandatory: bool
    notes_by_version: dict[str, str]


def parse_manifest(payload: dict[str, Any]) -> UpdateManifest:
    """Parse a remote update manifest JSON object."""
    notes_by_version: dict[str, str] = {}
    raw_notes = payload.get("notes_by_version")
    if isinstance(raw_notes, dict):
        notes_by_version = {
            str(key): str(value)
            for key, value in raw_notes.items()
            if str(value).strip()
        }

    return UpdateManifest(
        version=str(payload.get("version", "")).strip(),
        download_url=_optional_str(payload.get("download_url")),
        release_notes=str(payload.get("release_notes", "")).strip(),
        checksum_sha256=_optional_str(payload.get("checksum_sha256")),
        mandatory=bool(payload.get("mandatory", False)),
        notes_by_version=notes_by_version,
    )


def get_release_notes(manifest: UpdateManifest, version: str | None = None) -> str:
    """Return release notes for *version* or the manifest default."""
    target = (version or manifest.version).strip()
    if target and target in manifest.notes_by_version:
        return manifest.notes_by_version[target]
    return manifest.release_notes


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
