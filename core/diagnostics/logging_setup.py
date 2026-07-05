"""Application logging setup with rotation and masking (C20)."""

from __future__ import annotations

import logging
import sys
import atexit
from collections import deque
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Queue

from core.diagnostics.masking_filter import ContextInjectFilter, MaskingFormatter

LOG_FILENAME = "stt-aio.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
MEMORY_BUFFER_LINES = 500

_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s%(context_suffix)s: %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_CONFIGURED = False
_LOG_FILE: Path | None = None
_memory_buffer: deque[str] = deque(maxlen=MEMORY_BUFFER_LINES)
_log_queue: Queue | None = None
_queue_listener: QueueListener | None = None
_atexit_registered = False


def flush_app_logging() -> None:
    """Drain async log queue (tests and shutdown)."""
    if _log_queue is not None and _queue_listener is not None:
        while True:
            try:
                record = _log_queue.get_nowait()
            except Exception:  # noqa: BLE001
                break
            if record is None:
                continue
            for handler in _queue_listener.handlers:
                handler.handle(record)
                handler.flush()


def _shutdown_logging() -> None:
    flush_app_logging()
    if _queue_listener is not None:
        try:
            _queue_listener.stop()
        except Exception:  # noqa: BLE001
            pass


class FallbackRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler with stderr/memory fallback (plan §7)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:  # noqa: BLE001
            try:
                message = self.format(record)
                _memory_buffer.append(message)
                sys.stderr.write(message + "\n")
            except Exception:  # noqa: BLE001
                self.handleError(record)
            else:
                self.handleError(record)


def get_memory_log_lines() -> list[str]:
    return list(_memory_buffer)


def get_log_file_path() -> Path | None:
    return _LOG_FILE


def _parse_level(level: str) -> int:
    normalized = level.strip().lower()
    mapping = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }
    return mapping.get(normalized, logging.INFO)


def set_level(level: str) -> None:
    logging.getLogger().setLevel(_parse_level(level))


def reset_app_logging() -> None:
    """Clear handlers (tests only)."""
    global _CONFIGURED, _LOG_FILE, _log_queue, _queue_listener, _atexit_registered
    flush_app_logging()
    if _queue_listener is not None:
        try:
            if getattr(_queue_listener, "_thread", None) is not None:
                _queue_listener.stop()
        except Exception:  # noqa: BLE001
            pass
        _queue_listener = None
    _log_queue = None
    _atexit_registered = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    _CONFIGURED = False
    _LOG_FILE = None
    _memory_buffer.clear()


def setup_app_logging(
    logs_dir: Path,
    *,
    level: str = "info",
    also_console: bool = True,
) -> Path:
    """Configure root logger with rotating file + optional console (idempotent)."""
    global _CONFIGURED, _LOG_FILE, _log_queue, _queue_listener, _atexit_registered

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / LOG_FILENAME
    _LOG_FILE = log_file

    root = logging.getLogger()
    root.setLevel(_parse_level(level))

    if _CONFIGURED:
        set_level(level)
        return log_file

    formatter = MaskingFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    context_filter = ContextInjectFilter()

    file_handler = FallbackRotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    handlers: list[logging.Handler] = [file_handler]
    if also_console:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.addFilter(context_filter)
        handlers.append(console)

    _log_queue = Queue(-1)
    queue_handler = QueueHandler(_log_queue)
    root.addHandler(queue_handler)
    _queue_listener = QueueListener(_log_queue, *handlers, respect_handler_level=True)
    _queue_listener.start()
    if not _atexit_registered:
        atexit.register(_shutdown_logging)
        _atexit_registered = True

    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging initialized: %s", log_file)
    return log_file


def get_logger(name: str) -> logging.Logger:
    """Plan §3: module logger (uses root handlers)."""
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, message: str, **fields: object) -> None:
    """Structured log helper: append key=value fields (plan §6.2)."""
    if fields:
        suffix = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        message = f"{message} | {suffix}"
    logger.log(level, message)
