"""Tests for HotkeyManager state machine."""

from __future__ import annotations

from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding, HotkeyMode
from tests.hotkey.helpers import (
    VK_CTRL,
    VK_ESCAPE,
    VK_SHIFT,
    VK_SPACE,
    chord_press,
    chord_release,
    press,
    release,
)


def _manager(backend: MockKeyboardBackend | None = None) -> HotkeyManager:
    backend = backend or MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(
            id="record",
            keys="ctrl+shift+space",
            action=HotkeyAction.RECORD,
        )
    )
    manager.register(
        HotkeyBinding(id="cancel", keys="escape", action=HotkeyAction.CANCEL)
    )
    manager.start()
    return manager


def test_ptt_start_and_stop() -> None:
    backend = MockKeyboardBackend()
    manager = _manager(backend)
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_record_stop(lambda: events.append("stop"))

    chord_press(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)
    chord_release(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)

    assert events == ["start", "stop"]
    manager.close()


def test_toggle_start_and_stop() -> None:
    backend = MockKeyboardBackend()
    manager = _manager(backend)
    manager.set_mode(HotkeyMode.TOGGLE)
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_record_stop(lambda: events.append("stop"))

    chord_press(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)
    chord_release(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)
    chord_press(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)
    chord_release(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)

    assert events == ["start", "stop"]
    manager.close()


def test_cancel_has_priority() -> None:
    backend = MockKeyboardBackend()
    manager = _manager(backend)
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_record_stop(lambda: events.append("stop"))
    manager.on_cancel(lambda: events.append("cancel"))

    chord_press(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)
    press(backend, VK_ESCAPE)
    release(backend, VK_ESCAPE)

    assert "start" in events
    assert "cancel" in events
    assert "stop" not in events
    manager.close()


def test_auto_send_on_alt_release_path() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend, auto_send_enabled=True)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.start()
    events: list[str] = []
    manager.on_record_start(lambda: events.append("start"))
    manager.on_auto_send(lambda: events.append("auto"))
    manager.on_record_stop(lambda: events.append("stop"))

    press(backend, VK_CTRL)
    press(backend, 0xA4)  # alt
    press(backend, VK_SPACE)
    release(backend, VK_SPACE)

    assert events == ["start", "auto"]
    manager.close()


def test_register_conflict_emits_callback() -> None:
    backend = MockKeyboardBackend(conflicts={"ctrl+shift+space"})
    manager = HotkeyManager(backend=backend)
    conflicts: list[str] = []
    manager.on_conflict(lambda binding: conflicts.append(binding.id))

    accepted = manager.register(
        HotkeyBinding(id="record", keys="ctrl+shift+space", action=HotkeyAction.RECORD)
    )

    assert accepted is False
    assert conflicts == ["record"]


def test_debounce_ignores_key_repeat() -> None:
    backend = MockKeyboardBackend()
    manager = _manager(backend)
    starts = 0

    def on_start() -> None:
        nonlocal starts
        starts += 1

    manager.on_record_start(on_start)

    press(backend, VK_CTRL)
    press(backend, VK_SHIFT)
    press(backend, VK_SPACE)
    press(backend, VK_SPACE, repeat=True)
    press(backend, VK_SPACE, repeat=True)

    assert starts == 1
    manager.close()
