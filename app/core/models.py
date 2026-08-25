from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Detection:
    type: str
    value: str
    start: int
    end: int
    confidence: float
    source: str


class Detector(Protocol):
    def detect(self, text: str, enabled: set[str]) -> list[Detection]: ...


@dataclass(slots=True)
class PreviewRow:
    original: str
    deidentified: str
    detections: list[Detection]


@dataclass(slots=True)
class FileAnalysis:
    path: str
    counts: dict[str, int] = field(default_factory=dict)
    previews: list[PreviewRow] = field(default_factory=list)
    replacements: int = 0


@dataclass(slots=True)
class RunResult:
    status: str
    files: list[FileAnalysis] = field(default_factory=list)
    error: str | None = None
    report_path: str | None = None

    @property
    def detection_count(self) -> int:
        return sum(sum(file.counts.values()) for file in self.files)

    @property
    def replacement_count(self) -> int:
        return sum(file.replacements for file in self.files)
