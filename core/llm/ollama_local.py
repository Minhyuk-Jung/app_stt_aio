"""Ollama local HTTP provider (C3)."""

from __future__ import annotations

from typing import Iterator
from urllib.parse import urljoin

from core.llm.base import LLMProvider
from core.llm.errors import CompletionError, ModelNotFoundError
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


class OllamaLocalProvider(LLMProvider):
    """Ollama `/api/chat` integration."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "",
        timeout_sec: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._model = model.strip()
        self._timeout = timeout_sec

    @property
    def provider_id(self) -> str:
        return "ollama"

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            supports_streaming=True,
            needs_network=False,
            context_window=32_000,
            cost_type=CostType.LOCAL,
        )

    def complete(self, request: LLMRequest) -> LLMResult:
        model = self._resolve_model()
        params = request.params.as_dict() if request.params else {}
        payload = {
            "model": model,
            "messages": build_messages(request),
            "stream": False,
            "options": {
                "temperature": params.get("temperature", 0.3),
                "top_p": params.get("top_p", 1.0),
                "num_predict": params.get("max_tokens", 2048),
            },
        }
        data = request_json(
            urljoin(self._base_url, "api/chat"),
            method="POST",
            payload=payload,
            timeout=self._timeout,
        )
        message = data.get("message") or {}
        text = str(message.get("content", "")).strip()
        if not text:
            raise CompletionError("ollama returned empty completion")
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = TokenUsage(
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            )
        return LLMResult(text=text, model=model, provider_id=self.provider_id, usage=usage)

    def stream(self, request: LLMRequest) -> Iterator[LLMDelta]:
        result = self.complete(request)
        yield LLMDelta(text=result.text, is_final=True)

    def list_models(self) -> list[ModelInfo]:
        data = request_json(
            urljoin(self._base_url, "api/tags"),
            timeout=self._timeout,
        )
        models = data.get("models") or []
        return [
            ModelInfo(
                id=str(item.get("name", "")),
                name=str(item.get("name", "")),
                size_bytes=item.get("size"),
            )
            for item in models
            if item.get("name")
        ]

    def test_connection(self) -> ConnResult:
        try:
            models = self.list_models()
        except Exception as exc:
            return ConnResult(success=False, message=str(exc))
        if not models:
            return ConnResult(success=True, message="connected (no models installed)")
        return ConnResult(success=True, message="connected", models=tuple(models))

    def _resolve_model(self) -> str:
        if self._model:
            return self._model
        models = self.list_models()
        if not models:
            raise ModelNotFoundError(
                "no Ollama model configured and none installed; set llm.model or run `ollama pull`"
            )
        return models[0].id
