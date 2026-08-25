from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def _database_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "PII Log Cleaner"
    root.mkdir(parents=True, exist_ok=True)
    return root / "history.db"


class HistoryStore:
    def __init__(self, database: Path | None = None) -> None:
        self.database = database or _database_path()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY,
                    executed_at TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    detection_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds REAL NOT NULL
                )
                """
            )
            connection.commit()

    def add(
        self,
        target_path: str,
        file_count: int,
        detection_count: int,
        status: str,
        duration_seconds: float,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO runs VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target_path, file_count, detection_count, status, duration_seconds),
            )
            connection.commit()

    def recent(self, limit: int = 5) -> list[tuple[str, str, str]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT executed_at, target_path, status FROM runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [(str(item[0]), str(item[1]), str(item[2])) for item in rows]

    def all(self) -> list[tuple[str, str, int, int, str, float]]:
        with closing(self._connect()) as connection:
            return list(
                connection.execute(
                    "SELECT executed_at, target_path, file_count, detection_count, status, duration_seconds FROM runs ORDER BY id DESC"
                )
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)
