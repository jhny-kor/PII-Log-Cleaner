from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Set before importing any model-related dependency so a packaged app never reaches the network.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.audit_log import app_logger, configure_application_logging
from app.ui.main_window import launch


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def main() -> int:
    configure_application_logging()
    app_logger.info("프로그램 시작")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--demo", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-regex-only", action="store_true", help=argparse.SUPPRESS)
    args, _unknown = parser.parse_known_args()
    return launch(bundle_root() / "models" / "schift-ko-pii-v6", args.allow_regex_only, args.demo)


if __name__ == "__main__":
    raise SystemExit(main())
