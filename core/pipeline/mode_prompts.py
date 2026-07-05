"""Pipeline prompt resolution via C7 ModeManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.modes.types import PromptSpec

if TYPE_CHECKING:
    from app.config.config import Config


def get_prompt_for_session(config: Config, session_id: str, stage: int) -> PromptSpec:
    """Return stage prompt for the session's resolved mode."""
    if config._mode_manager is None:
        config.bind_mode_manager()

    stored = config._store.sessions.get(session_id)
    mode_id = stored.mode_id if stored is not None else None
    mode = config.mode_manager.resolve_mode(mode_id)
    return config.mode_manager.get_prompt(mode, stage)
