"""Settings tab pages (C14 + C18 Models)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.export.naming import validate_filename_pattern
from core.export.templates.registry import TEMPLATES
from core.llm.registry import registered_provider_ids as llm_provider_ids
from core.secrets import LLM_API_KEY_SECRET, STT_API_KEY_SECRET
from core.stt.registry import registered_provider_ids as stt_provider_ids
from core.store.models import DictionaryType
from app.ui.settings.workers import SettingsTaskRunner

if TYPE_CHECKING:
    from app.services.remote_gateway_service import RemoteGatewayService
    from app.ui.settings.controller import SettingsController

ActiveModeCallback = Callable[[str, str], None]
ModesChangedCallback = Callable[[], None]


def _wrap_scroll(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    return scroll


def _choice_combo(controller: SettingsController, key: str) -> QComboBox:
    combo = QComboBox()
    for choice in controller.get_choice_keys(key):
        combo.addItem(choice, choice)
    return combo


def _set_combo_value(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentText(value)


class GeneralSettingsPage(QWidget):
    """Audio, inject, and session queue settings."""

    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks or SettingsTaskRunner()
        self._loading = False

        inner = QWidget()
        layout = QVBoxLayout(inner)

        audio_group = QGroupBox("오디오")
        audio_form = QFormLayout(audio_group)
        self._device = QComboBox()
        self._device.currentIndexChanged.connect(self._save_device)
        audio_form.addRow("마이크", self._device)
        self._vad_engine = _choice_combo(controller, "audio.vad_engine")
        self._vad_engine.currentIndexChanged.connect(self._save_vad_engine)
        audio_form.addRow("VAD 엔진", self._vad_engine)
        self._vad = QDoubleSpinBox()
        self._vad.setRange(0.0, 1.0)
        self._vad.setSingleStep(0.05)
        self._vad.valueChanged.connect(lambda v: self._save("audio.vad_threshold", v))
        audio_form.addRow("VAD 임계값", self._vad)
        self._min_speech = QSpinBox()
        self._min_speech.setRange(50, 5000)
        self._min_speech.setSuffix(" ms")
        self._min_speech.valueChanged.connect(lambda v: self._save("audio.min_speech_ms", v))
        audio_form.addRow("최소 발화", self._min_speech)
        self._hangover = QSpinBox()
        self._hangover.setRange(100, 3000)
        self._hangover.setSuffix(" ms")
        self._hangover.valueChanged.connect(lambda v: self._save("audio.hangover_ms", v))
        audio_form.addRow("행오버", self._hangover)
        self._max_segment = QSpinBox()
        self._max_segment.setRange(1000, 300000)
        self._max_segment.setSuffix(" ms")
        self._max_segment.valueChanged.connect(lambda v: self._save("audio.max_segment_ms", v))
        audio_form.addRow("최대 세그먼트", self._max_segment)
        layout.addWidget(audio_group)

        inject_group = QGroupBox("텍스트 주입")
        inject_form = QFormLayout(inject_group)
        self._inject_method = _choice_combo(controller, "inject.default_method")
        self._inject_method.currentIndexChanged.connect(self._save_inject_method)
        inject_form.addRow("기본 방식", self._inject_method)
        self._inject_threshold = QSpinBox()
        self._inject_threshold.setRange(50, 10000)
        self._inject_threshold.valueChanged.connect(
            lambda v: self._save("inject.length_threshold", v)
        )
        inject_form.addRow("클립보드 전환 길이", self._inject_threshold)
        self._press_enter = QCheckBox("주입 후 Enter 키 입력")
        self._press_enter.toggled.connect(lambda v: self._save("inject.press_enter", v))
        inject_form.addRow("", self._press_enter)
        layout.addWidget(inject_group)

        session_group = QGroupBox("세션")
        session_form = QFormLayout(session_group)
        self._queue_policy = _choice_combo(controller, "session.queue_policy")
        self._queue_policy.currentIndexChanged.connect(self._save_queue_policy)
        session_form.addRow("동시 녹음 정책", self._queue_policy)
        layout.addWidget(session_group)

        update_group = QGroupBox("업데이트")
        update_form = QFormLayout(update_group)
        self._update_manifest = QLineEdit()
        self._update_manifest.setPlaceholderText("https://example.com/stt-aio/update.json")
        self._update_manifest.editingFinished.connect(self._save_update_manifest)
        update_form.addRow("매니페스트 URL", self._update_manifest)
        self._update_auto_check = QCheckBox("앱 시작 시 업데이트 자동 확인")
        self._update_auto_check.toggled.connect(
            lambda v: self._save("update.auto_check", v)
        )
        update_form.addRow("", self._update_auto_check)
        update_row = QHBoxLayout()
        self._update_check_btn = QPushButton("업데이트 확인")
        self._update_check_btn.clicked.connect(self._check_updates)
        update_row.addWidget(self._update_check_btn)
        update_row.addStretch()
        update_form.addRow("", update_row)
        layout.addWidget(update_group)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.addWidget(_wrap_scroll(inner))

    def reload(self) -> None:
        self._loading = True
        self._device.blockSignals(True)
        self._device.clear()
        for opt in self._controller.list_audio_devices():
            self._device.addItem(opt.label, opt.device_id)
        current = str(self._controller.get_setting("audio.device_id"))
        _set_combo_value(self._device, current)
        self._device.blockSignals(False)

        _set_combo_value(self._vad_engine, str(self._controller.get_setting("audio.vad_engine")))
        self._vad.setValue(float(self._controller.get_setting("audio.vad_threshold")))
        self._min_speech.setValue(int(self._controller.get_setting("audio.min_speech_ms")))
        self._hangover.setValue(int(self._controller.get_setting("audio.hangover_ms")))
        self._max_segment.setValue(int(self._controller.get_setting("audio.max_segment_ms")))
        _set_combo_value(self._inject_method, str(self._controller.get_setting("inject.default_method")))
        self._inject_threshold.setValue(int(self._controller.get_setting("inject.length_threshold")))
        self._press_enter.setChecked(bool(self._controller.get_setting("inject.press_enter")))
        _set_combo_value(self._queue_policy, str(self._controller.get_setting("session.queue_policy")))
        self._update_manifest.setText(str(self._controller.get_setting("update.manifest_url")))
        self._update_auto_check.setChecked(bool(self._controller.get_setting("update.auto_check")))
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)

    def _save_device(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("audio.device_id", self._device.currentData())

    def _save_vad_engine(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("audio.vad_engine", self._vad_engine.currentData())

    def _save_inject_method(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("inject.default_method", self._inject_method.currentData())

    def _save_queue_policy(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("session.queue_policy", self._queue_policy.currentData())

    def _save_update_manifest(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("update.manifest_url", self._update_manifest.text().strip())

    def _check_updates(self) -> None:
        from app.ui.update_check import run_update_check_dialog

        run_update_check_dialog(
            self._tasks,
            str(self._controller.get_setting("update.manifest_url")),
            self,
        )


class SttSettingsPage(QWidget):
    """STT provider and model settings."""

    _PROVIDER_LABELS = {
        "faster_whisper_local": "로컬 (faster-whisper)",
        "openai_transcribe": "OpenAI",
        "groq_transcribe": "Groq",
        "deepgram_transcribe": "Deepgram",
    }

    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._provider = QComboBox()
        for provider_id in controller.get_choice_keys("stt.provider"):
            label = self._PROVIDER_LABELS.get(provider_id, provider_id)
            self._provider.addItem(label, provider_id)
        self._provider.currentIndexChanged.connect(self._save_provider)
        form.addRow("Provider", self._provider)

        key_row = QHBoxLayout()
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("클라우드 STT 키 (미설정 시 LLM 키 사용)")
        key_row.addWidget(self._api_key)
        save_key = QPushButton("저장")
        save_key.clicked.connect(self._save_api_key)
        key_row.addWidget(save_key)
        del_key = QPushButton("삭제")
        del_key.clicked.connect(self._delete_api_key)
        key_row.addWidget(del_key)
        form.addRow("클라우드 API 키", key_row)

        self._key_hint = QLabel()
        self._key_hint.setWordWrap(True)
        form.addRow("키 상태", self._key_hint)

        self._model = QComboBox()
        self._model.setEditable(True)
        for item in controller.list_whisper_catalog():
            self._model.addItem(f"{item.name} ({item.id})", item.id)
        self._model.currentIndexChanged.connect(self._save_model)
        form.addRow("모델", self._model)

        self._language = QLineEdit()
        self._language.editingFinished.connect(self._save_language)
        form.addRow("언어 코드", self._language)

        self._fallback = QCheckBox("로컬 STT로 폴백")
        self._fallback.toggled.connect(lambda v: self._save("stt.fallback_to_local", v))
        form.addRow("", self._fallback)

        layout.addLayout(form)

        row = QHBoxLayout()
        self._check_btn = QPushButton("모델 준비 상태 확인")
        self._check_btn.clicked.connect(self._run_check)
        row.addWidget(self._check_btn)
        row.addStretch()
        layout.addLayout(row)

        self._status = QLabel("모델 상태를 확인하려면 버튼을 누르세요.")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        _set_combo_value(self._provider, str(self._controller.get_setting("stt.provider")))
        _set_combo_value(self._model, str(self._controller.get_setting("stt.model")))
        self._language.setText(str(self._controller.get_setting("stt.language")))
        self._fallback.setChecked(bool(self._controller.get_setting("stt.fallback_to_local")))
        self._api_key.clear()
        self._key_hint.setText(
            self._controller.get_api_key_hint(STT_API_KEY_SECRET) or "미설정"
        )
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)

    def _save_provider(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("stt.provider", self._provider.currentData())

    def _save_model(self) -> None:
        if self._loading:
            return
        data = self._model.currentData()
        value = data if data is not None else self._model.currentText().strip()
        self._controller.save_setting("stt.model", value)

    def _save_language(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("stt.language", self._language.text().strip())

    def _save_api_key(self) -> None:
        if self._loading:
            return
        value = self._api_key.text().strip()
        if not value:
            return
        self._controller.set_api_key(STT_API_KEY_SECRET, value)
        self._api_key.clear()
        self._key_hint.setText(self._controller.get_api_key_hint(STT_API_KEY_SECRET))

    def _delete_api_key(self) -> None:
        if self._loading:
            return
        if self._controller.delete_api_key(STT_API_KEY_SECRET):
            self._key_hint.setText(
                self._controller.get_api_key_hint(STT_API_KEY_SECRET) or "미설정"
            )

    def _run_check(self) -> None:
        self._check_btn.setEnabled(False)
        self._status.setText("확인 중…")

        def on_finished(result) -> None:
            self._check_btn.setEnabled(True)
            prefix = "✓" if result.ok else "✗"
            self._status.setText(f"{prefix} {result.message}")

        def on_failed(message: str) -> None:
            self._check_btn.setEnabled(True)
            self._status.setText(f"오류: {message}")

        self._tasks.run_stt_readiness(
            self._controller,
            on_finished=on_finished,
            on_failed=on_failed,
        )


class LlmSettingsPage(QWidget):
    """LLM provider, API key, and connection test."""

    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._provider = _choice_combo(controller, "llm.provider")
        self._provider.currentIndexChanged.connect(self._save_provider)
        form.addRow("Provider", self._provider)

        key_row = QHBoxLayout()
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("붙여넣기 후 저장")
        key_row.addWidget(self._api_key)
        save_key = QPushButton("저장")
        save_key.clicked.connect(self._save_api_key)
        key_row.addWidget(save_key)
        del_key = QPushButton("삭제")
        del_key.clicked.connect(self._delete_api_key)
        key_row.addWidget(del_key)
        form.addRow("API 키", key_row)

        self._key_hint = QLabel()
        self._key_hint.setWordWrap(True)
        form.addRow("키 상태", self._key_hint)

        self._base_url = QLineEdit()
        self._base_url.editingFinished.connect(self._save_base_url)
        form.addRow("Base URL", self._base_url)

        self._model = QComboBox()
        self._model.setEditable(True)
        self._model.currentIndexChanged.connect(self._save_model)
        form.addRow("모델", self._model)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.valueChanged.connect(lambda v: self._save("llm.temperature", v))
        form.addRow("Temperature", self._temperature)

        self._max_output = QSpinBox()
        self._max_output.setRange(64, 32768)
        self._max_output.valueChanged.connect(lambda v: self._save("llm.max_output", v))
        form.addRow("최대 출력 토큰", self._max_output)

        self._timeout = QSpinBox()
        self._timeout.setRange(5, 600)
        self._timeout.setSuffix(" 초")
        self._timeout.valueChanged.connect(lambda v: self._save("llm.timeout_sec", v))
        form.addRow("타임아웃", self._timeout)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("연결 테스트")
        self._test_btn.clicked.connect(self._run_test)
        btn_row.addWidget(self._test_btn)
        self._models_btn = QPushButton("모델 목록 새로고침")
        self._models_btn.clicked.connect(self._run_refresh_models)
        btn_row.addWidget(self._models_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._conn_status = QLabel()
        self._conn_status.setWordWrap(True)
        layout.addWidget(self._conn_status)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        _set_combo_value(self._provider, str(self._controller.get_setting("llm.provider")))
        self._api_key.clear()
        self._key_hint.setText(self._controller.get_api_key_hint() or "미설정")
        self._base_url.setText(str(self._controller.get_setting("llm.base_url")))
        _set_combo_value(self._model, str(self._controller.get_setting("llm.model")))
        self._temperature.setValue(float(self._controller.get_setting("llm.temperature")))
        self._max_output.setValue(int(self._controller.get_setting("llm.max_output")))
        self._timeout.setValue(int(self._controller.get_setting("llm.timeout_sec")))
        self._conn_status.clear()
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)

    def _save_provider(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("llm.provider", self._provider.currentData())

    def _save_base_url(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("llm.base_url", self._base_url.text().strip())

    def _save_model(self) -> None:
        if self._loading:
            return
        data = self._model.currentData()
        value = data if data is not None else self._model.currentText().strip()
        self._controller.save_setting("llm.model", value)

    def _save_api_key(self) -> None:
        from core.secrets import LLM_API_KEY_SECRET

        value = self._api_key.text().strip()
        if not value:
            QMessageBox.warning(self, "API 키", "저장할 키를 입력하세요.")
            return
        self._controller.set_api_key(LLM_API_KEY_SECRET, value)
        self._api_key.clear()
        self._key_hint.setText(self._controller.get_api_key_hint())

    def _delete_api_key(self) -> None:
        from core.secrets import LLM_API_KEY_SECRET

        if self._controller.delete_api_key(LLM_API_KEY_SECRET):
            self._key_hint.setText("삭제됨")
        else:
            self._key_hint.setText(self._controller.get_api_key_hint() or "미설정")

    def _run_test(self) -> None:
        self._test_btn.setEnabled(False)
        self._conn_status.setText("연결 테스트 중…")
        provider = self._provider.currentData()

        def on_finished(result) -> None:
            self._test_btn.setEnabled(True)
            self._conn_status.setText(self._controller.format_connection_result(result))

        def on_failed(message: str) -> None:
            self._test_btn.setEnabled(True)
            self._conn_status.setText(f"오류: {message}")

        self._tasks.run_llm_test(
            self._controller,
            provider,
            on_finished=on_finished,
            on_failed=on_failed,
        )

    def _run_refresh_models(self) -> None:
        self._models_btn.setEnabled(False)
        provider = self._provider.currentData()

        def on_finished(models) -> None:
            self._models_btn.setEnabled(True)
            current = str(self._controller.get_setting("llm.model"))
            self._loading = True
            self._model.clear()
            for info in models:
                self._model.addItem(info.name or info.id, info.id)
            _set_combo_value(self._model, current)
            self._loading = False
            self._conn_status.setText(f"모델 {len(models)}개 조회됨")

        def on_failed(message: str) -> None:
            self._models_btn.setEnabled(True)
            self._conn_status.setText(f"모델 조회 실패: {message}")

        self._tasks.run_llm_models(
            self._controller,
            provider,
            on_finished=on_finished,
            on_failed=on_failed,
        )


class HotkeySettingsPage(QWidget):
    """Hotkey bindings and mode."""

    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._mode = _choice_combo(controller, "hotkey.mode")
        self._mode.currentIndexChanged.connect(self._save_mode)
        form.addRow("동작 방식", self._mode)

        self._record = QLineEdit()
        self._record.editingFinished.connect(self._validate_record)
        form.addRow("녹음 단축키", self._record)

        self._cancel = QLineEdit()
        self._cancel.editingFinished.connect(self._validate_cancel)
        form.addRow("취소 단축키", self._cancel)

        self._auto_send = QCheckBox("처리 완료 후 자동 전송")
        self._auto_send.toggled.connect(lambda v: self._save("hotkey.auto_send", v))
        form.addRow("", self._auto_send)

        layout.addLayout(form)
        self._validation = QLabel()
        self._validation.setWordWrap(True)
        layout.addWidget(self._validation)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        _set_combo_value(self._mode, str(self._controller.get_setting("hotkey.mode")))
        self._record.setText(str(self._controller.get_setting("hotkey.record_binding")))
        self._cancel.setText(str(self._controller.get_setting("hotkey.cancel_binding")))
        self._auto_send.setChecked(bool(self._controller.get_setting("hotkey.auto_send")))
        self._validation.clear()
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)

    def _save_mode(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("hotkey.mode", self._mode.currentData())

    def _validate_record(self) -> None:
        if self._loading:
            return
        text = self._record.text().strip()
        result = self._controller.validate_hotkey_binding(text)
        if not result.ok:
            self._validation.setText(result.message)
            return
        pair = self._controller.validate_hotkey_pair(text, self._cancel.text().strip())
        if pair is not None:
            self._validation.setText(pair.message)
            return
        self._controller.save_setting("hotkey.record_binding", text)
        self._validation.setText("녹음 단축키 저장됨")

    def _validate_cancel(self) -> None:
        if self._loading:
            return
        text = self._cancel.text().strip()
        result = self._controller.validate_hotkey_binding(text)
        if not result.ok:
            self._validation.setText(result.message)
            return
        pair = self._controller.validate_hotkey_pair(self._record.text().strip(), text)
        if pair is not None:
            self._validation.setText(pair.message)
            return
        self._controller.save_setting("hotkey.cancel_binding", text)
        self._validation.setText("취소 단축키 저장됨")


class TextprocSettingsPage(QWidget):
    """Text post-processing toggles (C17)."""

    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._loading = False

        layout = QVBoxLayout(self)
        self._normalize = QCheckBox("공백·문장부호 정규화")
        self._normalize.toggled.connect(lambda v: self._save("textproc.normalize", v))
        layout.addWidget(self._normalize)
        self._dictionary = QCheckBox("사전 치환")
        self._dictionary.toggled.connect(lambda v: self._save("textproc.dictionary", v))
        layout.addWidget(self._dictionary)
        self._snippets = QCheckBox("스니펫 확장")
        self._snippets.toggled.connect(lambda v: self._save("textproc.snippets", v))
        layout.addWidget(self._snippets)
        self._punct = QCheckBox("문장부호 앞뒤 공백 정리")
        self._punct.toggled.connect(lambda v: self._save("textproc.punctuation_spacing", v))
        layout.addWidget(self._punct)
        self._number = QCheckBox("숫자 주변 공백 정리")
        self._number.toggled.connect(lambda v: self._save("textproc.number_spacing", v))
        layout.addWidget(self._number)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        self._normalize.setChecked(bool(self._controller.get_setting("textproc.normalize")))
        self._dictionary.setChecked(bool(self._controller.get_setting("textproc.dictionary")))
        self._snippets.setChecked(bool(self._controller.get_setting("textproc.snippets")))
        self._punct.setChecked(bool(self._controller.get_setting("textproc.punctuation_spacing")))
        self._number.setChecked(bool(self._controller.get_setting("textproc.number_spacing")))
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)


class DictionarySettingsPage(QWidget):
    """Dictionary and snippet entry management."""

    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list)

        form = QFormLayout()
        self._term = QLineEdit()
        form.addRow("용어", self._term)
        self._replacement = QLineEdit()
        form.addRow("치환", self._replacement)
        self._type = QComboBox()
        self._type.addItem("사전", DictionaryType.VOCAB.value)
        self._type.addItem("스니펫", DictionaryType.SNIPPET.value)
        form.addRow("유형", self._type)
        layout.addLayout(form)

        row = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self._add_entry)
        row.addWidget(add_btn)
        del_btn = QPushButton("삭제")
        del_btn.clicked.connect(self._delete_entry)
        row.addWidget(del_btn)
        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.reload)
        row.addWidget(refresh_btn)
        row.addStretch()
        layout.addLayout(row)

    def reload(self) -> None:
        self._list.clear()
        for entry in self._controller.list_dictionary_entries():
            kind = "사전" if entry.type == DictionaryType.VOCAB else "스니펫"
            flag = "" if entry.enabled else " (비활성)"
            self._list.addItem(f"[{kind}] {entry.term} → {entry.replacement}{flag}")

    def _add_entry(self) -> None:
        term = self._term.text().strip()
        replacement = self._replacement.text().strip()
        if not term or not replacement:
            QMessageBox.warning(self, "사전", "용어와 치환 값을 모두 입력하세요.")
            return
        entry_type = DictionaryType(self._type.currentData())
        self._controller.add_dictionary_entry(
            term=term,
            replacement=replacement,
            entry_type=entry_type,
        )
        self._term.clear()
        self._replacement.clear()
        self.reload()

    def _delete_entry(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        entries = self._controller.list_dictionary_entries()
        if row >= len(entries):
            return
        entry = entries[row]
        if QMessageBox.question(self, "삭제", f"'{entry.term}' 항목을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self._controller.delete_dictionary_entry(entry.id)
        self.reload()


def _provider_combo(ids: tuple[str, ...]) -> QComboBox:
    combo = QComboBox()
    combo.addItem("(앱 기본)", "")
    for provider_id in ids:
        combo.addItem(provider_id, provider_id)
    return combo


def _set_provider_combo(combo: QComboBox, value: str | None) -> None:
    normalized = (value or "").strip()
    if not normalized:
        combo.setCurrentIndex(0)
        return
    for index in range(combo.count()):
        if combo.itemData(index) == normalized:
            combo.setCurrentIndex(index)
            return
    combo.addItem(normalized, normalized)
    combo.setCurrentIndex(combo.count() - 1)


class _ModeEditorDialog(QDialog):
    def __init__(self, controller: SettingsController, *, mode=None, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._mode = mode
        self.setWindowTitle("모드 편집" if mode else "모드 추가")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("이름", self._name)
        self._target = QSpinBox()
        self._target.setRange(0, 3)
        form.addRow("대상 단계", self._target)
        self._inject = QSpinBox()
        self._inject.setRange(0, 3)
        form.addRow("주입 단계", self._inject)
        self._correction = QTextEdit()
        self._correction.setPlaceholderText("2차 교정 프롬프트 (선택)")
        form.addRow("교정 프롬프트", self._correction)
        self._report = QTextEdit()
        self._report.setPlaceholderText("3차 보고서 프롬프트 (선택)")
        form.addRow("보고서 프롬프트", self._report)
        self._stt_provider = _provider_combo(stt_provider_ids())
        form.addRow("STT Provider", self._stt_provider)
        self._llm_provider = _provider_combo(llm_provider_ids())
        form.addRow("LLM Provider", self._llm_provider)
        self._enabled = QCheckBox("활성")
        form.addRow("", self._enabled)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if mode is not None:
            self._name.setText(mode.name)
            self._target.setValue(mode.target_stage)
            self._inject.setValue(mode.inject_stage)
            self._correction.setPlainText(mode.correction_prompt)
            self._report.setPlainText(mode.report_prompt)
            self._enabled.setChecked(mode.enabled)
            _set_provider_combo(self._stt_provider, mode.stt_provider)
            _set_provider_combo(self._llm_provider, mode.llm_provider)

    def build_draft(self):
        from core.modes.types import ModeDraft

        stt = str(self._stt_provider.currentData() or "").strip() or None
        llm = str(self._llm_provider.currentData() or "").strip() or None
        return ModeDraft(
            name=self._name.text().strip(),
            target_stage=self._target.value(),
            inject_stage=self._inject.value(),
            correction_prompt=self._correction.toPlainText(),
            report_prompt=self._report.toPlainText(),
            stt_provider=stt,
            llm_provider=llm,
            enabled=self._enabled.isChecked(),
        )


class ModesSettingsPage(QWidget):
    """Mode CRUD and active mode selection."""

    def __init__(
        self,
        controller: SettingsController,
        *,
        on_active_mode_changed: ActiveModeCallback | None = None,
        on_modes_changed: ModesChangedCallback | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._on_active_mode_changed = on_active_mode_changed
        self._on_modes_changed = on_modes_changed

        layout = QHBoxLayout(self)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._show_detail)
        layout.addWidget(self._list, 1)

        right = QVBoxLayout()
        self._detail = QLabel("모드를 선택하세요.")
        self._detail.setWordWrap(True)
        right.addWidget(self._detail)

        row1 = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self._add_mode)
        row1.addWidget(add_btn)
        edit_btn = QPushButton("편집")
        edit_btn.clicked.connect(self._edit_mode)
        row1.addWidget(edit_btn)
        del_btn = QPushButton("삭제")
        del_btn.clicked.connect(self._delete_mode)
        row1.addWidget(del_btn)
        restore_btn = QPushButton("기본값 복원")
        restore_btn.clicked.connect(self._restore_mode)
        row1.addWidget(restore_btn)
        right.addLayout(row1)

        row2 = QHBoxLayout()
        default_btn = QPushButton("기본 모드로")
        default_btn.clicked.connect(self._set_default)
        row2.addWidget(default_btn)
        active_btn = QPushButton("활성 모드로")
        active_btn.clicked.connect(self._set_active)
        row2.addWidget(active_btn)
        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.reload)
        row2.addWidget(refresh_btn)
        row2.addStretch()
        right.addLayout(row2)
        right.addStretch()
        layout.addLayout(right, 1)

    def reload(self) -> None:
        current_id = self._controller.get_setting("mode.active_id")
        self._list.clear()
        for mode in self._controller.list_modes():
            tags: list[str] = []
            if mode.is_default:
                tags.append("기본")
            if mode.is_builtin:
                tags.append("내장")
            if str(current_id) == mode.id:
                tags.append("활성")
            suffix = f" ({', '.join(tags)})" if tags else ""
            self._list.addItem(f"{mode.name}{suffix}")

    def _selected_mode(self):
        row = self._list.currentRow()
        if row < 0:
            return None
        modes = self._controller.list_modes()
        if row >= len(modes):
            return None
        return modes[row]

    def _show_detail(self, row: int) -> None:
        if row < 0:
            self._detail.setText("모드를 선택하세요.")
            return
        mode = self._selected_mode()
        if mode is None:
            return
        self._detail.setText(
            f"ID: {mode.id}\n"
            f"대상 단계: {mode.target_stage} · 주입 단계: {mode.inject_stage}\n"
            f"STT: {mode.stt_provider or '(앱 기본)'} · "
            f"LLM: {mode.llm_provider or '(앱 기본)'}\n"
            f"내장: {'예' if mode.is_builtin else '아니오'} · "
            f"기본: {'예' if mode.is_default else '아니오'}"
        )

    def _notify_modes_changed(self) -> None:
        if self._on_modes_changed is not None:
            self._on_modes_changed()
        self.reload()

    def _add_mode(self) -> None:
        dialog = _ModeEditorDialog(self._controller, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        draft = dialog.build_draft()
        if not draft.name:
            QMessageBox.warning(self, "모드", "이름을 입력하세요.")
            return
        self._controller.create_mode(draft)
        self._notify_modes_changed()

    def _edit_mode(self) -> None:
        mode = self._selected_mode()
        if mode is None:
            return
        if mode.is_builtin:
            QMessageBox.information(self, "모드", "내장 모드는 '기본값 복원'으로 되돌릴 수 있습니다.")
            return
        dialog = _ModeEditorDialog(self._controller, mode=mode, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        draft = dialog.build_draft()
        self._controller.update_mode(mode.id, draft)
        self._notify_modes_changed()

    def _delete_mode(self) -> None:
        mode = self._selected_mode()
        if mode is None:
            return
        if mode.is_builtin or mode.is_default:
            QMessageBox.warning(self, "모드", "내장·기본 모드는 삭제할 수 없습니다.")
            return
        if QMessageBox.question(self, "삭제", f"'{mode.name}' 모드를 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self._controller.delete_mode(mode.id)
        self._notify_modes_changed()

    def _restore_mode(self) -> None:
        mode = self._selected_mode()
        if mode is None or not mode.is_builtin:
            QMessageBox.information(self, "모드", "내장 모드를 선택하세요.")
            return
        self._controller.restore_builtin_mode(mode.id)
        self._notify_modes_changed()

    def _set_default(self) -> None:
        mode = self._selected_mode()
        if mode is None:
            return
        self._controller.set_default_mode(mode.id)
        self._notify_modes_changed()

    def _set_active(self) -> None:
        mode = self._selected_mode()
        if mode is None:
            return
        self._controller.set_active_mode_id(mode.id)
        if self._on_active_mode_changed is not None:
            self._on_active_mode_changed(mode.id, mode.name)
        self.reload()


class PrivacySettingsPage(QWidget):
    """Privacy, logging, and diagnostics settings."""

    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._keep_audio = QCheckBox("녹음 오디오 보관")
        self._keep_audio.toggled.connect(self._on_keep_audio)
        form.addRow("", self._keep_audio)

        self._retention = QSpinBox()
        self._retention.setRange(0, 365)
        self._retention.setSuffix(" 일")
        self._retention.valueChanged.connect(lambda v: self._save("privacy.audio_retention_days", v))
        form.addRow("보관 기간", self._retention)

        self._telemetry = QCheckBox("익명 사용 통계 전송 (미구현)")
        self._telemetry.setEnabled(False)
        self._telemetry.toggled.connect(lambda v: self._save("privacy.telemetry", v))
        form.addRow("", self._telemetry)

        self._log_level = _choice_combo(controller, "logging.level")
        self._log_level.currentIndexChanged.connect(self._save_log_level)
        form.addRow("로그 레벨", self._log_level)

        self._log_path = QLabel()
        self._log_path.setWordWrap(True)
        form.addRow("로그 파일", self._log_path)

        layout.addLayout(form)

        diag_row = QHBoxLayout()
        export_btn = QPushButton("진단 패키지보내기…")
        export_btn.clicked.connect(self._export_diagnostics)
        diag_row.addWidget(export_btn)
        open_logs_btn = QPushButton("로그 폴더 열기")
        open_logs_btn.clicked.connect(self._open_logs_dir)
        diag_row.addWidget(open_logs_btn)
        diag_row.addStretch()
        layout.addLayout(diag_row)

        note = QLabel(
            "문제 재현 시 로그 레벨을 debug로 올린 뒤 진단 패키지를 보내세요. "
            "오디오 파일은 로컬에만 저장되며, 진단 패키지에는 API 키·원문 텍스트·"
            "오디오가 포함되지 않습니다."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        keep = bool(self._controller.get_setting("privacy.keep_audio"))
        self._keep_audio.setChecked(keep)
        self._retention.setEnabled(keep)
        self._retention.setValue(int(self._controller.get_setting("privacy.audio_retention_days")))
        self._telemetry.setChecked(bool(self._controller.get_setting("privacy.telemetry")))
        _set_combo_value(self._log_level, str(self._controller.get_setting("logging.level")))
        self._log_path.setText(self._controller.get_log_file_path())
        self._loading = False

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self._controller.save_setting(key, value)

    def _save_log_level(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("logging.level", self._log_level.currentData())

    def _on_keep_audio(self, checked: bool) -> None:
        self._retention.setEnabled(checked)
        self._save("privacy.keep_audio", checked)

    def _export_diagnostics(self) -> None:
        consent = QMessageBox.question(
            self,
            "진단 패키지",
            "다음 정보가 zip으로 저장됩니다:\n"
            "- 최근 로그 파일\n"
            "- 앱/OS/Provider 설정 스냅샷 (API 키·원문 텍스트 제외)\n"
            "- 최근 오류 이벤트\n\n"
            "계속할까요?",
        )
        if consent != QMessageBox.StandardButton.Yes:
            return

        from datetime import datetime

        default_name = f"stt-aio-diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        dest, _filter = QFileDialog.getSaveFileName(
            self,
            "진단 패키지 저장",
            str(Path.home() / default_name),
            "ZIP 파일 (*.zip)",
        )
        if not dest:
            return
        result = self._controller.export_diagnostics_package(dest)
        if result.ok:
            QMessageBox.information(self, "진단 패키지", result.message)
        else:
            QMessageBox.warning(self, "진단 패키지", result.message)

    def _open_logs_dir(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        logs_dir = self._controller.get_logs_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(logs_dir))


class ExportSettingsPage(QWidget):
    """Export defaults (C8 settings tab)."""

    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        dir_row = QHBoxLayout()
        self._default_dir = QLineEdit()
        self._default_dir.editingFinished.connect(self._save_dir)
        dir_row.addWidget(self._default_dir)
        browse = QPushButton("찾아보기")
        browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse)
        form.addRow("기본 저장 폴더", dir_row)

        self._pattern = QLineEdit()
        self._pattern.setPlaceholderText("{date}-{time}_{mode}_{stage}")
        self._pattern.editingFinished.connect(self._save_pattern)
        form.addRow("파일명 패턴", self._pattern)

        self._docx_template = QComboBox()
        for template_id, info in TEMPLATES.items():
            self._docx_template.addItem(info.name, template_id)
        self._docx_template.currentIndexChanged.connect(self._save_template)
        form.addRow("docx 템플릿", self._docx_template)

        layout.addLayout(form)
        self._pattern_hint = QLabel(
            "사용 가능 변수: {date}, {time}, {mode}, {stage}"
        )
        self._pattern_hint.setWordWrap(True)
        layout.addWidget(self._pattern_hint)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        self._default_dir.setText(str(self._controller.get_setting("export.default_dir")))
        self._pattern.setText(str(self._controller.get_setting("export.filename_pattern")))
        _set_combo_value(
            self._docx_template,
            str(self._controller.get_setting("export.default_docx_template")),
        )
        self._loading = False

    def _save_dir(self) -> None:
        if self._loading:
            return
        self._controller.save_setting("export.default_dir", self._default_dir.text().strip())

    def _save_pattern(self) -> None:
        if self._loading:
            return
        pattern = self._pattern.text().strip()
        error = validate_filename_pattern(pattern)
        if error:
            QMessageBox.warning(self, "파일명 패턴", error)
            return
        self._controller.save_setting("export.filename_pattern", pattern)

    def _save_template(self) -> None:
        if self._loading:
            return
        self._controller.save_setting(
            "export.default_docx_template",
            self._docx_template.currentData(),
        )

    def _browse_dir(self) -> None:
        current = self._default_dir.text().strip()
        start = current if current else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "기본 저장 폴더", start)
        if chosen:
            self._default_dir.setText(chosen)
            self._controller.save_setting("export.default_dir", chosen)


class RemoteSettingsPage(QWidget):
    """Remote recording gateway control (C15)."""

    def __init__(
        self,
        controller: SettingsController,
        gateway: RemoteGatewayService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._gateway = gateway
        self._loading = False

        layout = QVBoxLayout(self)
        intro = QLabel(
            "모바일 브라우저에서 녹음한 오디오를 이 PC로 전송합니다. "
            "서버를 시작한 뒤 표시된 PIN으로 페어링하세요.\n"
            "※ 모바일 마이크는 HTTPS가 필요합니다. Tunnel 없이 로컬 HTTP만 쓰면 "
            "PC 브라우저에서만 테스트할 수 있습니다."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self._port = QSpinBox()
        self._port.setRange(1024, 65535)
        self._port.valueChanged.connect(self._save_port)
        form.addRow("포트", self._port)
        self._use_tunnel = QCheckBox("Cloudflare Tunnel 사용 (cloudflared 필요)")
        self._use_tunnel.toggled.connect(self._save_tunnel)
        form.addRow("", self._use_tunnel)
        self._lan_fallback = QCheckBox(
            "Tunnel 실패 시 LAN 폴백 (0.0.0.0 — HTTP, 모바일 마이크 불가)"
        )
        self._lan_fallback.toggled.connect(self._save_lan_fallback)
        form.addRow("", self._lan_fallback)
        layout.addLayout(form)

        row = QHBoxLayout()
        self._start_btn = QPushButton("서버 시작")
        self._start_btn.clicked.connect(self._start_server)
        row.addWidget(self._start_btn)
        self._stop_btn = QPushButton("서버 중지")
        self._stop_btn.clicked.connect(self._stop_server)
        row.addWidget(self._stop_btn)
        self._copy_btn = QPushButton("접속 URL 복사")
        self._copy_btn.clicked.connect(self._copy_url)
        row.addWidget(self._copy_btn)
        layout.addLayout(row)

        self._status = QLabel("서버가 중지되어 있습니다.")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setVisible(False)
        layout.addWidget(self._qr_label)
        layout.addStretch()

    def reload(self) -> None:
        self._loading = True
        self._port.setValue(int(self._controller.get_setting("remote.port")))
        self._use_tunnel.setChecked(bool(self._controller.get_setting("remote.use_tunnel")))
        self._lan_fallback.setChecked(bool(self._controller.get_setting("remote.lan_fallback")))
        if self._gateway is not None and not self._gateway.can_use_tunnel():
            self._use_tunnel.setEnabled(False)
            self._use_tunnel.setToolTip("cloudflared가 PATH에 없습니다.")
        self._refresh_status()
        self._loading = False

    def _save_port(self, value: int) -> None:
        if self._loading:
            return
        self._controller.save_setting("remote.port", value)

    def _save_tunnel(self, value: bool) -> None:
        if self._loading:
            return
        self._controller.save_setting("remote.use_tunnel", value)

    def _save_lan_fallback(self, value: bool) -> None:
        if self._loading:
            return
        self._controller.save_setting("remote.lan_fallback", value)

    def _start_server(self) -> None:
        if self._gateway is None:
            QMessageBox.warning(self, "원격 녹음", "게이트웨이 서비스를 사용할 수 없습니다.")
            return
        if self._gateway.is_running:
            self._refresh_status()
            return
        port = int(self._controller.get_setting("remote.port"))
        use_tunnel = bool(self._controller.get_setting("remote.use_tunnel"))
        lan_fallback = bool(self._controller.get_setting("remote.lan_fallback"))
        try:
            info = self._gateway.start(
                port=port,
                use_tunnel=use_tunnel,
                lan_fallback=lan_fallback,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "원격 녹음", str(exc))
            return
        self._show_access(info)
        msg_lines = [f"PWA: {info.pwa_url}", f"PIN: {info.pin}"]
        if info.tunnel_failed:
            msg_lines.append("※ Tunnel 실패 — 모바일 녹음은 HTTPS(Tunnel)가 필요합니다.")
            if info.lan_url:
                msg_lines.append(f"LAN(HTTP): {info.lan_url}/pwa/ — PC 브라우저 테스트용")
        elif not info.mobile_recording_available:
            msg_lines.append("※ Tunnel 미사용 — PC 브라우저(localhost)에서만 녹음 테스트 가능")
        QMessageBox.information(self, "원격 녹음", "\n".join(msg_lines))

    def _stop_server(self) -> None:
        if self._gateway is not None:
            self._gateway.stop()
        self._status.setText("서버가 중지되었습니다.")
        self._qr_label.setVisible(False)
        self._qr_label.clear()
        self._refresh_buttons()

    def _copy_url(self) -> None:
        if self._gateway is None or not self._gateway.is_running:
            QMessageBox.information(self, "원격 녹음", "먼저 서버를 시작하세요.")
            return
        info = self._gateway.access_info
        if info is None:
            return
        from PySide6.QtGui import QGuiApplication

        url = info.public_url or (info.local_url.rstrip("/") + "/pwa/")
        QGuiApplication.clipboard().setText(f"{url}\nPIN: {info.pin}")
        QMessageBox.information(self, "원격 녹음", "접속 URL과 PIN을 클립보드에 복사했습니다.")

    def _refresh_status(self) -> None:
        if self._gateway is None or not self._gateway.is_running:
            self._status.setText("서버가 중지되어 있습니다.")
            self._refresh_buttons()
            return
        info = self._gateway.access_info
        if info is not None:
            self._show_access(info)
        self._refresh_buttons()

    def _show_access(self, info) -> None:
        local_pwa = f"{info.local_url.rstrip('/')}/pwa/"
        lines = [f"로컬 PWA: {local_pwa}", f"PIN: {info.pin}"]
        qr_target: str | None = None
        if info.public_url:
            lines.insert(0, f"공개 URL (HTTPS): {info.public_url}")
            qr_target = info.public_url
        elif info.lan_url:
            lines.insert(
                0,
                f"LAN URL: {info.lan_url.rstrip('/')}/pwa/ (HTTP — 모바일 마이크 불가)",
            )
        if info.tunnel_failed:
            detail = info.tunnel_error or "알 수 없음"
            lines.append(f"※ Tunnel 시작 실패: {detail}")
        elif not info.mobile_recording_available:
            lines.append("※ Tunnel 없음 — 스마트폰 녹음 불가, PC 브라우저 테스트만 가능")
        self._status.setText("\n".join(lines))
        from app.ui.qr_util import make_qr_pixmap

        if qr_target is None:
            self._qr_label.setVisible(False)
            self._qr_label.clear()
            return
        pixmap = make_qr_pixmap(qr_target)
        if pixmap is not None:
            self._qr_label.setPixmap(pixmap)
            self._qr_label.setVisible(True)
        else:
            self._qr_label.setText(
                "QR 표시 불가 — pip install stt-aio[ui] (qrcode, pillow) 설치 후 다시 시도하세요."
            )
            self._qr_label.setVisible(True)

    def _refresh_buttons(self) -> None:
        running = self._gateway is not None and self._gateway.is_running
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._copy_btn.setEnabled(running)
        self._port.setEnabled(not running)


class ModelsSettingsPage(QWidget):
    """Whisper model catalog, download, and Ollama probe (C18)."""

    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._downloading_id: str | None = None

        layout = QVBoxLayout(self)

        path_group = QGroupBox("모델 저장 경로")
        path_form = QFormLayout(path_group)
        self._effective_path = QLabel()
        self._effective_path.setWordWrap(True)
        path_form.addRow("현재 경로", self._effective_path)
        self._default_path = QLabel()
        self._default_path.setWordWrap(True)
        path_form.addRow("기본 경로", self._default_path)
        path_row = QHBoxLayout()
        self._custom_path = QLineEdit()
        self._custom_path.setPlaceholderText("비우면 앱 기본 경로 사용")
        self._custom_path.editingFinished.connect(self._save_custom_path)
        path_row.addWidget(self._custom_path)
        browse = QPushButton("찾아보기")
        browse.clicked.connect(self._browse_custom_path)
        path_row.addWidget(browse)
        clear_path = QPushButton("기본 경로 사용")
        clear_path.clicked.connect(self._clear_custom_path)
        path_row.addWidget(clear_path)
        path_form.addRow("오프라인 경로", path_row)
        layout.addWidget(path_group)

        layout.addWidget(QLabel("Whisper 모델"))
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["ID", "이름", "크기", "설명", "상태", ""])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._progress_label = QLabel()
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)
        self._cancel_btn = QPushButton("다운로드 취소")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_download)
        layout.addWidget(self._cancel_btn)

        active_row = QHBoxLayout()
        self._active_btn = QPushButton("선택 모델을 활성 STT 모델로")
        self._active_btn.clicked.connect(self._set_active)
        active_row.addWidget(self._active_btn)
        self._remove_btn = QPushButton("로컬 설치 삭제")
        self._remove_btn.clicked.connect(self._remove_model)
        active_row.addWidget(self._remove_btn)
        self._repair_btn = QPushButton("손상 설치 정리")
        self._repair_btn.clicked.connect(self._repair_model)
        active_row.addWidget(self._repair_btn)
        refresh_btn = QPushButton("목록 새로고침")
        refresh_btn.clicked.connect(self.reload)
        active_row.addWidget(refresh_btn)
        active_row.addStretch()
        layout.addLayout(active_row)

        ollama_group = QGroupBox("Ollama 모델 (참고)")
        ollama_layout = QVBoxLayout(ollama_group)
        ollama_row = QHBoxLayout()
        self._ollama_btn = QPushButton("Ollama 모델 조회")
        self._ollama_btn.clicked.connect(self._probe_ollama)
        ollama_row.addWidget(self._ollama_btn)
        ollama_row.addStretch()
        ollama_layout.addLayout(ollama_row)
        self._ollama_list = QListWidget()
        ollama_layout.addWidget(self._ollama_list)
        layout.addWidget(ollama_group)

    def reload(self) -> None:
        self._custom_path.setText(self._controller.get_models_custom_path())
        self._effective_path.setText(self._controller.get_models_dir())
        self._default_path.setText(self._controller.get_default_models_dir())
        installed = {m.id: m for m in self._controller.list_whisper_installed()}
        active = self._controller.get_active_whisper_model()
        catalog = self._controller.list_whisper_catalog()

        self._table.setRowCount(len(catalog))
        for row, item in enumerate(catalog):
            inst = installed.get(item.id)
            corrupt_error = self._controller.inspect_whisper_install(item.id)
            if inst is not None:
                status = "내장" if inst.status == "builtin" else "설치됨"
            elif corrupt_error:
                status = "손상 (재다운로드 필요)"
            else:
                status = "미설치"
            if item.id == active:
                status += " · 활성"

            self._table.setItem(row, 0, QTableWidgetItem(item.id))
            self._table.setItem(row, 1, QTableWidgetItem(item.name))
            self._table.setItem(row, 2, QTableWidgetItem(f"~{item.size_mb} MB"))
            self._table.setItem(row, 3, QTableWidgetItem(item.description))
            self._table.setItem(row, 4, QTableWidgetItem(status))

            local_ok = inst is not None and inst.status != "builtin"
            btn_label = "재다운로드" if local_ok else "다운로드"
            btn = QPushButton(btn_label)
            btn.setEnabled(self._downloading_id is None)
            btn.clicked.connect(
                lambda _checked=False, mid=item.id, redo=local_ok: self._download(mid, force=redo)
            )
            self._table.setCellWidget(row, 5, btn)

    def _selected_model_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _save_custom_path(self) -> None:
        result = self._controller.set_models_custom_path(self._custom_path.text().strip())
        if not result.ok:
            QMessageBox.warning(self, "모델 경로", result.message)
            return
        self.reload()

    def _browse_custom_path(self) -> None:
        current = self._custom_path.text().strip()
        start = current if current else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "오프라인 모델 폴더", start)
        if chosen:
            self._custom_path.setText(chosen)
            result = self._controller.set_models_custom_path(chosen)
            if not result.ok:
                QMessageBox.warning(self, "모델 경로", result.message)
                return
            self.reload()

    def _clear_custom_path(self) -> None:
        self._custom_path.clear()
        result = self._controller.set_models_custom_path("")
        if result.ok:
            self.reload()

    def _set_active(self) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            QMessageBox.information(self, "모델", "테이블에서 모델을 선택하세요.")
            return
        if not self._controller.is_whisper_model_available(model_id):
            answer = QMessageBox.question(
                self,
                "모델 미설치",
                f"'{model_id}' 모델이 로컬에 없습니다.\n"
                "내장 faster-whisper 캐시에 의존하거나 런타임 다운로드가 필요할 수 있습니다.\n"
                "그래도 활성 모델로 지정할까요?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        result = self._controller.set_active_whisper_model(model_id)
        if result.ok:
            QMessageBox.information(self, "모델", result.message)
        else:
            QMessageBox.warning(self, "모델", result.message)
        self.reload()

    def _remove_model(self) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            return
        if QMessageBox.question(
            self,
            "삭제",
            f"'{model_id}' 로컬 설치를 삭제할까요?",
        ) != QMessageBox.StandardButton.Yes:
            return
        if self._controller.remove_whisper_model(model_id):
            self.reload()
        else:
            QMessageBox.information(self, "모델", "로컬 설치본이 없습니다.")

    def _repair_model(self) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            QMessageBox.information(self, "모델", "테이블에서 모델을 선택하세요.")
            return
        error = self._controller.inspect_whisper_install(model_id)
        if not error:
            QMessageBox.information(self, "모델", "손상된 로컬 설치가 감지되지 않았습니다.")
            return
        if QMessageBox.question(
            self,
            "손상 설치 정리",
            f"'{model_id}' 폴더를 삭제하고 다시 다운로드할 수 있게 할까요?\n{error}",
        ) != QMessageBox.StandardButton.Yes:
            return
        if self._controller.repair_whisper_install(model_id):
            QMessageBox.information(self, "모델", "손상된 설치를 정리했습니다.")
            self.reload()
        else:
            QMessageBox.warning(self, "모델", "정리할 손상 설치가 없습니다.")

    def _cancel_download(self) -> None:
        if self._downloading_id is None:
            return
        if self._tasks.cancel_whisper_download():
            self._progress_label.setText(f"{self._downloading_id}: 취소 요청 중…")

    def _download(self, model_id: str, *, force: bool = False) -> None:
        if self._downloading_id is not None:
            QMessageBox.information(self, "다운로드", "이미 다운로드가 진행 중입니다.")
            return
        self._downloading_id = model_id
        self._progress.setVisible(True)
        self._progress_label.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._progress.setValue(0)
        self._progress_label.setText(f"{model_id} 다운로드 준비 중…")

        def on_progress(downloaded: int, total: int, state: str) -> None:
            if total > 0:
                self._progress.setMaximum(total)
                self._progress.setValue(min(downloaded, total))
            pct = ""
            if total > 0:
                pct = f" ({100 * downloaded // total}%)"
            self._progress_label.setText(f"{model_id}: {state}{pct} ({downloaded}/{total})")

        def on_finished(_path: str) -> None:
            self._downloading_id = None
            self._progress.setVisible(False)
            self._progress_label.setVisible(False)
            self._cancel_btn.setVisible(False)
            QMessageBox.information(self, "다운로드", f"{model_id} 설치가 완료되었습니다.")
            self.reload()

        def on_failed(message: str) -> None:
            self._downloading_id = None
            self._progress.setVisible(False)
            self._progress_label.setVisible(False)
            self._cancel_btn.setVisible(False)
            if "취소" in message:
                QMessageBox.information(self, "다운로드", message)
            else:
                QMessageBox.warning(self, "다운로드 실패", message)

        self._tasks.run_whisper_download(
            self._controller,
            model_id,
            on_progress=on_progress,
            on_finished=on_finished,
            on_failed=on_failed,
            force=force,
        )

    def _probe_ollama(self) -> None:
        self._ollama_btn.setEnabled(False)
        self._ollama_list.clear()
        self._ollama_list.addItem("조회 중…")

        def on_finished(models) -> None:
            self._ollama_btn.setEnabled(True)
            self._ollama_list.clear()
            if not models:
                self._ollama_list.addItem("모델 없음 또는 Ollama 미연결")
                return
            for model in models:
                size = ""
                if model.size_bytes:
                    size_mb = model.size_bytes // (1024 * 1024)
                    size = f" · {size_mb} MB"
                self._ollama_list.addItem(f"{model.name}{size}")

        def on_failed(message: str) -> None:
            self._ollama_btn.setEnabled(True)
            self._ollama_list.clear()
            self._ollama_list.addItem(f"오류: {message}")

        self._tasks.run_ollama_models_probe(
            self._controller,
            on_finished=on_finished,
            on_failed=on_failed,
        )
