"""Diagnostics zip export (C20)."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.diagnostics.errors import recent_errors
from core.diagnostics.logging_setup import (
    BACKUP_COUNT,
    LOG_FILENAME,
    get_log_file_path,
    get_memory_log_lines,
)
from core.secrets import mask_secrets

if TYPE_CHECKING:
    from app.config.config import Config

from core.version import get_version

logger = logging.getLogger(__name__)

APP_VERSION = get_version()
_REDACT_KEY_TOKENS = ("api_key", "secret", "password", "token", "authorization")


def _redact_path(value: str) -> str:
    """Anonymize user home segments in exported paths (plan §9)."""
    if not value:
        return value
    home = Path.home()
    try:
        text = str(Path(value).resolve())
    except OSError:
        text = value
    home_text = str(home)
    if home_text and home_text in text:
        return text.replace(home_text, "~")
    return text


@dataclass(frozen=True)
class DiagnosticsExportResult:
    path: Path
    failures: tuple[str, ...]


def _redact_setting_key(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(token in lowered for token in _REDACT_KEY_TOKENS):
        return "***"
    if isinstance(value, str) and len(value) > 500:
        return f"<redacted {len(value)} chars>"
    return value


def snapshot_settings(config: Config) -> dict[str, Any]:
    from app.config.schema import SCHEMA_BY_KEY

    snapshot: dict[str, Any] = {}
    for key in SCHEMA_BY_KEY:
        snapshot[key] = _redact_setting_key(key, config.get(key))
    snapshot["meta.has_llm_api_key"] = config.has_llm_api_key()
    snapshot["meta.active_mode_id"] = config.get_active_mode_id()
    return snapshot


def collect_hardware_info() -> dict[str, Any]:
    """Collect CPU/GPU hints for diagnostics (plan §6.3)."""
    info: dict[str, Any] = {
        "cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "architecture": platform.architecture()[0],
    }
    try:
        import ctranslate2

        cuda_count = ctranslate2.get_cuda_device_count()
        info["cuda_device_count"] = cuda_count
        info["cuda_available"] = cuda_count > 0
    except Exception as exc:  # noqa: BLE001
        info["cuda_probe_error"] = str(exc)

    try:
        import torch

        info["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["torch_cuda_device"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch_installed"] = False
    except Exception as exc:  # noqa: BLE001
        info["torch_probe_error"] = str(exc)

    return info


def collect_environment(
    *,
    config: Config | None = None,
    capture=None,
    remote_gateway: dict[str, Any] | None = None,
) -> dict[str, Any]:
    info: dict[str, Any] = {
        "app_version": APP_VERSION,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cwd": _redact_path(os.getcwd()),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "hardware": collect_hardware_info(),
    }

    if config is not None:
        info["paths"] = {
            "root": _redact_path(str(config.paths().root)),
            "db": _redact_path(str(config.paths().db)),
            "models": _redact_path(str(config.model_manager.models_dir)),
            "logs": _redact_path(str(config.paths().logs)),
        }
        info["providers"] = {
            "stt_provider": config.get("stt.provider"),
            "stt_model": config.get("stt.model"),
            "llm_provider": config.get("llm.provider"),
            "llm_model": config.get("llm.model"),
        }
        info["settings"] = snapshot_settings(config)
        try:
            ok, message = config.model_manager.readiness_message()
            info["stt_model_readiness"] = {"ok": ok, "message": message}
        except Exception as exc:  # noqa: BLE001
            info["stt_model_readiness"] = {"ok": False, "message": str(exc)}

    devices: list[dict[str, Any]] = []
    if capture is not None:
        try:
            for device in capture.list_devices():
                devices.append(
                    {
                        "id": str(device.id),
                        "name": device.name,
                        "is_default": device.is_default,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            info["audio_devices_error"] = str(exc)
    info["audio_devices"] = devices

    if remote_gateway is not None:
        info["remote_gateway"] = remote_gateway

    log_file = get_log_file_path()
    if log_file is not None:
        info["log_file"] = _redact_path(str(log_file))

    return info


def _iter_log_files(logs_dir: Path) -> list[Path]:
    if not logs_dir.is_dir():
        return []
    files = sorted(
        logs_dir.glob(f"{LOG_FILENAME}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [path for path in files if path.is_file()]


def _collect_log_payloads(logs_dir: Path, failures: list[str]) -> dict[str, str]:
    payloads: dict[str, str] = {}
    log_files = _iter_log_files(logs_dir)
    if not log_files:
        failures.append("디스크 로그 파일을 찾지 못했습니다.")
        memory_lines = get_memory_log_lines()
        if memory_lines:
            payloads["logs/memory-buffer.log"] = mask_secrets("\n".join(memory_lines))
        else:
            failures.append("메모리 로그 버퍼도 비어 있습니다.")
        return payloads

    for log_path in log_files[: BACKUP_COUNT + 1]:
        try:
            text = mask_secrets(log_path.read_text(encoding="utf-8", errors="replace"))
            payloads[f"logs/{log_path.name}"] = text
        except OSError as exc:
            failures.append(f"로그 읽기 실패 ({log_path.name}): {exc}")
    return payloads


def export_diagnostics(
    dest_zip: Path,
    *,
    logs_dir: Path,
    config: Config | None = None,
    capture=None,
    remote_gateway: dict[str, Any] | None = None,
) -> DiagnosticsExportResult:
    """Create a diagnostics zip at dest_zip (plan §6.3, §7 partial export)."""
    failures: list[str] = []
    dest_zip = Path(dest_zip)
    if dest_zip.suffix.lower() != ".zip":
        dest_zip = dest_zip.with_suffix(".zip")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    env = collect_environment(
        config=config,
        capture=capture,
        remote_gateway=remote_gateway,
    )
    errors = recent_errors()
    log_payloads = _collect_log_payloads(logs_dir, failures)

    try:
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "README.txt",
                "STT-AIO 진단 패키지\n"
                "- environment.json: 앱/환경/CPU·GPU/설정/원격 게이트웨이 스냅샷(민감정보 마스킹)\n"
                "- errors.json: 최근 오류 이벤트\n"
                "- logs/: 최근 로그 파일(또는 memory-buffer.log)\n"
                "- modes/dictionary/프롬프트 원문은 기본 제외\n"
                "오디오·API 키·원문 텍스트는 포함되지 않습니다.\n",
            )
            archive.writestr(
                "environment.json",
                json.dumps(env, ensure_ascii=False, indent=2),
            )
            archive.writestr(
                "errors.json",
                json.dumps(errors, ensure_ascii=False, indent=2),
            )
            for name, content in log_payloads.items():
                archive.writestr(name, content)
            if failures:
                archive.writestr(
                    "export_failures.json",
                    json.dumps(failures, ensure_ascii=False, indent=2),
                )
    except OSError as exc:
        failures.append(f"zip 생성 실패: {exc}")
        raise

    logger.info("Diagnostics exported to %s (failures=%d)", dest_zip, len(failures))
    return DiagnosticsExportResult(path=dest_zip, failures=tuple(failures))
