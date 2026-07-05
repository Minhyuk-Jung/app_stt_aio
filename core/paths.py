"""Application data path rules (shared by Store, Config, etc.)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "STT-AIO"


@dataclass(frozen=True)
class AppPaths:
    root: Path
    db: Path
    models: Path
    audio: Path
    logs: Path


def get_app_data_root() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def get_app_paths(root: Path | None = None) -> AppPaths:
    base = root or get_app_data_root()
    return AppPaths(
        root=base,
        db=base / "app.db",
        models=base / "models",
        audio=base / "audio",
        logs=base / "logs",
    )


def ensure_app_dirs(paths: AppPaths | None = None) -> AppPaths:
    p = paths or get_app_paths()
    for directory in (p.root, p.models, p.audio, p.logs, p.root / "exports"):
        directory.mkdir(parents=True, exist_ok=True)
    return p
