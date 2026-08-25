from __future__ import annotations

import logging
import os
from pathlib import Path


app_logger = logging.getLogger("pii_log_cleaner")


def configure_application_logging() -> None:
    """Create a local operational log that intentionally never receives source text or paths."""
    if app_logger.handlers:
        return
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "PII Log Cleaner"
    root.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(root / "application.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
