"""HotkeyPage onboarding tests (controller only, no global hook)."""

from __future__ import annotations

import pytest

from app.config import Config
from app.ui.onboarding.steps.pages import HotkeyPage
from app.ui.settings.controller import SettingsController
from core.secrets import reset_default_store
from core.secrets.mock_store import MemorySecretStore


@pytest.fixture
def controller(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "hotkey.db", migrate_backup=False)
    ctrl = SettingsController(cfg, secret_store=secrets)
    yield ctrl
    cfg.close()
    reset_default_store(None)


def test_hotkey_conflict_check_shows_status(qtbot, controller: SettingsController):
    page = HotkeyPage(controller)
    qtbot.addWidget(page)
    page.initializePage()

    page._record.setText("ctrl+shift+r")
    page._cancel.setText("escape")
    page._check_conflicts()

    text = page._status.text()
    assert "녹음" in text
    assert "취소" in text


def test_validate_page_persists_bindings(qtbot, controller: SettingsController):
    page = HotkeyPage(controller)
    qtbot.addWidget(page)
    page.initializePage()

    page._record.setText("ctrl+shift+r")
    page._cancel.setText("escape")
    assert page.validatePage() is True

    assert controller.get_setting("hotkey.record_binding") == "ctrl+shift+r"
    assert controller.get_setting("hotkey.cancel_binding") == "escape"
