"""Typed application configuration backed by C6 Store."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config.migration import migrate_settings, repair_invalid_settings
from app.config.schema import (
    SCHEMA_BY_KEY,
    SECTIONS,
    SettingDef,
    keys_in_section,
    parse_value,
    serialize_value,
    validate_value,
)
from core.audio.settings import AudioSettings
from core.paths import AppPaths, ensure_app_dirs, get_app_paths
from core.inject import InjectMethod, InjectOptions, Injector
from core.stt import STTProvider, STTOptions, create_provider
from core.stt.registry import resolve_provider_id
from core.store import Store
from core.store.repos.setting_repo import SettingRepo

logger = logging.getLogger(__name__)

ChangeCallback = Callable[[str, Any], None]


class Config:
    """Type-safe settings facade over SettingRepo."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._settings: SettingRepo = store.settings
        self._cache: dict[str, Any] = {}
        self._listeners: dict[str, list[ChangeCallback]] = defaultdict(list)
        self._stt_session = None
        self._injector: Injector | None = None
        self._hotkey_manager = None
        self._session_manager = None
        self._pipeline = None
        self._pipeline_queue = None
        self._mode_manager = None
        self._model_manager = None
        self._llm_session = None
        self._text_processor = None
        self._logging_listener_registered = False
        base = ensure_app_dirs(get_app_paths(store.db.path.parent))
        self._paths = AppPaths(
            root=base.root,
            db=store.db.path,
            models=base.models,
            audio=base.audio,
            logs=base.logs,
        )
        self._initialize()

    @classmethod
    def open(cls, db_path=None, *, migrate_backup: bool = True) -> Config:
        return cls(Store(db_path, migrate_backup=migrate_backup))

    @classmethod
    def open_safe(cls, db_path=None) -> Config:
        """Open config in read-only safe mode (C6 recovery path)."""
        return cls(Store.open_readonly(db_path))

    @property
    def readonly(self) -> bool:
        return self._store.readonly

    def run_privacy_maintenance(self) -> int:
        """Enforce audio retention policy (C19). Returns deleted file count."""
        from core.privacy import purge_expired_audio

        return purge_expired_audio(
            self._paths.audio,
            retention_days=int(self.get("privacy.audio_retention_days")),
            keep_audio=bool(self.get("privacy.keep_audio")),
        )

    def _initialize(self) -> None:
        if self.readonly:
            self._reload_cache()
            self.bind_mode_manager()
            self.bind_model_manager()
            self.apply_logging()
            return
        migrate_settings(self._settings)
        repaired = repair_invalid_settings(
            self._settings,
            backup_dir=self._paths.logs,
        )
        if repaired:
            logger.info("Repaired invalid settings: %s", ", ".join(repaired))
        self._reload_cache()
        self.bind_mode_manager()
        self.bind_model_manager()
        self.apply_logging()
        if not str(self.get("mode.active_id")).strip():
            self.set("mode.active_id", self.mode_manager.get_default_mode().id)

    def bind_mode_manager(self, manager=None):
        """Create/reuse ModeManager and seed built-in modes (C7)."""
        from core.modes import ModeManager

        if manager is not None:
            self._mode_manager = manager
            return manager
        if self._mode_manager is None:
            self._mode_manager = ModeManager(self._store.modes)
            self._mode_manager.seed_defaults()
        return self._mode_manager

    @property
    def mode_manager(self):
        """Bound mode manager with seeded defaults."""
        if self._mode_manager is None:
            raise RuntimeError("Call bind_mode_manager() before accessing mode_manager")
        return self._mode_manager

    def bind_model_manager(self, manager=None):
        """Create/reuse ModelManager (C18)."""
        from core.models import ModelManager

        if manager is not None:
            self._model_manager = manager
            return self._model_manager
        if self._model_manager is None:
            self._model_manager = ModelManager(self)
        return self._model_manager

    @property
    def model_manager(self):
        """Bound model manager for Whisper/Ollama helpers."""
        if self._model_manager is None:
            raise RuntimeError("Call bind_model_manager() before accessing model_manager")
        return self._model_manager

    def get_active_mode_id(self) -> str:
        """Return configured active mode id, falling back to the default mode."""
        if self._mode_manager is None:
            self.bind_mode_manager()
        requested = str(self.get("mode.active_id")).strip()
        if requested:
            stored = self._store.modes.get(requested)
            if stored is not None and stored.enabled:
                return requested
        return self.mode_manager.get_default_mode().id

    def set_active_mode_id(self, mode_id: str) -> str:
        """Persist the user's active mode selection (C7/C12)."""
        if self._mode_manager is None:
            self.bind_mode_manager()
        mode = self.mode_manager.get_mode(mode_id)
        if not mode.enabled:
            raise ValueError(f"mode is disabled: {mode_id}")
        self.set("mode.active_id", mode_id)
        return mode_id

    def get_active_mode(self):
        """Return the active Mode record."""
        return self.mode_manager.get_mode(self.get_active_mode_id())

    @property
    def schema_version(self) -> int:
        raw = self._settings.get("config.schema_version")
        if raw is None:
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    @classmethod
    def from_paths(cls, paths: AppPaths, *, migrate_backup: bool = True) -> Config:
        ensure_app_dirs(paths)
        return cls(Store(paths.db, migrate_backup=migrate_backup))

    def _reload_cache(self) -> None:
        self._cache.clear()
        for key, defn in SCHEMA_BY_KEY.items():
            raw = self._settings.get(key)
            if raw is None:
                self._cache[key] = defn.default
                continue
            try:
                parsed = parse_value(defn, raw)
                validate_value(defn, parsed)
                self._cache[key] = parsed
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Cache reload repaired invalid setting %s (%s): %s",
                    key,
                    raw,
                    exc,
                )
                self._settings.set(key, serialize_value(defn, defn.default))
                self._cache[key] = defn.default

    def paths(self) -> AppPaths:
        return self._paths

    def apply_logging(self) -> Path:
        """Apply C20 logging from logging.level."""
        from core.diagnostics import set_level, setup_app_logging

        level = str(self.get("logging.level"))
        log_file = setup_app_logging(self._paths.logs, level=level)
        set_level(level)

        if not self._logging_listener_registered:
            def on_logging_change(_key: str, _value: object) -> None:
                set_level(str(self.get("logging.level")))

            self.on_change("logging.level", on_logging_change)
            self._logging_listener_registered = True
        return log_file

    def export_diagnostics_zip(self, dest_zip: Path, *, capture=None, remote_gateway=None):
        from core.diagnostics import export_diagnostics

        return export_diagnostics(
            dest_zip,
            logs_dir=self._paths.logs,
            config=self,
            capture=capture,
            remote_gateway=remote_gateway,
        )

    def get_audio_settings(self) -> AudioSettings:
        return AudioSettings(
            device_id=self.get("audio.device_id"),
            vad_engine=str(self.get("audio.vad_engine")),
            vad_threshold=self.get("audio.vad_threshold"),
            min_speech_ms=self.get("audio.min_speech_ms"),
            hangover_ms=self.get("audio.hangover_ms"),
            max_segment_ms=self.get("audio.max_segment_ms"),
        )

    def resolve_export_dir(self) -> Path:
        configured = str(self.get("export.default_dir")).strip()
        if configured:
            path = Path(configured)
        else:
            path = self._paths.root / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def bind_audio_capture(self, capture) -> None:
        """Apply audio settings and subscribe to device changes (C1 integration)."""
        capture.apply_settings(self.get_audio_settings())

        def on_audio_change(_key: str, _value: object) -> None:
            capture.apply_settings(self.get_audio_settings())

        for key in keys_in_section("audio"):
            self.on_change(key, on_audio_change)

    def get_stt_options(self) -> STTOptions:
        from core.store.models import DictionaryType

        language = str(self.get("stt.language"))
        entries = self._store.dictionaries.list_enabled(DictionaryType.VOCAB)
        hotwords = tuple(entry.term for entry in entries if entry.term.strip())
        initial_prompt = ", ".join(hotwords[:40]) if hotwords else ""
        return STTOptions(
            language=language,
            hotwords=hotwords,
            initial_prompt=initial_prompt,
        )

    def get_llm_params(self):
        from core.llm.types import LLMParams

        return LLMParams(
            temperature=self.get("llm.temperature"),
            max_tokens=self.get("llm.max_output"),
        )

    def get_proc_options(self):
        """TextProcessor toggles for C17."""
        from core.textproc.types import ProcOptions

        return ProcOptions(
            normalize=self.get("textproc.normalize"),
            dictionary=self.get("textproc.dictionary"),
            snippets=self.get("textproc.snippets"),
            punctuation_spacing=self.get("textproc.punctuation_spacing"),
            number_spacing=self.get("textproc.number_spacing"),
        )

    def list_dictionary_entries(
        self,
        entry_type=None,
        *,
        enabled_only: bool = False,
    ):
        """List dictionary/snippet entries (C13/C17 bridge)."""
        from core.store.models import DictionaryType

        if enabled_only:
            return self._store.dictionaries.list_enabled(entry_type)
        return self._store.dictionaries.list_all(entry_type)

    def add_dictionary_entry(
        self,
        *,
        term: str,
        replacement: str,
        entry_type,
        enabled: bool = True,
    ):
        entry = self._store.dictionaries.create(
            term=term,
            replacement=replacement,
            entry_type=entry_type,
            enabled=enabled,
        )
        self.invalidate_text_processor_cache()
        return entry

    def update_dictionary_entry(self, entry):
        updated = self._store.dictionaries.update(entry)
        self.invalidate_text_processor_cache()
        return updated

    def delete_dictionary_entry(self, entry_id: str) -> bool:
        deleted = self._store.dictionaries.delete(entry_id)
        if deleted:
            self.invalidate_text_processor_cache()
        return deleted

    def bind_text_processor(self):
        """Create/replace C17 TextProcessor bound to store dictionaries."""
        from core.textproc import TextProcessor

        self._text_processor = TextProcessor(
            self._store.dictionaries,
            options_provider=self.get_proc_options,
        )
        return self._text_processor

    def invalidate_text_processor_cache(self) -> None:
        if self._text_processor is not None:
            self._text_processor.invalidate_cache()

    @property
    def text_processor(self):
        if self._text_processor is None:
            raise RuntimeError("Call bind_text_processor() before accessing text_processor")
        return self._text_processor

    def test_llm_connection(self, provider_id: str | None = None):
        """Connection test for settings UI (C3/C14 bridge)."""
        if self._llm_session is None:
            self.bind_llm_session()
        return self.llm_session.test_connection(provider_id)

    def list_llm_models(self, provider_id: str | None = None):
        """List models from the configured LLM provider."""
        if self._llm_session is None:
            self.bind_llm_session()
        return self.llm_session.list_models(provider_id)

    def get_llm_api_key(self) -> str | None:
        """Resolve LLM API key from C19 store, then environment (C3/C14)."""
        import os

        from core.secrets import LLM_API_KEY_SECRET, get_default_store

        stored = get_default_store().get_secret(LLM_API_KEY_SECRET)
        if stored:
            return stored
        env_value = os.environ.get("STT_AIO_LLM_API_KEY", "").strip()
        return env_value or None

    def get_stt_api_key(self) -> str | None:
        """Resolve cloud STT API key; falls back to LLM key when unset (C19)."""
        import os

        from core.secrets import STT_API_KEY_SECRET, get_default_store

        stored = get_default_store().get_secret(STT_API_KEY_SECRET)
        if stored:
            return stored
        env_value = os.environ.get("STT_AIO_STT_API_KEY", "").strip()
        if env_value:
            return env_value
        return self.get_llm_api_key()

    def set_stt_api_key(self, value: str) -> None:
        """Store cloud STT API key via C19."""
        from core.secrets import STT_API_KEY_SECRET, get_default_store

        get_default_store().set_secret(STT_API_KEY_SECRET, value)
        if self._stt_session is not None:
            self._stt_session.refresh()

    def delete_stt_api_key(self) -> bool:
        from core.secrets import STT_API_KEY_SECRET, get_default_store

        deleted = get_default_store().delete_secret(STT_API_KEY_SECRET)
        if deleted and self._stt_session is not None:
            self._stt_session.refresh()
        return deleted

    def has_stt_api_key(self) -> bool:
        return self.get_stt_api_key() is not None

    def set_llm_api_key(self, value: str) -> None:
        """Store LLM API key via C19 (settings UI entry point)."""
        from core.secrets import LLM_API_KEY_SECRET, get_default_store

        get_default_store().set_secret(LLM_API_KEY_SECRET, value)
        if self._llm_session is not None:
            self._llm_session.refresh()

    def delete_llm_api_key(self) -> bool:
        from core.secrets import LLM_API_KEY_SECRET, get_default_store

        deleted = get_default_store().delete_secret(LLM_API_KEY_SECRET)
        if deleted and self._llm_session is not None:
            self._llm_session.refresh()
        return deleted

    def has_llm_api_key(self) -> bool:
        return self.get_llm_api_key() is not None

    def create_llm_provider(self, provider_id: str | None = None):
        from core.llm import create_provider as create_llm_provider

        resolved = provider_id or self.get("llm.provider")
        return create_llm_provider(
            resolved,
            base_url=self.get("llm.base_url"),
            model=self.get("llm.model"),
            api_key=self.get_llm_api_key(),
            timeout_sec=float(self.get("llm.timeout_sec")),
        )

    def bind_llm_session(self):
        """Create/replace managed LLM session and refresh on llm.* changes (C3)."""
        from app.llm.session import LLMProviderSession

        first_bind = self._llm_session is None
        if self._llm_session is not None:
            self._llm_session.close()
        self._llm_session = LLMProviderSession(self)

        if first_bind:
            def on_llm_change(_key: str, _value: object) -> None:
                if self._llm_session is not None:
                    self._llm_session.refresh()

            for key in keys_in_section("llm"):
                self.on_change(key, on_llm_change)
        return self._llm_session

    @property
    def llm_session(self):
        """Bound LLM session (always current after settings changes)."""
        if self._llm_session is None:
            raise RuntimeError("Call bind_llm_session() before accessing llm_session")
        return self._llm_session

    def create_stt_provider(
        self,
        *,
        device: str = "auto",
        compute_type: str = "default",
    ) -> STTProvider:
        """Create the configured STT provider (C2 integration)."""
        provider_id = str(self.get("stt.provider"))
        resolved = resolve_provider_id(provider_id)
        api_key = self.get_stt_api_key()
        timeout_sec = float(self.get("llm.timeout_sec"))
        cloud_model = str(self.get("stt.cloud_model") or "")

        if resolved == "openai_transcribe":
            from core.stt.openai_transcribe import OpenAITranscribeProvider

            return OpenAITranscribeProvider(
                base_url=str(self.get("stt.cloud_base_url") or self.get("llm.base_url")),
                api_key=api_key,
                model=cloud_model or "whisper-1",
                timeout_sec=timeout_sec,
            )
        if resolved == "groq_transcribe":
            from core.stt.groq_transcribe import GroqTranscribeProvider

            return GroqTranscribeProvider(
                api_key=api_key,
                model=cloud_model or "whisper-large-v3",
                base_url=str(self.get("stt.cloud_base_url") or "https://api.groq.com/openai/v1"),
                timeout_sec=timeout_sec,
            )
        if resolved == "deepgram_transcribe":
            from core.stt.deepgram_transcribe import DeepgramTranscribeProvider

            return DeepgramTranscribeProvider(
                api_key=api_key,
                model=cloud_model or "nova-2",
                timeout_sec=timeout_sec,
            )
        return create_provider(
            resolved,
            models_dir=self.model_manager.models_dir,
            model_id=self.get("stt.model"),
            device=device,
            compute_type=compute_type,
        )

    def bind_stt_session(self):
        """Create/replace managed STT session and refresh on stt.* changes."""
        from app.stt.session import STTProviderSession

        if self._stt_session is not None:
            self._stt_session.close()
        self._stt_session = STTProviderSession(self)

        def on_stt_change(_key: str, _value: object) -> None:
            if self._stt_session is not None:
                self._stt_session.refresh()

        for key in keys_in_section("stt"):
            self.on_change(key, on_stt_change)
        self.on_change("models.custom_path", on_stt_change)
        return self._stt_session

    def get_inject_options(self) -> InjectOptions:
        return InjectOptions(
            press_enter=self.get("inject.press_enter"),
            length_threshold=self.get("inject.length_threshold"),
        )

    def create_injector(self) -> Injector:
        method_name = str(self.get("inject.default_method"))
        return Injector(
            default_method=InjectMethod(method_name),
            length_threshold=self.get("inject.length_threshold"),
            press_enter=self.get("inject.press_enter"),
        )

    def bind_injector(self) -> Injector:
        """Create injector and refresh when inject.* settings change."""
        self._injector = self.create_injector()

        def on_inject_change(_key: str, _value: object) -> None:
            self._injector = self.create_injector()

        for key in keys_in_section("inject"):
            self.on_change(key, on_inject_change)
        return self._injector

    @property
    def stt_session(self):
        """Bound STT session (always current after settings changes)."""
        if self._stt_session is None:
            raise RuntimeError("Call bind_stt_session() before accessing stt_session")
        return self._stt_session

    @property
    def injector(self) -> Injector:
        """Bound injector (always current after settings changes)."""
        if self._injector is None:
            raise RuntimeError("Call bind_injector() before accessing injector")
        return self._injector

    def bind_hotkey(self, manager=None):
        """Create/replace HotkeyManager and refresh on hotkey.* changes (C9)."""
        from app.hotkey import HotkeyManager

        first_bind = self._hotkey_manager is None
        if self._hotkey_manager is not None:
            self._hotkey_manager.close()
        self._hotkey_manager = manager or HotkeyManager()
        self._hotkey_manager.apply_config(self)

        if first_bind:
            def on_hotkey_change(_key: str, _value: object) -> None:
                if self._hotkey_manager is not None:
                    self._hotkey_manager.apply_config(self)

            for key in keys_in_section("hotkey"):
                self.on_change(key, on_hotkey_change)
        return self._hotkey_manager

    @property
    def hotkey_manager(self):
        """Bound hotkey manager (always current after settings changes)."""
        if self._hotkey_manager is None:
            raise RuntimeError("Call bind_hotkey() before accessing hotkey_manager")
        return self._hotkey_manager

    def bind_session_manager(self, capture, manager=None):
        """Create SessionManager wired to capture (C10 integration)."""
        from app.session import SessionManager

        if self._session_manager is not None:
            self._session_manager.close()
        self._session_manager = manager or SessionManager(self, capture)
        return self._session_manager

    @property
    def session_manager(self):
        """Bound session manager."""
        if self._session_manager is None:
            raise RuntimeError("Call bind_session_manager() before accessing session_manager")
        return self._session_manager

    def bind_pipeline(self, pipeline=None):
        """Create/reuse Pipeline with a shared execution queue (C4)."""
        from core.pipeline import Pipeline, PipelineQueue

        if pipeline is not None:
            self._pipeline = pipeline
            return pipeline
        if self._pipeline is not None:
            return self._pipeline
        if self._pipeline_queue is None:
            self._pipeline_queue = PipelineQueue()
        self._pipeline = Pipeline(self, queue=self._pipeline_queue)
        return self._pipeline

    @property
    def pipeline(self):
        """Bound pipeline (shared queue across runs)."""
        if self._pipeline is None:
            raise RuntimeError("Call bind_pipeline() before accessing pipeline")
        return self._pipeline

    def get(self, key: str) -> Any:
        if key not in SCHEMA_BY_KEY:
            logger.warning("Unknown config key requested: %s", key)
            raw = self._settings.get(key)
            return raw
        return self._cache.get(key, SCHEMA_BY_KEY[key].default)

    def set(self, key: str, value: Any) -> Any:
        if self.readonly:
            from core.store.errors import ReadOnlyStoreError

            raise ReadOnlyStoreError(
                f"Cannot change '{key}' while database is in read-only safe mode."
            )
        if key not in SCHEMA_BY_KEY:
            logger.warning("Ignoring unknown config key: %s", key)
            return value

        defn = SCHEMA_BY_KEY[key]
        if key == "stt.provider":
            value = resolve_provider_id(str(value))
        validated = validate_value(defn, value)
        serialized = serialize_value(defn, validated)
        self._settings.set(key, serialized)
        self._cache[key] = validated
        self._notify(key, validated)
        return validated

    def get_section(self, section: str) -> dict[str, Any]:
        if section not in SECTIONS:
            logger.warning("Unknown config section: %s", section)
            return {}
        return {
            defn.key.split(".", 1)[1]: self.get(defn.key)
            for defn in SCHEMA_BY_KEY.values()
            if defn.section == section
        }

    def on_change(self, key: str, callback: ChangeCallback) -> None:
        self._listeners[key].append(callback)

    def reset(self, key: str | None = None, section: str | None = None) -> None:
        if key is not None:
            self._reset_key(key)
            return
        if section is not None:
            for defn in SCHEMA_BY_KEY.values():
                if defn.section == section:
                    self._reset_key(defn.key)
            return
        for defn in SCHEMA_BY_KEY.values():
            self._reset_key(defn.key)

    def _reset_key(self, key: str) -> None:
        if key not in SCHEMA_BY_KEY:
            logger.warning("Cannot reset unknown config key: %s", key)
            return
        defn = SCHEMA_BY_KEY[key]
        self.set(key, defn.default)

    def _notify(self, key: str, value: Any) -> None:
        for callback in self._listeners.get(key, []):
            callback(key, value)

    def close(self) -> None:
        if self._stt_session is not None:
            self._stt_session.close()
            self._stt_session = None
        if self._llm_session is not None:
            self._llm_session.close()
            self._llm_session = None
        if self._hotkey_manager is not None:
            self._hotkey_manager.close()
            self._hotkey_manager = None
        if self._session_manager is not None:
            self._session_manager.close()
            self._session_manager = None
        self._injector = None
        self._store.close()

    def __enter__(self) -> Config:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
