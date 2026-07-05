"""C18 ModelManager data types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ModelInstallStatus = Literal["not_installed", "installed", "builtin", "downloading", "error"]
DownloadState = Literal["starting", "downloading", "verifying", "finished", "error"]

ProgressCallback = Callable[[int, int, DownloadState], None]


@dataclass(frozen=True)
class ModelCatalogItem:
    id: str
    name: str
    size_mb: int
    description: str
    repo_id: str | None = None


@dataclass(frozen=True)
class InstalledModel:
    id: str
    path: Path | str
    status: ModelInstallStatus
    source: str = "local"


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size_bytes: int | None = None
    modified_at: str | None = None
