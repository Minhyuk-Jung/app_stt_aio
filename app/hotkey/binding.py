"""Parse hotkey chord strings like ctrl+shift+space (C9)."""

from __future__ import annotations

from dataclasses import dataclass

from app.hotkey.errors import HotkeyBindingError

MODIFIER_ALIASES: dict[str, str] = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "menu": "alt",
    "win": "win",
    "windows": "win",
}

VK_BY_NAME: dict[str, int] = {
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "pause": 0x13,
    "capslock": 0x14,
    "scrolllock": 0x91,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}

for index in range(1, 13):
    VK_BY_NAME[f"f{index}"] = 0x6F + index

for letter in "abcdefghijklmnopqrstuvwxyz":
    VK_BY_NAME[letter] = ord(letter.upper())

for digit in "0123456789":
    VK_BY_NAME[digit] = ord(digit)

MODIFIER_VKS: dict[str, tuple[int, ...]] = {
    "ctrl": (0xA2, 0xA3, 0x11),
    "shift": (0xA0, 0xA1, 0x10),
    "alt": (0xA4, 0xA5, 0x12),
    "win": (0x5B, 0x5C, 0x5D),
}


@dataclass(frozen=True)
class KeyChord:
    modifiers: frozenset[str]
    key_name: str
    vk: int


def parse_binding(keys: str) -> KeyChord:
    """Parse a '+'-separated chord into modifiers and main virtual key."""
    normalized = keys.strip().lower()
    if not normalized:
        raise HotkeyBindingError("binding cannot be empty")

    parts = [part.strip() for part in normalized.split("+") if part.strip()]
    if not parts:
        raise HotkeyBindingError(f"invalid binding: {keys!r}")

    modifiers: set[str] = set()
    main_key: str | None = None
    for part in parts:
        if part in MODIFIER_ALIASES:
            modifiers.add(MODIFIER_ALIASES[part])
            continue
        if main_key is not None:
            raise HotkeyBindingError(
                f"binding must contain a single main key: {keys!r}"
            )
        main_key = part

    if main_key is None:
        raise HotkeyBindingError(f"binding requires a main key: {keys!r}")

    vk = VK_BY_NAME.get(main_key)
    if vk is None:
        raise HotkeyBindingError(f"unknown key name: {main_key!r}")

    return KeyChord(modifiers=frozenset(modifiers), key_name=main_key, vk=vk)


def modifier_from_vk(vk: int) -> str | None:
    for name, codes in MODIFIER_VKS.items():
        if vk in codes:
            return name
    return None


def chord_matches_pressed(chord: KeyChord, pressed_modifiers: set[str]) -> bool:
    return chord.modifiers.issubset(pressed_modifiers)
