"""Tests for injection bridge."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.session.injection_bridge import inject_transcript
from core.inject.types import InjectMethod, InjectResult


def test_inject_transcript_delegates_to_pipeline_inject() -> None:
    config = MagicMock()
    expected = InjectResult(
        success=True,
        method_used=InjectMethod.UNICODE,
        chars_injected=3,
    )

    with patch("app.session.injection_bridge.inject_stage_text", return_value=expected) as mock:
        result = inject_transcript(
            config,
            "안녕",
            inject_method="unicode",
            press_enter=True,
        )

    assert result is expected
    mock.assert_called_once_with(
        config,
        "안녕",
        inject_method="unicode",
        press_enter=True,
    )
