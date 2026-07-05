"""Tests for gap-closure features (audio retention, STT hotwords, safe mode)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Config
from core.privacy import purge_expired_audio
from core.store.errors import ReadOnlyStoreError


def test_purge_expired_audio_deletes_old_files(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old = audio_dir / "old.wav"
    old.write_bytes(b"wav")
    old_time = datetime.now(timezone.utc) - timedelta(days=30)
    ts = old_time.timestamp()
    import os

    os.utime(old, (ts, ts))
    deleted = purge_expired_audio(audio_dir, retention_days=7, keep_audio=False)
    assert deleted == 1
    assert not old.exists()


def test_get_stt_options_includes_hotwords(tmp_path: Path) -> None:
    from core.store.models import DictionaryType

    config = Config.open(tmp_path / "hotwords.db", migrate_backup=False)
    config._store.dictionaries.create(
        term="STT-AIO",
        replacement="STT-AIO",
        entry_type=DictionaryType.VOCAB,
    )
    opts = config.get_stt_options()
    assert "STT-AIO" in opts.hotwords
    assert "STT-AIO" in opts.initial_prompt
    config.close()


def test_config_readonly_blocks_writes(tmp_path: Path) -> None:
    db = tmp_path / "safe.db"
    Config.open(db, migrate_backup=False).close()
    config = Config.open_safe(db)
    assert config.readonly is True
    with pytest.raises(ReadOnlyStoreError):
        config.set("stt.language", "en")
    config.close()
