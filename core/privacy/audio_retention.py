"""Audio file retention policy enforcement (C19)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def purge_expired_audio(
    audio_dir: Path,
    *,
    retention_days: int,
    keep_audio: bool,
) -> int:
    """Delete audio files older than retention_days. Returns deleted count."""
    if keep_audio or retention_days <= 0:
        return 0
    if not audio_dir.is_dir():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0
    for path in audio_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning("Failed to delete audio file %s: %s", path, exc)
    if deleted:
        from core.diagnostics import log_event

        log_event(
            logger,
            logging.INFO,
            "audio retention purge",
            deleted=deleted,
            retention_days=retention_days,
            audio_dir=str(audio_dir),
        )
    return deleted
