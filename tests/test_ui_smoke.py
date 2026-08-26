from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
    from PySide6.QtGui import QDropEvent, QIcon
    from PySide6.QtWidgets import QApplication
except ImportError:  # Core checks stay runnable without GUI dependencies.
    QApplication = None


class BrandAssetTests(unittest.TestCase):
    def test_provided_brand_assets_are_packaged(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("pii-log-cleaner-icon.png", "pii-log-cleaner-wordmark.png", "pii-log-cleaner-icon.ico"):
            self.assertTrue((root / "resources" / "icons" / "branding" / name).is_file(), name)


@unittest.skipUnless(QApplication, "PySide6 is not installed")
class WindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_regex_only_workflow_analyzes_then_writes_separate_output(self) -> None:
        from app.ui.main_window import MainWindow

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "access.log"
            source.write_text("INFO phone=010-1234-5678 email=abc@example.com\n", encoding="utf-8")
            previous_data_dir = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = str(root / "app-data")
            window = MainWindow(root / "missing-model", allow_regex_only=True)
            window.show()
            try:
                self._wait_until(lambda: window.detector is not None)
                window.add_paths([source])
                window.start_analysis()
                self._wait_until(lambda: window.analysis_result is not None and window.active_action is None)
                self.assertEqual(window.analysis_result.detection_count, 2)
                self.assertEqual(len(window.current_previews), 1)

                window.start_deidentification()
                output = source.with_name("access_deid.log")
                self._wait_until(lambda: output.exists() and window.active_action is None)
                self.assertIn("[PHONE_1]", output.read_text(encoding="utf-8"))
                self.assertEqual(source.read_text(encoding="utf-8"), "INFO phone=010-1234-5678 email=abc@example.com\n")
            finally:
                window.close()
                if previous_data_dir is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = previous_data_dir

    def test_flaticon_icon_assets_are_packaged(self) -> None:
        from app.ui.main_window import _application_icon, _asset_path

        for name in ("folder", "file", "scanner", "shield", "power", "delete", "vision"):
            self.assertTrue(_asset_path(f"flaticon/{name}.png").is_file(), name)
            self.assertFalse(QIcon(str(_asset_path(f"flaticon/{name}.png"))).isNull(), name)
        self.assertFalse(_application_icon().isNull())

    def test_dragged_files_and_folders_expand_using_recursive_option(self) -> None:
        from app.ui.main_window import _expand_targets

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            top_level = root / "access.log"
            nested = root / "archive" / "service.txt"
            top_level.write_text("top", encoding="utf-8")
            nested.parent.mkdir()
            nested.write_text("nested", encoding="utf-8")

            direct, had_error = _expand_targets([root], include_subfolders=False)
            self.assertFalse(had_error)
            self.assertEqual(direct, [top_level])

            recursive, had_error = _expand_targets([root], include_subfolders=True)
            self.assertFalse(had_error)
            self.assertEqual(set(recursive), {top_level, nested})

    def test_drop_table_emits_local_file_paths(self) -> None:
        from app.ui.main_window import FileDropTable

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text("INFO", encoding="utf-8")
            received: list[Path] = []
            table = FileDropTable()
            table.paths_dropped.connect(received.extend)
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(str(path))])
            event = QDropEvent(
                QPointF(),
                Qt.DropAction.CopyAction,
                mime_data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            table.dropEvent(event)
            self.assertEqual(received, [path])

    def _wait_until(self, predicate: object, timeout: float = 8.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for the UI workflow")


if __name__ == "__main__":
    unittest.main()
