from __future__ import annotations

from pathlib import Path


class EncodingDetectionError(ValueError):
    pass


def detect_encoding(path: Path) -> str:
    """Return an encoding only when a known Korean log encoding decodes cleanly."""
    with path.open("rb") as source:
        sample = source.read(128 * 1024)
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp949", "euc_kr"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise EncodingDetectionError("인코딩을 자동으로 확인하지 못했습니다.")
