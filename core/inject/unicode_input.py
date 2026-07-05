"""SendInput unicode text injection."""

from __future__ import annotations

from core.inject.errors import InjectionFailedError
from core.inject.text_encoding import text_to_utf16_units
from core.inject.win32_api import (
    INPUT,
    INPUT_KEYBOARD,
    INPUT_UNION,
    KEYBDINPUT,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    ULONG_PTR,
    VK_BACK,
    VK_RETURN,
    send_input,
    sleep_ms,
)

_UNICODE_CHUNK_SIZE = 64


def _keyboard_event(scan_code: int, *, key_up: bool = False) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
    event.union = INPUT_UNION(
        ki=KEYBDINPUT(0, scan_code, flags, 0, ULONG_PTR(0))
    )
    return event


def _build_vk_events(vk_code: int, count: int = 1) -> list[INPUT]:
    events: list[INPUT] = []
    for _ in range(count):
        down = INPUT()
        down.type = INPUT_KEYBOARD
        down.union = INPUT_UNION(ki=KEYBDINPUT(vk_code, 0, 0, 0, ULONG_PTR(0)))
        up = INPUT()
        up.type = INPUT_KEYBOARD
        up.union = INPUT_UNION(
            ki=KEYBDINPUT(vk_code, 0, KEYEVENTF_KEYUP, 0, ULONG_PTR(0))
        )
        events.extend([down, up])
    return events


def send_backspaces(count: int) -> None:
    if count <= 0:
        return
    _send_events(_build_vk_events(VK_BACK, count))


def send_enter() -> None:
    _send_events(_build_vk_events(VK_RETURN, 1))


def send_unicode_text(text: str, *, per_char_delay_ms: int = 0) -> int:
    if not text:
        return 0
    units = text_to_utf16_units(text)
    for index in range(0, len(units), _UNICODE_CHUNK_SIZE):
        chunk = units[index : index + _UNICODE_CHUNK_SIZE]
        events: list[INPUT] = []
        for unit in chunk:
            events.append(_keyboard_event(unit, key_up=False))
            events.append(_keyboard_event(unit, key_up=True))
        _send_events(events)
        if per_char_delay_ms > 0:
            sleep_ms(per_char_delay_ms * len(chunk))
    return len(text)


def _send_events(events: list[INPUT]) -> None:
    if not events:
        return
    sent = send_input(events)
    if sent != len(events):
        raise InjectionFailedError(
            f"SendInput sent {sent} of {len(events)} keyboard events"
        )
