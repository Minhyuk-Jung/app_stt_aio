"""Tests for secret/text masking (C19/C20)."""

from __future__ import annotations

from core.secrets.masking import mask_secrets, mask_user_text


def test_mask_user_text_truncates_long_strings() -> None:
    long_text = "가" * 400
    masked = mask_user_text(long_text)
    assert "redacted 400 chars" in masked
    assert len(masked) < 400


def test_mask_secrets_redacts_token_and_long_text() -> None:
    payload = "sk-abcdefghijklmnopqrst " + ("secret " * 80)
    masked = mask_secrets(payload)
    assert "sk-abcdefghijklmnopqrst" not in masked
    assert "redacted" in masked
