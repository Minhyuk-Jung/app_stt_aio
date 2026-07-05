"""Session manager errors (C10)."""

from __future__ import annotations


class SessionError(Exception):
    """Base session error."""


class SessionNotFoundError(SessionError):
    """Session id does not exist."""


class SessionStateError(SessionError):
    """Invalid session state transition."""


class SessionBusyError(SessionError):
    """Session manager rejected a new request while busy."""


class SessionNotImplementedError(SessionError):
    """Feature planned for a later phase."""
