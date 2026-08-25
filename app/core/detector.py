from __future__ import annotations

from pathlib import Path

from .model_detector import ModelUnavailableError, OfflineSchiftDetector
from .models import Detection
from .overlap_resolver import resolve_overlaps
from .policies import MODEL_TYPES
from .regex_detector import RegexDetector


class PIIDetector:
    """Composes structured regex findings with local-only NER findings."""

    def __init__(self, model_dir: Path, allow_regex_only: bool = False) -> None:
        self.regex = RegexDetector()
        self.model = OfflineSchiftDetector(model_dir)
        self.allow_regex_only = allow_regex_only
        self.model_ready = False

    def initialize(self) -> None:
        try:
            self.model.load()
            self.model_ready = True
        except ModelUnavailableError:
            if not self.allow_regex_only:
                raise

    def detect(self, text: str, enabled: set[str]) -> list[Detection]:
        findings = self.regex.detect(text, enabled)
        if self.model_ready and MODEL_TYPES & enabled:
            findings.extend(self.model.detect(text, enabled))
        return resolve_overlaps(findings)
