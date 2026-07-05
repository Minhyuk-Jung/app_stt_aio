"""Tests for log masking filter (C20)."""

from __future__ import annotations

import logging

from core.diagnostics.masking_filter import MaskingFilter


def test_masking_filter_redacts_api_key_pattern() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization: Bearer sk-abcdefghijklmnop",
        args=(),
        exc_info=None,
    )
    assert MaskingFilter().filter(record) is True
    assert "sk-abcdefghijklmnop" not in str(record.msg)
    assert "****" in str(record.msg)
