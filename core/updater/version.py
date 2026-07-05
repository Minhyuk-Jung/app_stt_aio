"""Semantic-ish version comparison for C22 update checks."""

from __future__ import annotations

import re


def parse_version(version: str) -> tuple[int, ...]:
    """Parse ``1.2.3`` / ``v0.1.0-beta`` into a numeric tuple for comparison."""
    cleaned = version.strip().lstrip("vV")
    parts: list[int] = []
    for piece in cleaned.split("."):
        match = re.match(r"(\d+)", piece)
        if match:
            parts.append(int(match.group(1)))
        else:
            break
    return tuple(parts) if parts else (0,)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True when *latest* is strictly newer than *current*."""
    return parse_version(latest) > parse_version(current)
