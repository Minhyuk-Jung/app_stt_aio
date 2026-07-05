"""Installer download with progress reporting (C22 §6.2 2단계).

Downloads to a temp file, verifies checksum, then moves to the final path.
Uses only the standard library (urllib) — no external dependencies.
"""

from __future__ import annotations

import logging
import os
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.diagnostics import get_logger
from core.updater.verify import ChecksumMismatchError, verify_checksum

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], None]
"""Called with (bytes_downloaded, total_bytes). total_bytes may be -1 if unknown."""

_CHUNK_SIZE = 65536  # 64 KiB
_CONNECT_TIMEOUT = 15.0
_READ_TIMEOUT = 120.0


class DownloadError(OSError):
    """Network or I/O error during download."""


def default_installer_path(version: str) -> Path:
    """Return the default download path for an installer of *version*."""
    from core.paths import get_app_paths

    updates_dir = get_app_paths().root / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    safe_version = version.replace("/", "_").replace("\\", "_")
    return updates_dir / f"STT-AIO-Setup-{safe_version}.exe"


def download_update(
    url: str,
    dest_path: Path,
    *,
    expected_sha256: str | None = None,
    on_progress: ProgressCallback | None = None,
    connect_timeout: float = _CONNECT_TIMEOUT,
) -> Path:
    """Download installer from *url* to *dest_path* with optional checksum verification.

    C22 §6.2 2단계: 설치본 다운로드 + 검증.

    Steps:
    1. Download to a temporary file in the same directory as *dest_path*.
    2. Optionally verify SHA-256 checksum against *expected_sha256*.
    3. Atomically rename temp file to *dest_path*.

    Args:
        url: HTTPS URL of the installer.
        dest_path: Final path for the downloaded installer.
        expected_sha256: If given, verify the digest after download.
        on_progress: Optional callback (bytes_done, total). total is -1 if unknown.
        connect_timeout: Connection timeout in seconds.

    Returns:
        *dest_path* after successful download (and optional checksum verification).

    Raises:
        DownloadError: On network/I/O errors.
        ChecksumMismatchError: If *expected_sha256* is given and does not match.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path_str = tempfile.mkstemp(
        dir=dest_path.parent,
        prefix=".tmp-download-",
        suffix=".part",
    )
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(tmp_fd, "wb") as tmp_fh:
            _fetch_to_file(url, tmp_fh, on_progress=on_progress, timeout=connect_timeout)

        if expected_sha256:
            verify_checksum(tmp_path, expected_sha256)

        tmp_path.replace(dest_path)
        logger.info("Download complete: %s → %s", url, dest_path)
        return dest_path

    except (DownloadError, ChecksumMismatchError):
        raise
    except Exception as exc:
        raise DownloadError(f"Download failed ({url}): {exc}") from exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _fetch_to_file(
    url: str,
    fh,
    *,
    on_progress: ProgressCallback | None,
    timeout: float,
) -> None:
    """Stream *url* into open file handle *fh*, calling *on_progress* periodically."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "STT-AIO-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            total = int(content_length) if content_length else -1
            downloaded = 0

            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

    except urllib.error.URLError as exc:
        raise DownloadError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DownloadError("Download timed out") from exc


def apply_update(installer_path: Path) -> None:
    """Launch the installer executable and allow it to run independently.

    C22 §6.2 2단계: 설치본 실행.

    The caller is responsible for closing the app after calling this function.
    On Windows, uses ``os.startfile`` so the installer runs with UAC elevation if needed.

    Args:
        installer_path: Path to the downloaded and verified installer (.exe).

    Raises:
        FileNotFoundError: If *installer_path* does not exist.
        OSError: If the OS cannot launch the installer.
    """
    installer_path = Path(installer_path)
    if not installer_path.exists():
        raise FileNotFoundError(f"Installer not found: {installer_path}")
    if not installer_path.suffix.lower() == ".exe":
        raise ValueError(f"Expected .exe installer, got: {installer_path.suffix}")

    logger.info("Launching installer: %s", installer_path)
    os.startfile(str(installer_path))  # type: ignore[attr-defined]  # Windows-only
