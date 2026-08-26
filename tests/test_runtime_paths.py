from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.model_detector import OfflineSchiftDetector
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
            hub = SimpleNamespace(hf_hub_download=lambda *_args, **_kwargs: "network")
            model = SimpleNamespace(HF_MODEL_ID="", AutoTokenizer=None, AutoConfig=None)
            loaded = []

            def load_model() -> None:
                loaded.append(hub.hf_hub_download(model.HF_MODEL_ID, "model.safetensors"))

            model._load_model = load_model

            def import_module(name: str) -> object:
                return model if name == "schift_ko_pii.detect" else hub

            with patch("app.core.model_detector.importlib.import_module", side_effect=import_module):
                detector.load()

            self.assertEqual(loaded, [str(model_dir / "model.safetensors")])

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
