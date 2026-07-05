"""Background workers for settings network tasks (C14)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.models.download_control import DownloadController

if TYPE_CHECKING:
    from app.ui.settings.controller import SettingsController


class _TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    level = Signal(float, float)


class _DownloadSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(str)
    failed = Signal(str)


class LlmConnectionTask(QRunnable):
    def __init__(self, controller: SettingsController, provider_id: str | None, signals: _TaskSignals) -> None:
        super().__init__()
        self._controller = controller
        self._provider_id = provider_id
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._controller.test_connection(self._provider_id)
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class LlmModelsTask(QRunnable):
    def __init__(self, controller: SettingsController, provider_id: str | None, signals: _TaskSignals) -> None:
        super().__init__()
        self._controller = controller
        self._provider_id = provider_id
        self.signals = signals

    def run(self) -> None:
        try:
            models = self._controller.refresh_models(self._provider_id)
            self.signals.finished.emit(models)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class SttReadinessTask(QRunnable):
    def __init__(self, controller: SettingsController, signals: _TaskSignals) -> None:
        super().__init__()
        self._controller = controller
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._controller.check_stt_model()
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class WhisperDownloadTask(QRunnable):
    def __init__(
        self,
        controller: SettingsController,
        model_id: str,
        signals: _DownloadSignals,
        download_controller: DownloadController,
        *,
        force: bool = False,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._model_id = model_id
        self._force = force
        self._download_controller = download_controller
        self.signals = signals

    def run(self) -> None:
        try:
            def on_progress(downloaded: int, total: int, state: str) -> None:
                self.signals.progress.emit(downloaded, total, state)

            path = self._controller.download_whisper_model(
                self._model_id,
                on_progress=on_progress,
                force=self._force,
                controller=self._download_controller,
            )
            self.signals.finished.emit(path)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class UpdateCheckTask(QRunnable):
    def __init__(self, manifest_url: str, signals: _TaskSignals) -> None:
        super().__init__()
        self._manifest_url = manifest_url
        self.signals = signals

    def run(self) -> None:
        try:
            from core.updater.checker import check_for_updates

            info = check_for_updates(self._manifest_url)
            self.signals.finished.emit(info)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class UpdateDownloadTask(QRunnable):
    """Download and verify installer off the UI thread (C22 §6.2)."""

    def __init__(
        self,
        info: object,
        dest_path: str,
        signals: _DownloadSignals,
    ) -> None:
        super().__init__()
        self._info = info
        self._dest_path = dest_path
        self.signals = signals

    def run(self) -> None:
        from pathlib import Path

        from core.updater.downloader import download_update

        info = self._info
        try:

            def on_progress(downloaded: int, total: int) -> None:
                state = "downloading" if total > 0 else "downloading (size unknown)"
                self.signals.progress.emit(downloaded, max(total, 0), state)

            path = download_update(
                str(info.download_url),
                Path(self._dest_path),
                expected_sha256=info.checksum_sha256,
                on_progress=on_progress,
            )
            self.signals.finished.emit(str(path))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class OllamaModelsProbeTask(QRunnable):
    def __init__(self, controller: SettingsController, signals: _TaskSignals) -> None:
        super().__init__()
        self._controller = controller
        self.signals = signals

    def run(self) -> None:
        try:
            models = self._controller.list_ollama_models_managed()
            self.signals.finished.emit(models)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class MicProbeTask(QRunnable):
    def __init__(
        self,
        controller: SettingsController,
        device_id: str,
        signals: _TaskSignals,
        *,
        emit_levels: bool = False,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._device_id = device_id
        self.signals = signals
        self._emit_levels = emit_levels

    def run(self) -> None:
        try:
            def on_level(peak: float, rms: float) -> None:
                if self._emit_levels:
                    self.signals.level.emit(peak, rms)

            result = self._controller.probe_microphone(
                self._device_id,
                on_level=on_level if self._emit_levels else None,
            )
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class InjectionTestTask(QRunnable):
    def __init__(
        self,
        controller: SettingsController,
        text: str,
        signals: _TaskSignals,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._text = text
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._controller.test_injection(self._text)
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class SettingsTaskRunner:
    """Run blocking settings operations off the UI thread."""

    def __init__(self) -> None:
        self._pool = QThreadPool.globalInstance()
        self._download_lock = threading.Lock()
        self._download_controller: DownloadController | None = None
        self._update_download_active = False

    def cancel_whisper_download(self) -> bool:
        with self._download_lock:
            if self._download_controller is None:
                return False
            self._download_controller.cancel()
            return True

    def _clear_download_controller(self, controller: DownloadController) -> None:
        with self._download_lock:
            if self._download_controller is controller:
                self._download_controller = None

    def run_llm_test(
        self,
        controller: SettingsController,
        provider_id: str | None,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(LlmConnectionTask(controller, provider_id, signals))

    def run_llm_models(
        self,
        controller: SettingsController,
        provider_id: str | None,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(LlmModelsTask(controller, provider_id, signals))

    def run_stt_readiness(
        self,
        controller: SettingsController,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(SttReadinessTask(controller, signals))

    def run_whisper_download(
        self,
        controller: SettingsController,
        model_id: str,
        *,
        on_progress,
        on_finished,
        on_failed,
        force: bool = False,
    ) -> None:
        download_controller = DownloadController()
        with self._download_lock:
            self._download_controller = download_controller
        signals = _DownloadSignals()
        signals.progress.connect(on_progress)

        def _finished(path: str) -> None:
            self._clear_download_controller(download_controller)
            on_finished(path)

        def _failed(message: str) -> None:
            self._clear_download_controller(download_controller)
            on_failed(message)

        signals.finished.connect(_finished)
        signals.failed.connect(_failed)
        self._pool.start(
            WhisperDownloadTask(
                controller,
                model_id,
                signals,
                download_controller,
                force=force,
            )
        )

    def run_update_check(
        self,
        manifest_url: str,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(UpdateCheckTask(manifest_url, signals))

    def try_begin_update_download(self) -> bool:
        with self._download_lock:
            if self._update_download_active:
                return False
            self._update_download_active = True
            return True

    def end_update_download(self) -> None:
        with self._download_lock:
            self._update_download_active = False

    def run_update_download(
        self,
        info,
        dest_path: str,
        *,
        on_progress,
        on_finished,
        on_failed,
    ) -> None:
        """Download verified installer in background (C22 §6.2)."""
        signals = _DownloadSignals()
        signals.progress.connect(on_progress)
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(UpdateDownloadTask(info, dest_path, signals))

    def run_ollama_models_probe(
        self,
        controller: SettingsController,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(OllamaModelsProbeTask(controller, signals))

    def run_mic_probe(
        self,
        controller: SettingsController,
        device_id: str,
        *,
        on_finished,
        on_failed,
        on_level=None,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        if on_level is not None:
            signals.level.connect(on_level)
        self._pool.start(
            MicProbeTask(controller, device_id, signals, emit_levels=on_level is not None)
        )

    def run_injection_test(
        self,
        controller: SettingsController,
        text: str,
        *,
        on_finished,
        on_failed,
    ) -> None:
        signals = _TaskSignals()
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        self._pool.start(InjectionTestTask(controller, text, signals))
