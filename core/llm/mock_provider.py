"""Deterministic mock LLM provider for tests."""

from __future__ import annotations

from typing import Iterator

from core.llm.base import LLMProvider
from core.llm.messages import build_messages
from core.llm.types import (
    ConnResult,
    CostType,
    LLMCapabilities,
    LLMDelta,
    LLMRequest,
    LLMResult,
    ModelInfo,
)


class MockLLMProvider(LLMProvider):
    """Echo-style provider that returns user text with optional prefix."""

    def __init__(self, *, prefix: str = "") -> None:
        self._prefix = prefix

    @property
    def provider_id(self) -> str:
        return "mock"

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            supports_streaming=True,
            needs_network=False,
            context_window=32_000,
            cost_type=CostType.FREE,
        )

    def complete(self, request: LLMRequest) -> LLMResult:
        messages = build_messages(request)
        body = messages[-1]["content"] if messages else ""
        text = f"{self._prefix}{body}".strip()
        return LLMResult(text=text, model="mock", provider_id=self.provider_id)

    def stream(self, request: LLMRequest) -> Iterator[LLMDelta]:
        result = self.complete(request)
        yield LLMDelta(text=result.text, is_final=True)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="mock", name="Mock Model")]

    def test_connection(self) -> ConnResult:
        return ConnResult(success=True, message="mock provider ready", models=self.list_models())
