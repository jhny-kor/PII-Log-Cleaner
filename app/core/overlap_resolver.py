from __future__ import annotations

from bisect import bisect_left

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
    accepted_starts: list[int] = []
    for candidate in candidates:
        index = bisect_left(accepted_starts, candidate.start)
        if index and accepted[index - 1].end > candidate.start:
            continue
        if index < len(accepted) and accepted[index].start < candidate.end:
            continue
        accepted.insert(index, candidate)
        accepted_starts.insert(index, candidate.start)
    return accepted
