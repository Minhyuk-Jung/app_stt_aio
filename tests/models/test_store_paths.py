"""Tests for model install verification (C18)."""

from __future__ import annotations

from pathlib import Path

from core.models.store_paths import (
    compute_manifest_checksum,
    is_locally_installed,
    model_install_dir,
    verify_model_install,
    write_install_marker,
)


def _seed_valid_install(model_dir: Path, *, model_id: str = "tiny") -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.bin").write_bytes(b"weights")
    write_install_marker(model_dir, model_id=model_id, source="test")


def test_verify_rejects_partial_without_weights(tmp_path: Path) -> None:
    model_dir = tmp_path / "tiny"
    model_dir.mkdir()
    (model_dir / "incomplete.part").write_text("partial")
    assert verify_model_install(model_dir, model_id="tiny") is not None
    assert is_locally_installed(model_dir, model_id="tiny") is False


def test_verify_accepts_marker_and_weights(tmp_path: Path) -> None:
    model_dir = tmp_path / "tiny"
    _seed_valid_install(model_dir)
    assert verify_model_install(model_dir, model_id="tiny") is None
    assert is_locally_installed(model_dir, model_id="tiny") is True


def test_checksum_mismatch_detected(tmp_path: Path) -> None:
    model_dir = tmp_path / "tiny"
    _seed_valid_install(model_dir)
    (model_dir / "model.bin").write_bytes(b"corrupted")
    assert verify_model_install(model_dir, model_id="tiny") is not None


def test_compute_manifest_checksum_changes_with_content(tmp_path: Path) -> None:
    model_dir = tmp_path / "tiny"
    _seed_valid_install(model_dir)
    first = compute_manifest_checksum(model_dir)
    (model_dir / "extra.txt").write_text("x")
    second = compute_manifest_checksum(model_dir)
    assert first != second


def test_legacy_manual_install_without_marker(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    model_dir = model_install_dir(models_dir, "custom")
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").write_bytes(b"x")
    assert verify_model_install(model_dir) is None
    assert is_locally_installed(model_dir) is True
