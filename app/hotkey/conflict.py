"""Hotkey registration conflict detection (C9)."""

from __future__ import annotations

import sys

from app.hotkey.binding import KeyChord, parse_binding
from app.hotkey.errors import HotkeyBindingError

FALLBACK_BINDINGS: tuple[str, ...] = (
    "ctrl+shift+space",
    "ctrl+alt+space",
    "ctrl+shift+f8",
    "f8",
    "pause",
)

CANCEL_FALLBACK_BINDINGS: tuple[str, ...] = (
    "escape",
    "ctrl+escape",
    "f12",
)


def check_binding_available(keys: str, *, backend=None) -> bool:
    """Return True when the binding can be registered without conflict."""
    try:
        chord = parse_binding(keys)
    except HotkeyBindingError:
        return False

    if backend is not None:
        return backend.test_register(chord)

    if sys.platform != "win32":
        return True

    from app.hotkey.backend_win import test_register_hotkey

    return test_register_hotkey(chord)


def suggest_fallback_binding(
    keys: str,
    *,
    backend=None,
    exclude: set[str] | None = None,
    candidates: tuple[str, ...] | None = None,
) -> str | None:
    """Suggest an alternative binding when registration conflicts (plan 7)."""
    blocked = set(exclude or ())
    blocked.add(keys.lower().strip())
    options = candidates or FALLBACK_BINDINGS
    for candidate in options:
        normalized = candidate.lower().strip()
        if normalized in blocked:
            continue
        if check_binding_available(candidate, backend=backend):
            return candidate
    return None
