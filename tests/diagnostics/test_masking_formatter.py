"""Masking formatter and path redaction tests (C20)."""

from __future__ import annotations

import json
import logging
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from app.config import Config
from core.diagnostics.diagnostics import _redact_path, collect_environment, export_diagnostics
from core.diagnostics.masking_filter import MaskingFormatter
from core.diagnostics.logging_setup import reset_app_logging, setup_app_logging
from core.secrets import reset_default_store
from core.secrets.mock_store import MemorySecretStore


def test_masking_formatter_masks_message() -> None:
    formatter = MaskingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization sk-abcdefghijklmnopqrst",
        args=(),
        exc_info=None,
    )
    text = formatter.format(record)
    assert "sk-abcdefghijklmnopqrst" not in text
    assert "sk-****" in text


def test_masking_formatter_masks_traceback() -> None:
    formatter = MaskingFormatter("%(message)s")
    try:
        raise ValueError("failed with sk-abcdefghijklmnopqrst token")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="boom",
        args=(),
        exc_info=exc_info,
    )
    text = formatter.format(record)
    assert "sk-abcdefghijklmnopqrst" not in text
    assert "sk-****" in text


def test_redact_path_replaces_home() -> None:
    home = Path.home()
    nested = home / "logs" / "stt-aio.log"
    redacted = _redact_path(str(nested))
    assert str(home) not in redacted
    assert redacted.startswith("~")


def test_collect_environment_redacts_cwd(config: Config, monkeypatch) -> None:
    home = Path.home()
    monkeypatch.chdir(home)
    env = collect_environment(config=config)
    assert str(home) not in env["cwd"]
    assert env["cwd"].startswith("~")


def test_export_environment_no_home_leak(config: Config, tmp_path, monkeypatch) -> None:
    home = Path.home()
    monkeypatch.chdir(home)
    logs_dir = config.paths().logs
    setup_app_logging(logs_dir, also_console=False)
    result = export_diagnostics(tmp_path / "paths.zip", logs_dir=logs_dir, config=config)
    with zipfile.ZipFile(result.path) as archive:
        env = json.loads(archive.read("environment.json"))
    home_text = str(home)
    if home_text:
        assert home_text not in env["cwd"]
        if "log_file" in env:
            assert home_text not in env["log_file"]


def test_concurrent_logging_writes(config: Config, tmp_path) -> None:
    reset_app_logging()
    logs_dir = tmp_path / "concurrent-logs"
    setup_app_logging(logs_dir, level="info", also_console=False)

    def worker(index: int) -> None:
        logging.getLogger(f"tests.concurrent.{index}").info("line-%s", index)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    log_file = logs_dir / "stt-aio.log"
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert text.count("line-") >= 20


@pytest.fixture
def config(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "mask.db", migrate_backup=False)
    yield cfg
    cfg.close()
    reset_default_store(None)


@pytest.fixture(autouse=True)
def _reset_logging():
    reset_app_logging()
    yield
    reset_app_logging()
