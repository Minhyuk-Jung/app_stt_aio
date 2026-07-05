"""Log context fields (session/component) for structured output (C20)."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_log_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "stt_aio_log_context",
    default={},
)


def get_context() -> dict[str, Any]:
    return dict(_log_context.get())


def bind_context(**fields: Any) -> None:
    current = dict(_log_context.get())
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    _log_context.set(current)


def clear_context() -> None:
    _log_context.set({})


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    token = _log_context.set({**_log_context.get(), **fields})
    try:
        yield
    finally:
        _log_context.reset(token)


def format_context_suffix() -> str:
    ctx = get_context()
    if not ctx:
        return ""
    parts = [f"{key}={value}" for key, value in sorted(ctx.items())]
    return " [" + " ".join(parts) + "]"
