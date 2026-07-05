"""Tests for C11 Config."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Config
from app.config.schema import CONFIG_SCHEMA_VERSION


@pytest.fixture
def config(tmp_path: Path) -> Config:
    cfg = Config.open(tmp_path / "config.db", migrate_backup=False)
    yield cfg
    cfg.close()


def test_paths(config: Config, tmp_path: Path) -> None:
    paths = config.paths()
    assert paths.root == tmp_path
    assert paths.db == tmp_path / "config.db"
    assert paths.models.name == "models"
    assert paths.audio.name == "audio"
    assert paths.logs.name == "logs"


def test_defaults_seeded_on_first_open(config: Config) -> None:
    assert config.get("stt.provider") == "faster_whisper_local"
    assert config.get("stt.model") == "base"
    assert config.get("stt.language") == "ko"
    assert config.get("hotkey.mode") == "ptt"
    assert config.get("hotkey.record_binding") == "ctrl+shift+space"
    assert config.get("hotkey.cancel_binding") == "escape"
    assert config.get("privacy.telemetry") is False
    assert config._settings.get("config.schema_version") == str(CONFIG_SCHEMA_VERSION)


def test_get_set_typed_values(config: Config) -> None:
    config.set("audio.device_id", "device-1")
    config.set("stt.model", "small")
    config.set("privacy.keep_audio", True)
    config.set("audio.vad_threshold", 0.7)

    assert config.get("audio.device_id") == "device-1"
    assert config.get("stt.model") == "small"
    assert config.get("privacy.keep_audio") is True
    assert config.get("audio.vad_threshold") == 0.7


def test_get_section(config: Config) -> None:
    config.set("stt.model", "small")
    config.set("stt.language", "en")

    section = config.get_section("stt")
    assert section["provider"] == "faster_whisper_local"
    assert section["model"] == "small"
    assert section["language"] == "en"


def test_validation_rejects_invalid_values(config: Config) -> None:
    with pytest.raises(ValueError):
        config.set("hotkey.mode", "invalid")
    with pytest.raises(ValueError):
        config.set("audio.vad_threshold", 2.0)


def test_reset_key_and_section(config: Config) -> None:
    config.set("stt.model", "large")
    config.set("hotkey.mode", "toggle")
    config.reset("stt.model")
    assert config.get("stt.model") == "base"
    assert config.get("hotkey.mode") == "toggle"

    config.reset(section="hotkey")
    assert config.get("hotkey.mode") == "ptt"


def test_on_change_callback(config: Config) -> None:
    changes: list[tuple[str, object]] = []

    def on_change(key: str, value: object) -> None:
        changes.append((key, value))

    config.on_change("stt.model", on_change)
    config.set("stt.model", "medium")
    assert changes == [("stt.model", "medium")]


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "persist.db"
    with Config.open(db_path, migrate_backup=False) as first:
        first.set("audio.device_id", "mic-42")
        first.set("hotkey.mode", "toggle")

    with Config.open(db_path, migrate_backup=False) as second:
        assert second.get("audio.device_id") == "mic-42"
        assert second.get("hotkey.mode") == "toggle"


def test_repair_invalid_stored_value(tmp_path: Path) -> None:
    db_path = tmp_path / "repair.db"
    with Config.open(db_path, migrate_backup=False) as cfg:
        cfg._settings.set("hotkey.mode", "not-a-mode")

    with Config.open(db_path, migrate_backup=False) as cfg:
        assert cfg.get("hotkey.mode") == "ptt"


def test_repair_writes_backup_file(tmp_path: Path) -> None:
    db_path = tmp_path / "repair_backup.db"
    with Config.open(db_path, migrate_backup=False) as cfg:
        cfg._settings.set("audio.vad_threshold", "not-a-float")

    with Config.open(db_path, migrate_backup=False) as cfg:
        assert cfg.get("audio.vad_threshold") == 0.5
        backups = list(cfg.paths().logs.glob("settings_repair_*.json"))
        assert len(backups) == 1
        assert "audio.vad_threshold" in backups[0].read_text(encoding="utf-8")


def test_schema_version_property(config: Config) -> None:
    assert config.schema_version == CONFIG_SCHEMA_VERSION


def test_resolve_export_dir(config: Config, tmp_path: Path) -> None:
    export_dir = config.resolve_export_dir()
    assert export_dir == tmp_path / "exports"
    assert export_dir.exists()
    config.set("export.default_dir", str(tmp_path / "custom"))
    custom = config.resolve_export_dir()
    assert custom == tmp_path / "custom"
    assert custom.exists()


def test_export_default_docx_template(config: Config) -> None:
    assert config.get("export.default_docx_template") == "basic"
    config.set("export.default_docx_template", "meeting")
    assert config.get("export.default_docx_template") == "meeting"
    with pytest.raises(ValueError):
        config.set("export.default_docx_template", "invalid")


def test_bind_audio_capture(config: Config) -> None:
    from core.audio import AudioCapture

    capture = AudioCapture()
    config.set("audio.device_id", "")
    config.set("audio.max_segment_ms", 45000)
    config.bind_audio_capture(capture)
    assert capture._max_batch_duration_ms == 45000

    config.set("audio.max_segment_ms", 20000)
    assert capture._max_batch_duration_ms == 20000

    config.set("audio.vad_threshold", 0.8)
    assert capture._max_batch_duration_ms == 20000


def test_cache_reload_persists_invalid_value_repair(tmp_path: Path) -> None:
    db_path = tmp_path / "cache_repair.db"
    with Config.open(db_path, migrate_backup=False) as cfg:
        cfg._settings.set("audio.min_speech_ms", "bad")

    with Config.open(db_path, migrate_backup=False) as cfg:
        assert cfg.get("audio.min_speech_ms") == 250
        assert cfg._settings.get("audio.min_speech_ms") == "250"
