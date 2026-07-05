"""Model cache path helpers (C18)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

INSTALL_MARKER = ".stt_aio_installed.json"
_WEIGHT_FILENAMES = ("model.bin", "model.safetensors")


def resolve_models_dir(*, default_dir: Path, custom_path: str) -> Path:
    custom = custom_path.strip()
    if custom:
        return Path(custom)
    return default_dir


def model_install_dir(models_dir: Path, model_id: str) -> Path:
    return models_dir / model_id.strip()


def read_install_marker(model_dir: Path) -> dict | None:
    marker = model_dir / INSTALL_MARKER
    if not marker.is_file():
        return None
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def has_model_weights(model_dir: Path) -> bool:
    for path in model_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in _WEIGHT_FILENAMES:
            return True
        if path.suffix in (".bin", ".safetensors") and path.stat().st_size > 1024:
            return True
    return False


def compute_manifest_checksum(model_dir: Path) -> str:
    """Checksum of relative path + file size entries (fast integrity probe)."""
    digest = hashlib.sha256()
    for path in sorted(
        p
        for p in model_dir.rglob("*")
        if p.is_file() and p.name != INSTALL_MARKER
    ):
        rel = path.relative_to(model_dir).as_posix()
        digest.update(f"{rel}:{path.stat().st_size}\n".encode())
    return digest.hexdigest()


def verify_model_install(model_dir: Path, *, model_id: str | None = None) -> str | None:
    """Return a user-facing error when install is invalid, else None."""
    if not model_dir.is_dir():
        return None

    marker = read_install_marker(model_dir)
    if marker is None:
        if not model_dir.exists():
            return None
        if any(model_dir.iterdir()) and not has_model_weights(model_dir):
            return "모델 가중치 파일이 없습니다. 부분 다운로드일 수 있습니다."
        if has_model_weights(model_dir):
            return None
        return None

    expected_id = model_id or marker.get("model_id")
    if expected_id and marker.get("model_id") != expected_id:
        return (
            f"설치 마커 모델 ID가 일치하지 않습니다 "
            f"({marker.get('model_id')} ≠ {expected_id})."
        )

    if not has_model_weights(model_dir):
        return "모델 가중치 파일이 없습니다. 다시 다운로드하세요."

    stored = marker.get("checksum")
    if stored:
        current = compute_manifest_checksum(model_dir)
        if current != stored:
            return "체크섬이 일치하지 않습니다. 손상된 설치로 보입니다."

    return None


def is_locally_installed(model_dir: Path, *, model_id: str | None = None) -> bool:
    if not model_dir.is_dir():
        return False
    error = verify_model_install(model_dir, model_id=model_id)
    if error is not None:
        return False
    marker = read_install_marker(model_dir)
    if marker is not None:
        return True
    return has_model_weights(model_dir)


def write_install_marker(
    model_dir: Path,
    *,
    model_id: str,
    source: str,
    checksum: str | None = None,
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": model_id,
        "source": source,
        "checksum": checksum or compute_manifest_checksum(model_dir),
    }
    (model_dir / INSTALL_MARKER).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
