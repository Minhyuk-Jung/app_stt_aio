"""Tests for Config <-> HotkeyManager binding."""

from __future__ import annotations

from app.hotkey import HotkeyManager
from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.types import HotkeyMode


def test_bind_hotkey_applies_config(tmp_path) -> None:
    from app.config import Config

    backend = MockKeyboardBackend()
    with Config.open(tmp_path / "hotkey.db", migrate_backup=False) as config:
        config.set("hotkey.mode", "toggle")
        config.set("hotkey.record_binding", "ctrl+space")
        config.set("hotkey.cancel_binding", "escape")
        manager = config.bind_hotkey(HotkeyManager(backend=backend))

        assert manager.mode == HotkeyMode.TOGGLE
        assert "record" in manager._bindings
        assert manager._bindings["record"].keys == "ctrl+space"

        config.set("hotkey.mode", "ptt")
        assert config.hotkey_manager.mode == HotkeyMode.PTT


def test_bind_hotkey_does_not_duplicate_change_listeners(tmp_path) -> None:
    from app.config import Config

    backend = MockKeyboardBackend()
    with Config.open(tmp_path / "hotkey2.db", migrate_backup=False) as config:
        config.bind_hotkey(HotkeyManager(backend=backend))
        config.bind_hotkey(HotkeyManager(backend=backend))
        assert len(config._listeners["hotkey.mode"]) == 1


def test_hotkey_manager_property_requires_bind(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "hotkey3.db", migrate_backup=False) as config:
        try:
            _ = config.hotkey_manager
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
