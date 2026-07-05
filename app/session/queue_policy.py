"""Queue policy for concurrent session requests (C10)."""

from __future__ import annotations

from enum import Enum


class QueuePolicy(str, Enum):
    QUEUE = "queue"
    CANCEL = "cancel"
    IGNORE = "ignore"


class QueueAction(str, Enum):
    ACCEPT = "accept"
    QUEUE = "queue"
    IGNORE = "ignore"
    CANCEL_CURRENT = "cancel_current"


def resolve_begin_action(
    policy: str | QueuePolicy,
    *,
    is_recording: bool,
    is_processing: bool,
) -> QueueAction:
    """Decide how to handle a new begin() while the manager is busy."""
    if not is_recording and not is_processing:
        return QueueAction.ACCEPT

    normalized = QueuePolicy(policy)
    if normalized is QueuePolicy.IGNORE:
        return QueueAction.IGNORE
    if normalized is QueuePolicy.CANCEL:
        return QueueAction.CANCEL_CURRENT
    return QueueAction.QUEUE
