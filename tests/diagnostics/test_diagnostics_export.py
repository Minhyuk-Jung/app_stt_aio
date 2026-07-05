"""Tests for diagnostics export (C20)."""

from __future__ import annotations

import json
import zipfile

import pytest

from app.config import Config
from core.diagnostics import report_error, setup_app_logging
from core.diagnostics.diagnostics import export_diagnostics
from core.diagnostics.errors import clear_errors, recent_errors
from core.diagnostics.logging_setup import LOG_FILENAME
from core.secrets import LLM_API_KEY_SECRET, reset_default_store
from core.secrets.mock_store import MemorySecretStore


@pytest.fixture(autouse=True)
def _reset_logging():
    from core.diagnostics.logging_setup import reset_app_logging

    reset_app_logging()
    yield
    reset_app_logging()


@pytest.fixture
def config(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "diag.db", migrate_backup=False)
    cfg.set_llm_api_key("sk-test-secret-key-12345678")
    yield cfg
    cfg.close()
    reset_default_store(None)


def test_report_error_records_event() -> None:
    clear_errors()
    long_msg = "x" * 400
    report_error(ValueError(long_msg), context={"component": "test"}, log=False)
    events = recent_errors()
    assert len(events) == 1
    assert events[0]["error_type"] == "ValueError"
    assert events[0]["context"]["component"] == "test"
    assert "redacted" in events[0]["message"]


def test_export_diagnostics_zip_contents(config: Config, tmp_path) -> None:
    logs_dir = config.paths().logs
    setup_app_logging(logs_dir, level="info", also_console=False)
    logging = __import__("logging")
    logging.getLogger("tests.export").info("token sk-abcdefghijklmnopqrst visible")

    dest = tmp_path / "diag.zip"
    result = export_diagnostics(dest, logs_dir=logs_dir, config=config)

    assert result.path.is_file()
    assert isinstance(result.failures, tuple)
    with zipfile.ZipFile(result.path) as archive:
        names = set(archive.namelist())
        assert "environment.json" in names
        assert "errors.json" in names
        assert any(name.startswith("logs/") for name in names)

        env = json.loads(archive.read("environment.json"))
        assert "hardware" in env
        assert "cpu_count" in env["hardware"]
        assert "stt_model_readiness" in env
        settings = env["settings"]
        assert settings["meta.has_llm_api_key"] is True
        assert LLM_API_KEY_SECRET not in settings or settings.get(LLM_API_KEY_SECRET) == "***"

        log_text = archive.read(f"logs/{LOG_FILENAME}").decode("utf-8")
        assert "sk-abcdefghijklmnopqrst" not in log_text
        assert "sk-****" in log_text


def test_export_diagnostics_includes_remote_gateway(config: Config, tmp_path) -> None:
    logs_dir = config.paths().logs
    setup_app_logging(logs_dir, level="info", also_console=False)
    dest = tmp_path / "diag-remote.zip"
    remote = {
        "running": True,
        "lan_url": "http://192.168.0.5:8765",
        "public_url": None,
        "pin_active": True,
    }
    result = export_diagnostics(
        dest,
        logs_dir=logs_dir,
        config=config,
        remote_gateway=remote,
    )
    with zipfile.ZipFile(result.path) as archive:
        env = json.loads(archive.read("environment.json"))
    assert env["remote_gateway"]["running"] is True
    assert env["remote_gateway"]["lan_url"] == "http://192.168.0.5:8765"
