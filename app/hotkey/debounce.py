"""Key repeat debounce for global hotkey hooks (C9)."""

from __future__ import annotations

import time


class KeyDebouncer:
    """Suppress repeated key-down events while a key is held."""

    def __init__(self, interval_ms: int = 50) -> None:
        self._interval_ms = interval_ms
        self._last_accepted: dict[str, float] = {}

    def accept(self, key_id: str, *, is_repeat: bool) -> bool:
        if not is_repeat:
            self._last_accepted[key_id] = time.monotonic()
            return True

        now = time.monotonic()
        last = self._last_accepted.get(key_id, 0.0)
        elapsed_ms = (now - last) * 1000
        if elapsed_ms < self._interval_ms:
            return False

        self._last_accepted[key_id] = now
        return True

    def reset(self, key_id: str | None = None) -> None:
        if key_id is None:
            self._last_accepted.clear()
            return
        self._last_accepted.pop(key_id, None)
