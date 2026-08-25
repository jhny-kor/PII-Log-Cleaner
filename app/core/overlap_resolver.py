from __future__ import annotations

from .models import Detection


_SOURCE_PRIORITY = {"regex": 0, "model": 1, "llm": 2}


def resolve_overlaps(detections: list[Detection]) -> list[Detection]:
    """Keep one authoritative offset range for every overlapping finding."""
    candidates = [item for item in detections if item.start >= 0 and item.end > item.start]
    candidates.sort(
        key=lambda item: (
            _SOURCE_PRIORITY.get(item.source, 9),
            item.start,
            -(item.end - item.start),
            -item.confidence,
        )
    )
    accepted: list[Detection] = []
    for candidate in candidates:
        if all(candidate.end <= current.start or candidate.start >= current.end for current in accepted):
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.start, item.end))
