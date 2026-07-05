"""Build environment helpers (C16) — PyInstaller-safe Python selection."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def venv_python() -> Path | None:
    candidate = project_root() / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else None


def has_pathlib_backport() -> bool:
    """True when a third-party `pathlib` shadows stdlib (breaks PyInstaller)."""
    spec = importlib.util.find_spec("pathlib")
    if spec is None or not spec.origin:
        return False
    origin = spec.origin.replace("\\", "/")
    return "site-packages" in origin


def pyinstaller_env_error() -> str | None:
    if not has_pathlib_backport():
        return None
    venv = venv_python()
    hint = (
        f"Use project venv: {venv} build/build.py --portable"
        if venv
        else "Create .venv and install build deps, then run build with that Python"
    )
    return (
        "Incompatible `pathlib` backport detected in site-packages (common with Anaconda). "
        f"{hint}. Or: conda remove pathlib"
    )


def resolve_build_python() -> str:
    venv = venv_python()
    if venv is not None:
        return str(venv)
    return sys.executable
