"""Settings UI controller — Qt-free bridge to C11/C7/C3 (C14)."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.config.schema import SCHEMA_BY_KEY
from app.hotkey.binding import parse_binding
from app.hotkey.conflict import check_binding_available
from app.hotkey.errors import HotkeyBindingError
from app.ui.settings.connection_messages import format_connection_result
from core.llm.types import ConnResult, ModelInfo
from core.models.errors import ModelError
from core.modes.types import ModeDraft
from core.secrets import LLM_API_KEY_SECRET, STT_API_KEY_SECRET, get_default_store
from core.store.models import Mode

if TYPE_CHECKING:
    from app.config.config import Config
    from app.hotkey.hotkey_manager import HotkeyManager
    from app.services.remote_gateway_service import RemoteGatewayService
    from core.audio.audio_capture import AudioCapture

logger = logging.getLogger(__name__)

LLM_API_KEY_ENV = "STT_AIO_LLM_API_KEY"
STT_API_KEY_ENV = "STT_AIO_STT_API_KEY"

ConnectionCallback = Callable[[ConnResult], None]
ModelListCallback = Callable[[list[ModelInfo]], None]


@dataclass(frozen=True)
class HotkeyValidation:
    ok: bool
    message: str


@dataclass(frozen=True)
class AudioDeviceOption:
    device_id: str
    label: str


@dataclass(frozen=True)
class ReadinessResult:
    ok: bool
    message: str


class SettingsController:
    """Plan section 3 actions without Qt dependencies (testable)."""

    def __init__(
        self,
        config: Config,
        *,
        hotkey_manager: HotkeyManager | None = None,
        capture: AudioCapture | None = None,
        gateway_service: RemoteGatewayService | None = None,
        secret_store=None,
    ) -> None:
        self._config = config
        self._hotkey = hotkey_manager
        self._capture = capture
        self._gateway = gateway_service
        self._secrets = secret_store or get_default_store()
        self._connection_listeners: list[ConnectionCallback] = []
        self._model_listeners: list[ModelListCallback] = []

    @property
    def config(self) -> Config:
        return self._config

    def save_setting(self, key: str, value: Any) -> Any:
        return self._config.set(key, value)

    def save_section_setting(self, section: str, key: str, value: Any) -> Any:
        """Plan section 3: save_setting(section, key, value)."""
        return self.save_setting(f"{section}.{key}", value)

    def get_setting(self, key: str) -> Any:
        return self._config.get(key)

    def get_choice_keys(self, key: str) -> tuple[str, ...]:
        defn = SCHEMA_BY_KEY.get(key)
        return defn.choices if defn and defn.choices else ()

    def list_audio_devices(self) -> list[AudioDeviceOption]:
        options = [AudioDeviceOption(device_id="", label="시스템 기본 마이크")]
        if self._capture is None:
            return options
        try:
            for device in self._capture.list_devices():
                suffix = " (기본)" if device.is_default else ""
                options.append(
                    AudioDeviceOption(
                        device_id=str(device.id),
                        label=f"{device.name}{suffix}",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Audio device enumeration failed: %s", exc)
        return options

    def set_api_key(self, name: str, value: str) -> None:
        """Persist API key via C19 secret store (plan section 3)."""
        if name == LLM_API_KEY_SECRET:
            self._config.set_llm_api_key(value)
            return
        if name == STT_API_KEY_SECRET:
            self._config.set_stt_api_key(value)
            return
        self._secrets.set_secret(name, value)
        self._refresh_llm_providers()

    def delete_api_key(self, name: str) -> bool:
        if name == LLM_API_KEY_SECRET:
            return self._config.delete_llm_api_key()
        if name == STT_API_KEY_SECRET:
            return self._config.delete_stt_api_key()
        deleted = self._secrets.delete_secret(name)
        if deleted:
            self._refresh_llm_providers()
        return deleted

    def has_api_key(self, name: str = LLM_API_KEY_SECRET) -> bool:
        if name == LLM_API_KEY_SECRET:
            return self._config.has_llm_api_key()
        if name == STT_API_KEY_SECRET:
            return self._config.has_stt_api_key()
        if self._secrets.has_secret(name):
            return True
        if name == STT_API_KEY_SECRET:
            return bool(os.environ.get(STT_API_KEY_ENV, "").strip())
        return bool(os.environ.get(LLM_API_KEY_ENV, "").strip())

    def get_api_key_hint(self, name: str = LLM_API_KEY_SECRET) -> str:
        if name == LLM_API_KEY_SECRET:
            from core.secrets import get_default_store

            stored = get_default_store().get_secret(LLM_API_KEY_SECRET)
            env_var = LLM_API_KEY_ENV
        elif name == STT_API_KEY_SECRET:
            from core.secrets import get_default_store

            stored = get_default_store().get_secret(STT_API_KEY_SECRET)
            env_var = STT_API_KEY_ENV
        else:
            stored = self._secrets.get_secret(name)
            env_var = ""
        if stored:
            return self.mask_secret(stored)
        env_value = os.environ.get(env_var, "").strip() if env_var else ""
        if env_value:
            return f"{self.mask_secret(env_value)} (환경 변수)"
        if name == STT_API_KEY_SECRET and self._config.has_llm_api_key():
            return "LLM API 키로 폴백"
        return ""

    def get_api_key_status(self) -> str:
        from core.secrets import get_default_store

        if get_default_store().has_secret(LLM_API_KEY_SECRET):
            return "configured_store"
        if os.environ.get(LLM_API_KEY_ENV, "").strip():
            return "configured_env"
        return "missing"

    @staticmethod
    def mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "****"
        return "*" * (len(value) - 4) + value[-4:]

    def on_connection_result(self, callback: ConnectionCallback) -> None:
        self._connection_listeners.append(callback)

    def on_model_list(self, callback: ModelListCallback) -> None:
        self._model_listeners.append(callback)

    def test_connection(self, provider_id: str | None = None) -> ConnResult:
        result = self._config.test_llm_connection(provider_id)
        if not result.success:
            from core.diagnostics import report_error

            report_error(
                result.message,
                context={"component": "llm", "provider": provider_id or self._config.get("llm.provider")},
                log=False,
            )
        for callback in self._connection_listeners:
            callback(result)
        return result

    def refresh_models(self, provider_id: str | None = None) -> list[ModelInfo]:
        models = self._config.list_llm_models(provider_id)
        for callback in self._model_listeners:
            callback(models)
        return models

    def format_connection_result(self, result: ConnResult) -> str:
        return format_connection_result(result)

    def check_stt_model(self) -> ReadinessResult:
        ok, message = self._config.model_manager.readiness_message()
        return ReadinessResult(ok, message)

    def list_whisper_catalog(self):
        return self._config.model_manager.list_catalog()

    def list_whisper_installed(self):
        return self._config.model_manager.list_installed()

    def get_active_whisper_model(self) -> str:
        return self._config.model_manager.get_active()

    def set_active_whisper_model(self, model_id: str) -> ReadinessResult:
        self._config.model_manager.set_active(model_id)
        return self.check_stt_model()

    def is_whisper_model_available(self, model_id: str) -> bool:
        return self._config.model_manager.is_installed(model_id)

    def download_whisper_model(
        self,
        model_id: str,
        on_progress=None,
        *,
        force: bool = False,
        controller=None,
    ) -> str:
        path = self._config.model_manager.download(
            model_id,
            on_progress=on_progress,
            force=force,
            controller=controller,
        )
        return str(path)

    def inspect_whisper_install(self, model_id: str) -> str | None:
        """Return error text when a partial/corrupt folder exists."""
        return self._config.model_manager.verify_install(model_id)

    def verify_whisper_install(self, model_id: str) -> ReadinessResult:
        error = self.inspect_whisper_install(model_id)
        if error:
            return ReadinessResult(False, error)
        if self._config.model_manager.is_installed(model_id):
            return ReadinessResult(True, "설치 검증 통과")
        return ReadinessResult(True, "로컬 캐시 없음 (내장 또는 미설치)")

    def repair_whisper_install(self, model_id: str) -> bool:
        return self._config.model_manager.repair_install(model_id)

    def get_models_dir(self) -> str:
        return str(self._config.model_manager.models_dir)

    def get_default_models_dir(self) -> str:
        return str(self._config.model_manager.default_models_dir)

    def remove_whisper_model(self, model_id: str) -> bool:
        return self._config.model_manager.remove(model_id)

    def set_models_custom_path(self, path: str) -> ReadinessResult:
        try:
            self._config.model_manager.set_custom_path(path)
        except ModelError as exc:
            return ReadinessResult(False, str(exc))
        return ReadinessResult(True, "오프라인 모델 경로가 저장되었습니다.")

    def get_models_custom_path(self) -> str:
        return self._config.model_manager.get_custom_path()

    def list_ollama_models_managed(self):
        return self._config.model_manager.list_ollama_models()

    def get_log_file_path(self) -> str:
        from core.diagnostics import get_log_file_path
        from core.diagnostics.logging_setup import LOG_FILENAME

        path = get_log_file_path()
        if path is not None:
            return str(path)
        return str(self._config.paths().logs / LOG_FILENAME)

    def get_logs_dir(self) -> str:
        return str(self._config.paths().logs)

    def export_diagnostics_package(self, dest_path: str) -> ReadinessResult:
        from pathlib import Path

        from core.diagnostics import report_error

        try:
            remote = None
            if self._gateway is not None:
                remote = self._gateway.diagnostics_snapshot()
            result = self._config.export_diagnostics_zip(
                Path(dest_path),
                capture=self._capture,
                remote_gateway=remote,
            )
            message = f"진단 패키지를 생성했습니다: {result.path}"
            if result.failures:
                warnings = "\n".join(f"- {item}" for item in result.failures)
                message += f"\n\n일부 항목을 수집하지 못했습니다:\n{warnings}"
            return ReadinessResult(True, message)
        except Exception as exc:  # noqa: BLE001
            report_error(exc)
            return ReadinessResult(False, str(exc))

    def validate_hotkey_binding(self, binding: str) -> HotkeyValidation:
        text = binding.strip()
        if not text:
            return HotkeyValidation(False, "단축키를 입력하세요.")
        try:
            parse_binding(text)
        except HotkeyBindingError as exc:
            return HotkeyValidation(False, str(exc))
        backend = getattr(self._hotkey, "_backend", None) if self._hotkey else None
        if not check_binding_available(text, backend=backend):
            return HotkeyValidation(False, "시스템에서 사용 중이거나 예약된 단축키입니다.")
        return HotkeyValidation(True, "사용 가능한 단축키입니다.")

    def validate_hotkey_pair(self, record: str, cancel: str) -> HotkeyValidation | None:
        """Return validation error when record/cancel bindings conflict."""
        if record.strip().lower() == cancel.strip().lower():
            return HotkeyValidation(False, "녹음과 취소 단축키는 서로 달라야 합니다.")
        return None

    def list_modes(self, *, enabled_only: bool = False) -> list[Mode]:
        return self._config.mode_manager.list_modes(enabled_only=enabled_only)

    def get_mode(self, mode_id: str) -> Mode:
        return self._config.mode_manager.get_mode(mode_id)

    def create_mode(self, draft: ModeDraft, *, mode_id: str | None = None) -> Mode:
        return self._config.mode_manager.create_mode(draft, mode_id=mode_id)

    def update_mode(self, mode_id: str, draft: ModeDraft) -> Mode:
        return self._config.mode_manager.update_mode(mode_id, draft)

    def delete_mode(self, mode_id: str) -> None:
        self._config.mode_manager.delete_mode(mode_id)

    def restore_builtin_mode(self, mode_id: str) -> Mode:
        return self._config.mode_manager.restore_builtin(mode_id)

    def set_default_mode(self, mode_id: str) -> Mode:
        return self._config.mode_manager.set_default_mode(mode_id)

    def set_active_mode_id(self, mode_id: str) -> str:
        return self._config.set_active_mode_id(mode_id)

    def list_dictionary_entries(self, *, enabled_only: bool = False):
        return self._config.list_dictionary_entries(enabled_only=enabled_only)

    def add_dictionary_entry(self, *, term: str, replacement: str, entry_type, enabled: bool = True):
        return self._config.add_dictionary_entry(
            term=term,
            replacement=replacement,
            entry_type=entry_type,
            enabled=enabled,
        )

    def delete_dictionary_entry(self, entry_id: str) -> bool:
        return self._config.delete_dictionary_entry(entry_id)

    def _refresh_llm_providers(self) -> None:
        if self._config._llm_session is not None:
            self._config._llm_session.refresh()

    # --- C21 Onboarding helpers ---

    def is_onboarding_completed(self) -> bool:
        return bool(self.get_setting("onboarding.completed"))

    def mark_onboarding_completed(self) -> None:
        self.save_setting("onboarding.completed", True)

    def apply_hotkey_bindings(self) -> None:
        if self._hotkey is not None:
            self._hotkey.apply_config(self._config)

    # Plan §3 named step operations
    def download_model(
        self,
        model_id: str,
        on_progress=None,
        *,
        force: bool = False,
    ) -> str:
        return self.download_whisper_model(model_id, on_progress=on_progress, force=force)

    def test_mic(
        self,
        device_id: str | None = None,
        *,
        duration_sec: float = 1.0,
    ) -> ReadinessResult:
        return self.probe_microphone(device_id, duration_sec=duration_sec)

    def set_hotkey(
        self,
        record: str,
        cancel: str,
        *,
        strict: bool = True,
    ) -> HotkeyValidation:
        """Save hotkey bindings when valid (plan §3: set_hotkey)."""
        record = record.strip()
        cancel = cancel.strip()
        record_result = self.validate_hotkey_binding(record)
        if not record_result.ok:
            return record_result if strict else HotkeyValidation(
                False, f"녹음 단축키 미저장: {record_result.message}"
            )
        cancel_result = self.validate_hotkey_binding(cancel)
        if not cancel_result.ok:
            return cancel_result if strict else HotkeyValidation(
                False, f"취소 단축키 미저장: {cancel_result.message}"
            )
        pair = self.validate_hotkey_pair(record, cancel)
        if pair is not None:
            return pair if strict else HotkeyValidation(False, f"단축키 미저장: {pair.message}")
        self.save_setting("hotkey.record_binding", record)
        self.save_setting("hotkey.cancel_binding", cancel)
        return HotkeyValidation(True, "단축키가 저장되었습니다.")

    def test_injection(self, text: str):
        """Inject sample text into the focused window (C5)."""
        from core.inject.types import InjectResult

        if self._config._injector is None:
            self._config.bind_injector()
        result = self._config.injector.inject(text)
        if not isinstance(result, InjectResult):
            raise TypeError("injector.inject must return InjectResult")
        return result

    def probe_microphone(
        self,
        device_id: str | None = None,
        *,
        duration_sec: float = 1.0,
        on_level=None,
    ) -> ReadinessResult:
        """Record briefly and verify input level (C1)."""
        if self._capture is None:
            return ReadinessResult(False, "오디오 캡처를 사용할 수 없습니다.")
        import time

        from core.audio.errors import AudioError
        from core.audio.level import compute_peak_rms

        did = device_id if device_id is not None else str(self.get_setting("audio.device_id"))
        try:
            self._capture.select_device(did or None)
            if on_level is not None:
                self._capture.set_level_callback(on_level)
            handle = self._capture.start_batch()
            time.sleep(max(0.2, duration_sec))
            buffer = self._capture.stop_batch(handle)
        except AudioError as exc:
            return ReadinessResult(False, str(exc))
        except Exception as exc:  # noqa: BLE001
            return ReadinessResult(False, str(exc))
        finally:
            if on_level is not None:
                self._capture.set_level_callback(None)

        peak, rms = compute_peak_rms(buffer.pcm_bytes)
        if buffer.is_empty or (peak < 0.01 and rms < 0.005):
            return ReadinessResult(
                False,
                "입력 신호가 거의 감지되지 않았습니다. 마이크와 권한을 확인하세요.",
            )
        return ReadinessResult(True, f"마이크 입력 확인 (peak={peak:.0%})")
