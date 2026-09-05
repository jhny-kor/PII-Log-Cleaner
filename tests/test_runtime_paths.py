from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.model_detector import ModelUnavailableError, OfflineSchiftDetector
from app.runtime import bundle_root


class RuntimePathTests(unittest.TestCase):
    def test_bundle_root_uses_pyinstaller_data_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.runtime.sys.frozen", True, create=True), patch(
                "app.runtime.sys._MEIPASS", directory, create=True
            ):
                self.assertEqual(bundle_root(), Path(directory))

    def test_model_loader_uses_bundled_weights_instead_of_the_hub(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            for name in OfflineSchiftDetector._REQUIRED_FILES:
                (model_dir / name).write_bytes(b"model")
            detector = OfflineSchiftDetector(model_dir)
            model = SimpleNamespace()
            loaded = []

            def set_model_id(path: str) -> None:
                model.HF_MODEL_ID = path
                model.cached_model = None

            model.set_model_id = set_model_id
            model.cached_model = "previous model"

            def load_model() -> None:
                self.assertIsNone(model.cached_model)
                self.assertEqual(model.HF_MODEL_ID, str(model_dir.resolve()))
                self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
                self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")
                loaded.extend(model._hf_download(name) for name in ("schift_heads.json", "model.safetensors"))

            model._load_model = load_model

            with patch("app.core.model_detector.importlib.import_module", return_value=model) as imports, patch.dict(
                os.environ, {"HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"}
            ):
                detector.load()
                detector.load()

            imports.assert_called_once_with("schift_ko_pii.detect")
            self.assertEqual(loaded, [str(model_dir.resolve() / name) for name in ("schift_heads.json", "model.safetensors")])
            with self.assertRaises(FileNotFoundError):
                model._hf_download("missing.json")

    def test_model_loader_rejects_snapshot_without_v7_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            for name in OfflineSchiftDetector._REQUIRED_FILES:
                if name != "schift_heads.json":
                    (model_dir / name).write_bytes(b"model")
            with patch("app.core.model_detector.importlib.import_module") as imports:
                with self.assertRaises(ModelUnavailableError):
                    OfflineSchiftDetector(model_dir).load()
            imports.assert_not_called()

    def test_model_detector_uses_package_windowing_once_per_file_segment(self) -> None:
        calls: list[str] = []

        def detect(text: str, **_kwargs: object) -> list[dict[str, object]]:
            calls.append(text)
            return [{"label": "private_person", "start": 0, "end": 3, "score": 1.0}]

        detector = OfflineSchiftDetector(Path("/bundled-model"))
        detector._module = SimpleNamespace(detect=detect)
        text = "김민수" * 5_000

        findings = detector.detect(text, {"PERSON"})

        self.assertEqual(calls, [text])
        self.assertEqual([(item.type, item.start, item.end) for item in findings], [("PERSON", 0, 3)])

    def test_model_detector_filters_non_name_person_spans(self) -> None:
        text = "123 이메일 김민수 김ㅇㅇ"

        def detect(_text: str, **_kwargs: object) -> list[dict[str, object]]:
            return [
                {"label": "private_person", "start": 0, "end": 3, "score": 0.99},
                {"label": "private_person", "start": 4, "end": 7, "score": 0.99},
                {"label": "private_person", "start": 8, "end": 11, "score": 0.99},
                {"label": "private_person", "start": 12, "end": 15, "score": 0.99},
            ]

        detector = OfflineSchiftDetector(Path("/bundled-model"))
        detector._module = SimpleNamespace(detect=detect)

        findings = detector.detect(text, {"PERSON"})

        self.assertEqual([item.value for item in findings], ["김민수", "김ㅇㅇ"])


if __name__ == "__main__":
    unittest.main()
