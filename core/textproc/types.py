"""TextProcessor context and result types (C17)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProcOptions:
    normalize: bool = True
    dictionary: bool = True
    snippets: bool = True
    punctuation_spacing: bool = False
    number_spacing: bool = False


@dataclass(frozen=True)
class ProcCtx:
    stage: int = 1
    source: str = "stt"
    target_app: str | None = None
    options: ProcOptions = field(default_factory=ProcOptions)


@dataclass(frozen=True)
class ProcResult:
    text: str
    applied: tuple[str, ...] = ()
