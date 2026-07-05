"""Korean text normalization rules (C17)."""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[^\S\n]+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:])")
_SPACE_AFTER_OPEN = re.compile(r"([\(\[\{「『])\s+")
_SPACE_BEFORE_CLOSE = re.compile(r"\s+([\)\]\}」』])")
_KO_UNITS = (
    "원|개|명|건|회|층|번|시|분|초|년|월|일|마리|대|권|장|벌|살|배|포|통|잔|병"
)
_DIGIT_UNIT_SPACE = re.compile(rf"(\d)\s+({_KO_UNITS})")


def basic_normalize(text: str) -> str:
    """Trim, remove control chars, collapse runs of whitespace (preserve newlines)."""
    cleaned = _CONTROL_CHARS.sub("", text)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    return cleaned.strip()


def apply_ko_surface_rules(
    text: str,
    *,
    punctuation_spacing: bool = False,
    number_spacing: bool = False,
) -> str:
    """Conservative Korean surface rules (plan 6.2 step 4)."""
    if not text:
        return text
    result = text
    if number_spacing:
        result = _DIGIT_UNIT_SPACE.sub(r"\1\2", result)
    if punctuation_spacing:
        result = _SPACE_BEFORE_PUNCT.sub(r"\1", result)
        result = _SPACE_AFTER_OPEN.sub(r"\1", result)
        result = _SPACE_BEFORE_CLOSE.sub(r"\1", result)
    return result


def normalize_ko(
    text: str,
    *,
    punctuation_spacing: bool = False,
    number_spacing: bool = False,
) -> str:
    """Full normalize path: basic + optional surface rules."""
    result = basic_normalize(text)
    return apply_ko_surface_rules(
        result,
        punctuation_spacing=punctuation_spacing,
        number_spacing=number_spacing,
    )
