"""Logging filters that apply C19 secret masking (C20)."""

from __future__ import annotations

import logging

from core.diagnostics.context import format_context_suffix
from core.secrets import mask_secrets


class MaskingFormatter(logging.Formatter):
    """Format log records and mask the full output including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_secrets(super().format(record))


class MaskingFilter(logging.Filter):
    """Mask secrets in log message and record args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        if record.args:
            record.args = tuple(
                mask_secrets(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


class ContextInjectFilter(logging.Filter):
    """Attach context suffix for formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.context_suffix = format_context_suffix()  # type: ignore[attr-defined]
        return True
