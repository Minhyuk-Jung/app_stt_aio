"""Mode preset management (C7)."""

from core.modes.errors import (
    ModeDeleteForbiddenError,
    ModeError,
    ModeNotFoundError,
    ModeValidationError,
)
from core.modes.mode_manager import ModeManager
from core.modes.prompts import PROMPT_TEXT_PLACEHOLDER, format_prompt
from core.modes.types import ModeDraft, PromptSpec

__all__ = [
    "ModeDeleteForbiddenError",
    "ModeDraft",
    "ModeError",
    "ModeManager",
    "ModeNotFoundError",
    "ModeValidationError",
    "PROMPT_TEXT_PLACEHOLDER",
    "PromptSpec",
    "format_prompt",
]
