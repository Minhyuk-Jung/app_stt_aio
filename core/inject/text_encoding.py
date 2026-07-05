"""UTF-16 code unit helpers for SendInput unicode injection."""

from __future__ import annotations


def text_to_utf16_units(text: str) -> list[int]:
    """Convert text to UTF-16 code units (includes surrogate pairs)."""
    encoded = text.encode("utf-16-le")
    return [
        int.from_bytes(encoded[index : index + 2], "little")
        for index in range(0, len(encoded), 2)
    ]


def surrogate_pair_count(text: str) -> int:
    return sum(1 for char in text if ord(char) > 0xFFFF)
