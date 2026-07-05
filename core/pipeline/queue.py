"""Pipeline execution queue (C4, P1 minimal serialization)."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from collections.abc import Iterator


class PipelineQueue:
    """Serialize pipeline runs within a process (P1 lock)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._lock:
            yield

    @property
    def is_locked(self) -> bool:
        return self._lock.locked()
