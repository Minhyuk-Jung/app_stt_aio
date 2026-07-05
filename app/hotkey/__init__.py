"""Hotkey manager package (C9)."""

from app.hotkey.errors import (
    HotkeyBindingError,
    HotkeyError,
    HotkeyRegistrationError,
    HotkeyStateError,
    PlatformNotSupportedError,
)
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding, HotkeyMode

__all__ = [
    "HotkeyAction",
    "HotkeyBinding",
    "HotkeyBindingError",
    "HotkeyError",
    "HotkeyManager",
    "HotkeyMode",
    "HotkeyRegistrationError",
    "HotkeyStateError",
    "PlatformNotSupportedError",
]
