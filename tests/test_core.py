from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from app.core.masker import Masker, MaskingMode
from app.core.models import Detection
from app.core.regex_detector import RegexDetector
from app.processing.file_processor import FileProcessor


class CoreRegressionTests(unittest.TestCase):
    def test_regex_detection_skips_explicit_version_and_order_number(self) -> None:
        text = (
            "rrn=900101-1234567 phone=010-1234-5678 email=abc@example.com "
            "ip=192.168.0.1 api_key=sk-1234567890 password=test1234 "
            "account=123-456-789012 version=1.2.3.4 order_no=9001011234567"
        )
        findings = RegexDetector().detect(
            text, {"RRN", "PHONE", "EMAIL", "IP", "API_KEY", "PASSWORD", "ACCOUNT"}
        )
        kinds = {item.type for item in findings}
        values = {item.value for item in findings}
        self.assertTrue({"RRN", "PHONE", "EMAIL", "IP", "API_KEY", "PASSWORD", "ACCOUNT"} <= kinds)
        self.assertNotIn("1.2.3.4", values)
        self.assertNotIn("9001011234567", values)

    def test_masker_uses_offsets_and_reuses_tokens(self) -> None:
        text = "010-1234-5678 / 010-1234-5678"
        detections = [
            Detection("PHONE", "010-1234-5678", 0, 13, 1.0, "regex"),
            Detection("PHONE", "010-1234-5678", 16, 29, 1.0, "regex"),
        ]
        result, count = Masker().apply(text, detections, MaskingMode.AUTO)
        self.assertEqual(count, 2)
        self.assertEqual(result, "[PHONE_1] / [PHONE_1]")
        with self.assertRaisesRegex(ValueError, "치환할 문자열"):
            Masker().apply(text, detections, MaskingMode.CUSTOM)
        partial, _ = Masker().apply(text[:13], detections[:1], MaskingMode.PARTIAL)
        self.assertEqual(partial, "010-****-5678")

    def test_streaming_deidentification_keeps_source_and_writes_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "access.log"
            original = "INFO user=김민수 phone=010-1234-5678\r\nversion=1.2.3.4\r\n"
            with source.open("w", encoding="utf-8", newline="") as handle:
                handle.write(original)
            processor = FileProcessor(
                RegexDetector(), {"PHONE", "IP", "RRN", "EMAIL", "API_KEY", "PASSWORD", "ACCOUNT"}, Masker(), threading.Event()
            )
            result = processor.deidentify_file(source, MaskingMode.AUTO, "", backup=True)
            output = source.with_name("access_deid.log")
            with source.open("r", encoding="utf-8", newline="") as handle:
                self.assertEqual(handle.read(), original)
            with (source.parent / "backup" / source.name).open("r", encoding="utf-8", newline="") as handle:
                self.assertEqual(handle.read(), original)
            with output.open("r", encoding="utf-8", newline="") as handle:
                deidentified = handle.read()
            self.assertIn("[PHONE_1]", deidentified)
            self.assertIn("version=1.2.3.4", deidentified)
            self.assertEqual(result.counts["PHONE"], 1)


if __name__ == "__main__":
    unittest.main()
