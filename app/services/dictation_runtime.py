"""P1 dictation runtime bootstrap (C9+C10+C1+C2+C5 wiring)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.config import Config
    from app.hotkey.hotkey_manager import HotkeyManager
    from app.session.session_manager import SessionManager
    from core.audio.audio_capture import AudioCapture


@dataclass
class DictationRuntime:
    config: Config
    capture: AudioCapture
    hotkey: HotkeyManager
    sessions: SessionManager


def create_dictation_runtime(config: Config) -> DictationRuntime:
    """Wire Config, capture, hotkey, and session manager for P1 MVP."""
    import threading

    from core.audio import AudioCapture

    capture = AudioCapture()
    config.bind_audio_capture(capture)
    config.bind_stt_session()
    config.bind_injector()
    config.bind_llm_session()
    config.bind_text_processor()
    config.bind_pipeline()

    hotkey = config.bind_hotkey()
    sessions = config.bind_session_manager(capture)
    sessions.wire_hotkey(hotkey)

    try:
        config.run_privacy_maintenance()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("Privacy maintenance failed: %s", exc)

    def _warmup_stt() -> None:
        try:
            config.stt_session.warmup()
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("STT warmup skipped: %s", exc)

    threading.Thread(target=_warmup_stt, name="stt-warmup", daemon=True).start()

    return DictationRuntime(
        config=config,
        capture=capture,
        hotkey=hotkey,
        sessions=sessions,
    )
