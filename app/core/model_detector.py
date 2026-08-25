from __future__ import annotations

import importlib
import os
import threading
from pathlib import Path

from .models import Detection
from .overlap_resolver import resolve_overlaps
from .policies import MODEL_TYPES


class ModelUnavailableError(RuntimeError):
    pass


class OfflineSchiftDetector:
    """Adapter around the bundled schift-ko-pii runtime with Hub access removed."""

    _REQUIRED_FILES = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "model.safetensors",
        "modeling_lfm2_bidirectional.py",
    )
    _LABELS = {
        "private_person": "PERSON",
        "person": "PERSON",
        "private_address": "ADDRESS",
        "address": "ADDRESS",
        "private_organization": "IDENTIFIER",
        "organization": "IDENTIFIER",
    }

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._module = None
        self._lock = threading.Lock()

    def load(self) -> None:
        missing = [name for name in self._REQUIRED_FILES if not (self.model_dir / name).is_file()]
        if missing:
            raise ModelUnavailableError("필수 모델 파일을 찾을 수 없습니다.")

        # Must be set before any Hugging Face dependency is imported.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        with self._lock:
            if self._module is not None:
                return
            try:
                module = importlib.import_module("schift_ko_pii.detect")
                module.HF_MODEL_ID = str(self.model_dir)
                module.hf_hub_download = self._local_model_file
                self._force_local_loading(module, "AutoTokenizer")
                self._force_local_loading(module, "AutoConfig")
                loader = getattr(module, "_load_model", None)
                if callable(loader):
                    loader()
            except Exception as exc:  # Never show internals or source text in the user UI.
                raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.") from exc
            self._module = module

    def detect(self, text: str, enabled: set[str]) -> list[Detection]:
        if not (MODEL_TYPES & enabled) or not text:
            return []
        if self._module is None:
            raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.")

        findings: list[Detection] = []
        # The model's own tokenizer-level overlap handles entities inside each window.
        for start in range(0, len(text), 7_500):
            chunk = text[start : start + 8_000]
            try:
                items = self._module.detect(chunk, postprocess=False, normalize=False)
            except Exception as exc:
                raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.") from exc
            for item in items:
                label = self._LABELS.get(str(item.get("label", "")).lower())
                if not label or label not in enabled:
                    continue
                local_start, local_end = int(item["start"]), int(item["end"])
                if local_start < 0 or local_end <= local_start or local_end > len(chunk):
                    continue
                findings.append(
                    Detection(
                        label,
                        chunk[local_start:local_end],
                        start + local_start,
                        start + local_end,
                        float(item.get("score", 0.0)),
                        "model",
                    )
                )
        return resolve_overlaps(findings)

    def _local_model_file(self, _repo_id: str, filename: str, **_kwargs: object) -> str:
        candidate = self.model_dir / filename
        if not candidate.is_file():
            raise FileNotFoundError(filename)
        return str(candidate)

    @staticmethod
    def _force_local_loading(module: object, name: str) -> None:
        loader_class = getattr(module, name, None)
        original = getattr(loader_class, "from_pretrained", None)
        if not callable(original):
            return

        def local_from_pretrained(path: str, *args: object, **kwargs: object) -> object:
            kwargs["local_files_only"] = True
            return original(path, *args, **kwargs)

        loader_class.from_pretrained = local_from_pretrained
