"""Helpers for injecting key chords in hotkey tests."""

from __future__ import annotations

from app.hotkey.backend import KeyEvent, MockKeyboardBackend

VK_CTRL = 0xA2
VK_SHIFT = 0xA0
VK_ALT = 0xA4
VK_SPACE = 0x20
VK_ESCAPE = 0x1B


def press(backend: MockKeyboardBackend, vk: int, *, repeat: bool = False) -> None:
    backend.inject(KeyEvent(vk=vk, is_down=True, is_repeat=repeat))


def release(backend: MockKeyboardBackend, vk: int) -> None:
    backend.inject(KeyEvent(vk=vk, is_down=False))


def chord_press(
    backend: MockKeyboardBackend,
    modifiers: list[int],
    main_vk: int,
    *,
    repeat: bool = False,
) -> None:
    for vk in modifiers:
        press(backend, vk)
    press(backend, main_vk, repeat=repeat)


def chord_release(
    backend: MockKeyboardBackend,
    modifiers: list[int],
    main_vk: int,
) -> None:
    release(backend, main_vk)
    for vk in reversed(modifiers):
        release(backend, vk)
