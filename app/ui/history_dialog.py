from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout


class HistoryDialog(QDialog):
    def __init__(self, rows: list[tuple[str, str, int, int, str, float]], parent: object = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("전체 실행 히스토리")
        self.resize(880, 420)
        layout = QVBoxLayout(self)
        table = QTableWidget(len(rows), 6, self)
        table.setHorizontalHeaderLabels(["실행 시간", "대상 경로", "파일 수", "탐지 건수", "상태", "처리 시간"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if column >= 2 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_index, column, item)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (0, 2, 3, 4, 5):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
