from __future__ import annotations

import os
import shutil
import threading
import uuid
from collections import Counter
from pathlib import Path
from typing import Iterator

from app.core.masker import Masker
from app.core.models import Detection, FileAnalysis, PreviewRow
from app.core.overlap_resolver import resolve_overlaps

from .encoding import detect_encoding


class ProcessingStopped(RuntimeError):
    pass


class FileProcessor:
    CHUNK_CHARS = 1_048_576
    OVERLAP_CHARS = 1_024
    PREVIEW_TEXT_LIMIT = 1_000

    def __init__(self, detector: object, enabled: set[str], masker: Masker, stop_event: threading.Event) -> None:
        self.detector = detector
        self.enabled = enabled
        self.masker = masker
        self.stop_event = stop_event

    def analyze_file(self, path: Path, mode: str, custom_text: str, preview_limit: int) -> FileAnalysis:
        analysis = FileAnalysis(path=str(path))
        encoding = detect_encoding(path)
        with path.open("r", encoding=encoding, newline="") as source:
            for original, detections in self._segments(source):
                self._check_stopped()
                findings = resolve_overlaps(detections)
                analysis.replacements += len(findings)
                self._add_counts(analysis, findings)
                if len(analysis.previews) < preview_limit:
                    deidentified, _ = self.masker.apply(original, findings, mode, custom_text)
                    self._add_preview_rows(analysis, original, deidentified, findings, preview_limit)
        return analysis

    def deidentify_file(self, path: Path, mode: str, custom_text: str, backup: bool) -> FileAnalysis:
        analysis = FileAnalysis(path=str(path))
        encoding = detect_encoding(path)
        output = self.output_path(path)
        temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
        try:
            if backup:
                backup_dir = path.parent / "backup"
                backup_dir.mkdir(exist_ok=True)
                shutil.copy2(path, backup_dir / path.name)
            with path.open("r", encoding=encoding, newline="") as source, temporary.open(
                "w", encoding=encoding, newline=""
            ) as target:
                for original, detections in self._segments(source):
                    self._check_stopped()
                    findings = resolve_overlaps(detections)
                    deidentified, replacements = self.masker.apply(original, findings, mode, custom_text)
                    target.write(deidentified)
                    analysis.replacements += replacements
                    self._add_counts(analysis, findings)
            os.replace(temporary, output)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return analysis

    @staticmethod
    def output_path(path: Path) -> Path:
        return path.with_name(f"{path.stem}_deid{path.suffix}")

    def _segments(self, source: object) -> Iterator[tuple[str, list[Detection]]]:
        """Yield bounded text blocks, retaining a short look-ahead for giant single lines."""
        buffer = ""
        while True:
            self._check_stopped()
            incoming = source.read(self.CHUNK_CHARS)
            if not incoming:
                if buffer:
                    yield buffer, self.detector.detect(buffer, self.enabled)
                return
            buffer += incoming
            while len(buffer) > self.CHUNK_CHARS:
                target = len(buffer) - self.OVERLAP_CHARS
                newline = buffer.rfind("\n", 0, target + 1)
                if newline >= 0:
                    cut = newline + 1
                    segment = buffer[:cut]
                    buffer = buffer[cut:]
                    yield segment, self.detector.detect(segment, self.enabled)
                    continue

                all_findings = self.detector.detect(buffer, self.enabled)
                cut = target
                for finding in all_findings:
                    if finding.start < cut < finding.end:
                        cut = finding.start
                if cut == 0 and len(buffer) < self.CHUNK_CHARS * 4:
                    break
                # ponytail: a model entity longer than 4 MiB falls back to a bounded split; normal logs end at newlines.
                cut = max(cut, target)
                segment = buffer[:cut]
                safe_findings = [finding for finding in all_findings if finding.end <= cut]
                buffer = buffer[cut:]
                yield segment, safe_findings

    def _add_preview_rows(
        self,
        analysis: FileAnalysis,
        original: str,
        deidentified: str,
        findings: list[Detection],
        preview_limit: int,
    ) -> None:
        if len(analysis.previews) >= preview_limit:
            return
        originals = original.splitlines(keepends=True) or [original]
        replacements = deidentified.splitlines(keepends=True) or [deidentified]
        offset = 0
        for raw, masked in zip(originals, replacements):
            if len(analysis.previews) >= preview_limit:
                return
            end = offset + len(raw)
            line_findings = [
                Detection(item.type, item.value, item.start - offset, item.end - offset, item.confidence, item.source)
                for item in findings
                if offset <= item.start and item.end <= end
            ]
            analysis.previews.append(
                PreviewRow(
                    self._trim(raw.rstrip("\r\n")),
                    self._trim(masked.rstrip("\r\n")),
                    line_findings,
                )
            )
            offset = end

    def _check_stopped(self) -> None:
        if self.stop_event.is_set():
            raise ProcessingStopped()

    @staticmethod
    def _add_counts(analysis: FileAnalysis, findings: list[Detection]) -> None:
        for kind, count in Counter(item.type for item in findings).items():
            analysis.counts[kind] = analysis.counts.get(kind, 0) + count

    def _trim(self, value: str) -> str:
        return value if len(value) <= self.PREVIEW_TEXT_LIMIT else f"{value[: self.PREVIEW_TEXT_LIMIT - 1]}…"
