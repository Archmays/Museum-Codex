import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PRODUCTION_PACKAGES = {
    "cookie": "1.1.1",
    "events": "3.3.0",
    "graphology": "0.26.0",
    "graphology-types": "0.24.8",
    "graphology-utils": "2.5.2",
    "react": "19.2.7",
    "react-dom": "19.2.7",
    "react-router": "7.18.1",
    "react-router-dom": "7.18.1",
    "scheduler": "0.27.0",
    "set-cookie-parser": "2.7.2",
    "sigma": "3.0.3",
}


class Museum04DependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

    def test_graph_dependencies_are_exact_stable_versions(self) -> None:
        self.assertEqual(self.package["dependencies"]["graphology"], "0.26.0")
        self.assertEqual(self.package["dependencies"]["sigma"], "3.0.3")
        for version in self.package["dependencies"].values():
            self.assertRegex(version, r"^\d+\.\d+\.\d+$")
            self.assertNotRegex(version, r"(?i)(alpha|beta|rc)")

    def test_lock_records_complete_mit_provenance_for_every_shipped_package(self) -> None:
        production = {
            path.removeprefix("node_modules/"): metadata
            for path, metadata in self.lock["packages"].items()
            if path.startswith("node_modules/") and metadata.get("dev") is not True
        }
        self.assertEqual({name: item["version"] for name, item in production.items()}, EXPECTED_PRODUCTION_PACKAGES)
        for name, metadata in production.items():
            with self.subTest(package=name):
                self.assertEqual(metadata.get("license"), "MIT")
                self.assertRegex(metadata.get("resolved", ""), rf"^https://registry\.npmjs\.org/.+/{re.escape(name.split('/')[-1])}-.+\.tgz$")
                self.assertTrue(metadata.get("integrity", "").startswith("sha512-"))

    def test_shipped_notice_covers_every_production_package_and_version(self) -> None:
        notice = (ROOT / "public" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Museum-Codex project code is all rights reserved", notice)
        self.assertIn("MIT License text", notice)
        for name, version in EXPECTED_PRODUCTION_PACKAGES.items():
            with self.subTest(package=name):
                self.assertIn(f"`{name}`", notice)
                self.assertIn(version, notice)

    def test_project_remains_private_and_has_no_project_license_file(self) -> None:
        self.assertIs(self.package["private"], True)
        self.assertFalse(any((ROOT / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")))


if __name__ == "__main__":
    unittest.main()
