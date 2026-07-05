"""P1 minimal Whisper model path resolver (C18 precursor)."""

from __future__ import annotations

from pathlib import Path

from core.models.errors import ModelNotFoundError
from core.models.store_paths import is_locally_installed, verify_model_install

KNOWN_WHISPER_MODELS: tuple[str, ...] = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v2",
    "large-v3",
)


def resolve_whisper_model_path(models_dir: Path, model_id: str) -> str:
    """Return a faster-whisper model size name or a validated on-disk directory."""
    model_id = model_id.strip()
    if not model_id:
        raise ModelNotFoundError("stt.model is empty")

    local_dir = models_dir / model_id
    if local_dir.is_dir():
        install_error = verify_model_install(local_dir, model_id=model_id)
        if install_error:
            raise ModelNotFoundError(
                f"Whisper model '{model_id}' at {local_dir} is invalid: {install_error} "
                "Use Settings → Models to repair or re-download."
            )
        if is_locally_installed(local_dir, model_id=model_id):
            return str(local_dir)

    if model_id in KNOWN_WHISPER_MODELS:
        return model_id

    raise ModelNotFoundError(
        f"Whisper model '{model_id}' is not installed at {local_dir}. "
        "Download via ModelManager (C18) or place files in the models directory."
    )


def is_custom_model_installed(models_dir: Path, model_id: str) -> bool:
    return is_locally_installed(models_dir / model_id.strip(), model_id=model_id.strip())
