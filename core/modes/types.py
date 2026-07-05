"""Mode domain types (C7)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptSpec:
    system_prompt: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeDraft:
    """Input for create/update without store metadata."""

    name: str
    target_stage: int
    inject_stage: int
    correction_prompt: str = ""
    report_prompt: str = ""
    stt_provider: str | None = None
    llm_provider: str | None = None
    is_default: bool = False
    enabled: bool = True
