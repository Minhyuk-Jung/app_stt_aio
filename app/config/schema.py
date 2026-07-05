"""Setting schema: keys, types, defaults, validation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SettingDef:
    key: str
    section: str
    type: type
    default: Any
    min_value: float | None = None
    max_value: float | None = None
    choices: tuple[str, ...] | None = None


CONFIG_SCHEMA_VERSION = 1

SETTING_DEFINITIONS: tuple[SettingDef, ...] = (
    # audio
    SettingDef("audio.device_id", "audio", str, ""),
    SettingDef(
        "audio.vad_engine",
        "audio",
        str,
        "energy",
        choices=("energy", "silero"),
    ),
    SettingDef("audio.vad_threshold", "audio", float, 0.5, 0.0, 1.0),
    SettingDef("audio.min_speech_ms", "audio", int, 250, 50, 5000),
    SettingDef("audio.hangover_ms", "audio", int, 500, 100, 3000),
    SettingDef("audio.max_segment_ms", "audio", int, 30000, 1000, 300000),
    # stt
    SettingDef(
        "stt.provider",
        "stt",
        str,
        "faster_whisper_local",
        choices=(
            "faster_whisper_local",
            "openai_transcribe",
            "groq_transcribe",
            "deepgram_transcribe",
        ),
    ),
    SettingDef("stt.model", "stt", str, "base"),
    SettingDef("stt.language", "stt", str, "ko"),
    SettingDef("stt.fallback_to_local", "stt", bool, True),
    SettingDef("stt.cloud_base_url", "stt", str, ""),
    SettingDef("stt.cloud_model", "stt", str, "whisper-1"),
    # llm
    SettingDef("llm.provider", "llm", str, "ollama", choices=("ollama", "openai_compat")),
    SettingDef("llm.model", "llm", str, ""),
    SettingDef("llm.base_url", "llm", str, "http://localhost:11434"),
    SettingDef("llm.temperature", "llm", float, 0.3, 0.0, 2.0),
    SettingDef("llm.max_output", "llm", int, 2048, 64, 32_768),
    SettingDef("llm.timeout_sec", "llm", int, 120, 5, 600),
    # hotkey
    SettingDef(
        "hotkey.mode",
        "hotkey",
        str,
        "ptt",
        choices=("ptt", "toggle"),
    ),
    SettingDef("hotkey.record_binding", "hotkey", str, "ctrl+shift+space"),
    SettingDef("hotkey.cancel_binding", "hotkey", str, "escape"),
    SettingDef("hotkey.auto_send", "hotkey", bool, False),
    # privacy
    SettingDef("privacy.keep_audio", "privacy", bool, False),
    SettingDef("privacy.audio_retention_days", "privacy", int, 7, 0, 365),
    SettingDef("privacy.telemetry", "privacy", bool, False),
    # logging (C20)
    SettingDef(
        "logging.level",
        "logging",
        str,
        "info",
        choices=("debug", "info", "warning", "error"),
    ),
    # inject
    SettingDef(
        "inject.default_method",
        "inject",
        str,
        "auto",
        choices=("auto", "unicode", "clipboard"),
    ),
    SettingDef("inject.length_threshold", "inject", int, 500, 50, 10000),
    SettingDef("inject.press_enter", "inject", bool, False),
    # session
    SettingDef(
        "session.queue_policy",
        "session",
        str,
        "queue",
        choices=("queue", "cancel", "ignore"),
    ),
    # mode
    SettingDef("mode.active_id", "mode", str, ""),
    # textproc (C17)
    SettingDef("textproc.normalize", "textproc", bool, True),
    SettingDef("textproc.dictionary", "textproc", bool, True),
    SettingDef("textproc.snippets", "textproc", bool, True),
    SettingDef("textproc.punctuation_spacing", "textproc", bool, False),
    SettingDef("textproc.number_spacing", "textproc", bool, False),
    # models (C18)
    SettingDef("models.custom_path", "models", str, ""),
    # update (C22)
    SettingDef("update.manifest_url", "update", str, ""),
    SettingDef("update.auto_check", "update", bool, False),
    # remote (C15)
    SettingDef("remote.port", "remote", int, 8765, 1024, 65535),
    SettingDef("remote.use_tunnel", "remote", bool, False),
    SettingDef("remote.lan_fallback", "remote", bool, True),
    # onboarding (C21)
    SettingDef("onboarding.completed", "onboarding", bool, False),
    # export
    SettingDef("export.default_dir", "export", str, ""),
    SettingDef(
        "export.filename_pattern",
        "export",
        str,
        "{date}-{time}_{mode}_{stage}",
    ),
    SettingDef(
        "export.default_docx_template",
        "export",
        str,
        "basic",
        choices=("basic", "meeting", "report"),
    ),
)

SCHEMA_BY_KEY: dict[str, SettingDef] = {d.key: d for d in SETTING_DEFINITIONS}

SECTIONS: tuple[str, ...] = tuple(
    dict.fromkeys(d.section for d in SETTING_DEFINITIONS)
)


def serialize_value(defn: SettingDef, value: Any) -> str:
    if defn.type is bool:
        return "true" if value else "false"
    return str(value)


def parse_value(defn: SettingDef, raw: str) -> Any:
    if defn.type is bool:
        lowered = raw.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
        raise ValueError(f"Invalid boolean value: {raw}")
    if defn.type is int:
        return int(raw)
    if defn.type is float:
        return float(raw)
    return raw


def validate_value(defn: SettingDef, value: Any) -> Any:
    if defn.type is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{defn.key} expects bool")
        parsed = value
    elif defn.type is int:
        parsed = int(value)
    elif defn.type is float:
        parsed = float(value)
    else:
        parsed = str(value)

    if defn.choices is not None and str(parsed) not in defn.choices:
        raise ValueError(
            f"{defn.key} must be one of {defn.choices}, got {parsed!r}"
        )

    if defn.min_value is not None and float(parsed) < defn.min_value:
        raise ValueError(f"{defn.key} must be >= {defn.min_value}")
    if defn.max_value is not None and float(parsed) > defn.max_value:
        raise ValueError(f"{defn.key} must be <= {defn.max_value}")
    return parsed


def keys_in_section(section: str) -> list[str]:
    return [d.key for d in SETTING_DEFINITIONS if d.section == section]
