"""Tests for Whisper model path resolver."""

from __future__ import annotations

import pytest

from core.models.errors import ModelNotFoundError
from core.models.resolver import (
    is_custom_model_installed,
    resolve_whisper_model_path,
)
from core.models.store_paths import write_install_marker


def _seed_model_dir(model_dir) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.bin").write_bytes(b"weights")
    write_install_marker(model_dir, model_id=model_dir.name, source="test")


def test_resolve_known_model_name(tmp_path) -> None:
    assert resolve_whisper_model_path(tmp_path / "models", "base") == "base"


def test_resolve_custom_model_directory(tmp_path) -> None:
    custom = tmp_path / "models" / "my-model"
    _seed_model_dir(custom)
    assert resolve_whisper_model_path(tmp_path / "models", "my-model") == str(custom)


def test_resolve_corrupt_local_directory_raises(tmp_path) -> None:
    corrupt = tmp_path / "models" / "base"
    corrupt.mkdir(parents=True)
    (corrupt / "partial.part").write_text("x")
    with pytest.raises(ModelNotFoundError, match="invalid"):
        resolve_whisper_model_path(tmp_path / "models", "base")


def test_resolve_unknown_model_raises(tmp_path) -> None:
    with pytest.raises(ModelNotFoundError, match="not installed"):
        resolve_whisper_model_path(tmp_path / "models", "unknown-model")


def test_is_custom_model_installed(tmp_path) -> None:
    models_dir = tmp_path / "models"
    assert is_custom_model_installed(models_dir, "local") is False
    _seed_model_dir(models_dir / "local")
    assert is_custom_model_installed(models_dir, "local") is True
