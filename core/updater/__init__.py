"""C22 Updater package — check, download, verify, apply."""

from core.updater.checker import (
    UpdateInfo,
    check_for_updates,
    fetch_manifest,
    get_release_notes_for_version,
    write_local_manifest,
)
from core.updater.downloader import DownloadError, apply_update, default_installer_path, download_update
from core.updater.manifest import UpdateManifest, get_release_notes, parse_manifest
from core.updater.verify import ChecksumMismatchError, compute_sha256, verify_checksum
from core.updater.version import is_newer_version, parse_version

__all__ = [
    "UpdateInfo",
    "UpdateManifest",
    "check_for_updates",
    "fetch_manifest",
    "get_release_notes",
    "get_release_notes_for_version",
    "write_local_manifest",
    "parse_manifest",
    "DownloadError",
    "default_installer_path",
    "download_update",
    "apply_update",
    "ChecksumMismatchError",
    "compute_sha256",
    "verify_checksum",
    "is_newer_version",
    "parse_version",
]
