"""Version check and update manifest (C22)."""

from __future__ import annotations

import json
import logging
import urllib.request

from core.updater.manifest import UpdateManifest, get_release_notes, parse_manifest
from core.updater.version import is_newer_version
from core.version import __version__

logger = logging.getLogger(__name__)


class UpdateInfo:
    """Update metadata returned by check_for_updates (C22 §3)."""

    __slots__ = (
        "current_version",
        "latest_version",
        "download_url",
        "release_notes",
        "checksum_sha256",
        "mandatory",
    )

    def __init__(
        self,
        *,
        current_version: str,
        latest_version: str,
        download_url: str | None,
        release_notes: str,
        checksum_sha256: str | None = None,
        mandatory: bool = False,
    ) -> None:
        self.current_version = current_version
        self.latest_version = latest_version
        self.download_url = download_url
        self.release_notes = release_notes
        self.checksum_sha256 = checksum_sha256
        self.mandatory = mandatory

    @property
    def supports_direct_download(self) -> bool:
        return bool(self.download_url and self.checksum_sha256)

    @classmethod
    def from_manifest(cls, manifest: UpdateManifest) -> UpdateInfo:
        return cls(
            current_version=__version__,
            latest_version=manifest.version,
            download_url=manifest.download_url,
            release_notes=get_release_notes(manifest),
            checksum_sha256=manifest.checksum_sha256,
            mandatory=manifest.mandatory,
        )


def fetch_manifest(manifest_url: str) -> UpdateManifest | None:
    """Fetch and parse remote manifest; returns None on failure."""
    url = manifest_url.strip()
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            logger.warning("update manifest is not a JSON object")
            return None
        return parse_manifest(payload)
    except Exception as exc:  # noqa: BLE001
        logger.debug("update manifest fetch failed: %s", exc)
        return None


def check_for_updates(manifest_url: str | None = None) -> UpdateInfo | None:
    """Fetch update manifest; returns None when URL unset, fetch fails, or up-to-date."""
    url = (manifest_url or "").strip()
    if not url:
        return None

    manifest = fetch_manifest(url)
    if manifest is None or not manifest.version:
        return None

    if not is_newer_version(manifest.version, __version__):
        logger.debug(
            "update check: current=%s latest=%s (no update)",
            __version__,
            manifest.version,
        )
        return None

    info = UpdateInfo.from_manifest(manifest)
    logger.info(
        "update available: %s -> %s (mandatory=%s)",
        info.current_version,
        info.latest_version,
        info.mandatory,
    )
    return info


def get_release_notes_for_version(
    manifest_url: str,
    version: str,
) -> str | None:
    """Fetch manifest and return notes for *version* (C22 §3)."""
    manifest = fetch_manifest(manifest_url)
    if manifest is None:
        return None
    return get_release_notes(manifest, version)


def write_local_manifest(path, info: UpdateInfo) -> None:
    from pathlib import Path

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "current": info.current_version,
                "latest": info.latest_version,
                "download_url": info.download_url,
                "release_notes": info.release_notes,
                "checksum_sha256": info.checksum_sha256,
                "mandatory": info.mandatory,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
