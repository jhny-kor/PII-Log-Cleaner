from __future__ import annotations

import ipaddress
import re

from .models import Detection


class RegexDetector:
    """Offline detector for structured values; no detected values are logged."""

    _RRN = re.compile(r"(?<!\d)(?P<value>\d{6}-?\d{7})(?!\d)")
    _PHONE = re.compile(
        r"(?<!\d)(?P<value>(?:01[016789][-\s]?\d{3,4}[-\s]?\d{4}|0(?:2|[3-6][1-5]|70)[-\s]?\d{3,4}[-\s]?\d{4}))(?!\d)"
    )
    _EMAIL = re.compile(
        r"(?<![\w.+-])(?P<value>[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+)"
    )
    _IP = re.compile(r"(?<![\w.])(?P<value>(?:\d{1,3}\.){3}\d{1,3})(?![\w.])")
    _URL = re.compile(r"(?<![\w@])(?P<value>https?://[^\s'\"<>]+)", re.IGNORECASE)
    _DATE = re.compile(r"(?<!\d)(?P<value>(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2})(?!\d)")
    _SECRET = re.compile(
        r"(?P<key>api[_-]?key|apikey|api-key|token|access[_-]?token|secret|password|passwd|pwd|authorization)\s*[:=]\s*(?P<value>(?:Bearer\s+)?[^\s,;]+)",
        re.IGNORECASE,
    )
    _ACCOUNT = re.compile(
        r"(?P<key>account|acct|계좌(?:번호)?)\s*[:=]\s*(?P<value>\d{2,6}(?:-\d{2,6}){1,3}|\d{10,18})",
        re.IGNORECASE,
    )
    _NON_RRN_KEY = re.compile(
        r"(?:order(?:[_-]?(?:no|number))?|version|build|transaction|invoice)\s*[:=]\s*$", re.IGNORECASE
    )
    _NON_IP_KEY = re.compile(r"(?:version|build|release)\s*[:=]\s*$", re.IGNORECASE)

    def detect(self, text: str, enabled: set[str]) -> list[Detection]:
        findings: list[Detection] = []
        if "RRN" in enabled:
            findings.extend(self._rrns(text))
        if "PHONE" in enabled:
            findings.extend(self._find(text, self._PHONE, "PHONE"))
        if "EMAIL" in enabled:
            findings.extend(self._find(text, self._EMAIL, "EMAIL"))
        if "IP" in enabled:
            findings.extend(self._ips(text))
        if "URL" in enabled:
            findings.extend(self._find(text, self._URL, "URL"))
        if "DATE" in enabled:
            findings.extend(self._find(text, self._DATE, "DATE"))
        if {"API_KEY", "PASSWORD"} & enabled:
            findings.extend(self._secrets(text, enabled))
        if "ACCOUNT" in enabled:
            findings.extend(self._accounts(text))
        return findings

    @staticmethod
    def _has_context(pattern: re.Pattern[str], text: str, start: int) -> bool:
        return bool(pattern.search(text[max(0, start - 40) : start]))

    @staticmethod
    def _rrn_checksum_valid(value: str) -> bool:
        digits = value.replace("-", "")
        if len(digits) != 13 or not digits.isdigit():
            return False
        weights = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
        check = (11 - sum(int(digit) * weight for digit, weight in zip(digits[:12], weights)) % 11) % 10
        return check == int(digits[-1])

    def _rrns(self, text: str) -> list[Detection]:
        findings: list[Detection] = []
        for match in self._RRN.finditer(text):
            value = match.group("value")
            if self._has_context(self._NON_RRN_KEY, text, match.start()):
                continue
            confidence = 1.0 if self._rrn_checksum_valid(value) else 0.85
            findings.append(Detection("RRN", value, match.start("value"), match.end("value"), confidence, "regex"))
        return findings

    def _ips(self, text: str) -> list[Detection]:
        findings: list[Detection] = []
        for match in self._IP.finditer(text):
            value = match.group("value")
            if self._has_context(self._NON_IP_KEY, text, match.start()):
                continue
            try:
                ipaddress.IPv4Address(value)
            except ipaddress.AddressValueError:
                continue
            findings.append(Detection("IP", value, match.start("value"), match.end("value"), 1.0, "regex"))
        return findings

    def _secrets(self, text: str, enabled: set[str]) -> list[Detection]:
        findings: list[Detection] = []
        password_keys = {"password", "passwd", "pwd"}
        for match in self._SECRET.finditer(text):
            kind = "PASSWORD" if match.group("key").lower().replace("-", "_") in password_keys else "API_KEY"
            if kind not in enabled:
                continue
            value = match.group("value")
            findings.append(Detection(kind, value, match.start("value"), match.end("value"), 1.0, "regex"))
        return findings

    def _accounts(self, text: str) -> list[Detection]:
        return [
            Detection("ACCOUNT", match.group("value"), match.start("value"), match.end("value"), 0.95, "regex")
            for match in self._ACCOUNT.finditer(text)
        ]

    @staticmethod
    def _find(text: str, pattern: re.Pattern[str], kind: str) -> list[Detection]:
        return [
            Detection(kind, match.group("value"), match.start("value"), match.end("value"), 1.0, "regex")
            for match in pattern.finditer(text)
        ]
