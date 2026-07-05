"""Tests for C20 logging setup."""

from __future__ import annotations

import logging

import pytest

from core.diagnostics.logging_setup import (
    LOG_FILENAME,
    MAX_BYTES,
    BACKUP_COUNT,
    flush_app_logging,
    get_log_file_path,
    get_memory_log_lines,
    set_level,
    setup_app_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    from core.diagnostics.logging_setup import reset_app_logging

    reset_app_logging()
    yield
    reset_app_logging()


def test_setup_app_logging_writes_file(tmp_path) -> None:
    log_file = setup_app_logging(tmp_path / "logs", level="debug", also_console=False)
    assert log_file == tmp_path / "logs" / LOG_FILENAME

    logging.getLogger("tests.logging").info("hello diagnostics")
    flush_app_logging()

    assert log_file.is_file()
    assert "hello diagnostics" in log_file.read_text(encoding="utf-8")


def test_set_level_filters_debug(tmp_path) -> None:
    setup_app_logging(tmp_path / "logs", level="warning", also_console=False)
    logger = logging.getLogger("tests.level")
    logger.debug("hidden")
    logger.warning("visible")
    flush_app_logging()

    log_file = get_log_file_path()
    assert log_file is not None
    text = log_file.read_text(encoding="utf-8")
    assert "visible" in text
    assert "hidden" not in text

    set_level("debug")
    logger.debug("now seen")
    flush_app_logging()
    assert "now seen" in log_file.read_text(encoding="utf-8")


def test_rotating_handler_limits(tmp_path) -> None:
    import core.diagnostics.logging_setup as logging_setup

    setup_app_logging(tmp_path / "logs", also_console=False)
    assert logging_setup._queue_listener is not None
    handler = next(
        h
        for h in logging_setup._queue_listener.handlers
        if hasattr(h, "maxBytes")
    )
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == BACKUP_COUNT
