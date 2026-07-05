"""Resolve PipelineMode from session metadata via C7 ModeManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.pipeline.types import PipelineMode

if TYPE_CHECKING:
    from app.config.config import Config


def resolve_mode_for_session(config: Config, session_id: str) -> PipelineMode:
    """Return pipeline routing mode for a session."""
    if config._mode_manager is None:
        config.bind_mode_manager()

    stored = config._store.sessions.get(session_id)
    mode_id = stored.mode_id if stored is not None else None
    mode = config.mode_manager.resolve_mode(mode_id)
    return config.mode_manager.to_pipeline_mode(mode)
