"""Text completion providers (C3)."""

from core.llm.base import LLMProvider
from core.llm.errors import (
    AuthenticationError,
    CompletionError,
    ContextExceededError,
    LLMError,
    ModelNotFoundError,
    NetworkError,
    ProviderNotFoundError,
)
from core.llm.mock_provider import MockLLMProvider
from core.llm.ollama_local import OllamaLocalProvider
from core.llm.openai_compat import OpenAICompatProvider
from core.llm.registry import create_provider, registered_provider_ids, resolve_provider_id
from core.llm.types import (
    ConnResult,
    CostType,
    LLMCapabilities,
    LLMDelta,
    LLMParams,
    LLMRequest,
    LLMResult,
    ModelInfo,
    ProviderState,
    TokenUsage,
)

__all__ = [
    "AuthenticationError",
    "CompletionError",
    "ConnResult",
    "ContextExceededError",
    "CostType",
    "LLMCapabilities",
    "LLMDelta",
    "LLMError",
    "LLMParams",
    "LLMProvider",
    "LLMRequest",
    "LLMResult",
    "MockLLMProvider",
    "ModelInfo",
    "ModelNotFoundError",
    "NetworkError",
    "OllamaLocalProvider",
    "OpenAICompatProvider",
    "ProviderNotFoundError",
    "ProviderState",
    "TokenUsage",
    "create_provider",
    "registered_provider_ids",
    "resolve_provider_id",
]
