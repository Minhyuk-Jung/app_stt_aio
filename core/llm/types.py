"""Shared LLM data types (C3 contract)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class CostType(str, Enum):
    FREE = "free"
    LOCAL = "local"
    PAID = "paid"


class ProviderState(str, Enum):
    READY = "ready"
    REQUESTING = "requesting"
    ERROR = "error"


@dataclass(frozen=True)
class LLMCapabilities:
    supports_streaming: bool
    needs_network: bool
    context_window: int
    cost_type: CostType


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True)
class ConnResult:
    success: bool
    message: str
    models: tuple[ModelInfo, ...] = ()


@dataclass
class LLMParams:
    temperature: float = 0.3
    max_tokens: int = 2048
    top_p: float = 1.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }


@dataclass
class LLMRequest:
    system_prompt: str
    user_text: str
    mode_id: str | None = None
    params: LLMParams | None = None
    stream: bool = False


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    provider_id: str
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class LLMDelta:
    text: str
    is_final: bool = False


LLMDeltaIterator = Iterator[LLMDelta]
