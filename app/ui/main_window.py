from __future__ import annotations

import itertools
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QSize, QThread, Qt
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.masker import MaskingMode
from app.core.models import Detection, PreviewRow, RunResult
from app.core.policies import SUPPORTED_EXTENSIONS, TYPE_LABELS, UI_TYPE_TO_CODES, enabled_codes, is_supported_file
from app.processing.worker import EngineInitWorker, ProcessingWorker
from app.storage.history import HistoryStore
from resources.strings import TEXT

from .history_dialog import HistoryDialog


class TitleBar(QFrame):
    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.setObjectName("titleBar")
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(8)
        icon = QLabel(self)
        icon.setObjectName("titleIcon")
        icon.setFixedSize(QSize(30, 30))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_asset = _asset_path("branding/pii-log-cleaner-icon.png")
        if icon_asset.is_file():
            icon.setPixmap(QPixmap(str(icon_asset)).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            shield = getattr(QStyle.StandardPixmap, "SP_VistaShield", QStyle.StandardPixmap.SP_DialogApplyButton)
            icon.setPixmap(self.style().standardIcon(shield).pixmap(28, 28))
        layout.addWidget(icon)
        wordmark_asset = _asset_path("branding/pii-log-cleaner-wordmark.png")
        if wordmark_asset.is_file():
            wordmark = QLabel(self)
            wordmark.setObjectName("brandLogo")
            wordmark.setFixedSize(QSize(108, 44))
            wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wordmark.setPixmap(QPixmap(str(wordmark_asset)).scaled(104, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(wordmark)
        else:
            title = QLabel(TEXT["app_title"], self)
            title.setObjectName("titleLabel")
            layout.addWidget(title)
        version = QLabel(TEXT["version"], self)
        version.setObjectName("versionLabel")
        layout.addWidget(version)
        layout.addStretch()
        for pixmap, action in (
            (QStyle.StandardPixmap.SP_TitleBarMinButton, window.showMinimized),
            (QStyle.StandardPixmap.SP_TitleBarMaxButton, window.toggle_maximized),
            (QStyle.StandardPixmap.SP_TitleBarCloseButton, window.close),
        ):
            button = QToolButton(self)
            button.setObjectName("titleButton")
            button.setIcon(self.style().standardIcon(pixmap))
            button.clicked.connect(action)
            layout.addWidget(button)

    def mouseDoubleClickEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().toggle_maximized()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle() is not None:
            if self.window().windowHandle().startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    _DEMO_FILE_DETAILS = {
        r"C:\logs\access.log": ("12.5 MB", "2025-08-24 10:23:11"),
        r"C:\logs\application.log": ("45.3 MB", "2025-08-24 09:15:42"),
        r"C:\logs\jeus.log": ("8.7 MB", "2025-08-22 09:15:30"),
        r"C:\logs\batch_20250824.log": ("22.1 MB", "2025-08-24 08:33:21"),
        r"C:\logs\sql.log": ("6.3 MB", "2025-08-20 14:22:10"),
    }

    def __init__(self, model_dir: Path, allow_regex_only: bool = False, demo: bool = False) -> None:
        super().__init__()
        self.model_dir = model_dir
        self.allow_regex_only = allow_regex_only
        self.demo = demo
        self.detector = None
        self.files: dict[Path, bool] = {}
        self.analysis_result: RunResult | None = None
        self.current_previews: list[PreviewRow] = []
        self.history = HistoryStore()
        self.engine_thread: QThread | None = None
        self.engine_worker: EngineInitWorker | None = None
        self.worker_thread: QThread | None = None
        self.worker: ProcessingWorker | None = None
        self.active_action: str | None = None
        self.started_at: datetime | None = None
        self.started_tick: float | None = None
        self._updating_files = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle(TEXT["app_title"])
        self.setWindowIcon(_application_icon())
        self.setMinimumSize(1_300, 860)
        self.resize(1_536, 1_024)
        self._build_ui()
        if self.demo:
            self.status.hide()
        self._load_history()
        if self.demo:
            self._load_demo_files()
        self._start_engine_initialization()

    def toggle_maximized(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _build_ui(self) -> None:
        outer = QWidget(self)
        root = QVBoxLayout(outer)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(TitleBar(self))

        body = QWidget(outer)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 16, 18, 12)
        body_layout.setSpacing(0)

        top = QGridLayout()
        top.setHorizontalSpacing(20)
        top.addWidget(self._target_group(), 0, 0)
        top.addWidget(self._summary_panel(), 0, 1)
        top.setColumnStretch(0, 58)
        top.setColumnStretch(1, 42)
        body_layout.addLayout(top, 4)

        middle = QGridLayout()
        middle.setHorizontalSpacing(20)
        middle.addWidget(self._detection_group(), 0, 0)
        middle.addWidget(self._masking_group(), 0, 1)
        middle.addWidget(self._options_group(), 0, 2)
        middle.addWidget(self._history_group(), 0, 3)
        middle.setColumnMinimumWidth(0, 400)
        middle.setColumnMinimumWidth(1, 315)
        middle.setColumnMinimumWidth(2, 310)
        middle.setColumnMinimumWidth(3, 415)
        body_layout.addLayout(middle, 5)
        body_layout.addWidget(self._preview_group(), 2)

        root.addWidget(body, 1)
        self.setCentralWidget(outer)
        self.status = QStatusBar(self)
        self.status.showMessage(TEXT["preparing"])
        self.setStatusBar(self.status)
        self.setStyleSheet(self._stylesheet())

    def _target_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["select_target"], self)
        layout = QVBoxLayout(group)
        top = QHBoxLayout()
        folder = self._button(TEXT["select_folder"], "folder", QStyle.StandardPixmap.SP_DirOpenIcon)
        folder.clicked.connect(self.choose_folder)
        files = self._button(TEXT["select_files"], "file", QStyle.StandardPixmap.SP_FileIcon)
        files.clicked.connect(self.choose_files)
        top.addWidget(folder)
        top.addWidget(files)
        top.addStretch()
        self.selected_files_label = QLabel(TEXT["selected_files"].format(count=0), group)
        self.selected_files_label.setObjectName("subtleText")
        top.addWidget(self.selected_files_label)
        layout.addLayout(top)

        self.file_table = QTableWidget(0, 5, group)
        self.file_table.setHorizontalHeaderLabels(["선택", TEXT["file_path"], TEXT["size"], TEXT["modified"], TEXT["remove"]])
        self._table_basics(self.file_table)
        self.file_table.itemChanged.connect(self._file_check_changed)
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.file_table.setColumnWidth(0, 54)
        self.file_table.setColumnWidth(2, 112)
        self.file_table.setColumnWidth(3, 190)
        self.file_table.setColumnWidth(4, 54)
        self.file_table.setMinimumHeight(188)
        layout.addWidget(self.file_table, 1)

        actions = QHBoxLayout()
        add = self._button(TEXT["add_files"], "file", QStyle.StandardPixmap.SP_FileDialogNewFolder)
        add.clicked.connect(self.choose_files)
        remove = self._button(TEXT["remove_selected"], "delete", QStyle.StandardPixmap.SP_TrashIcon)
        remove.clicked.connect(self.remove_checked_files)
        clear = self._button(TEXT["remove_all"], "delete", QStyle.StandardPixmap.SP_TrashIcon)
        clear.clicked.connect(self.clear_files)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addWidget(clear)
        actions.addStretch()
        formats = QLabel(TEXT["supported_formats"], group)
        formats.setObjectName("subtleText")
        actions.addWidget(formats)
        layout.addLayout(actions)
        return group

    def _summary_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        actions = QHBoxLayout()
        self.analysis_button = self._button(TEXT["start_analysis"], "scanner", QStyle.StandardPixmap.SP_MediaPlay, "primaryButton")
        self.analysis_button.setMinimumHeight(50)
        self.analysis_button.setEnabled(False)
        self.analysis_button.clicked.connect(self.start_analysis)
        self.deidentify_button = self._button(TEXT["run_deid"], "shield", QStyle.StandardPixmap.SP_DialogApplyButton, "secondaryButton")
        self.deidentify_button.setMinimumHeight(50)
        self.deidentify_button.setEnabled(False)
        self.deidentify_button.clicked.connect(self.start_deidentification)
        self.stop_button = self._button(TEXT["stop"], "power", QStyle.StandardPixmap.SP_MediaStop)
        self.stop_button.setMinimumHeight(50)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.request_stop)
        actions.addWidget(self.analysis_button, 1)
        actions.addWidget(self.deidentify_button, 1)
        actions.addWidget(self.stop_button, 0)
        layout.addLayout(actions)

        group = QGroupBox(TEXT["summary"], panel)
        group_layout = QVBoxLayout(group)
        self.summary_table = QTableWidget(6, 2, group)
        self.summary_table.setHorizontalHeaderLabels([TEXT["summary_item"], TEXT["summary_value"]])
        self._table_basics(self.summary_table)
        self.summary_table.setMinimumHeight(218)
        self.summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._set_summary({}, None, None)
        group_layout.addWidget(self.summary_table)
        layout.addWidget(group, 1)
        return panel

    def _detection_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["detect_items"], self)
        layout = QVBoxLayout(group)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        positions = (
            ("이름", 0, 0),
            ("주민등록번호", 0, 1),
            ("IP 주소", 1, 0),
            ("주소", 1, 1),
            ("URL", 2, 0),
            ("계좌번호", 2, 1),
            ("이메일", 3, 0),
            ("전화번호", 3, 1),
            ("날짜", 4, 0),
            ("API Key / 비밀번호", 4, 1),
            ("기타 식별정보", 5, 1),
        )
        self.detect_boxes: dict[str, QCheckBox] = {}
        for label, row, column in positions:
            box = QCheckBox(label, group)
            box.setChecked(True)
            self.detect_boxes[label] = box
            grid.addWidget(box, row, column)
        layout.addLayout(grid)
        layout.addStretch()
        note = QLabel("* 선택한 항목만 탐지 및 치환됩니다.", group)
        note.setObjectName("subtleText")
        layout.addWidget(note)
        return group

    def _masking_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["masking"], self)
        layout = QVBoxLayout(group)
        self.auto_radio = QRadioButton(TEXT["auto"], group)
        self.custom_radio = QRadioButton(TEXT["custom"], group)
        self.partial_radio = QRadioButton(TEXT["partial"], group)
        self.auto_radio.setChecked(True)
        radios = QButtonGroup(group)
        radios.addButton(self.auto_radio)
        radios.addButton(self.custom_radio)
        radios.addButton(self.partial_radio)
        radios.buttonToggled.connect(self._masking_mode_changed)
        layout.addWidget(self.auto_radio)
        layout.addWidget(self._detail(TEXT["auto_detail"]))
        layout.addSpacing(4)
        layout.addWidget(self.custom_radio)
        layout.addWidget(self._detail(TEXT["custom_detail"]))
        self.custom_input = QLineEdit(group)
        self.custom_input.setPlaceholderText(TEXT["custom_placeholder"])
        self.custom_input.setEnabled(False)
        layout.addWidget(self.custom_input)
        layout.addSpacing(4)
        layout.addWidget(self.partial_radio)
        layout.addWidget(self._detail(TEXT["partial_detail"]))
        self.partial_style = QLineEdit("010-1234-5678 → 010-****-5678", group)
        self.partial_style.setReadOnly(True)
        self.partial_style.setEnabled(False)
        layout.addWidget(self.partial_style)
        layout.addStretch()
        return group

    def _options_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["options"], self)
        layout = QVBoxLayout(group)
        self.backup_box = self._option(layout, TEXT["backup"], TEXT["backup_detail"], True)
        self.report_box = self._option(layout, TEXT["report"], TEXT["report_detail"], True)
        self.large_file_box = self._option(layout, TEXT["large_file"], TEXT["large_file_detail"], True)
        self.encoding_box = self._option(layout, TEXT["encoding"], TEXT["encoding_detail"], True)
        self.recursive_box = self._option(layout, TEXT["recursive"], TEXT["recursive_detail"], False)
        layout.addStretch()
        return group

    def _history_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["history"], self)
        layout = QVBoxLayout(group)
        view_all = QToolButton(group)
        view_all.setText(TEXT["view_all"])
        view_all.setObjectName("linkButton")
        view_all.clicked.connect(self.show_history)
        layout.addWidget(view_all, alignment=Qt.AlignmentFlag.AlignRight)
        self.history_table = QTableWidget(0, 3, group)
        self.history_table.setHorizontalHeaderLabels([TEXT["history_time"], TEXT["history_target"], TEXT["history_status"]])
        self._table_basics(self.history_table)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table, 1)
        return group

    def _preview_group(self) -> QGroupBox:
        group = QGroupBox(TEXT["preview"], self)
        layout = QVBoxLayout(group)
        self.preview_table = QTableWidget(0, 3, group)
        self.preview_table.setHorizontalHeaderLabels([TEXT["original"], TEXT["deidentified"], TEXT["found"]])
        self._table_basics(self.preview_table)
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.preview_table.setMinimumHeight(184)
        layout.addWidget(self.preview_table, 1)
        footer = QHBoxLayout()
        note = QLabel(TEXT["preview_note"], group)
        note.setObjectName("subtleText")
        footer.addWidget(note)
        footer.addStretch()
        whole = self._button(TEXT["view_full_preview"], "vision", QStyle.StandardPixmap.SP_FileDialogDetailedView)
        whole.clicked.connect(self.show_full_preview)
        footer.addWidget(whole)
        layout.addLayout(footer)
        return group

    def _button(self, text: str, icon_name: str, fallback: QStyle.StandardPixmap, object_name: str = "") -> QPushButton:
        button = QPushButton(text, self)
        color = "#ffffff" if object_name == "primaryButton" else "#1768d4"
        button.setIcon(self._icon(icon_name, fallback, color))
        button.setIconSize(QSize(18, 18))
        if object_name:
            button.setObjectName(object_name)
        return button

    def _icon(self, icon_name: str, fallback: QStyle.StandardPixmap, color: str = "#1768d4") -> QIcon:
        asset = _asset_path(f"flaticon/{icon_name}.png")
        if not asset.is_file():
            return self.style().standardIcon(fallback)
        pixmap = QPixmap(str(asset))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _detail(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("detailText")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _table_basics(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)

    @staticmethod
    def _option(layout: QVBoxLayout, title: str, detail: str, checked: bool) -> QCheckBox:
        checkbox = QCheckBox(title)
        checkbox.setChecked(checked)
        layout.addWidget(checkbox)
        note = QLabel(detail)
        note.setObjectName("detailText")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addSpacing(3)
        return checkbox

    def choose_files(self) -> None:
        filters = "지원 파일 (" + " ".join(f"*{extension}" for extension in SUPPORTED_EXTENSIONS) + ")"
        selected, _ = QFileDialog.getOpenFileNames(self, TEXT["select_files"], "", filters)
        self.add_paths([Path(path) for path in selected])

    def choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, TEXT["select_folder"])
        if not chosen:
            return
        folder = Path(chosen)
        try:
            candidates = folder.rglob("*") if self.recursive_box.isChecked() else folder.iterdir()
            self.add_paths([path for path in candidates if is_supported_file(path)])
        except PermissionError:
            self.status.showMessage(TEXT["permission_error"])

    def add_paths(self, paths: list[Path]) -> None:
        duplicates = 0
        added = 0
        for path in paths:
            if not is_supported_file(path):
                continue
            canonical = path.resolve()
            if canonical in self.files:
                duplicates += 1
                continue
            self.files[canonical] = True
            added += 1
        self._populate_file_table()
        if duplicates:
            self.status.showMessage(TEXT["duplicates_skipped"].format(count=duplicates))
        elif added:
            self.status.showMessage(TEXT["files_added"].format(count=added))
        elif paths:
            self.status.showMessage(TEXT["nothing_found"])

    def remove_checked_files(self) -> None:
        self.files = {path: checked for path, checked in self.files.items() if not checked}
        self._populate_file_table()

    def clear_files(self) -> None:
        self.files.clear()
        self.analysis_result = None
        self.current_previews.clear()
        self._populate_file_table()
        self._populate_preview([])
        self._set_busy(False)

    def _populate_file_table(self) -> None:
        self._updating_files = True
        self.file_table.setRowCount(len(self.files))
        for row, (path, checked) in enumerate(self.files.items()):
            choice = QTableWidgetItem()
            choice.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            choice.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            choice.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 0, choice)
            file_item = QTableWidgetItem(str(path))
            file_item.setToolTip(str(path))
            self.file_table.setItem(row, 1, file_item)
            try:
                info = path.stat()
                size = QTableWidgetItem(self._format_size(info.st_size))
                size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.file_table.setItem(row, 2, size)
                self.file_table.setItem(row, 3, QTableWidgetItem(datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")))
            except OSError:
                demo_detail = self._DEMO_FILE_DETAILS.get(str(path)) if self.demo else None
                size = QTableWidgetItem(demo_detail[0] if demo_detail else "-")
                size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.file_table.setItem(row, 2, size)
                self.file_table.setItem(row, 3, QTableWidgetItem(demo_detail[1] if demo_detail else "-"))
            remove = QToolButton(self.file_table)
            remove.setIcon(self._icon("delete", QStyle.StandardPixmap.SP_TitleBarCloseButton))
            remove.setIconSize(QSize(16, 16))
            remove.clicked.connect(lambda _checked=False, target=path: self._remove_path(target))
            self.file_table.setCellWidget(row, 4, remove)
        self._updating_files = False
        self.selected_files_label.setText(TEXT["selected_files"].format(count=sum(self.files.values())))

    def _remove_path(self, path: Path) -> None:
        self.files.pop(path, None)
        self._populate_file_table()

    def _file_check_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_files or item.column() != 0:
            return
        path = list(self.files)[item.row()]
        self.files[path] = item.checkState() == Qt.CheckState.Checked
        self.selected_files_label.setText(TEXT["selected_files"].format(count=sum(self.files.values())))

    def _masking_mode_changed(self) -> None:
        self.custom_input.setEnabled(self.custom_radio.isChecked())
        self.partial_style.setEnabled(self.partial_radio.isChecked())

    def _masking_mode(self) -> str:
        if self.custom_radio.isChecked():
            return MaskingMode.CUSTOM
        if self.partial_radio.isChecked():
            return MaskingMode.PARTIAL
        return MaskingMode.AUTO

    def _selected_paths(self) -> list[Path]:
        return [path for path, checked in self.files.items() if checked and path.exists()]

    def _selected_codes(self) -> set[str]:
        return enabled_codes({label for label, box in self.detect_boxes.items() if box.isChecked()})

    def start_analysis(self) -> None:
        if not self._selected_paths():
            self.status.showMessage(TEXT["no_files"])
            return
        if self.detector is None:
            self.status.showMessage(TEXT["model_error"].replace("\n", " "))
            return
        if self._masking_mode() == MaskingMode.CUSTOM and not self.custom_input.text().strip():
            self.status.showMessage(TEXT["custom_required"])
            return
        self._start_processing("analysis")

    def start_deidentification(self) -> None:
        if self.analysis_result is None:
            self.status.showMessage(TEXT["no_analysis"])
            return
        self._start_processing("deidentify")

    def _start_processing(self, action: str) -> None:
        paths = self._selected_paths()
        self.active_action = action
        self.started_at = datetime.now()
        self.started_tick = perf_counter()
        self._set_busy(True)
        thread = QThread(self)
        worker = ProcessingWorker(
            paths,
            self.detector,
            self._selected_codes(),
            self._masking_mode(),
            self.custom_input.text(),
            action,
            self.backup_box.isChecked(),
            self.report_box.isChecked(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._processing_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.worker_thread, self.worker = thread, worker
        thread.start()

    def request_stop(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.stop_button.setEnabled(False)
            self.status.showMessage("현재 처리 중인 구간을 마친 뒤 중지합니다.")

    def _show_progress(self, current: int, total: int) -> None:
        self.status.showMessage(TEXT["processing"].format(current=current, total=total))

    def _processing_finished(self, result: RunResult) -> None:
        elapsed = perf_counter() - self.started_tick if self.started_tick else 0.0
        completed_at = datetime.now()
        self._set_summary(
            {
                TEXT["summary_file_count"]: f"{len(result.files)}개",
                TEXT["summary_detection_count"]: f"{result.detection_count:,}건",
                TEXT["summary_replacement_count"]: f"{result.replacement_count:,}건",
                TEXT["summary_duration"]: self._format_duration(elapsed),
                TEXT["summary_started"]: self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else "-",
                TEXT["summary_finished"]: completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            },
            result.detection_count,
            result.replacement_count,
        )
        if result.status == "complete":
            if self.active_action == "analysis":
                self.analysis_result = result
                self.current_previews = list(itertools.islice((row for file in result.files for row in file.previews), 100))
                self._populate_preview(self.current_previews)
                self.status.showMessage(TEXT["analysis_complete"])
            else:
                self.status.showMessage(TEXT["deid_complete"])
            self._save_history(TEXT["complete"], result, elapsed)
        elif result.status == "cancelled":
            self.status.showMessage(TEXT["cancelled"])
            self._save_history(TEXT["cancelled"], result, elapsed)
        else:
            self.status.showMessage(result.error or "처리 중 오류가 발생했습니다.")
        self.active_action = None
        self.worker = None
        self.worker_thread = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.analysis_button.setEnabled(False)
            self.deidentify_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            return
        self.analysis_button.setEnabled(self.detector is not None)
        self.deidentify_button.setEnabled(self.detector is not None and self.analysis_result is not None)
        self.stop_button.setEnabled(False)

    def _set_summary(self, values: dict[str, str], detections: int | None, replacements: int | None) -> None:
        labels = (
            TEXT["summary_file_count"],
            TEXT["summary_detection_count"],
            TEXT["summary_replacement_count"],
            TEXT["summary_duration"],
            TEXT["summary_started"],
            TEXT["summary_finished"],
        )
        for row, label in enumerate(labels):
            self.summary_table.setItem(row, 0, QTableWidgetItem(label))
            value = QTableWidgetItem(values.get(label, "-"))
            if label == TEXT["summary_detection_count"] and detections:
                value.setForeground(Qt.GlobalColor.red)
            if label == TEXT["summary_replacement_count"] and replacements:
                value.setForeground(Qt.GlobalColor.blue)
            self.summary_table.setItem(row, 1, value)

    def _populate_preview(self, rows: list[PreviewRow]) -> None:
        self.preview_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self.preview_table.setItem(index, 0, QTableWidgetItem(row.original))
            self.preview_table.setItem(index, 1, QTableWidgetItem(row.deidentified))
            widget = QWidget(self.preview_table)
            badges = QHBoxLayout(widget)
            badges.setContentsMargins(8, 3, 8, 3)
            badges.setSpacing(5)
            if row.detections:
                for kind in dict.fromkeys(item.type for item in row.detections):
                    badge = QLabel(TYPE_LABELS.get(kind, kind), widget)
                    badge.setObjectName("badge")
                    badge.setProperty("kind", kind)
                    badges.addWidget(badge)
            else:
                badges.addWidget(QLabel("-", widget))
            badges.addStretch()
            self.preview_table.setCellWidget(index, 2, widget)

    def _save_history(self, status: str, result: RunResult, duration: float) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        self.history.add(str(paths[0].parent), len(result.files), result.detection_count, status, duration)
        self._load_history()

    def _load_history(self) -> None:
        self._populate_history_rows(self.history.recent())

    def _populate_history_rows(self, rows: list[tuple[str, str, str]]) -> None:
        self.history_table.setRowCount(len(rows))
        for row_index, (when, target, status) in enumerate(rows):
            self.history_table.setItem(row_index, 0, QTableWidgetItem(when))
            path = QTableWidgetItem(target)
            path.setToolTip(target)
            self.history_table.setItem(row_index, 1, path)
            item = QTableWidgetItem(status)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status == TEXT["complete"]:
                item.setForeground(QColor("#0b8754"))
            self.history_table.setItem(row_index, 2, item)

    def show_history(self) -> None:
        HistoryDialog(self.history.all(), self).exec()

    def show_full_preview(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(TEXT["preview"])
        dialog.resize(1_100, 600)
        layout = QVBoxLayout(dialog)
        copy = QTableWidget(0, 3, dialog)
        copy.setHorizontalHeaderLabels([TEXT["original"], TEXT["deidentified"], TEXT["found"]])
        self._table_basics(copy)
        copy.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        copy.setRowCount(len(self.current_previews))
        for index, row in enumerate(self.current_previews):
            copy.setItem(index, 0, QTableWidgetItem(row.original))
            copy.setItem(index, 1, QTableWidgetItem(row.deidentified))
            copy.setItem(index, 2, QTableWidgetItem(", ".join(TYPE_LABELS.get(item.type, item.type) for item in row.detections) or "-"))
        layout.addWidget(copy)
        dialog.exec()

    def _start_engine_initialization(self) -> None:
        thread = QThread(self)
        worker = EngineInitWorker(self.model_dir, self.allow_regex_only)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(self._engine_ready)
        worker.failed.connect(self._engine_failed)
        worker.ready.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.engine_thread, self.engine_worker = thread, worker
        thread.start()

    def _engine_ready(self, detector: object) -> None:
        self.detector = detector
        self.status.showMessage(TEXT["ready"])
        self._set_busy(False)

    def _engine_failed(self, _message: str) -> None:
        self.detector = None
        self.status.showMessage(TEXT["model_error"].replace("\n", " "))
        self.analysis_button.setEnabled(False)
        if not self.demo:
            QMessageBox.critical(self, TEXT["app_title"], TEXT["model_error"])

    def _load_demo_files(self) -> None:
        self.files = {
            Path(r"C:\logs\access.log"): True,
            Path(r"C:\logs\application.log"): True,
            Path(r"C:\logs\jeus.log"): True,
            Path(r"C:\logs\batch_20250824.log"): True,
            Path(r"C:\logs\sql.log"): True,
        }
        self._populate_file_table()
        self.analysis_result = RunResult("complete")
        self._set_summary(
            {
                TEXT["summary_file_count"]: "5개",
                TEXT["summary_detection_count"]: "5,842건",
                TEXT["summary_replacement_count"]: "5,842건",
                TEXT["summary_duration"]: "00:01:35",
                TEXT["summary_started"]: "2025-08-24 10:23:11",
                TEXT["summary_finished"]: "2025-08-24 10:24:46",
            },
            5842,
            5842,
        )
        self.current_previews = [
            PreviewRow(
                "2025-08-24 10:23:11 INFO user=김민수 phone=010-1234-5678",
                "2025-08-24 10:23:11 INFO user=[PERSON_1] phone=[PHONE_1]",
                [Detection("PERSON", "김민수", 0, 0, 1.0, "model"), Detection("PHONE", "", 0, 0, 1.0, "regex")],
            ),
            PreviewRow(
                "ip=192.168.0.15 email=kiminsu@gmail.com address=서울특별시 강남구 …",
                "ip=[IP_1] email=[EMAIL_1] address=[ADDRESS_1]",
                [Detection("IP", "", 0, 0, 1.0, "regex"), Detection("EMAIL", "", 0, 0, 1.0, "regex"), Detection("ADDRESS", "", 0, 0, 1.0, "model")],
            ),
            PreviewRow(
                "rrn=900101-1234567 account=123-456-789012",
                "rrn=[RRN_1] account=[ACCOUNT_1]",
                [Detection("RRN", "", 0, 0, 1.0, "regex"), Detection("ACCOUNT", "", 0, 0, 1.0, "regex")],
            ),
            PreviewRow("POST /login HTTP/1.1 User-Agent: Mozilla/5.0", "POST /login HTTP/1.1 User-Agent: Mozilla/5.0", []),
            PreviewRow("api_key=sk-1234567890abcdef", "api_key=[API_KEY_1]", [Detection("API_KEY", "", 0, 0, 1.0, "regex")]),
        ]
        self._populate_preview(self.current_previews)
        self._populate_history_rows(
            [
                ("2025-08-24 10:23:11", r"C:\logs\app_logs", TEXT["complete"]),
                ("2025-08-23 15:42:33", r"C:\logs\system", TEXT["complete"]),
                ("2025-08-22 09:15:30", r"C:\logs\access", TEXT["complete"]),
                ("2025-08-21 18:33:10", r"C:\logs\batch", TEXT["complete"]),
                ("2025-08-20 14:22:10", r"C:\logs\jeus", TEXT["complete"]),
            ]
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.request_stop()
        event.accept()

    @staticmethod
    def _format_size(size: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return "-"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _stylesheet() -> str:
        return """
            QMainWindow, QWidget { background: #f8fafc; color: #172033; font-family: 'Segoe UI', 'Malgun Gothic'; font-size: 13px; }
            QFrame#titleBar { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1765c9, stop:1 #0e4a9d); }
            QLabel#titleIcon { background: rgba(255, 255, 255, 0.96); border-radius: 8px; }
            QLabel#brandLogo { background: rgba(255, 255, 255, 0.96); border-radius: 5px; padding: 1px; }
            QLabel#titleLabel { color: white; background: transparent; font-size: 20px; font-weight: 700; }
            QLabel#versionLabel { color: #dbeafe; background: transparent; font-size: 14px; }
            QToolButton#titleButton { border: 0; padding: 10px; background: transparent; }
            QToolButton#titleButton:hover { background: #093775; }
            QGroupBox { background: white; border: 1px solid #d7e1ef; border-radius: 6px; margin-top: 13px; padding: 10px 0; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { min-height: 30px; border: 1px solid #b9cce7; background: #ffffff; border-radius: 5px; padding: 4px 14px; font-weight: 600; }
            QPushButton:hover { background: #eff6ff; border-color: #5e94df; }
            QPushButton:disabled { color: #8b9ab0; background: #f8fafc; border-color: #dce5f0; }
            QPushButton#primaryButton { color: white; background: #1967d2; border-color: #1967d2; font-size: 16px; }
            QPushButton#primaryButton:hover { background: #1158ba; }
            QPushButton#secondaryButton { color: #1260c7; border-color: #8cb4e8; background: #ffffff; font-size: 16px; }
            QTableWidget { background: white; alternate-background-color: #f8fbff; border: 1px solid #d7e1ef; gridline-color: #dce5f0; selection-background-color: #e8f1ff; }
            QHeaderView::section { background: #f7f9fc; border: 0; border-right: 1px solid #dce5f0; border-bottom: 1px solid #dce5f0; padding: 7px; font-weight: 700; }
            QCheckBox, QRadioButton { spacing: 7px; font-size: 14px; }
            QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
            QLineEdit { min-height: 26px; border: 1px solid #c7d5e7; border-radius: 4px; background: white; padding: 2px 7px; }
            QLabel#subtleText { color: #64748b; }
            QLabel#detailText { color: #64748b; font-size: 12px; margin-left: 25px; }
            QLabel#badge { color: #0b7650; background: #e4f8ee; border-radius: 11px; padding: 3px 8px; font-weight: 700; }
            QLabel#badge[kind="IP"], QLabel#badge[kind="EMAIL"], QLabel#badge[kind="ADDRESS"] { color: #1768d4; background: #e5f1ff; }
            QLabel#badge[kind="RRN"], QLabel#badge[kind="API_KEY"], QLabel#badge[kind="PASSWORD"] { color: #ed6812; background: #fff0e5; }
            QLabel#badge[kind="ACCOUNT"] { color: #4b5565; background: #eef2f7; }
            QToolButton#linkButton { color: #1768d4; border: 0; background: transparent; font-weight: 700; }
            QStatusBar { background: white; border-top: 1px solid #dce5f0; color: #526277; }
        """


def launch(model_dir: Path, allow_regex_only: bool = False, demo: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(TEXT["app_title"])
    app.setWindowIcon(_application_icon())
    window = MainWindow(model_dir, allow_regex_only, demo)
    window.show()
    return app.exec()


def _asset_path(name: str) -> Path:
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "resources" / "icons" / name


def _application_icon() -> QIcon:
    asset = _asset_path("branding/pii-log-cleaner-icon.png")
    return QIcon(str(asset)) if asset.is_file() else QIcon()
