"""Tests for mode validation."""

from __future__ import annotations

import pytest

from core.modes.defaults import DEFAULT_CORRECTION_PROMPT
from core.modes.errors import ModeValidationError
from core.modes.types import ModeDraft
from core.modes.validation import normalize_prompt, validate_mode_draft


def test_validate_rejects_inject_above_target() -> None:
    draft = ModeDraft(name="bad", target_stage=1, inject_stage=2)
    with pytest.raises(ModeValidationError, match="inject_stage"):
        validate_mode_draft(draft)


def test_validate_fills_blank_correction_prompt() -> None:
    draft = ModeDraft(name="polish", target_stage=2, inject_stage=2)
    validated = validate_mode_draft(draft)
    assert validated.correction_prompt == DEFAULT_CORRECTION_PROMPT


def test_normalize_prompt_keeps_custom_text() -> None:
    custom = "사용자 정의 프롬프트"
    assert normalize_prompt(2, custom) == custom


def test_validate_rejects_empty_name() -> None:
    with pytest.raises(ModeValidationError, match="name"):
        validate_mode_draft(ModeDraft(name="  ", target_stage=1, inject_stage=1))
