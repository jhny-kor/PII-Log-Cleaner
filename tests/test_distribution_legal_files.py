from __future__ import annotations

import hashlib
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

    def test_windows_build_selects_an_available_python_three_runtime_and_uses_brand_icon(self) -> None:
        build_script = (ROOT / "build-windows.ps1").read_text(encoding="utf-8")
        installer_script = (ROOT / "installer" / "PII-Log-Cleaner.iss").read_text(encoding="utf-8")

        self.assertIn('$script:PythonArguments = @("-3")', build_script)
        self.assertNotIn('"-3.11"', build_script)
        self.assertIn('Get-PythonApplications @("python.exe", "python", "python3.exe", "python3")', build_script)
        self.assertIn('Restore-ModelWeights $ModelSnapshot', build_script)
        self.assertIn('Assert-ModelSnapshot $ModelSnapshot', build_script)
        self.assertIn('Resolve-Path -LiteralPath $ModelSnapshot', build_script)
        self.assertIn("--icon $AppIcon", build_script)
        self.assertIn('$PyInstallerWork = Join-Path $BuildRoot "w"', build_script)
        self.assertIn('$PyInstallerDist = Join-Path $BuildRoot "p"', build_script)
        self.assertIn('--name "PII"', build_script)
        self.assertIn('& $Iscc $InstallerScript', build_script)
        self.assertNotIn('--output-dir=', build_script)
        self.assertIn("SetupIconFile=..\\resources\\icons\\branding\\pii-log-cleaner-icon.ico", installer_script)
        self.assertIn('#define MyAppExeName "PII.exe"', installer_script)
        self.assertIn('Source: "..\\build\\p\\PII\\*"', installer_script)

    def test_bundled_model_parts_match_the_recorded_sha256(self) -> None:
        model_dir = ROOT / "models" / "schift-ko-pii-v6"
        parts = sorted(model_dir.glob("model.safetensors.part-*"))
        expected = (model_dir / "model.safetensors.sha256").read_text(encoding="utf-8").split()[0]

        self.assertGreater(len(parts), 0)
        self.assertTrue(all(part.stat().st_size <= 50 * 1024 * 1024 for part in parts))
        digest = hashlib.sha256()
        for part in parts:
            with part.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        self.assertEqual(expected, digest.hexdigest())

    def test_transformers_and_hub_requirements_use_compatible_versions(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("transformers==5.15.0", requirements)
        self.assertIn("huggingface-hub>=1.5,<2", requirements)


if __name__ == "__main__":
    unittest.main()
