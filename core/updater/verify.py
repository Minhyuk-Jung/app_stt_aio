"""Installer integrity verification (C22 §6.3 원칙).

Verifies SHA-256 checksum before allowing the installer to run.
Signature verification is deferred to a later stage (codesign policy).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536  # 64 KiB


class ChecksumMismatchError(ValueError):
    """Raised when the downloaded file does not match the expected checksum."""


def compute_sha256(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected_sha256: str) -> None:
    """Raise ChecksumMismatchError when the file does not match *expected_sha256*.

    C22 §6.3: "무결성 검증(checksum) 통과 전 실행 금지."

    Args:
        path: Downloaded installer file path.
        expected_sha256: Expected lowercase hex SHA-256 digest from the manifest.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ChecksumMismatchError: If the digest does not match.
    """
    if not path.exists():
        raise FileNotFoundError(f"Installer not found: {path}")

    expected = expected_sha256.strip().lower()
    actual = compute_sha256(path)

    if actual != expected:
        logger.error(
            "Checksum mismatch for %s: expected=%s actual=%s",
            path.name,
            expected,
            actual,
        )
        raise ChecksumMismatchError(
            f"Installer checksum mismatch for {path.name}.\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}"
        )

    logger.info("Checksum verified OK: %s (%s)", path.name, actual[:16] + "...")
