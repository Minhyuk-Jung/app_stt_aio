"""OpenAI-compatible chat completions provider (C3)."""

from __future__ import annotations

import os
from typing import Iterator
from urllib.parse import urljoin

from core.llm.base import LLMProvider
from core.llm.errors import AuthenticationError, CompletionError, ModelNotFoundError
from core.llm.http_util import request_json
from core.llm.messages import build_messages
from core.llm.types import (
    ConnResult,
    CostType,
    LLMCapabilities,
    LLMDelta,
    LLMRequest,
    LLMResult,
    ModelInfo,
    TokenUsage,
)


class OpenAICompatProvider(LLMProvider):
    """`/v1/chat/completions` adapter for OpenAI/Groq/OpenRouter/etc."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._model = model.strip()
        self._api_key = api_key or os.environ.get("STT_AIO_LLM_API_KEY", "").strip()
        self._timeout = timeout_sec

    @property
    def provider_id(self) -> str:
        return "openai_compat"

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            supports_streaming=True,
            needs_network=True,
            context_window=128_000,
            cost_type=CostType.PAID,
        )

    def complete(self, request: LLMRequest) -> LLMResult:
        model = self._require_model()
        params = request.params.as_dict() if request.params else {}
        payload = {
            "model": model,
            "messages": build_messages(request),
            "temperature": params.get("temperature", 0.3),
            "top_p": params.get("top_p", 1.0),
            "max_tokens": params.get("max_tokens", 2048),
        }
        data = request_json(
            urljoin(self._base_url, "v1/chat/completions"),
            method="POST",
            payload=payload,
            headers=self._auth_headers(),
            timeout=self._timeout,
        )
        choices = data.get("choices") or []
        if not choices:
            raise CompletionError("openai-compatible API returned no choices")
        message = choices[0].get("message") or {}
        text = str(message.get("content", "")).strip()
        if not text:
            raise CompletionError("openai-compatible API returned empty content")
        usage_raw = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("prompt_tokens"),
            completion_tokens=usage_raw.get("completion_tokens"),
        )
        return LLMResult(
            text=text,
            model=str(data.get("model") or model),
            provider_id=self.provider_id,
            usage=usage,
        )

    def stream(self, request: LLMRequest) -> Iterator[LLMDelta]:
        result = self.complete(request)
        yield LLMDelta(text=result.text, is_final=True)

    def list_models(self) -> list[ModelInfo]:
        try:
            data = request_json(
                urljoin(self._base_url, "v1/models"),
                headers=self._auth_headers(),
                timeout=self._timeout,
            )
        except Exception:
            if self._model:
                return [ModelInfo(id=self._model, name=self._model)]
            raise
        models = data.get("data") or []
        return [
            ModelInfo(id=str(item.get("id", "")), name=str(item.get("id", "")))
            for item in models
            if item.get("id")
        ]

    def test_connection(self) -> ConnResult:
        if not self._api_key:
            return ConnResult(success=False, message="API key is not configured")
        try:
            models = self.list_models()
        except AuthenticationError as exc:
            return ConnResult(success=False, message=str(exc))
        except Exception as exc:
            return ConnResult(success=False, message=str(exc))
        return ConnResult(success=True, message="connected", models=tuple(models))

    def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise AuthenticationError(
                "API key missing; set STT_AIO_LLM_API_KEY or pass api_key to the provider"
            )
        return {"Authorization": f"Bearer {self._api_key}"}

    def _require_model(self) -> str:
        if self._model:
            return self._model
        raise ModelNotFoundError("llm.model is required for openai_compat provider")
