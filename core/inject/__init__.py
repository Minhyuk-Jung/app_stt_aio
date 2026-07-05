"""Text injection into the focused window (C5, Windows)."""

from core.inject.errors import (
    ClipboardBusyError,
    InjectError,
    InjectionFailedError,
    NoForegroundWindowError,
    PlatformNotSupportedError,
)
from core.inject.injector import Injector
from core.inject.types import InjectCapabilities, InjectMethod, InjectOptions, InjectResult

__all__ = [
    "ClipboardBusyError",
    "InjectCapabilities",
    "InjectError",
    "InjectMethod",
    "InjectOptions",
    "InjectResult",
    "InjectionFailedError",
    "Injector",
    "NoForegroundWindowError",
    "PlatformNotSupportedError",
]
