"""Tests for hotkey -> audio capture wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding
from app.services.recording_triggers import wire_hotkey_to_audio_capture
from core.audio.format import AudioBuffer
from tests.hotkey.helpers import VK_CTRL, VK_SHIFT, VK_SPACE, chord_press, chord_release, press, release


def test_wire_hotkey_starts_and_stops_capture() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.start()

    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle
    capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01")

    stopped: list[AudioBuffer] = []
    wire_hotkey_to_audio_capture(
        manager,
        capture,
        on_batch_stopped=stopped.append,
    )

    press(backend, VK_CTRL)
    press(backend, VK_SPACE)
    release(backend, VK_SPACE)

    capture.start_batch.assert_called_once()
    capture.stop_batch.assert_called_once_with(handle)
    assert len(stopped) == 1
    manager.close()


def test_wire_hotkey_cancel_discards_capture() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    manager.register(
        HotkeyBinding(id="cancel", keys="escape", action=HotkeyAction.CANCEL)
    )
    manager.start()

    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle

    wire_hotkey_to_audio_capture(manager, capture)

    press(backend, VK_CTRL)
    press(backend, VK_SPACE)
    press(backend, 0x1B)  # escape

    capture.cancel.assert_called_once_with(handle)
    capture.stop_batch.assert_not_called()
    manager.close()


def test_wire_hotkey_ignores_stop_without_active_handle() -> None:
    backend = MockKeyboardBackend()
    manager = HotkeyManager(backend=backend)
    manager.register(
        HotkeyBinding(id="record", keys="ctrl+shift+space", action=HotkeyAction.RECORD)
    )
    manager.start()

    capture = MagicMock()
    wire_hotkey_to_audio_capture(manager, capture)

    chord_release(backend, [VK_CTRL, VK_SHIFT], VK_SPACE)

    capture.stop_batch.assert_not_called()
    manager.close()
