"""LLMProvider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from core.llm.types import (
    ConnResult,
    LLMCapabilities,
    LLMDelta,
    LLMRequest,
    LLMResult,
    ModelInfo,
)


class LLMProvider(ABC):
    """Replaceable text completion provider contract (C3)."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable provider identifier."""

    @abstractmethod
    def capabilities(self) -> LLMCapabilities:
        """Return supported features and constraints."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResult:
        """Run a single completion request."""

    def stream(self, request: LLMRequest) -> Iterator[LLMDelta]:
        raise NotImplementedError(
            f"{self.provider_id} does not support streaming completions"
        )

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """List models exposed by the provider."""

    @abstractmethod
    def test_connection(self) -> ConnResult:
        """Validate connectivity for settings UI."""

    def close(self) -> None:
        """Release provider resources."""

    def __enter__(self) -> LLMProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
