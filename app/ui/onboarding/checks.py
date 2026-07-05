"""Onboarding step readiness checks (C21 plan §6.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.config import Config
    from app.ui.settings.controller import SettingsController

ONBOARDING_KEY = "onboarding.completed"
RECOMMENDED_WHISPER_MODEL = "base"
INJECTION_SAMPLE_TEXT = "안녕하세요, STT-AIO 테스트입니다."

STEPS: tuple[str, ...] = (
    "welcome",
    "provider",
    "model",
    "mic",
    "injection",
    "hotkey",
    "done",
)


@dataclass(frozen=True)
class StepCheck:
    ok: bool
    message: str


def is_completed(config: Config) -> bool:
    return bool(config.get(ONBOARDING_KEY))


def mark_completed(config: Config) -> None:
    config.set(ONBOARDING_KEY, True)


def check_provider(
    config: Config,
    controller: SettingsController,
    *,
    connection_tested: bool = False,
) -> StepCheck:
    provider = str(config.get("llm.provider"))
    if provider == "openai_compat" and not controller.has_api_key():
        return StepCheck(False, "클라우드 Provider — API 키가 필요합니다.")
    if connection_tested:
        return StepCheck(True, f"LLM Provider: {provider} (연결 테스트 성공)")
    return StepCheck(True, f"LLM Provider: {provider}")


def check_model(config: Config) -> StepCheck:
    ok, message = config.model_manager.readiness_message()
    return StepCheck(ok, message)


def check_mic(
    controller: SettingsController,
    *,
    mic_tested: bool = False,
) -> StepCheck:
    if mic_tested:
        return StepCheck(True, "마이크 입력 테스트 확인됨")
    devices = controller.list_audio_devices()
    if controller._capture is None:
        return StepCheck(False, "마이크 장치를 확인할 수 없습니다.")
    if len(devices) <= 1:
        return StepCheck(False, "마이크 장치 목록을 가져오지 못했습니다.")
    return StepCheck(False, "마이크 테스트 미실행 (설정에서 다시 시도 권장)")


def check_hotkey(controller: SettingsController) -> StepCheck:
    record = str(controller.get_setting("hotkey.record_binding")).strip()
    cancel = str(controller.get_setting("hotkey.cancel_binding")).strip()
    record_result = controller.validate_hotkey_binding(record)
    if not record_result.ok:
        return StepCheck(False, record_result.message)
    cancel_result = controller.validate_hotkey_binding(cancel)
    if not cancel_result.ok:
        return StepCheck(False, cancel_result.message)
    pair = controller.validate_hotkey_pair(record, cancel)
    if pair is not None:
        return StepCheck(False, pair.message)
    return StepCheck(True, "단축키 설정이 유효합니다.")


def check_injection(
    controller: SettingsController,
    *,
    injection_verified: bool = False,
) -> StepCheck:
    if injection_verified:
        return StepCheck(True, "한글 주입 테스트 확인됨")
    try:
        if controller.config._injector is None:
            controller.config.bind_injector()
        caps = controller.config.injector.capabilities()
        if not caps.supports_unicode and not caps.supports_clipboard:
            return StepCheck(False, "이 환경에서는 텍스트 주입을 지원하지 않습니다.")
        return StepCheck(False, "한글 주입 테스트 미확인 (설정에서 다시 시도 권장)")
    except Exception as exc:  # noqa: BLE001
        return StepCheck(False, str(exc))


def summarize_readiness(
    config: Config,
    controller: SettingsController,
    *,
    injection_verified: bool = False,
    mic_tested: bool = False,
    connection_tested: bool = False,
) -> dict[str, StepCheck]:
    return {
        "provider": check_provider(
            config, controller, connection_tested=connection_tested
        ),
        "model": check_model(config),
        "mic": check_mic(controller, mic_tested=mic_tested),
        "injection": check_injection(controller, injection_verified=injection_verified),
        "hotkey": check_hotkey(controller),
    }
