"""Tests for session queue policy."""

from __future__ import annotations

from app.session.queue_policy import QueueAction, resolve_begin_action


def test_resolve_begin_accepts_when_idle() -> None:
    assert (
        resolve_begin_action("queue", is_recording=False, is_processing=False)
        is QueueAction.ACCEPT
    )


def test_resolve_begin_queues_when_busy() -> None:
    assert (
        resolve_begin_action("queue", is_recording=False, is_processing=True)
        is QueueAction.QUEUE
    )
    assert (
        resolve_begin_action("ignore", is_recording=True, is_processing=False)
        is QueueAction.IGNORE
    )
    assert (
        resolve_begin_action("cancel", is_recording=False, is_processing=True)
        is QueueAction.CANCEL_CURRENT
    )
