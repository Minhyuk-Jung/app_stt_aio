"""Ollama model list probe (C18)."""

from __future__ import annotations

from core.llm.http_util import request_json
from core.models.errors import ModelError
from core.models.types import OllamaModel


def list_ollama_models(base_url: str, *, timeout_sec: float = 10.0) -> list[OllamaModel]:
    root = base_url.rstrip("/") + "/"
    try:
        payload = request_json(
            f"{root}api/tags",
            method="GET",
            timeout_sec=timeout_sec,
        )
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Ollama 연결 실패: {exc}") from exc

    models: list[OllamaModel] = []
    for entry in payload.get("models", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        size = entry.get("size")
        modified = entry.get("modified_at")
        models.append(
            OllamaModel(
                name=name,
                size_bytes=int(size) if size is not None else None,
                modified_at=str(modified) if modified else None,
            )
        )
    return models
