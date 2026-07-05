"""Application services."""

from app.services.batch_dictation import BatchDictationResult, transcribe_and_inject
from app.services.dictation_runtime import DictationRuntime, create_dictation_runtime
from app.services.recording_triggers import wire_hotkey_to_audio_capture

__all__ = [
    "BatchDictationResult",
    "DictationRuntime",
    "create_dictation_runtime",
    "transcribe_and_inject",
    "wire_hotkey_to_audio_capture",
]
