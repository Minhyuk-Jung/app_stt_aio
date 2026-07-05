"""Log masking helpers (C19/C20 bridge)."""

from __future__ import annotations

import re

_API_KEY_PATTERN = re.compile(
    r"(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_LONG_TEXT_THRESHOLD = 300


def mask_user_text(text: str, *, max_visible: int = 120) -> str:
    """Truncate long user/transcription text for safe logging (plan §9)."""
    if len(text) <= max_visible:
        return text
    return f"{text[:max_visible]}… <redacted {len(text)} chars>"


def mask_secrets(text: str) -> str:
    """Mask common secret patterns and long user text before logging."""
    masked = _API_KEY_PATTERN.sub(r"\1=****", text)
    masked = _TOKEN_PATTERN.sub("sk-****", masked)
    if len(masked) > _LONG_TEXT_THRESHOLD:
        return mask_user_text(masked)
    return masked
