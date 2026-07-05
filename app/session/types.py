"""Session domain types (C10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.inject.types import InjectResult
from core.store.models import SessionSource, SessionStatus

SessionStateCallback = Callable[[str, SessionStatus], None]
InjectCallback = Callable[["SessionArtifact"], None]


@dataclass(frozen=True)
class SessionArtifact:
    session_id: str
    stage: int
    text: str
    language: str
    inject_result: InjectResult | None = None


@dataclass
class PendingBegin:
    source: SessionSource
    mode_id: str | None = None
