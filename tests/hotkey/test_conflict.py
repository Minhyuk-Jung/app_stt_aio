"""Tests for hotkey conflict probing."""

from __future__ import annotations

from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.conflict import check_binding_available


def test_check_binding_rejects_invalid_chord() -> None:
    assert check_binding_available("not+a+real+key+combo+ever") is False


def test_check_binding_uses_backend_conflicts() -> None:
    backend = MockKeyboardBackend(conflicts={"ctrl+shift+space"})
    assert check_binding_available("ctrl+shift+space", backend=backend) is False
    assert check_binding_available("escape", backend=backend) is True
