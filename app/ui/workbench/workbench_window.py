"""Workbench main window (C13 P2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.workbench.controller import DEFAULT_PAGE_SIZE
from app.ui.workbench.labels import (
    SESSION_SOURCE_LABELS,
    format_session_status,
)
from core.export import ExportTarget
from core.export.naming import ensure_unique_path
from core.store.models import SessionStatus

if TYPE_CHECKING:
    from app.ui.workbench.controller import WorkbenchController


_STATUS_FILTER_OPTIONS: list[tuple[str, SessionStatus | None]] = [
    ("전체", None),
    ("완료", SessionStatus.DONE),
    ("처리 중", SessionStatus.PROCESSING),
    ("녹음 중", SessionStatus.RECORDING),
    ("오류", SessionStatus.ERROR),
    ("취소", SessionStatus.CANCELED),
]

_ACTIVE_STATUSES = frozenset({SessionStatus.RECORDING, SessionStatus.PROCESSING})


class _StageTab(QWidget):
    def __init__(
        self,
        stage: int,
        controller: WorkbenchController,
        *,
        get_docx_template,
        confirm_overwrite,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._stage = stage
        self._controller = controller
        self._get_docx_template = get_docx_template
        self._confirm_overwrite = confirm_overwrite
        self._session_id: str | None = None
        self._artifact_id: str | None = None
        self._saved_text = ""
        self._dirty = False

        layout = QVBoxLayout(self)
        self._meta = QLabel("산출물 없음")
        self._meta.setWordWrap(True)
        layout.addWidget(self._meta)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText(f"{stage}차 산출물이 없습니다.")
        self._editor.setReadOnly(True)
        self._editor.textChanged.connect(self._mark_dirty)
        layout.addWidget(self._editor)

        btn_row = QHBoxLayout()
        self._edit_btn = QPushButton("편집")
        self._edit_btn.clicked.connect(self._toggle_edit)
        btn_row.addWidget(self._edit_btn)
        self._save_btn = QPushButton("저장")
        self._save_btn.clicked.connect(self._save)
        self._save_btn.setEnabled(False)
        btn_row.addWidget(self._save_btn)
        txt_btn = QPushButton("txt보내기")
        txt_btn.clicked.connect(lambda: self._export("txt"))
        btn_row.addWidget(txt_btn)
        md_btn = QPushButton("md보내기")
        md_btn.clicked.connect(lambda: self._export("md"))
        btn_row.addWidget(md_btn)
        docx_btn = QPushButton("docx보내기")
        docx_btn.clicked.connect(lambda: self._export("docx"))
        btn_row.addWidget(docx_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def current_text(self) -> str:
        return self._editor.toPlainText()

    def load(self, session_id: str | None, artifact) -> None:
        self._session_id = session_id
        self._artifact_id = None
        self._saved_text = ""
        self._dirty = False
        self._editor.setReadOnly(True)
        self._edit_btn.setText("편집")
        self._save_btn.setEnabled(False)
        if artifact is None or session_id is None:
            self._editor.clear()
            self._meta.setText("산출물 없음")
            return
        self._artifact_id = artifact.id
        self._saved_text = artifact.text
        self._editor.setPlainText(artifact.text)
        provider = artifact.provider or "—"
        created = artifact.created_at.strftime("%Y-%m-%d %H:%M")
        meta = f"provider: {provider} · 저장: {created}"
        if artifact.prompt_snapshot:
            prompt = artifact.prompt_snapshot.replace("\n", " ").strip()
            if len(prompt) > 60:
                prompt = prompt[:57] + "..."
            meta += f"\nprompt: {prompt}"
        self._meta.setText(meta)

    def _mark_dirty(self) -> None:
        if not self._editor.isReadOnly():
            self._dirty = True

    def _toggle_edit(self) -> None:
        if self._artifact_id is None:
            return
        if self._editor.isReadOnly():
            self._editor.setReadOnly(False)
            self._edit_btn.setText("읽기 전용")
            self._save_btn.setEnabled(True)
            return
        if self._dirty:
            answer = QMessageBox.question(
                self,
                "저장되지 않은 변경",
                "저장하지 않고 읽기 전용으로 전환하면 편집 내용이 사라집니다. 계속하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
            self._editor.setPlainText(self._saved_text)
            self._dirty = False
        self._editor.setReadOnly(True)
        self._edit_btn.setText("편집")
        self._save_btn.setEnabled(False)

    def _save(self) -> None:
        if self._artifact_id is None:
            return
        text = self._editor.toPlainText()
        updated = self._controller.update_artifact_text(self._artifact_id, text)
        if updated is None:
            QMessageBox.warning(self, "저장", "산출물 저장에 실패했습니다.")
            return
        self._saved_text = text
        self._dirty = False
        self._editor.setReadOnly(True)
        self._edit_btn.setText("편집")
        self._save_btn.setEnabled(False)
        QMessageBox.information(self, "저장", f"{self._stage}차 산출물을 저장했습니다.")

    def _export(self, export_format: str) -> None:
        session_id = self._session_id
        if session_id is None or self._artifact_id is None:
            QMessageBox.information(self, "보내기", "보낼 산출물이 없습니다.")
            return
        default_path = str(
            self._controller.resolve_default_export_path(
                session_id,
                self._stage,
                export_format=export_format,
            )
        )
        if export_format == "md":
            caption = "md보내기"
            file_filter = "Markdown Files (*.md)"
        elif export_format == "docx":
            caption = "docx보내기"
            file_filter = "Word Documents (*.docx)"
        else:
            caption = "txt보내기"
            file_filter = "Text Files (*.txt)"
        dest, _filter = QFileDialog.getSaveFileName(
            self,
            caption,
            default_path,
            file_filter,
        )
        if not dest:
            return
        from pathlib import Path

        dest_path = Path(dest)
        if dest_path.exists():
            dest_path = ensure_unique_path(dest_path)
        dest = str(dest_path)
        if not self._confirm_overwrite(dest):
            return
        text_override = self.current_text() if self._dirty else None
        template = self._get_docx_template() if export_format == "docx" else None
        result = self._controller.request_export(
            session_id,
            self._stage,
            dest,
            export_format=export_format,
            text_override=text_override,
            template=template,
        )
        if result.success:
            QMessageBox.information(self, "보내기", f"저장됨: {result.path}")
        else:
            message = result.error or "보내기 실패"
            if result.suggestion:
                message = f"{message}\n\n{result.suggestion}"
            QMessageBox.warning(self, "보내기", message)


class WorkbenchWindow(QDialog):
    """Session history and stage artifact viewer (C13 P2)."""

    def __init__(self, controller: WorkbenchController, *, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._session_id: str | None = None
        self._all_summaries = []
        self._page_offset = 0
        self._block_selection = False

        self.setWindowTitle("STT-AIO 작업대")
        self.setMinimumSize(900, 560)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("세션 ID·모드·본문 검색 (전체 DB)")
        self._search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search)
        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(lambda: self.reload(preserve_selection=True))
        search_row.addWidget(refresh_btn)
        left_layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("상태"))
        self._status_filter = QComboBox()
        for label, _status in _STATUS_FILTER_OPTIONS:
            self._status_filter.addItem(label)
        self._status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._status_filter)
        filter_row.addWidget(QLabel("모드"))
        self._mode_filter = QComboBox()
        self._mode_filter.addItem("전체", None)
        for mode_id, mode_name in controller.list_enabled_modes():
            self._mode_filter.addItem(mode_name, mode_id)
        self._mode_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._mode_filter)
        filter_row.addStretch()
        left_layout.addLayout(filter_row)

        self._empty_label = QLabel("세션 기록이 없습니다.\n받아쓰기를 실행하면 여기에 표시됩니다.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.hide()
        left_layout.addWidget(self._empty_label)

        self._session_list = QListWidget()
        self._session_list.currentItemChanged.connect(self._on_session_selected)
        left_layout.addWidget(self._session_list)

        page_row = QHBoxLayout()
        self._prev_page_btn = QPushButton("이전")
        self._prev_page_btn.clicked.connect(self._prev_page)
        page_row.addWidget(self._prev_page_btn)
        self._page_label = QLabel()
        page_row.addWidget(self._page_label)
        self._next_page_btn = QPushButton("다음")
        self._next_page_btn.clicked.connect(self._next_page)
        page_row.addWidget(self._next_page_btn)
        page_row.addStretch()
        self._session_count = QLabel()
        page_row.addWidget(self._session_count)
        left_layout.addLayout(page_row)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        header_row = QHBoxLayout()
        self._session_header = QLabel("세션을 선택하세요")
        self._session_header.setWordWrap(True)
        header_row.addWidget(self._session_header, stretch=1)
        self._copy_id_btn = QPushButton("ID 복사")
        self._copy_id_btn.setEnabled(False)
        self._copy_id_btn.clicked.connect(self._copy_session_id)
        header_row.addWidget(self._copy_id_btn)
        self._export_all_btn = QPushButton("전체 md보내기")
        self._export_all_btn.clicked.connect(lambda: self._export_all_stages("md"))
        header_row.addWidget(self._export_all_btn)
        self._export_all_docx_btn = QPushButton("전체 docx보내기")
        self._export_all_docx_btn.clicked.connect(lambda: self._export_all_stages("docx"))
        header_row.addWidget(self._export_all_docx_btn)
        right_layout.addLayout(header_row)

        filter_row_docx = QHBoxLayout()
        filter_row_docx.addWidget(QLabel("docx 템플릿"))
        self._docx_template = QComboBox()
        for template_id, template_name in controller.list_export_templates("docx"):
            self._docx_template.addItem(template_name, template_id)
        filter_row_docx.addWidget(self._docx_template)
        filter_row_docx.addStretch()
        right_layout.addLayout(filter_row_docx)

        self._tabs = QTabWidget()
        self._stage_tabs: dict[int, _StageTab] = {}
        for stage in (1, 2, 3):
            tab = _StageTab(
                stage,
                controller,
                get_docx_template=self._current_docx_template,
                confirm_overwrite=self._confirm_overwrite,
            )
            self._stage_tabs[stage] = tab
            self._tabs.addTab(tab, f"{stage}차")
        right_layout.addWidget(self._tabs)

        reprocess_row = QHBoxLayout()
        self._reprocess_from = QComboBox()
        self._reprocess_from.addItem("2차부터", 2)
        self._reprocess_from.addItem("3차부터", 3)
        reprocess_row.addWidget(QLabel("재가공:"))
        reprocess_row.addWidget(self._reprocess_from)
        self._reprocess_btn = QPushButton("재가공 실행")
        self._reprocess_btn.clicked.connect(self._run_reprocess)
        reprocess_row.addWidget(self._reprocess_btn)
        reprocess_row.addStretch()
        right_layout.addLayout(reprocess_row)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self._try_close)
        layout.addWidget(buttons)

    def reload(self, *, preserve_selection: bool = False) -> None:
        selected_id = self._session_id if preserve_selection else None
        status = self._current_status_filter()
        mode_id = self._current_mode_filter()
        query = self._search.text().strip()
        self._all_summaries = self._controller.list_sessions(
            limit=DEFAULT_PAGE_SIZE,
            offset=self._page_offset,
            status=status,
            mode_id=mode_id,
            query=query or None,
        )
        self._update_pagination_controls(status, mode_id, query)
        self._render_session_list()
        target_id = selected_id or self._controller.get_focus_session_id()
        if target_id:
            self._select_session_by_id(target_id)

    def refresh_if_viewing(self, session_id: str) -> None:
        """Refresh list and detail when a known session changes."""
        self.reload(preserve_selection=True)
        if self._session_id != session_id:
            return
        if any(tab.dirty for tab in self._stage_tabs.values()):
            return
        self._load_session(session_id)

    def refresh_after_stage(self, session_id: str, stage: int) -> None:
        self.reload(preserve_selection=True)
        if self._session_id != session_id:
            return
        if any(tab.dirty for tab in self._stage_tabs.values()):
            return
        self._load_session(session_id, focus_stage=stage)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_docx_template_from_config()
        self.reload()

    def _sync_docx_template_from_config(self) -> None:
        template_id = self._controller.default_docx_template()
        index = self._docx_template.findData(template_id)
        if index >= 0:
            self._docx_template.setCurrentIndex(index)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def _try_close(self) -> None:
        if self._confirm_discard():
            self.close()

    def _confirm_discard(self) -> bool:
        if not any(tab.dirty for tab in self._stage_tabs.values()):
            return True
        answer = QMessageBox.question(
            self,
            "저장되지 않은 변경",
            "저장하지 않은 편집 내용이 있습니다. 닫으시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer is QMessageBox.StandardButton.Yes

    def _current_status_filter(self) -> SessionStatus | None:
        index = self._status_filter.currentIndex()
        if index < 0 or index >= len(_STATUS_FILTER_OPTIONS):
            return None
        return _STATUS_FILTER_OPTIONS[index][1]

    def _current_mode_filter(self) -> str | None:
        return self._mode_filter.currentData()

    def _on_search_changed(self) -> None:
        self._page_offset = 0
        self.reload(preserve_selection=True)

    def _on_filter_changed(self) -> None:
        self._page_offset = 0
        self.reload(preserve_selection=True)

    def _prev_page(self) -> None:
        if self._page_offset <= 0:
            return
        self._page_offset = max(0, self._page_offset - DEFAULT_PAGE_SIZE)
        self.reload(preserve_selection=True)

    def _next_page(self) -> None:
        status = self._current_status_filter()
        mode_id = self._current_mode_filter()
        query = self._search.text().strip()
        total = self._controller.count_sessions(
            status=status,
            mode_id=mode_id,
            query=query or None,
        )
        if self._page_offset + DEFAULT_PAGE_SIZE >= total:
            return
        self._page_offset += DEFAULT_PAGE_SIZE
        self.reload(preserve_selection=True)

    def _update_pagination_controls(
        self,
        status: SessionStatus | None,
        mode_id: str | None,
        query: str,
    ) -> None:
        total = self._controller.count_sessions(
            status=status,
            mode_id=mode_id,
            query=query or None,
        )
        page = self._page_offset // DEFAULT_PAGE_SIZE + 1
        page_count = max(1, (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE)
        self._page_label.setText(f"{page} / {page_count}")
        self._prev_page_btn.setEnabled(self._page_offset > 0)
        self._next_page_btn.setEnabled(self._page_offset + DEFAULT_PAGE_SIZE < total)

    def _render_session_list(self) -> None:
        self._session_list.clear()
        shown = 0
        for summary in self._all_summaries:
            status_label = format_session_status(summary.status)
            label = (
                f"{summary.created_at.strftime('%m-%d %H:%M')} · "
                f"{summary.mode_name} · {status_label}\n"
                f"{summary.preview_text}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, summary.id)
            if summary.status in _ACTIVE_STATUSES:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._session_list.addItem(item)
            shown += 1

        status = self._current_status_filter()
        mode_id = self._current_mode_filter()
        query = self._search.text().strip()
        total = self._controller.count_sessions(
            status=status,
            mode_id=mode_id,
            query=query or None,
        )
        self._session_count.setText(f"표시 {shown} / 전체 {total}")
        is_empty = total == 0
        self._empty_label.setVisible(is_empty)
        self._session_list.setVisible(not is_empty)

    def _on_session_selected(self, current: QListWidgetItem | None, previous) -> None:
        if self._block_selection:
            return
        if previous is not None and any(tab.dirty for tab in self._stage_tabs.values()):
            if not self._confirm_discard():
                self._block_selection = True
                self._session_list.setCurrentItem(previous)
                self._block_selection = False
                return
            for tab in self._stage_tabs.values():
                tab.clear_dirty()
        if current is None:
            self._session_id = None
            self._copy_id_btn.setEnabled(False)
            return
        session_id = str(current.data(Qt.ItemDataRole.UserRole))
        self._load_session(session_id)

    def _select_session_by_id(self, session_id: str) -> None:
        for row in range(self._session_list.count()):
            item = self._session_list.item(row)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole)) == session_id:
                self._block_selection = True
                self._session_list.setCurrentRow(row)
                self._block_selection = False
                return

    def _load_session(self, session_id: str, *, focus_stage: int | None = None) -> None:
        self._session_id = session_id
        detail = self._controller.get_session_detail(session_id)
        if detail is None:
            self._session_header.setText("세션을 찾을 수 없습니다.")
            self._export_all_btn.setEnabled(False)
            self._export_all_docx_btn.setEnabled(False)
            self._copy_id_btn.setEnabled(False)
            return
        session = detail.session
        source_label = SESSION_SOURCE_LABELS.get(session.source, session.source.value)
        status_label = format_session_status(session.status)
        active_note = ""
        if session.status in _ACTIVE_STATUSES:
            active_note = " · 진행 중"
        self._session_header.setText(
            f"ID: {session.id[:8]}… · {detail.mode_name} · "
            f"{status_label} · {source_label} · "
            f"{session.created_at.strftime('%Y-%m-%d %H:%M')}{active_note}"
        )
        self._copy_id_btn.setEnabled(True)
        self._export_all_btn.setEnabled(bool(detail.artifacts))
        self._export_all_docx_btn.setEnabled(bool(detail.artifacts))
        has_stage1 = 1 in detail.artifacts
        self._reprocess_btn.setEnabled(has_stage1 and session.status is SessionStatus.DONE)
        for stage, tab in self._stage_tabs.items():
            tab.load(session_id, detail.artifacts.get(stage))
        self._update_tab_titles(detail.artifacts)
        if focus_stage is not None and focus_stage in self._stage_tabs:
            self._tabs.setCurrentIndex(focus_stage - 1)

    def _update_tab_titles(self, artifacts: dict) -> None:
        for stage in (1, 2, 3):
            title = f"{stage}차"
            if stage in artifacts:
                title += " ●"
            self._tabs.setTabText(stage - 1, title)

    def _run_reprocess(self) -> None:
        if not self._session_id:
            return
        from_stage = int(self._reprocess_from.currentData())
        stage1 = self._stage_tabs.get(1)
        seed_text = stage1.current_text() if stage1 is not None else None
        if stage1 is not None and stage1.dirty:
            answer = QMessageBox.question(
                self,
                "재가공",
                "1차 산출물에 저장되지 않은 변경이 있습니다. 현재 편집 내용으로 재가공하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        result = self._controller.request_reprocess(
            self._session_id,
            from_stage,
            seed_text=seed_text,
        )
        if result.success:
            QMessageBox.information(
                self,
                "재가공",
                f"재가공이 완료되었습니다. (단계: {', '.join(map(str, result.stages_completed))})",
            )
            self._load_session(self._session_id, focus_stage=from_stage)
        else:
            QMessageBox.warning(self, "재가공", result.error or "재가공에 실패했습니다.")

    def _copy_session_id(self) -> None:
        if not self._session_id:
            return
        QGuiApplication.clipboard().setText(self._session_id)
        QMessageBox.information(self, "ID 복사", "세션 ID를 클립보드에 복사했습니다.")

    def _current_docx_template(self) -> str:
        value = self._docx_template.currentData()
        return str(value) if value else "basic"

    def _confirm_overwrite(self, dest_path: str) -> bool:
        from pathlib import Path

        path = Path(dest_path)
        if not path.exists():
            return True
        answer = QMessageBox.question(
            self,
            "파일 덮어쓰기",
            f"이미 존재하는 파일입니다.\n{path.name}\n\n덮어쓰시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer is QMessageBox.StandardButton.Yes

    def _export_all_stages(self, export_format: str) -> None:
        session_id = self._session_id
        if session_id is None:
            return
        detail = self._controller.get_session_detail(session_id)
        if detail is None or not detail.artifacts:
            QMessageBox.information(self, "보내기", "보낼 산출물이 없습니다.")
            return
        stages = tuple(sorted(detail.artifacts))
        default_path = str(
            self._controller.resolve_default_export_path(
                session_id,
                "all",
                export_format=export_format,
            )
        )
        if export_format == "docx":
            caption = "전체 docx보내기"
            file_filter = "Word Documents (*.docx)"
        else:
            caption = "전체 md보내기"
            file_filter = "Markdown Files (*.md)"
        dest, _filter = QFileDialog.getSaveFileName(
            self,
            caption,
            default_path,
            file_filter,
        )
        if not dest:
            return
        if not self._confirm_overwrite(dest):
            return
        overrides: dict[int, str] = {}
        for stage, tab in self._stage_tabs.items():
            if tab.dirty and stage in stages:
                overrides[stage] = tab.current_text()
        target = ExportTarget(
            session_id=session_id,
            stages=stages,
            include_meta=True,
            template=self._current_docx_template() if export_format == "docx" else None,
        )
        result = self._controller.request_export_target(
            target,
            dest,
            export_format=export_format,
            text_overrides=overrides or None,
        )
        if result.success:
            QMessageBox.information(self, "보내기", f"저장됨: {result.path}")
        else:
            message = result.error or "보내기 실패"
            if result.suggestion:
                message = f"{message}\n\n{result.suggestion}"
            QMessageBox.warning(self, "보내기", message)
