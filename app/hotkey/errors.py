"""Hotkey errors (C9)."""

from __future__ import annotations


class HotkeyError(Exception):
    """Base hotkey error."""


class PlatformNotSupportedError(HotkeyError):
    """Hotkey backend is not available on this platform."""


class HotkeyBindingError(HotkeyError):
    """Invalid hotkey binding string."""


class HotkeyStateError(HotkeyError):
    """Invalid manager state transition."""


class HotkeyRegistrationError(HotkeyError):
    """Failed to register a global hotkey binding."""
