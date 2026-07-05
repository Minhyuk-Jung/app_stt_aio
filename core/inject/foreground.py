"""Active window checks."""

from __future__ import annotations

import sys

from core.inject.errors import NoForegroundWindowError, PlatformNotSupportedError
from core.inject.win32_api import get_foreground_window

_ADMIN_WINDOW_HINT = (
    " If the target app runs as administrator, launch STT-AIO with "
    "matching elevation."
)


def ensure_foreground_window() -> int:
    if sys.platform != "win32":
        raise PlatformNotSupportedError("Injector requires Windows")
    hwnd = get_foreground_window()
    if hwnd == 0:
        raise NoForegroundWindowError(
            "no foreground window available for injection." + _ADMIN_WINDOW_HINT
        )
    return hwnd


def has_foreground_window() -> bool:
    if sys.platform != "win32":
        return False
    return get_foreground_window() != 0
