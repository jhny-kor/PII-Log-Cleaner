from __future__ import annotations

from pathlib import Path


SUPPORTED_EXTENSIONS = (
    ".log",
    ".txt",
    ".out",
    ".csv",
    ".sql",
    ".xls",
    ".xlsx",
    ".docx",
    ".doc",
    ".hwp",
    ".hwpx",
)

TYPE_LABELS = {
    "PERSON": "이름",
    "RRN": "주민등록번호",
    "PHONE": "전화번호",
    "IP": "IP 주소",
    "ADDRESS": "주소",
    "ACCOUNT": "계좌번호",
    "URL": "URL",
    "EMAIL": "이메일",
    "DATE": "날짜",
    "API_KEY": "API Key / 비밀번호",
    "PASSWORD": "API Key / 비밀번호",
    "IDENTIFIER": "기타 식별정보",
}

UI_TYPE_TO_CODES = {
    "이름": {"PERSON"},
    "주민등록번호": {"RRN"},
    "전화번호": {"PHONE"},
    "IP 주소": {"IP"},
    "주소": {"ADDRESS"},
    "계좌번호": {"ACCOUNT"},
    "URL": {"URL"},
    "이메일": {"EMAIL"},
    "날짜": {"DATE"},
    "API Key / 비밀번호": {"API_KEY", "PASSWORD"},
    "기타 식별정보": {"IDENTIFIER"},
}

TOKEN_LABELS = {
    "PERSON": "PERSON",
    "RRN": "RRN",
    "PHONE": "PHONE",
    "IP": "IP",
    "ADDRESS": "ADDRESS",
    "ACCOUNT": "ACCOUNT",
    "URL": "URL",
    "EMAIL": "EMAIL",
    "DATE": "DATE",
    "API_KEY": "API_KEY",
    "PASSWORD": "PASSWORD",
    "IDENTIFIER": "IDENTIFIER",
}

MODEL_TYPES = {"PERSON", "ADDRESS", "IDENTIFIER"}


def enabled_codes(labels: set[str]) -> set[str]:
    """Translate visible Korean checkbox labels to detector type codes."""
    return {code for label in labels for code in UI_TYPE_TO_CODES[label]}


def is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
