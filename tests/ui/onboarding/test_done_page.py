"""DonePage summary rendering (no full wizard navigation)."""

from __future__ import annotations

import pytest

from app.config import Config
from app.ui.onboarding.steps.pages import DonePage
from app.ui.settings.controller import SettingsController
from core.secrets import reset_default_store
from core.secrets.mock_store import MemorySecretStore


@pytest.fixture
def controller(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "done.db", migrate_backup=False)
    ctrl = SettingsController(cfg, secret_store=secrets)
    yield ctrl
    cfg.close()
    reset_default_store(None)


def test_done_page_renders_summary_without_wizard(qtbot, controller: SettingsController):
    page = DonePage(controller)
    qtbot.addWidget(page)

    page.initializePage()
    text = page._summary.toPlainText()

    assert "설정 화면" in text
    assert "한글 주입" in text
