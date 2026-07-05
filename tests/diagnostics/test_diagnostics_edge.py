"""Additional diagnostics edge-case tests (C20)."""

from __future__ import annotations

import json
import logging
import zipfile
from unittest.mock import patch

import pytest

from app.config import Config
from core.diagnostics.diagnostics import export_diagnostics
from core.diagnostics.logging_setup import (
    FallbackRotatingFileHandler,
    flush_app_logging,
    get_memory_log_lines,
    reset_app_logging,
    setup_app_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    reset_app_logging()
    yield
    reset_app_logging()


def test_memory_buffer_on_file_write_failure(tmp_path) -> None:
    import core.diagnostics.logging_setup as logging_module
    from logging.handlers import RotatingFileHandler

    setup_app_logging(tmp_path / "logs", level="info", also_console=False)
    listener = logging_module._queue_listener
    handlers = list(listener.handlers) if listener is not None else []
    if listener is not None:
        try:
            listener.stop()
        except Exception:  # noqa: BLE001
            pass
        logging_module._queue_listener = None
    real_emit = RotatingFileHandler.emit

    def deny_tests_memory(self, record) -> None:
        if record.name == "tests.memory":
            raise OSError("denied")
        return real_emit(self, record)

    with patch("logging.handlers.RotatingFileHandler.emit", deny_tests_memory):
        logging.getLogger("tests.memory").error("fallback line")
        while logging_module._log_queue is not None:
            try:
                record = logging_module._log_queue.get_nowait()
            except Exception:  # noqa: BLE001
                break
            if record is None:
                continue
            for handler in handlers:
                handler.handle(record)
    assert any("fallback line" in line for line in get_memory_log_lines())


def test_export_without_disk_logs_uses_memory_buffer(config: Config, tmp_path) -> None:
    from logging.handlers import RotatingFileHandler

    empty_logs = tmp_path / "empty-logs"
    empty_logs.mkdir()
    setup_app_logging(tmp_path / "active-logs", level="info", also_console=False)
    real_emit = RotatingFileHandler.emit

    def deny_tests_memory(self, record) -> None:
        if record.name == "tests.memory":
            raise OSError("denied")
        return real_emit(self, record)

    with patch("logging.handlers.RotatingFileHandler.emit", deny_tests_memory):
        logging.getLogger("tests.memory").warning("buffered line")
        flush_app_logging()

    result = export_diagnostics(tmp_path / "diag.zip", logs_dir=empty_logs, config=config)
    with zipfile.ZipFile(result.path) as archive:
        assert "logs/memory-buffer.log" in archive.namelist()
        content = archive.read("logs/memory-buffer.log").decode("utf-8")
        assert "buffered line" in content


def test_export_failures_written_to_zip(config: Config, tmp_path) -> None:
    logs_dir = tmp_path / "no-logs"
    logs_dir.mkdir()
    reset_app_logging()
    result = export_diagnostics(tmp_path / "partial.zip", logs_dir=logs_dir, config=config)
    with zipfile.ZipFile(result.path) as archive:
        assert "export_failures.json" in archive.namelist()
        failures = json.loads(archive.read("export_failures.json"))
        assert failures


def test_fallback_handler_type(tmp_path) -> None:
    import core.diagnostics.logging_setup as logging_setup

    setup_app_logging(tmp_path / "logs", also_console=False)
    assert logging_setup._queue_listener is not None
    assert any(
        isinstance(h, FallbackRotatingFileHandler)
        for h in logging_setup._queue_listener.handlers
    )


@pytest.fixture
def config(tmp_path):
    from core.secrets import reset_default_store
    from core.secrets.mock_store import MemorySecretStore

    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "diag-edge.db", migrate_backup=False)
    yield cfg
    cfg.close()
    reset_default_store(None)
