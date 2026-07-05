"""Recent error events for diagnostics export (C20)."""

from __future__ import annotations

import logging
import traceback
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.diagnostics.context import get_context
from core.secrets import mask_secrets

logger = logging.getLogger(__name__)

_MAX_ERRORS = 50
_recent_errors: deque[dict[str, Any]] = deque(maxlen=_MAX_ERRORS)


@dataclass
class ErrorEvent:
    timestamp: str
    error_type: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    traceback: str | None = None


def report_error(
    error: BaseException | str,
    *,
    context: dict[str, Any] | None = None,
    log: bool = True,
) -> None:
    """Record an error event and emit a masked log line."""
    if isinstance(error, BaseException):
        message = mask_secrets(str(error))
        error_type = type(error).__name__
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        tb = mask_secrets(tb)
    else:
        message = mask_secrets(error)
        error_type = "Error"
        tb = None

    merged = {**get_context(), **(context or {})}
    event = ErrorEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_type=error_type,
        message=message,
        context=merged,
        traceback=tb,
    )
    _recent_errors.append(asdict(event))

    if log:
        logger.error("%s: %s", error_type, message, exc_info=isinstance(error, BaseException))


def recent_errors() -> list[dict[str, Any]]:
    return list(_recent_errors)


def clear_errors() -> None:
    _recent_errors.clear()
