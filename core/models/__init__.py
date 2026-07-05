"""Model path helpers and ModelManager (C18)."""

from core.models.catalog import WHISPER_CATALOG
from core.models.errors import ModelDownloadError, ModelError, ModelNotFoundError
from core.models.model_manager import ModelManager
from core.models.resolver import (
    KNOWN_WHISPER_MODELS,
    is_custom_model_installed,
    resolve_whisper_model_path,
)
from core.models.store_paths import (
    compute_manifest_checksum,
    is_locally_installed,
    verify_model_install,
    write_install_marker,
)
from core.models.types import InstalledModel, ModelCatalogItem, OllamaModel

__all__ = [
    "KNOWN_WHISPER_MODELS",
    "ModelCatalogItem",
    "ModelDownloadError",
    "ModelError",
    "ModelManager",
    "ModelNotFoundError",
    "OllamaModel",
    "InstalledModel",
    "WHISPER_CATALOG",
    "compute_manifest_checksum",
    "is_custom_model_installed",
    "is_locally_installed",
    "resolve_whisper_model_path",
    "verify_model_install",
    "write_install_marker",
]
