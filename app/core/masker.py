from __future__ import annotations

from collections import defaultdict

from .models import Detection
from .overlap_resolver import resolve_overlaps
from .policies import TOKEN_LABELS


class MaskingMode:
    AUTO = "auto"
    CUSTOM = "custom"
    PARTIAL = "partial"


class Masker:
    """Applies resolved offsets from right to left, never global string replacement."""

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = defaultdict(int)

    def apply(self, text: str, detections: list[Detection], mode: str, custom_text: str = "") -> tuple[str, int]:
        if mode == MaskingMode.CUSTOM and not custom_text.strip():
            raise ValueError("치환할 문자열을 입력해주세요.")
        resolved = resolve_overlaps(detections)
        result = text
        for finding in reversed(resolved):
            replacement = self._replacement(finding, mode, custom_text)
            result = result[: finding.start] + replacement + result[finding.end :]
        return result, len(resolved)

    def _replacement(self, finding: Detection, mode: str, custom_text: str) -> str:
        if mode == MaskingMode.CUSTOM:
            return custom_text
        if mode == MaskingMode.PARTIAL:
            return self._partial(finding.type, finding.value)
        key = (finding.type, finding.value)
        if key not in self._tokens:
            self._counters[finding.type] += 1
            self._tokens[key] = f"[{TOKEN_LABELS.get(finding.type, finding.type)}_{self._counters[finding.type]}]"
        return self._tokens[key]

    @staticmethod
    def _partial(kind: str, value: str) -> str:
        if kind == "PHONE":
            digits = "".join(char for char in value if char.isdigit())
            prefix = 3 if digits.startswith("01") else 2
            return f"{digits[:prefix]}-{'*' * max(1, len(digits) - prefix - 4)}-{digits[-4:]}"
        if kind == "EMAIL" and "@" in value:
            local, domain = value.split("@", 1)
            return f"{local[: min(3, max(1, len(local)))]}***@{domain}"
        if kind == "RRN":
            digits = value.replace("-", "")
            return f"{digits[:6]}-{'*' * max(0, len(digits) - 6)}"
        if kind == "ACCOUNT":
            pieces = value.split("-")
            if len(pieces) > 1:
                return "-".join([pieces[0], *["***"] * (len(pieces) - 2), f"***{pieces[-1][-3:]}"])
            return f"{value[:3]}{'*' * max(1, len(value) - 6)}{value[-3:]}"
        if kind == "IP":
            pieces = value.split(".")
            return f"{pieces[0]}.{pieces[1]}.*.*" if len(pieces) == 4 else "*" * len(value)
        if kind in {"API_KEY", "PASSWORD"}:
            return "********"
        if kind == "URL":
            return "https://***" if value.lower().startswith("https://") else "http://***"
        return "*" * max(3, len(value))
