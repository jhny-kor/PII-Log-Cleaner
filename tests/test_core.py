from __future__ import annotations

import tempfile
import threading
import unittest
from random import Random
from pathlib import Path

from app.core.masker import Masker, MaskingMode
from app.core.models import Detection
from app.core.overlap_resolver import resolve_overlaps
from app.core.regex_detector import RegexDetector
from app.processing.file_processor import FileProcessor


class CoreRegressionTests(unittest.TestCase):
    def test_overlap_resolution_matches_previous_selection_rules(self) -> None:
        random = Random(20260827)
        detections = [
            Detection(
                "TEST",
                str(index),
                start := random.randrange(-2, 500),
                start + random.randrange(-1, 30),
                random.random(),
                random.choice(("regex", "model", "llm", "other")),
            )
            for index in range(500)
        ]

        candidates = [item for item in detections if item.start >= 0 and item.end > item.start]
        candidates.sort(
            key=lambda item: (
                {"regex": 0, "model": 1, "llm": 2}.get(item.source, 9),
                item.start,
                -(item.end - item.start),
                -item.confidence,
            )
        )
        expected: list[Detection] = []
        for candidate in candidates:
            if all(
                candidate.end <= current.start or candidate.start >= current.end
                for current in expected
            ):
                expected.append(candidate)

        self.assertEqual(
            resolve_overlaps(detections),
            sorted(expected, key=lambda item: (item.start, item.end)),
        )

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

    def test_regex_detects_contextual_and_placeholder_names(self) -> None:
        findings = RegexDetector().detect(
            "성명=김민수 user=김ㅇㅇ 이메일=abc@example.com", {"PERSON"}
        )
        self.assertEqual([item.value for item in findings], ["김민수", "김ㅇㅇ"])

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
        class CountingDetector:
            def __init__(self) -> None:
                self.calls = 0

            def detect(self, text: str, enabled: set[str]) -> list[Detection]:
                self.calls += 1
                return RegexDetector().detect(text, enabled)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "access.log"
            original = "INFO user=김민수 phone=010-1234-5678\r\nversion=1.2.3.4\r\n"
            with source.open("w", encoding="utf-8", newline="") as handle:
                handle.write(original)
            detector = CountingDetector()
            processor = FileProcessor(
                detector, {"PHONE", "IP", "RRN", "EMAIL", "API_KEY", "PASSWORD", "ACCOUNT"}, Masker(), threading.Event()
            )
            result = processor.deidentify_file(source, MaskingMode.AUTO, "", backup=True, preview_limit=100)
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
            self.assertEqual(detector.calls, 1)
            self.assertTrue(any("[PHONE_1]" in row.deidentified for row in result.previews))


if __name__ == "__main__":
    unittest.main()
