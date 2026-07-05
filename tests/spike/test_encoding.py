"""P0 encoding spike unit checks."""

from __future__ import annotations

from core.inject.text_encoding import text_to_utf16_units


def test_korean_utf16_roundtrip() -> None:
    text = "안녕하세요 STT-AIO 한글 주입 테스트"
    units = text_to_utf16_units(text)
    recovered = b"".join(unit.to_bytes(2, "little") for unit in units).decode("utf-16-le")
    assert recovered == text
