"""Tests for pipeline execution queue."""

from __future__ import annotations

import threading
import time

from core.pipeline.queue import PipelineQueue


def test_exclusive_blocks_until_released() -> None:
    queue = PipelineQueue()
    order: list[str] = []
    started = threading.Event()
    proceed = threading.Event()

    def worker() -> None:
        with queue.exclusive():
            order.append("enter")
            started.set()
            proceed.wait(timeout=2.0)
            order.append("leave")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert started.wait(timeout=2.0)

    acquired = False

    def try_enter() -> None:
        nonlocal acquired
        with queue.exclusive():
            acquired = True

    blocker = threading.Thread(target=try_enter, daemon=True)
    blocker.start()
    time.sleep(0.05)
    assert acquired is False

    proceed.set()
    thread.join(timeout=2.0)
    blocker.join(timeout=2.0)
    assert acquired is True
    assert order == ["enter", "leave"]
