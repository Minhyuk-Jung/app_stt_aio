"""Mode domain errors (C7)."""

from __future__ import annotations


class ModeError(Exception):
    """Base error for mode management."""


class ModeNotFoundError(ModeError):
    def __init__(self, mode_id: str) -> None:
        super().__init__(f"mode not found: {mode_id}")
        self.mode_id = mode_id


class ModeValidationError(ModeError):
    pass


class ModeDeleteForbiddenError(ModeError):
    pass
