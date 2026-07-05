"""Injector error types."""

from __future__ import annotations


class InjectError(Exception):
    """Base error for text injection operations."""


class PlatformNotSupportedError(InjectError):
    """Injector is only supported on Windows."""


class NoForegroundWindowError(InjectError):
    """No active foreground window is available for injection."""


class ClipboardBusyError(InjectError):
    """Clipboard is locked by another application."""


class InjectionFailedError(InjectError):
    """Text injection failed."""
