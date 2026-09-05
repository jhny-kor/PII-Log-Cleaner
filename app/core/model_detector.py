from __future__ import annotations

import importlib
import os
import re
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
        "schift_heads.json",
    )
    _LABELS = {
        "private_person": "PERSON",
        "person": "PERSON",
        "private_address": "ADDRESS",
        "address": "ADDRESS",
    }
    _PERSON_SURNAMES = frozenset("김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진지엄채원천방공현함변염여추도석선설마길연위표명기")
    _PERSON_STOPWORDS = frozenset(
        {
            "이메일",
            "이벤트",
            "주소값",
            "주민등록",
            "김밥",
            "김치",
            "박물관",
            "최대값",
            "정상값",
        }
    )

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir.resolve()
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
                module.set_model_id(str(self.model_dir))
                # 0.6.0 resolves the manifest and weights through this private hook.
                # Tokenizer/config/custom code load directly from the same local directory.
                module._hf_download = self._local_model_file
                module._load_model()
            except Exception as exc:  # Never show internals or source text in the user UI.
                raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.") from exc
            self._module = module

    def detect(self, text: str, enabled: set[str]) -> list[Detection]:
        if not (MODEL_TYPES & enabled) or not text:
            return []
        if self._module is None:
            raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.")

        try:
            # schift-ko-pii already tokenizes and overlaps long input internally.
            items = self._module.detect(text, postprocess=False, normalize=False, extended=False)
        except Exception as exc:
            raise ModelUnavailableError("개인정보 탐지 엔진을 초기화하지 못했습니다.") from exc

        findings: list[Detection] = []
        for item in items:
            label = self._LABELS.get(str(item.get("label", "")).lower())
            if not label or label not in enabled:
                continue
            start, end = int(item["start"]), int(item["end"])
            if start < 0 or end <= start or end > len(text):
                continue
            value = text[start:end]
            if label == "PERSON" and not self._is_person_candidate(value):
                continue
            findings.append(
                Detection(
                    label,
                    value,
                    start,
                    end,
                    float(item.get("score", 0.0)),
                    "model",
                )
            )
        return resolve_overlaps(findings)

    @classmethod
    def _is_person_candidate(cls, value: str) -> bool:
        value = value.strip()
        return (
            3 <= len(value) <= 4
            and re.fullmatch(r"[가-힣ㅇ]+", value) is not None
            and value[0] in cls._PERSON_SURNAMES
            and value not in cls._PERSON_STOPWORDS
        )

    def _local_model_file(self, filename: str) -> str:
        candidate = self.model_dir / filename
        if not candidate.is_file():
            raise FileNotFoundError(filename)
        return str(candidate)
