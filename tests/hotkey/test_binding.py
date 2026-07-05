"""Tests for hotkey chord parsing."""

from __future__ import annotations

import pytest

from app.hotkey.binding import parse_binding
from app.hotkey.errors import HotkeyBindingError


def test_parse_binding_with_modifiers() -> None:
    chord = parse_binding("ctrl+shift+space")
    assert chord.modifiers == frozenset({"ctrl", "shift"})
    assert chord.key_name == "space"
    assert chord.vk == 0x20


def test_parse_binding_single_key() -> None:
    chord = parse_binding("escape")
    assert chord.modifiers == frozenset()
    assert chord.vk == 0x1B


def test_parse_binding_rejects_unknown_key() -> None:
    with pytest.raises(HotkeyBindingError):
        parse_binding("ctrl+unknown")
