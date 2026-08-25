from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # Core checks stay runnable without GUI dependencies.
    QApplication = None


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
