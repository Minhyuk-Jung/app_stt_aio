"""Injector data types (C5 contract)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InjectMethod(str, Enum):
    AUTO = "auto"
    UNICODE = "unicode"
    CLIPBOARD = "clipboard"


@dataclass(frozen=True)
class InjectCapabilities:
    supports_unicode: bool
    supports_clipboard: bool
    supports_replacement: bool
    platform: str = "windows"


@dataclass
class InjectOptions:
    press_enter: bool = False
    per_char_delay_ms: int = 0
    length_threshold: int = 500
    unicode_fallback_to_clipboard: bool = True
    target_check: bool = True
    allow_replacement: bool = True


@dataclass(frozen=True)
class InjectResult:
    success: bool
    method_used: InjectMethod
    chars_injected: int = 0
    error: str | None = None
