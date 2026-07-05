"""Qt-free UI action helpers (C12)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.session.session_manager import SessionManager


def resolve_cancel_session_id(
    sessions: SessionManager,
    manual_session_id: str | None,
) -> str | None:
    """Pick the active session for tray/menu cancel."""
    return (
        sessions.recording_session_id
        or sessions.processing_session_id
        or manual_session_id
    )
