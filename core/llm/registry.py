"""LLM provider factory registry."""

from __future__ import annotations

from collections.abc import Callable

from core.llm.base import LLMProvider
from core.llm.errors import ProviderNotFoundError
from core.llm.mock_provider import MockLLMProvider
from core.llm.ollama_local import OllamaLocalProvider
from core.llm.openai_compat import OpenAICompatProvider

ProviderFactory = Callable[..., LLMProvider]

_REGISTRY: dict[str, ProviderFactory] = {
    "ollama": OllamaLocalProvider,
    "openai_compat": OpenAICompatProvider,
    "mock": MockLLMProvider,
}

_PROVIDER_ALIASES: dict[str, str] = {
    "local": "ollama",
    "openai": "openai_compat",
}


def registered_provider_ids() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def resolve_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip()
    if normalized in _REGISTRY:
        return normalized
    alias = _PROVIDER_ALIASES.get(normalized.lower())
    if alias:
        return alias
    raise ProviderNotFoundError(
        f"Unknown LLM provider '{provider_id}'. "
        f"Available: {', '.join(registered_provider_ids())}"
    )


def create_provider(
    provider_id: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "",
    api_key: str | None = None,
    timeout_sec: float = 120.0,
) -> LLMProvider:
    resolved = resolve_provider_id(provider_id)
    factory = _REGISTRY[resolved]
    if resolved == "ollama":
        return factory(base_url=base_url, model=model, timeout_sec=timeout_sec)
    if resolved == "openai_compat":
        return factory(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_sec=timeout_sec,
        )
    return factory()
