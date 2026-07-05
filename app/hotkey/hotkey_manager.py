"""Global hotkey manager (C9)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from app.hotkey.backend import KeyEvent, KeyboardBackend, create_keyboard_backend
from app.hotkey.binding import (
    KeyChord,
    chord_matches_pressed,
    modifier_from_vk,
    parse_binding,
)
from app.hotkey.conflict import (
    CANCEL_FALLBACK_BINDINGS,
    check_binding_available as probe_binding,
    suggest_fallback_binding,
)
from app.hotkey.debounce import KeyDebouncer
from app.hotkey.errors import HotkeyBindingError, HotkeyRegistrationError, HotkeyStateError
from app.hotkey.types import (
    ConflictCallback,
    HotkeyAction,
    HotkeyBinding,
    HotkeyCallback,
    HotkeyMode,
    RecordTriggerState,
)

if TYPE_CHECKING:
    from app.config.config import Config

logger = logging.getLogger(__name__)

_RESERVED_IDS = frozenset({"record", "cancel"})


class HotkeyManager:
    """Dispatch global hotkey events to record/cancel/auto-send callbacks."""

    def __init__(
        self,
        *,
        backend: KeyboardBackend | None = None,
        debounce_ms: int = 50,
        auto_send_enabled: bool = False,
    ) -> None:
        self._backend = backend or create_keyboard_backend()
        self._debouncer = KeyDebouncer(interval_ms=debounce_ms)
        self._auto_send_enabled = auto_send_enabled
        self._mode = HotkeyMode.PTT
        self._record_state = RecordTriggerState.IDLE
        self._bindings: dict[str, HotkeyBinding] = {}
        self._chords: dict[str, KeyChord] = {}
        self._pressed_modifiers: set[str] = set()
        self._started = False

        self._on_record_start: list[HotkeyCallback] = []
        self._on_record_stop: list[HotkeyCallback] = []
        self._on_cancel: list[HotkeyCallback] = []
        self._on_auto_send: list[HotkeyCallback] = []
        self._on_conflict: list[ConflictCallback] = []

    @property
    def mode(self) -> HotkeyMode:
        return self._mode

    @property
    def record_state(self) -> RecordTriggerState:
        return self._record_state

    @property
    def is_running(self) -> bool:
        return self._started

    def bindings(self) -> list[HotkeyBinding]:
        """Return currently registered bindings (for settings UI / diagnostics)."""
        return list(self._bindings.values())

    def on_record_start(self, callback: HotkeyCallback) -> None:
        self._on_record_start.append(callback)

    def on_record_stop(self, callback: HotkeyCallback) -> None:
        self._on_record_stop.append(callback)

    def on_cancel(self, callback: HotkeyCallback) -> None:
        self._on_cancel.append(callback)

    def on_auto_send(self, callback: HotkeyCallback) -> None:
        self._on_auto_send.append(callback)

    def on_conflict(self, callback: ConflictCallback) -> None:
        self._on_conflict.append(callback)

    def set_mode(self, mode: HotkeyMode | str) -> None:
        self._mode = HotkeyMode(mode)
        if self._record_state == RecordTriggerState.RECORDING:
            self._finish_recording(auto_send=False)

    def set_auto_send_enabled(self, enabled: bool) -> None:
        self._auto_send_enabled = enabled

    def register(self, binding: HotkeyBinding) -> bool:
        try:
            chord = parse_binding(binding.keys)
        except HotkeyBindingError as exc:
            logger.warning("Invalid hotkey binding %s: %s", binding.keys, exc)
            self._emit_conflict(binding)
            return False

        if not self._backend.test_register(chord):
            logger.warning("Hotkey conflict for binding %s (%s)", binding.id, binding.keys)
            self._emit_conflict(binding)
            return False

        self._bindings[binding.id] = binding
        self._chords[binding.id] = chord
        return True

    def unregister(self, binding_id: str) -> None:
        self._bindings.pop(binding_id, None)
        self._chords.pop(binding_id, None)

    def test_binding(self, keys: str) -> bool:
        return probe_binding(keys, backend=self._backend)

    def suggest_fallback(self, keys: str) -> str | None:
        return suggest_fallback_binding(keys, backend=self._backend)

    def apply_config(self, config: Config) -> None:
        self.set_mode(config.get("hotkey.mode"))
        self.set_auto_send_enabled(bool(config.get("hotkey.auto_send")))

        for binding_id in list(self._bindings):
            if binding_id in _RESERVED_IDS:
                self.unregister(binding_id)

        record_keys = str(config.get("hotkey.record_binding"))
        cancel_keys = str(config.get("hotkey.cancel_binding"))
        self._register_record_binding(record_keys)
        self._register_cancel_binding(cancel_keys)

    def _register_record_binding(self, record_keys: str) -> None:
        binding = HotkeyBinding(
            id="record",
            keys=record_keys,
            action=HotkeyAction.RECORD,
            mode=self._mode,
        )
        if self.register(binding):
            return

        fallback = suggest_fallback_binding(record_keys, backend=self._backend)
        if fallback is None:
            from core.diagnostics import report_error

            report_error(
                f"No fallback record binding available for {record_keys}",
                context={"component": "hotkey", "binding": record_keys},
            )
            return

        logger.warning(
            "Record binding %s conflicts; using fallback %s",
            record_keys,
            fallback,
        )
        self.register(
            HotkeyBinding(
                id="record",
                keys=fallback,
                action=HotkeyAction.RECORD,
                mode=self._mode,
            )
        )

    def _register_cancel_binding(self, cancel_keys: str) -> None:
        if self.register(
            HotkeyBinding(
                id="cancel",
                keys=cancel_keys,
                action=HotkeyAction.CANCEL,
            )
        ):
            return

        fallback = suggest_fallback_binding(
            cancel_keys,
            backend=self._backend,
            candidates=CANCEL_FALLBACK_BINDINGS,
        )
        if fallback is None:
            from core.diagnostics import report_error

            report_error(
                f"No fallback cancel binding available for {cancel_keys}",
                context={"component": "hotkey", "binding": cancel_keys},
            )
            return

        logger.warning(
            "Cancel binding %s conflicts; using fallback %s",
            cancel_keys,
            fallback,
        )
        self.register(
            HotkeyBinding(
                id="cancel",
                keys=fallback,
                action=HotkeyAction.CANCEL,
            )
        )

    def start(self, *, max_attempts: int = 2) -> None:
        if self._started:
            return

        if os.environ.get("STT_AIO_NFR_BENCH") == "1":
            logger.info("Skipping keyboard hook (STT_AIO_NFR_BENCH=1)")
            self._started = True
            return

        attempts = max(1, max_attempts)
        for attempt in range(attempts):
            self._backend.start(self._handle_key_event)
            if hasattr(self._backend, "wait_ready"):
                ready = self._backend.wait_ready(timeout=1.0)
                hook_failed = getattr(self._backend, "hook_failed", False)
                if ready and not hook_failed:
                    self._started = True
                    return
                self._backend.stop()
                logger.warning(
                    "Keyboard hook start failed (attempt %s/%s)",
                    attempt + 1,
                    attempts,
                )
                continue
            self._started = True
            return

        raise HotkeyRegistrationError("Failed to start global keyboard hook")

    def stop(self) -> None:
        if not self._started:
            return
        self._backend.stop()
        self._started = False
        self._pressed_modifiers.clear()
        self._record_state = RecordTriggerState.IDLE
        self._debouncer.reset()

    def close(self) -> None:
        self.stop()

    def _binding_for_action(self, action: HotkeyAction) -> HotkeyBinding | None:
        for binding in self._bindings.values():
            if binding.action == action:
                return binding
        return None

    def _handle_key_event(self, event: KeyEvent) -> None:
        modifier = modifier_from_vk(event.vk)
        if modifier is not None:
            if event.is_down:
                self._pressed_modifiers.add(modifier)
            else:
                self._pressed_modifiers.discard(modifier)
            if (
                self._mode == HotkeyMode.PTT
                and self._record_state == RecordTriggerState.RECORDING
                and modifier in self._record_chord().modifiers
            ):
                self._finish_recording(auto_send=self._should_auto_send())
            return

        cancel_binding = self._binding_for_action(HotkeyAction.CANCEL)
        if cancel_binding is not None:
            cancel_chord = self._chords[cancel_binding.id]
            if event.vk == cancel_chord.vk and event.is_down:
                if chord_matches_pressed(cancel_chord, self._pressed_modifiers):
                    self._emit_cancel()
                    return

        record_binding = self._binding_for_action(HotkeyAction.RECORD)
        if record_binding is None:
            return

        record_chord = self._chords[record_binding.id]
        if event.vk != record_chord.vk:
            return
        if not chord_matches_pressed(record_chord, self._pressed_modifiers):
            return

        key_id = f"record:{record_chord.vk}"
        if event.is_down:
            if not self._debouncer.accept(key_id, is_repeat=event.is_repeat):
                return
            if self._mode == HotkeyMode.PTT:
                if self._record_state == RecordTriggerState.IDLE:
                    self._emit_record_start()
            else:
                if self._record_state == RecordTriggerState.IDLE:
                    self._emit_record_start()
                elif self._record_state == RecordTriggerState.RECORDING:
                    self._finish_recording(auto_send=self._should_auto_send())
            return

        if self._mode == HotkeyMode.PTT:
            if self._record_state == RecordTriggerState.RECORDING:
                self._finish_recording(auto_send=self._should_auto_send())

    def _record_chord(self) -> KeyChord:
        record_binding = self._binding_for_action(HotkeyAction.RECORD)
        if record_binding is None:
            raise HotkeyStateError("record binding is not registered")
        return self._chords[record_binding.id]

    def _should_auto_send(self) -> bool:
        return self._auto_send_enabled and "alt" in self._pressed_modifiers

    def _emit_record_start(self) -> None:
        self._record_state = RecordTriggerState.RECORDING
        for callback in self._on_record_start:
            callback()

    def _finish_recording(self, *, auto_send: bool) -> None:
        self._record_state = RecordTriggerState.IDLE
        if auto_send:
            self._emit_auto_send()
        else:
            self._emit_record_stop()

    def _emit_record_stop(self) -> None:
        for callback in self._on_record_stop:
            callback()

    def _emit_auto_send(self) -> None:
        for callback in self._on_auto_send:
            callback()

    def _emit_cancel(self) -> None:
        self._record_state = RecordTriggerState.IDLE
        for callback in self._on_cancel:
            callback()

    def _emit_conflict(self, binding: HotkeyBinding) -> None:
        candidates = (
            CANCEL_FALLBACK_BINDINGS
            if binding.action == HotkeyAction.CANCEL
            else None
        )
        suggestion = suggest_fallback_binding(
            binding.keys,
            backend=self._backend,
            candidates=candidates,
        )
        if suggestion:
            logger.info(
                "Suggested fallback binding for %s (%s): %s",
                binding.id,
                binding.keys,
                suggestion,
            )
        for callback in self._on_conflict:
            callback(binding)
