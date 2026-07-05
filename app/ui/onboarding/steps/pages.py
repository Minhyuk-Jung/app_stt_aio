"""Individual onboarding wizard pages (C21 §6.1)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWizardPage,
)

from app.ui.onboarding.checks import INJECTION_SAMPLE_TEXT, RECOMMENDED_WHISPER_MODEL
from app.ui.settings.controller import SettingsController
from app.ui.settings.workers import SettingsTaskRunner
from core.secrets import LLM_API_KEY_SECRET

if TYPE_CHECKING:
    from app.ui.onboarding.onboarding_wizard import OnboardingWizard


def _set_combo_value(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentText(value)


def _is_skipping(page: QWizardPage) -> bool:
    wizard = page.wizard()
    if wizard is not None and hasattr(wizard, "is_skipping"):
        return wizard.is_skipping()
    return False


def _injection_failure_hint(error: str | None) -> str:
    text = (error or "").lower()
    if "foreground" in text or "window" in text or "창" in (error or ""):
        return (
            "활성 입력 창이 없거나 관리자 권한 앱에는 주입할 수 없습니다. "
            "일반 앱의 입력란을 클릭한 뒤 다시 시도하세요."
        )
    if "clipboard" in text or "클립보드" in (error or ""):
        return "클립보드가 다른 앱에 의해 잠겨 있을 수 있습니다. 잠시 후 다시 시도하세요."
    if "platform" in text or "windows" in text:
        return "텍스트 주입은 Windows에서만 지원됩니다."
    return (
        "설정 > 일반 > 텍스트 주입에서 유니코드/클립보드 방식을 바꿔 보세요. "
        "문제가 계속되면 설정 화면에서 다시 테스트할 수 있습니다."
    )


class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("STT-AIO에 오신 것을 환영합니다")
        self.setSubTitle(
            "음성 받아쓰기를 사용하기 전에 Provider, 모델, 마이크, "
            "텍스트 주입, 단축키를 간단히 설정합니다.\n"
            "각 단계는 건너뛸 수 있으며, 나중에 설정 화면에서 다시 변경할 수 있습니다."
        )
        layout = QVBoxLayout(self)
        note = QLabel(
            "• 로컬 우선: Whisper + Ollama (기본)\n"
            "• 클라우드: OpenAI 호환 API 사용 시 키가 필요합니다\n"
            "• Whisper 모델은 첫 사용 시 다운로드될 수 있습니다"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()


class ProviderPage(QWizardPage):
    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self.setTitle("LLM Provider 선택")
        self.setSubTitle("교정·리포트에 사용할 LLM Provider를 선택하세요.")

        layout = QVBoxLayout(self)
        group = QButtonGroup(self)
        self._local = QRadioButton("로컬 우선 (Ollama)")
        self._cloud = QRadioButton("클라우드 (OpenAI 호환 API)")
        group.addButton(self._local)
        group.addButton(self._cloud)
        layout.addWidget(self._local)
        layout.addWidget(self._cloud)

        self._cloud_notice = QLabel(
            "클라우드 선택 시 음성·텍스트가 선택한 API 서버로 전송될 수 있습니다."
        )
        self._cloud_notice.setWordWrap(True)
        self._cloud_notice.setVisible(False)
        layout.addWidget(self._cloud_notice)

        form = QFormLayout()
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("sk-…")
        form.addRow("API 키", self._api_key)
        self._key_hint = QLabel()
        self._key_hint.setWordWrap(True)
        form.addRow("키 상태", self._key_hint)
        self._base_url = QLineEdit()
        form.addRow("Base URL", self._base_url)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("연결 테스트")
        self._test_btn.clicked.connect(self._run_test)
        btn_row.addWidget(self._test_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

        self._local.toggled.connect(self._on_mode_changed)
        self._cloud.toggled.connect(self._on_mode_changed)
        self._connection_tested = False

    def connection_tested(self) -> bool:
        return self._connection_tested

    def initializePage(self) -> None:
        provider = str(self._controller.get_setting("llm.provider"))
        if provider == "openai_compat":
            self._cloud.setChecked(True)
        else:
            self._local.setChecked(True)
        self._base_url.setText(str(self._controller.get_setting("llm.base_url")))
        self._api_key.clear()
        self._key_hint.setText(self._controller.get_api_key_hint() or "미설정")
        self._status.clear()
        self._connection_tested = False
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        cloud = self._cloud.isChecked()
        self._cloud_notice.setVisible(cloud)
        self._api_key.setEnabled(cloud)
        self._base_url.setEnabled(cloud)
        self._test_btn.setEnabled(True)

    def validatePage(self) -> bool:
        if self._local.isChecked():
            self._controller.save_setting("llm.provider", "ollama")
            return True
        self._controller.save_setting("llm.provider", "openai_compat")
        self._controller.save_setting("llm.base_url", self._base_url.text().strip())
        key = self._api_key.text().strip()
        if key:
            self._controller.set_api_key(LLM_API_KEY_SECRET, key)
            self._key_hint.setText(self._controller.get_api_key_hint())
        return True

    def _selected_provider(self) -> str:
        return "openai_compat" if self._cloud.isChecked() else "ollama"

    def _run_test(self) -> None:
        if not self.validatePage():
            return
        self._test_btn.setEnabled(False)
        self._status.setText("연결 테스트 중…")
        provider = self._selected_provider()

        def on_finished(result) -> None:
            self._test_btn.setEnabled(True)
            text = self._controller.format_connection_result(result)
            if result.success:
                self._connection_tested = True
            if not result.success:
                text += "\n나중에 설정 > LLM에서 다시 시도할 수 있습니다."
            self._status.setText(text)

        def on_failed(message: str) -> None:
            self._test_btn.setEnabled(True)
            self._status.setText(f"오류: {message}\n나중에 설정에서 다시 시도할 수 있습니다.")

        self._tasks.run_llm_test(
            self._controller,
            provider,
            on_finished=on_finished,
            on_failed=on_failed,
        )


class ModelPage(QWizardPage):
    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self.setTitle("Whisper STT 모델")
        self.setSubTitle(
            f"권장 모델: {RECOMMENDED_WHISPER_MODEL} (균형). "
            "다운로드하지 않아도 내장 캐시에 의존할 수 있습니다."
        )

        layout = QVBoxLayout(self)
        self._info = QLabel()
        self._info.setWordWrap(True)
        layout.addWidget(self._info)

        path_row = QHBoxLayout()
        self._custom_path = QLineEdit()
        self._custom_path.setPlaceholderText("오프라인 모델 폴더 (선택)")
        path_row.addWidget(self._custom_path)
        browse = QPushButton("찾아보기")
        browse.clicked.connect(self._browse_path)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        btn_row = QHBoxLayout()
        self._download_btn = QPushButton(f"'{RECOMMENDED_WHISPER_MODEL}' 다운로드")
        self._download_btn.clicked.connect(self._download_recommended)
        btn_row.addWidget(self._download_btn)
        self._retry_btn = QPushButton("다운로드 재시도")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self._download_recommended)
        btn_row.addWidget(self._retry_btn)
        self._check_btn = QPushButton("준비 상태 확인")
        self._check_btn.clicked.connect(self._check_readiness)
        btn_row.addWidget(self._check_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._progress_label = QLabel()
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def initializePage(self) -> None:
        self._custom_path.setText(self._controller.get_models_custom_path())
        self._progress.setVisible(False)
        self._progress_label.setVisible(False)
        self._retry_btn.setVisible(False)
        self._refresh_info()

    def _refresh_info(self) -> None:
        active = self._controller.get_active_whisper_model()
        installed = self._controller.is_whisper_model_available(RECOMMENDED_WHISPER_MODEL)
        self._info.setText(
            f"활성 STT 모델: {active}\n"
            f"권장 모델({RECOMMENDED_WHISPER_MODEL}) 로컬 설치: "
            f"{'예' if installed else '아니오'}\n"
            f"모델 경로: {self._controller.get_models_dir()}"
        )

    def validatePage(self) -> bool:
        if _is_skipping(self):
            return True
        path = self._custom_path.text().strip()
        if path:
            result = self._controller.set_models_custom_path(path)
            if not result.ok:
                self._status.setText(
                    f"{result.message}\n경로는 저장되지 않았습니다. 다음으로 진행할 수 있습니다."
                )
        active = self._controller.get_active_whisper_model() or RECOMMENDED_WHISPER_MODEL
        self._controller.set_active_whisper_model(active)
        return True

    def _browse_path(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        current = self._custom_path.text().strip()
        start = current if current else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "오프라인 모델 폴더", start)
        if chosen:
            self._custom_path.setText(chosen)

    def _check_readiness(self) -> None:
        self._check_btn.setEnabled(False)
        self._status.setText("확인 중…")

        def on_finished(result) -> None:
            self._check_btn.setEnabled(True)
            prefix = "✓" if result.ok else "✗"
            self._status.setText(f"{prefix} {result.message}")
            self._refresh_info()

        def on_failed(message: str) -> None:
            self._check_btn.setEnabled(True)
            self._status.setText(f"오류: {message}")

        self._tasks.run_stt_readiness(self._controller, on_finished=on_finished, on_failed=on_failed)

    def _download_recommended(self) -> None:
        self._download_btn.setEnabled(False)
        self._retry_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress_label.setVisible(True)
        self._progress.setRange(0, 0)

        def on_progress(downloaded: int, total: int, state: str) -> None:
            if total > 0:
                self._progress.setRange(0, total)
                self._progress.setValue(downloaded)
            self._progress_label.setText(state)

        def on_finished(_path: str) -> None:
            self._download_btn.setEnabled(True)
            self._retry_btn.setVisible(False)
            self._progress.setVisible(False)
            self._progress_label.setVisible(False)
            self._controller.set_active_whisper_model(RECOMMENDED_WHISPER_MODEL)
            self._status.setText(f"다운로드 완료. 활성 모델: {RECOMMENDED_WHISPER_MODEL}")
            self._refresh_info()

        def on_failed(message: str) -> None:
            self._download_btn.setEnabled(True)
            self._retry_btn.setVisible(True)
            self._retry_btn.setEnabled(True)
            self._progress.setVisible(False)
            self._progress_label.setVisible(False)
            self._status.setText(
                f"다운로드 실패: {message}\n"
                "재시도하거나 설정 > 모델에서 나중에 다운로드할 수 있습니다."
            )

        self._tasks.run_whisper_download(
            self._controller,
            RECOMMENDED_WHISPER_MODEL,
            on_progress=on_progress,
            on_finished=on_finished,
            on_failed=on_failed,
        )


class MicPage(QWizardPage):
    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._mic_tested = False
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(80)
        self._live_timer.timeout.connect(self._poll_live_level)
        self._live_peak = 0.0
        self.setTitle("마이크 테스트")
        self.setSubTitle("사용할 마이크를 선택하고 짧게 녹음해 입력 레벨을 확인합니다.")

        layout = QVBoxLayout(self)
        perm = QLabel(
            "Windows 설정 > 개인 정보 > 마이크에서 이 앱의 마이크 접근을 허용해야 합니다."
        )
        perm.setWordWrap(True)
        layout.addWidget(perm)

        form = QFormLayout()
        self._device = QComboBox()
        form.addRow("마이크", self._device)
        layout.addLayout(form)

        self._level = QProgressBar()
        self._level.setRange(0, 100)
        self._level.setValue(0)
        self._level.setTextVisible(False)
        layout.addWidget(self._level)

        self._test_btn = QPushButton("마이크 테스트 (약 1초)")
        self._test_btn.clicked.connect(self._run_test)
        layout.addWidget(self._test_btn)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def mic_tested(self) -> bool:
        return self._mic_tested

    def initializePage(self) -> None:
        self._mic_tested = False
        self._device.clear()
        for opt in self._controller.list_audio_devices():
            self._device.addItem(opt.label, opt.device_id)
        current = str(self._controller.get_setting("audio.device_id"))
        _set_combo_value(self._device, current)
        self._level.setValue(0)
        self._status.clear()

    def validatePage(self) -> bool:
        self._controller.save_setting("audio.device_id", self._device.currentData())
        return True

    def _run_test(self) -> None:
        device_id = str(self._device.currentData() or "")
        self._controller.save_setting("audio.device_id", device_id)
        self._test_btn.setEnabled(False)
        self._level.setValue(0)
        self._status.setText("녹음 중… 마이크에 말해 보세요.")
        self._live_peak = 0.0
        self._live_timer.start()

        def on_finished(result) -> None:
            self._live_timer.stop()
            self._test_btn.setEnabled(True)
            prefix = "✓" if result.ok else "✗"
            self._status.setText(f"{prefix} {result.message}")
            if result.ok:
                self._mic_tested = True
            if result.ok and "peak=" in result.message:
                try:
                    peak_text = result.message.split("peak=")[1].rstrip(")")
                    peak = float(peak_text.replace("%", "")) / 100.0
                    self._level.setValue(min(100, int(peak * 100)))
                except (IndexError, ValueError):
                    self._level.setValue(50)

        def on_failed(message: str) -> None:
            self._live_timer.stop()
            self._test_btn.setEnabled(True)
            self._status.setText(f"오류: {message}")

        def on_level(peak: float, _rms: float) -> None:
            self._live_peak = max(self._live_peak, peak)
            self._level.setValue(min(100, int(peak * 100)))

        self._tasks.run_mic_probe(
            self._controller,
            device_id,
            on_finished=on_finished,
            on_failed=on_failed,
            on_level=on_level,
        )

    def _poll_live_level(self) -> None:
        self._level.setValue(min(100, int(self._live_peak * 100)))


class InjectionPage(QWizardPage):
    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._injection_verified = False
        self.setTitle("한글 주입 테스트")
        self.setSubTitle(
            "아래 입력란을 클릭한 뒤 '샘플 주입'을 누르세요. "
            "한글이 정상 입력되면 Windows 주입이 준비된 것입니다."
        )

        layout = QVBoxLayout(self)
        self._field = QLineEdit()
        self._field.setPlaceholderText("여기를 클릭한 뒤 샘플 주입")
        self._field.textChanged.connect(self._on_field_changed)
        layout.addWidget(self._field)

        self._inject_btn = QPushButton("샘플 한글 주입")
        self._inject_btn.clicked.connect(self._inject_sample)
        layout.addWidget(self._inject_btn)

        self._confirmed = QCheckBox("한글이 정상적으로 입력되었습니다")
        self._confirmed.toggled.connect(self._on_confirmed)
        layout.addWidget(self._confirmed)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        hint = QLabel(
            "주입 실패 시: (1) 입력란 포커스 확인 (2) 관리자 권한 앱 회피 "
            "(3) 설정에서 유니코드/클립보드 방식 변경"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def injection_verified(self) -> bool:
        return self._injection_verified or self._confirmed.isChecked()

    def _on_field_changed(self) -> None:
        if INJECTION_SAMPLE_TEXT in self._field.text():
            self._injection_verified = True

    def _on_confirmed(self, checked: bool) -> None:
        if checked:
            self._injection_verified = True

    def _verify_field_text(self) -> None:
        if INJECTION_SAMPLE_TEXT in self._field.text():
            self._injection_verified = True
            self._confirmed.setChecked(True)

    def _inject_sample(self) -> None:
        self._field.clear()
        self._field.setFocus(Qt.FocusReason.OtherFocusReason)
        self._inject_btn.setEnabled(False)
        self._status.setText("주입 중…")

        def on_finished(result) -> None:
            self._inject_btn.setEnabled(True)
            if result.success:
                QTimer.singleShot(80, self._verify_field_text)
                self._status.setText(
                    f"주입 완료 ({result.method_used.value}, {result.chars_injected}자). "
                    "입력란에 한글이 보이는지 확인하세요."
                )
            else:
                from core.diagnostics import report_error

                report_error(
                    result.error or "injection failed",
                    context={"component": "onboarding", "stage": "injection"},
                    log=False,
                )
                self._status.setText(
                    f"주입 실패: {result.error or '알 수 없는 오류'}\n"
                    f"{_injection_failure_hint(result.error)}"
                )

        def on_failed(message: str) -> None:
            self._inject_btn.setEnabled(True)
            self._status.setText(f"주입 오류: {message}")

        self._tasks.run_injection_test(
            self._controller,
            INJECTION_SAMPLE_TEXT,
            on_finished=on_finished,
            on_failed=on_failed,
        )

    def validatePage(self) -> bool:
        return True


class HotkeyPage(QWizardPage):
    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setTitle("단축키 설정")
        self.setSubTitle("녹음·취소 단축키를 지정합니다. 충돌 시 앱 시작 시 폴백이 적용됩니다.")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._mode = QComboBox()
        for choice in controller.get_choice_keys("hotkey.mode"):
            self._mode.addItem(choice, choice)
        form.addRow("동작 방식", self._mode)
        self._record = QLineEdit()
        form.addRow("녹음", self._record)
        self._cancel = QLineEdit()
        form.addRow("취소", self._cancel)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        check_btn = QPushButton("충돌 확인")
        check_btn.clicked.connect(self._check_conflicts)
        btn_row.addWidget(check_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def initializePage(self) -> None:
        _set_combo_value(self._mode, str(self._controller.get_setting("hotkey.mode")))
        self._record.setText(str(self._controller.get_setting("hotkey.record_binding")))
        self._cancel.setText(str(self._controller.get_setting("hotkey.cancel_binding")))
        self._status.clear()

    def _check_conflicts(self) -> None:
        record = self._record.text().strip()
        cancel = self._cancel.text().strip()
        messages: list[str] = []
        for label, binding in (("녹음", record), ("취소", cancel)):
            result = self._controller.validate_hotkey_binding(binding)
            if result.ok:
                messages.append(f"{label}: 사용 가능")
            else:
                messages.append(f"{label}: {result.message}")
                if self._controller._hotkey is not None:
                    fallback = self._controller._hotkey.suggest_fallback(binding)
                    if fallback:
                        messages.append(f"  → 제안: {fallback}")
        pair = self._controller.validate_hotkey_pair(record, cancel)
        if pair is not None:
            messages.append(pair.message)
        self._status.setText("\n".join(messages))

    def validatePage(self) -> bool:
        if _is_skipping(self):
            return True
        self._controller.save_setting("hotkey.mode", self._mode.currentData())
        result = self._controller.set_hotkey(
            self._record.text().strip(),
            self._cancel.text().strip(),
            strict=False,
        )
        if result.ok:
            self._status.setText(result.message)
        else:
            self._status.setText(f"{result.message}\n다음으로 진행할 수 있습니다.")
        return True


class DonePage(QWizardPage):
    def __init__(self, controller: SettingsController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setTitle("설정 완료")
        self.setSubTitle("아래 항목을 확인한 뒤 '마침'을 누르세요.")

        layout = QVBoxLayout(self)
        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        layout.addWidget(self._summary)

    def initializePage(self) -> None:
        from app.ui.onboarding.checks import summarize_readiness

        injection_ok = False
        mic_ok = False
        connection_ok = False
        wizard = self.wizard()
        if wizard is not None:
            for page_id in wizard.pageIds():
                page = wizard.page(page_id)
                if isinstance(page, InjectionPage):
                    injection_ok = page.injection_verified()
                elif isinstance(page, MicPage):
                    mic_ok = page.mic_tested()
                elif isinstance(page, ProviderPage):
                    connection_ok = page.connection_tested()

        checks = summarize_readiness(
            self._controller.config,
            self._controller,
            injection_verified=injection_ok,
            mic_tested=mic_ok,
            connection_tested=connection_ok,
        )
        lines = []
        for name, check in checks.items():
            mark = "✓" if check.ok else "○"
            lines.append(f"{mark} {name}: {check.message}")
        incomplete = [name for name, check in checks.items() if not check.ok]
        if incomplete:
            lines.append("")
            lines.append(
                f"미완료({', '.join(incomplete)}) 항목은 설정 화면에서 완료할 수 있습니다."
            )
        if not injection_ok:
            lines.insert(0, "⚠ 한글 주입 테스트가 확인되지 않았습니다. 실사용 전 반드시 검증하세요.\n")
        lines.append("")
        lines.append("설정 화면에서 언제든지 변경할 수 있습니다.")
        self._summary.setPlainText("\n".join(lines))
