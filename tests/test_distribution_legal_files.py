from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionLegalFilesTests(unittest.TestCase):
    def test_legal_files_are_present_and_packaged(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        notice_text = (ROOT / "NOTICE").read_text(encoding="utf-8")
        build_script = (ROOT / "build-windows.ps1").read_text(encoding="utf-8")

        self.assertIn("Apache License\n                           Version 2.0", license_text)
        self.assertIn("Copyright 2026 jhny-kor", notice_text)
        self.assertIn("Schift License v2.0", notice_text)
        for variable in ("$ProjectLicense", "$ProjectNotice", "$ThirdPartyNotices"):
            self.assertIn(f'--add-data "{variable};."', build_script)


if __name__ == "__main__":
    unittest.main()
