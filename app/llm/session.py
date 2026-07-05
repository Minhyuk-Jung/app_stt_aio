"""Managed LLM provider lifecycle (C3 + C11)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.llm import LLMProvider, LLMRequest, LLMResult, create_provider
from core.llm.errors import LLMError
from core.llm.registry import resolve_provider_id

if TYPE_CHECKING:
    from app.config.config import Config

logger = logging.getLogger(__name__)


class LLMProviderSession:
    """Holds providers and refreshes on config changes."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._providers: dict[str, LLMProvider] = {}

    def refresh(self) -> None:
        for provider in self._providers.values():
            provider.close()
        self._providers.clear()
        logger.info("LLM providers cleared for refresh")

    def complete(
        self,
        request: LLMRequest,
        *,
        provider_id: str | None = None,
    ) -> LLMResult:
        if not request.user_text.strip() and not request.system_prompt.strip():
            return LLMResult(text="", model="none", provider_id="skipped")
        provider = self._get_provider(provider_id)
        try:
            return provider.complete(request)
        except LLMError as exc:
            from core.diagnostics import report_error

            report_error(
                exc,
                context={
                    "component": "llm",
                    "provider": provider.provider_id,
                    "model": request.model or self._config.get("llm.model"),
                },
                log=False,
            )
            raise
        except Exception as exc:
            from core.diagnostics import report_error
            from core.llm.errors import CompletionError

            report_error(
                exc,
                context={
                    "component": "llm",
                    "provider": provider.provider_id,
                },
                log=False,
            )
            raise CompletionError(str(exc)) from exc

    def stream(
        self,
        request: LLMRequest,
        *,
        provider_id: str | None = None,
    ):
        provider = self._get_provider(provider_id)
        yield from provider.stream(request)

    def test_connection(self, provider_id: str | None = None):
        return self._get_provider(provider_id).test_connection()

    def list_models(self, provider_id: str | None = None):
        return self._get_provider(provider_id).list_models()

    def close(self) -> None:
        for provider in self._providers.values():
            provider.close()
        self._providers.clear()

    def _get_provider(self, provider_id: str | None) -> LLMProvider:
        resolved = resolve_provider_id(provider_id or self._config.get("llm.provider"))
        if resolved not in self._providers:
            self._providers[resolved] = self._config.create_llm_provider(resolved)
        return self._providers[resolved]
