"""Tests for C14 SettingsController."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.ui.settings.controller import LLM_API_KEY_ENV, SettingsController
from core.modes.types import ModeDraft
from core.secrets import LLM_API_KEY_SECRET, reset_default_store
from core.secrets.mock_store import MemorySecretStore
from core.store.models import DictionaryType


@pytest.fixture
def controller(tmp_path):
    config = Config.open(tmp_path / "settings.db", migrate_backup=False)
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    ctrl = SettingsController(config, secret_store=secrets)
    yield ctrl
    config.close()
    reset_default_store(None)


def test_save_and_get_setting(controller: SettingsController) -> None:
    controller.save_setting("stt.model", "small")
    assert controller.get_setting("stt.model") == "small"


def test_save_section_setting(controller: SettingsController) -> None:
    controller.save_section_setting("stt", "model", "medium")
    assert controller.get_setting("stt.model") == "medium"


def test_mask_secret() -> None:
    assert SettingsController.mask_secret("") == ""
    assert SettingsController.mask_secret("ab") == "****"
    assert SettingsController.mask_secret("secret-key").endswith("-key")


def test_api_key_status_from_env(controller: SettingsController, monkeypatch) -> None:
    monkeypatch.delenv(LLM_API_KEY_ENV, raising=False)
    assert controller.get_api_key_status() == "missing"
    monkeypatch.setenv(LLM_API_KEY_ENV, "test-key")
    assert controller.get_api_key_status() == "configured_env"


def test_set_api_key_uses_secret_store(controller: SettingsController) -> None:
    controller.set_api_key(LLM_API_KEY_SECRET, "sk-test-1234")
    assert controller.get_api_key_status() == "configured_store"
    assert controller.get_api_key_hint().endswith("1234")
    assert controller.delete_api_key(LLM_API_KEY_SECRET) is True
    assert controller.get_api_key_status() == "missing"


def test_connection_listener_receives_result(controller: SettingsController) -> None:
    from core.llm import MockLLMProvider

    events: list[bool] = []
    controller.on_connection_result(lambda result: events.append(result.success))
    controller.config.bind_llm_session()
    controller.config._llm_session._providers["ollama"] = MockLLMProvider()
    controller.test_connection("ollama")
    assert events == [True]


def test_check_stt_model_reports_builtin(controller: SettingsController) -> None:
    result = controller.check_stt_model()
    assert result.ok is True
    assert "base" in result.message or "STT" in result.message


def test_validate_hotkey_binding_invalid() -> None:
    ctrl = SettingsController(MagicMock())
    result = ctrl.validate_hotkey_binding("not+a+real+key+combo+ever")
    assert result.ok is False


def test_validate_hotkey_binding_valid() -> None:
    ctrl = SettingsController(MagicMock())
    with patch("app.ui.settings.controller.check_binding_available", return_value=True):
        result = ctrl.validate_hotkey_binding("escape")
    assert result.ok is True


def test_validate_hotkey_pair_rejects_duplicate() -> None:
    ctrl = SettingsController(MagicMock())
    result = ctrl.validate_hotkey_pair("escape", "escape")
    assert result is not None
    assert result.ok is False


def test_test_connection_delegates(controller: SettingsController) -> None:
    from core.llm import MockLLMProvider

    controller.config.bind_llm_session()
    controller.config._llm_session._providers["ollama"] = MockLLMProvider()
    result = controller.test_connection("ollama")
    assert result.success is True


def test_mode_crud(controller: SettingsController) -> None:
    created = controller.create_mode(
        ModeDraft(
            name="테스트 모드",
            target_stage=1,
            inject_stage=1,
        )
    )
    assert created.name == "테스트 모드"
    updated = controller.update_mode(
        created.id,
        ModeDraft(
            name="수정 모드",
            target_stage=2,
            inject_stage=2,
            correction_prompt="교정",
        ),
    )
    assert updated.target_stage == 2
    controller.delete_mode(created.id)


def test_dictionary_api(controller: SettingsController) -> None:
    entry = controller.add_dictionary_entry(
        term="foo",
        replacement="bar",
        entry_type=DictionaryType.VOCAB,
    )
    listed = controller.list_dictionary_entries()
    assert any(item.id == entry.id for item in listed)
    assert controller.delete_dictionary_entry(entry.id) is True
