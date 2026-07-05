"""ProviderPage onboarding tests (fake tasks, no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.ui.onboarding.steps.pages import ProviderPage
from app.ui.settings.controller import SettingsController
from core.llm.types import ConnResult
from core.secrets import reset_default_store
from core.secrets.mock_store import MemorySecretStore


class FakeProviderTasks:
    def run_llm_test(self, controller, provider_id, *, on_finished, on_failed) -> None:
        self.on_finished = on_finished
        self.on_failed = on_failed


@pytest.fixture
def controller(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "provider.db", migrate_backup=False)
    ctrl = SettingsController(cfg, secret_store=secrets)
    yield ctrl
    cfg.close()
    reset_default_store(None)


def test_local_provider_validate_saves_ollama(qtbot, controller: SettingsController):
    tasks = FakeProviderTasks()
    page = ProviderPage(controller, tasks)
    qtbot.addWidget(page)
    page.initializePage()

    page._local.setChecked(True)
    assert page.validatePage() is True
    assert controller.get_setting("llm.provider") == "ollama"


def test_connection_test_success_marks_tested(qtbot, controller: SettingsController):
    tasks = FakeProviderTasks()
    page = ProviderPage(controller, tasks)
    qtbot.addWidget(page)
    page.initializePage()

    page._run_test()
    tasks.on_finished(ConnResult(success=True, message="연결됨"))

    assert page.connection_tested() is True
    assert "연결됨" in page._status.text()


def test_connection_test_failure_shows_retry_hint(qtbot, controller: SettingsController):
    tasks = FakeProviderTasks()
    page = ProviderPage(controller, tasks)
    qtbot.addWidget(page)
    page.initializePage()

    page._run_test()
    tasks.on_finished(ConnResult(success=False, message="401 Unauthorized"))

    assert page.connection_tested() is False
    assert "설정 > LLM" in page._status.text()
