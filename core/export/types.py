"""Export contracts (C8/C13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ExportTarget:
    session_id: str
    stages: tuple[int, ...] = (1,)
    include_meta: bool = False
    template: str | None = None


@dataclass(frozen=True)
class ExportResult:
    path: Path
    format: str
    success: bool
    error: str | None = None
    suggestion: str | None = None


@dataclass(frozen=True)
class TemplateInfo:
    id: str
    name: str
    formats: tuple[str, ...]


@dataclass(frozen=True)
class ExportPayload:
    """Resolved session content passed from C13/C6 lookup."""

    session_id: str
    mode_name: str
    created_at: datetime
    stages: dict[int, str]
    providers: dict[int, str | None] = field(default_factory=dict)
