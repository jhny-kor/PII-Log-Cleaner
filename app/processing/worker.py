from __future__ import annotations

import errno
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.audit_log import app_logger
from app.core.detector import PIIDetector
from app.core.masker import Masker, MaskingMode
from app.core.models import RunResult
from app.processing.encoding import EncodingDetectionError
from app.processing.file_processor import FileProcessor, ProcessingStopped
from app.report.csv_report import write_csv_report


class EngineInitWorker(QObject):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, model_dir: Path, allow_regex_only: bool = False) -> None:
        super().__init__()
        self.model_dir = model_dir
        self.allow_regex_only = allow_regex_only

    @Slot()
    def run(self) -> None:
        try:
            detector = PIIDetector(self.model_dir, self.allow_regex_only)
            detector.initialize()
        except Exception:
            self.failed.emit("개인정보 탐지 엔진을 초기화하지 못했습니다.")
            return
        app_logger.info("모델 초기화 성공")
        self.ready.emit(detector)


class ProcessingWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(object)

    def __init__(
        self,
        paths: list[Path],
        detector: PIIDetector,
        enabled: set[str],
        mode: str,
        custom_text: str,
        action: str,
        backup: bool,
        report: bool,
        preview_limit: int = 100,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.detector = detector
        self.enabled = enabled
        self.mode = mode
        self.custom_text = custom_text
        self.action = action
        self.backup = backup
        self.report = report
        self.preview_limit = preview_limit
        self.stop_event = threading.Event()

    def request_stop(self) -> None:
        self.stop_event.set()

    @Slot()
    def run(self) -> None:
        if self.mode == MaskingMode.CUSTOM and not self.custom_text.strip():
            self.finished.emit(RunResult("failed", error="치환할 문자열을 입력해주세요."))
            return
        processor = FileProcessor(self.detector, self.enabled, Masker(), self.stop_event)
        result = RunResult("complete")
        app_logger.info("%s 시작: 파일 %d개", "분석" if self.action == "analysis" else "비식별화", len(self.paths))
        try:
            for index, path in enumerate(self.paths, start=1):
                self.progress.emit(index, len(self.paths))
                if self.action == "analysis":
                    result.files.append(processor.analyze_file(path, self.mode, self.custom_text, self.preview_limit))
                else:
                    result.files.append(processor.deidentify_file(path, self.mode, self.custom_text, self.backup))
            if self.action == "deidentify" and self.report and result.files:
                result.report_path = str(write_csv_report(result.files, self.paths[0].parent))
        except ProcessingStopped:
            result.status = "cancelled"
            app_logger.info("처리 중지")
        except Exception as exc:
            result.status = "failed"
            result.error = self._message_for(exc)
            app_logger.info("처리 오류")
        else:
            app_logger.info("탐지 %d건", result.detection_count)
            app_logger.info("처리 완료")
        self.finished.emit(result)

    @staticmethod
    def _message_for(error: Exception) -> str:
        if isinstance(error, EncodingDetectionError):
            return "인코딩을 자동으로 확인하지 못했습니다."
        if isinstance(error, PermissionError):
            return "파일을 읽을 권한이 없습니다."
        if isinstance(error, OSError) and error.errno == errno.ENOSPC:
            return "결과 파일을 저장할 공간이 부족합니다."
        if isinstance(error, OSError):
            return "파일이 다른 프로그램에서 사용 중입니다."
        return "처리 중 오류가 발생했습니다."
