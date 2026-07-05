"""Whisper model catalog (C18)."""

from __future__ import annotations

from core.models.types import ModelCatalogItem

WHISPER_CATALOG: tuple[ModelCatalogItem, ...] = (
    ModelCatalogItem(
        id="tiny",
        name="Whisper Tiny",
        size_mb=75,
        description="가장 빠름, 정확도 낮음",
        repo_id="Systran/faster-whisper-tiny",
    ),
    ModelCatalogItem(
        id="base",
        name="Whisper Base",
        size_mb=145,
        description="P1 기본값, 균형",
        repo_id="Systran/faster-whisper-base",
    ),
    ModelCatalogItem(
        id="small",
        name="Whisper Small",
        size_mb=480,
        description="정확도 향상",
        repo_id="Systran/faster-whisper-small",
    ),
    ModelCatalogItem(
        id="medium",
        name="Whisper Medium",
        size_mb=1500,
        description="고정확, 느림",
        repo_id="Systran/faster-whisper-medium",
    ),
    ModelCatalogItem(
        id="large-v2",
        name="Whisper Large v2",
        size_mb=3100,
        description="대형 모델 v2",
        repo_id="Systran/faster-whisper-large-v2",
    ),
    ModelCatalogItem(
        id="large-v3",
        name="Whisper Large v3",
        size_mb=3100,
        description="대형 모델 v3",
        repo_id="Systran/faster-whisper-large-v3",
    ),
)

CATALOG_BY_ID: dict[str, ModelCatalogItem] = {item.id: item for item in WHISPER_CATALOG}
