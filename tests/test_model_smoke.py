from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("PII_RUN_MODEL_SMOKE") == "1", "Set PII_RUN_MODEL_SMOKE=1 for real v7 inference")
class ModelSmokeTests(unittest.TestCase):
    def test_v7_masks_text_and_documents_offline_with_original_offsets(self) -> None:
        # A fresh process ensures empty-cache offline settings precede all HF imports.
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, HF_HOME=directory, HF_MODULES_CACHE=str(Path(directory) / "modules"))
            result = subprocess.run(
                [sys.executable, __file__], cwd=Path(__file__).resolve().parents[1],
                env=env, capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def _smoke() -> None:
    import threading
    from unittest.mock import patch
    from zipfile import ZipFile

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core.detector import PIIDetector
    from app.core.masker import Masker, MaskingMode
    from app.processing.file_processor import FileProcessor

    with patch("socket.socket.connect", side_effect=AssertionError("Network prohibited")) as connect:
        detector = PIIDetector(Path("models/schift-ko-pii-v7"))
        detector.initialize()
        sample = "김민수는 서울특별시 강남구 테헤란로 521에 살고 전화번호는 010-1234-5678입니다."
        enabled = {"PERSON", "ADDRESS", "PHONE"}
        text = "처리 상태 정상.\n" * 180 + sample
        findings = detector.detect(text, enabled)
        expected = {"PERSON": "김민수", "ADDRESS": "서울특별시 강남구 테헤란로 521", "PHONE": "010-1234-5678"}
        for kind, value in expected.items():
            match = next(item for item in findings if item.type == kind and item.value == value)
            assert (match.start, match.end) == (text.index(value), text.index(value) + len(value))
            assert match.source == ("regex" if kind == "PHONE" else "model")

        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".txt", ".docx", ".xlsx", ".hwpx"):
                source = Path(directory) / f"sample{suffix}"
                if suffix == ".txt":
                    source.write_text(sample, encoding="utf-8")
                else:
                    with ZipFile(source, "w") as archive:
                        archive.writestr("content.xml", f'<document xmlns="urn:test"><t>{sample}</t></document>')
                original = source.read_bytes()
                processor = FileProcessor(detector, enabled, Masker(), threading.Event())
                analysis = processor.deidentify_file(source, MaskingMode.AUTO, "", False)
                output = processor.output_path(source)
                if suffix == ".txt":
                    masked = output.read_text(encoding="utf-8")
                else:
                    with ZipFile(output) as archive:
                        masked = archive.read("content.xml").decode()
                assert source.read_bytes() == original
                for kind, value in expected.items():
                    assert analysis.counts[kind] == 1
                    assert f"[{kind}_1]" in masked and value not in masked
        connect.assert_not_called()


if __name__ == "__main__":
    _smoke()
