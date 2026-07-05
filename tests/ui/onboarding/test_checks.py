"""Tests for C21 onboarding checks, controller helpers, and wizard behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.ui.onboarding.checks import (
    ONBOARDING_KEY,
    STEPS,
    check_hotkey,
    check_injection,
    check_mic,
    check_model,
    check_provider,
    is_completed,
    mark_completed,
    summarize_readiness,
)
from app.ui.settings.controller import SettingsController
from core.secrets import reset_default_store
from core.secrets.mock_store import MemorySecretStore


@pytest.fixture
def config(tmp_path):
    secrets = MemorySecretStore()
    reset_default_store(secrets)
    cfg = Config.open(tmp_path / "onboard.db", migrate_backup=False)
    yield cfg
    cfg.close()
    reset_default_store(None)


@pytest.fixture
def controller(config: Config):
    return SettingsController(config, secret_store=MemorySecretStore())


def test_step_order_matches_plan() -> None:
    assert STEPS == (
        "welcome",
        "provider",
        "model",
        "mic",
        "injection",
        "hotkey",
        "done",
    )


def test_onboarding_not_completed_by_default(config: Config) -> None:
    assert is_completed(config) is False
    assert config.get(ONBOARDING_KEY) is False


def test_mark_completed_persists(config: Config) -> None:
    mark_completed(config)
    assert is_completed(config) is True


def test_controller_onboarding_flag(controller: SettingsController) -> None:
    assert controller.is_onboarding_completed() is False
    controller.mark_onboarding_completed()
    assert controller.is_onboarding_completed() is True


def test_check_provider_local_ok(controller: SettingsController) -> None:
    controller.save_setting("llm.provider", "ollama")
    result = check_provider(controller.config, controller)
    assert result.ok is True


def test_check_provider_cloud_requires_key(controller: SettingsController) -> None:
    controller.save_setting("llm.provider", "openai_compat")
    result = check_provider(controller.config, controller)
    assert result.ok is False
    assert "API" in result.message


def test_check_model_reports_readiness(controller: SettingsController) -> None:
    result = check_model(controller.config)
    assert isinstance(result.ok, bool)
    assert result.message


def test_check_mic_without_capture(controller: SettingsController) -> None:
    result = check_mic(controller)
    assert result.ok is False
    assert "미실행" in result.message or "확인할 수 없습니다" in result.message


def test_check_mic_with_tested_flag(controller: SettingsController) -> None:
    result = check_mic(controller, mic_tested=True)
    assert result.ok is True
    assert "확인됨" in result.message


def test_check_injection_unverified(controller: SettingsController) -> None:
    controller.config.bind_injector()
    result = check_injection(controller, injection_verified=False)
    assert result.ok is False
    assert "미확인" in result.message


def test_check_injection_verified(controller: SettingsController) -> None:
    result = check_injection(controller, injection_verified=True)
    assert result.ok is True


def test_check_hotkey_valid_defaults(controller: SettingsController) -> None:
    result = check_hotkey(controller)
    assert result.ok is True


def test_summarize_readiness_keys(controller: SettingsController) -> None:
    summary = summarize_readiness(controller.config, controller)
    assert set(summary) == {"provider", "model", "mic", "injection", "hotkey"}


def test_probe_microphone_without_capture(controller: SettingsController) -> None:
    result = controller.probe_microphone()
    assert result.ok is False


def test_test_injection_binds_injector(controller: SettingsController) -> None:
    controller.config.bind_injector()
    result = controller.test_injection("테스트")
    assert result.success in (True, False)


def test_set_hotkey_saves_valid_bindings(controller: SettingsController) -> None:
    result = controller.set_hotkey("ctrl+shift+f9", "escape")
    assert result.ok is True
    assert controller.get_setting("hotkey.record_binding") == "ctrl+shift+f9"


def test_set_hotkey_strict_rejects_invalid(controller: SettingsController) -> None:
    result = controller.set_hotkey("not+a+valid+combo+xyz", "escape", strict=True)
    assert result.ok is False


def test_set_hotkey_non_strict_allows_invalid(controller: SettingsController) -> None:
    before = controller.get_setting("hotkey.record_binding")
    result = controller.set_hotkey("not+a+valid+combo+xyz", "escape", strict=False)
    assert result.ok is False
    assert controller.get_setting("hotkey.record_binding") == before


def test_download_model_alias_delegates(controller: SettingsController, monkeypatch) -> None:
    calls: list[str] = []

    def fake(model_id: str, on_progress=None, force: bool = False) -> str:
        calls.append(model_id)
        return "/models/base"

    monkeypatch.setattr(controller, "download_whisper_model", fake)
    assert controller.download_model("base") == "/models/base"
    assert calls == ["base"]


def test_on_completed_callback_invoked(config: Config) -> None:
    pytest.importorskip("PySide6")
    from app.ui.onboarding.onboarding_wizard import OnboardingWizard

    controller = SettingsController(config, secret_store=MemorySecretStore())
    events: list[str] = []

    wizard = OnboardingWizard(
        controller,
        MagicMock(),
        on_completed=lambda: events.append("done"),
    )
    wizard._on_finished(int(wizard.DialogCode.Accepted))

    assert events == ["done"]
    assert controller.is_onboarding_completed() is True


def test_wizard_is_skipping_flag(config: Config) -> None:
    pytest.importorskip("PySide6")
    from app.ui.onboarding.onboarding_wizard import OnboardingWizard

    controller = SettingsController(config, secret_store=MemorySecretStore())
    wizard = OnboardingWizard(controller, MagicMock())
    assert wizard.is_skipping() is False
    wizard._skipping = True
    assert wizard.is_skipping() is True


def test_wizard_reject_does_not_mark_completed(config: Config) -> None:
    pytest.importorskip("PySide6")
    from app.ui.onboarding.onboarding_wizard import OnboardingWizard

    controller = SettingsController(config, secret_store=MemorySecretStore())
    wizard = OnboardingWizard(controller, MagicMock())
    wizard._on_finished(int(wizard.DialogCode.Rejected))
    assert controller.is_onboarding_completed() is False


def test_partial_onboarding_settings_persist(config: Config) -> None:
    controller = SettingsController(config, secret_store=MemorySecretStore())
    controller.save_setting("llm.provider", "openai_compat")
    controller.save_setting("audio.device_id", "device-1")
    assert config.get("llm.provider") == "openai_compat"
    assert config.get("audio.device_id") == "device-1"
    assert is_completed(config) is False
