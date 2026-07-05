"""STT provider factory registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from core.stt.base import STTProvider
from core.stt.errors import ProviderNotFoundError
from core.stt.faster_whisper_local import FasterWhisperLocalProvider

ProviderFactory = Callable[..., STTProvider]

_LOCAL_FACTORY: ProviderFactory = FasterWhisperLocalProvider

_CLOUD_PROVIDER_IDS = frozenset(
    {
        "openai_transcribe",
        "groq_transcribe",
        "deepgram_transcribe",
    }
)

_ALL_PROVIDER_IDS = frozenset({"faster_whisper_local", *_CLOUD_PROVIDER_IDS})

# Aliases for config defaults / UI labels.
# deepgram_transcribe supports both batch REST and WebSocket streaming (C2 §6.3).
_PROVIDER_ALIASES: dict[str, str] = {
    "local": "faster_whisper_local",
    "faster-whisper": "faster_whisper_local",
    "openai": "openai_transcribe",
    "groq": "groq_transcribe",
    "deepgram": "deepgram_transcribe",
    "deepgram_stream": "deepgram_transcribe",
    "deepgram-stream": "deepgram_transcribe",
}


def registered_provider_ids() -> tuple[str, ...]:
    return tuple(sorted(_ALL_PROVIDER_IDS))


def resolve_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip()
    if normalized in _ALL_PROVIDER_IDS:
        return normalized
    alias = _PROVIDER_ALIASES.get(normalized.lower())
    if alias:
        return alias
    raise ProviderNotFoundError(
        f"Unknown STT provider '{provider_id}'. "
        f"Available: {', '.join(registered_provider_ids())}"
    )


def create_provider(
    provider_id: str,
    *,
    models_dir: Path,
    model_id: str = "base",
    device: str = "auto",
    compute_type: str = "default",
) -> STTProvider:
    """Create a local STT provider. Cloud providers use Config.create_stt_provider()."""
    resolved = resolve_provider_id(provider_id)
    if resolved in _CLOUD_PROVIDER_IDS:
        raise ProviderNotFoundError(
            f"Cloud provider '{resolved}' must be created via Config.create_stt_provider()"
        )
    return _LOCAL_FACTORY(
        models_dir=models_dir,
        model_id=model_id,
        device=device,
        compute_type=compute_type,
    )
