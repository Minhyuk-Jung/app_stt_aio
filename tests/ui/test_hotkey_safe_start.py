"""Regression: app must not crash when global hotkey registration fails."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.hotkey.errors import HotkeyRegistrationError
from app.ui.app_shell import start_hotkey_safe


def test_survives_registration_error():
    hotkey = MagicMock()
    hotkey.start.side_effect = HotkeyRegistrationError("conflict")
    tray = MagicMock()

    assert start_hotkey_safe(hotkey, tray) is False
    tray.show_message.assert_called_once()


def test_returns_true_on_success():
    hotkey = MagicMock()
    tray = MagicMock()

    assert start_hotkey_safe(hotkey, tray) is True
    tray.show_message.assert_not_called()


def test_reraises_unexpected_errors():
    hotkey = MagicMock()
    hotkey.start.side_effect = ValueError("boom")

    with pytest.raises(ValueError):
        start_hotkey_safe(hotkey, MagicMock())
