"""Tests for pipeline inject adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.inject.types import InjectMethod, InjectResult
from core.pipeline.inject import inject_stage_text


def test_inject_stage_text_empty_returns_success_without_calling_injector() -> None:
    config = MagicMock()
    config._injector = MagicMock()

    result = inject_stage_text(config, "   ")

    assert result.success is True
    assert result.chars_injected == 0
    config.injector.inject.assert_not_called()


def test_inject_stage_text_delegates_to_injector() -> None:
    config = MagicMock()
    config._injector = MagicMock()
    config.get_inject_options.return_value = MagicMock(press_enter=False)
    config.injector.inject.return_value = InjectResult(
        success=True,
        method_used=InjectMethod.UNICODE,
        chars_injected=4,
    )

    result = inject_stage_text(config, "안녕하세요", press_enter=True)

    assert result.chars_injected == 4
    config.injector.inject.assert_called_once()
