"""Tests for build/build_env.py."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load_build_env():
    sys.path.insert(0, str(ROOT / "build"))
    try:
        return importlib.import_module("build_env")
    finally:
        sys.path.pop(0)


def test_project_root_points_at_repo() -> None:
    mod = _load_build_env()
    assert (mod.project_root() / "build" / "build_env.py").is_file()


def test_pyinstaller_env_error_when_pathlib_backport() -> None:
    mod = _load_build_env()
    fake_venv = Path("C:/fake/.venv/Scripts/python.exe")
    with patch.object(mod, "has_pathlib_backport", return_value=True):
        with patch.object(mod, "venv_python", return_value=fake_venv):
            err = mod.pyinstaller_env_error()
    assert err is not None
    assert "pathlib" in err.lower()
    assert ".venv" in err


def test_pyinstaller_env_error_none_when_clean() -> None:
    mod = _load_build_env()
    with patch.object(mod, "has_pathlib_backport", return_value=False):
        assert mod.pyinstaller_env_error() is None


def test_resolve_build_python_prefers_venv(tmp_path: Path) -> None:
    mod = _load_build_env()
    fake_venv = tmp_path / ".venv" / "Scripts" / "python.exe"
    fake_venv.parent.mkdir(parents=True)
    fake_venv.write_text("", encoding="utf-8")
    with patch.object(mod, "venv_python", return_value=fake_venv):
        assert mod.resolve_build_python() == str(fake_venv)
