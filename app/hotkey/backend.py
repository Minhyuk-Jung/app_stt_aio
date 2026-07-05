"""Keyboard backend abstraction for hotkey capture (C9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from app.hotkey.binding import KeyChord

KeyEventHandler = Callable[["KeyEvent"], None]


@dataclass(frozen=True)
class KeyEvent:
    vk: int
    is_down: bool
    is_repeat: bool = False


class KeyboardBackend(Protocol):
    def start(self, handler: KeyEventHandler) -> None: ...

    def stop(self) -> None: ...

    def test_register(self, chord: KeyChord) -> bool: ...

    def wait_ready(self, timeout: float = 1.0) -> bool: ...

    @property
    def hook_failed(self) -> bool: ...


class MockKeyboardBackend:
    """Test backend that injects key events programmatically."""

    def __init__(self, *, conflicts: set[str] | None = None) -> None:
        self._handler: KeyEventHandler | None = None
        self._running = False
        self._conflicts = conflicts or set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def hook_failed(self) -> bool:
        return False

    def start(self, handler: KeyEventHandler) -> None:
        self._handler = handler
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._handler = None

    def wait_ready(self, timeout: float = 1.0) -> bool:
        return self._running

    def inject(self, event: KeyEvent) -> None:
        if self._running and self._handler is not None:
            self._handler(event)

    def test_register(self, chord: KeyChord) -> bool:
        key = "+".join(sorted(chord.modifiers) + [chord.key_name])
        return key not in self._conflicts


class NullKeyboardBackend:
    """No-op backend for unsupported platforms."""

    @property
    def hook_failed(self) -> bool:
        return False

    def start(self, handler: KeyEventHandler) -> None:
        return None

    def stop(self) -> None:
        return None

    def wait_ready(self, timeout: float = 1.0) -> bool:
        return True

    def test_register(self, chord: KeyChord) -> bool:
        return True


def create_keyboard_backend() -> KeyboardBackend:
    import sys

    if sys.platform == "win32":
        from app.hotkey.backend_win import WinKeyboardBackend

        return WinKeyboardBackend()
    return NullKeyboardBackend()
