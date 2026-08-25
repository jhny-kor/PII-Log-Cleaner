from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.core.models import FileAnalysis
from app.core.policies import TYPE_LABELS


def write_csv_report(analyses: list[FileAnalysis], destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    report = destination / f"pii_report_{datetime.now():%Y%m%d_%H%M%S}.csv"
    columns = ["파일", *[TYPE_LABELS[key] for key in ("PERSON", "PHONE", "RRN", "IP", "EMAIL")], "총 탐지"]
    with report.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for analysis in analyses:
            counts = Counter(analysis.counts)
            writer.writerow(
                {
                    "파일": Path(analysis.path).name,
                    TYPE_LABELS["PERSON"]: counts["PERSON"],
                    TYPE_LABELS["PHONE"]: counts["PHONE"],
                    TYPE_LABELS["RRN"]: counts["RRN"],
                    TYPE_LABELS["IP"]: counts["IP"],
                    TYPE_LABELS["EMAIL"]: counts["EMAIL"],
                    "총 탐지": sum(counts.values()),
                }
            )
    return report
