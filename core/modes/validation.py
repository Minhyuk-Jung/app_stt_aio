"""Mode field validation (C7)."""

from __future__ import annotations

from core.modes.defaults import DEFAULT_CORRECTION_PROMPT, DEFAULT_REPORT_PROMPT
from core.modes.errors import ModeValidationError
from core.modes.types import ModeDraft


def normalize_prompt(stage: int, prompt: str) -> str:
    """Replace blank prompts with built-in defaults."""
    text = prompt.strip()
    if text:
        return text
    if stage == 2:
        return DEFAULT_CORRECTION_PROMPT
    if stage == 3:
        return DEFAULT_REPORT_PROMPT
    return ""


def validate_mode_draft(draft: ModeDraft) -> ModeDraft:
    if not draft.name.strip():
        raise ModeValidationError("mode name is required")
    if draft.target_stage not in (1, 2, 3):
        raise ModeValidationError("target_stage must be 1, 2, or 3")
    if draft.inject_stage not in (0, 1, 2, 3):
        raise ModeValidationError("inject_stage must be 0, 1, 2, or 3")
    if draft.inject_stage > draft.target_stage:
        raise ModeValidationError("inject_stage must be <= target_stage")

    correction = draft.correction_prompt.strip()
    report = draft.report_prompt.strip()
    if draft.target_stage >= 2:
        correction = normalize_prompt(2, correction)
    if draft.target_stage >= 3:
        report = normalize_prompt(3, report)

    return ModeDraft(
        name=draft.name.strip(),
        target_stage=draft.target_stage,
        inject_stage=draft.inject_stage,
        correction_prompt=correction,
        report_prompt=report,
        stt_provider=draft.stt_provider,
        llm_provider=draft.llm_provider,
        is_default=draft.is_default,
        enabled=draft.enabled,
    )
