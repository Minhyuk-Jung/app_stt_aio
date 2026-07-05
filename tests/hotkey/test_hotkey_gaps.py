"""Additional tests for hotkey gap coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.binding import parse_binding
from app.hotkey.conflict import suggest_fallback_binding
from app.hotkey.errors import HotkeyRegistrationError
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding, HotkeyMode
from tests.hotkey.helpers import VK_CTRL, VK_SHIFT, VK_SPACE, chord_press, chord_release, press, release


def test_parse_special_keys_supported() -> None:
    assert parse_binding("capslock").vk == 0x14
    assert parse_binding("scrolllock").vk == 0x91
    assert parse_binding("pause").vk == 0x13


def test_set_mode_stops_active_recording() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.start()
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_record_stop(lambda: events.append("stop"))

    press(backend, VK_CTRL)
    press(backend, VK_SPACE)
    manager.set_mode(HotkeyMode.TOGGLE)

    assert events == ["start", "stop"]
    manager.close()


def test_ptt_does_not_restart_while_recording() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.start()
    starts = 0

    def on_start() -> None:
        nonlocal starts
        starts += 1

    manager.on_record_start(on_start)

    press(backend, VK_CTRL)
    press(backend, VK_SPACE)
    press(backend, VK_SPACE, repeat=True)

    assert starts == 1
    manager.close()


def test_apply_config_uses_fallback_on_record_conflict() -> None:
    backend = MockKeyboardBackend(conflicts={"ctrl+shift+space"})
    manager = HotkeyManager(backend=backend)

    config = MagicMock()
    config.get.side_effect = lambda key: {
        "hotkey.mode": "ptt",
        "hotkey.auto_send": False,
        "hotkey.record_binding": "ctrl+shift+space",
        "hotkey.cancel_binding": "escape",
    }[key]

    manager.apply_config(config)

    assert manager._bindings["record"].keys == "ctrl+alt+space"


def test_suggest_fallback_skips_conflicting_candidate() -> None:
    backend = MockKeyboardBackend(conflicts={"ctrl+shift+space"})
    suggestion = suggest_fallback_binding("ctrl+shift+space", backend=backend)
    assert suggestion == "ctrl+alt+space"


class FailingHookBackend(MockKeyboardBackend):
    @property
    def hook_failed(self) -> bool:
        return True

    def wait_ready(self, timeout: float = 1.0) -> bool:
        return True


def test_start_raises_when_hook_fails() -> None:
    manager = HotkeyManager(backend=FailingHookBackend())
    with pytest.raises(HotkeyRegistrationError):
        manager.start(max_attempts=1)


def test_start_skips_hook_when_nfr_bench_env(monkeypatch) -> None:
    backend = FailingHookBackend()
    manager = HotkeyManager(backend=backend)
    monkeypatch.setenv("STT_AIO_NFR_BENCH", "1")
    manager.start(max_attempts=1)
    assert manager.is_running is True
    assert backend.is_running is False


def test_bindings_returns_registered_items() -> None:
    manager = HotkeyManager(backend=MockKeyboardBackend())
    binding = HotkeyBinding(id="record", keys="f8", action=HotkeyAction.RECORD)
    manager.register(binding)
    assert manager.bindings() == [binding]


def test_toggle_fast_double_press_cycles_recording() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.set_mode("toggle")
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.start()
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_record_stop(lambda: events.append("stop"))

    press(backend, VK_CTRL)
    press(backend, VK_SPACE)
    release(backend, VK_SPACE)
    press(backend, VK_SPACE)
    release(backend, VK_SPACE)

    assert events == ["start", "stop"]
    manager.close()
