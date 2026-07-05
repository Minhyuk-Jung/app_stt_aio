"""Tests for application path helpers."""

from __future__ import annotations

from core.paths import APP_NAME, ensure_app_dirs, get_app_paths


def test_get_app_paths_structure(tmp_path) -> None:
    paths = get_app_paths(tmp_path / "appdata")

    assert paths.root == tmp_path / "appdata"
    assert paths.db == paths.root / "app.db"
    assert paths.models == paths.root / "models"
    assert paths.audio == paths.root / "audio"
    assert paths.logs == paths.root / "logs"


def test_ensure_app_dirs_creates_directories(tmp_path) -> None:
    paths = get_app_paths(tmp_path / APP_NAME)
    ensure_app_dirs(paths)

    assert paths.root.is_dir()
    assert paths.models.is_dir()
    assert paths.audio.is_dir()
    assert paths.logs.is_dir()
    assert (paths.root / "exports").is_dir()
