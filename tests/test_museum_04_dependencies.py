import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PRODUCTION_PACKAGES = {
    "@mapbox/jsonlint-lines-primitives": ("2.0.3", "MIT"),
    "@mapbox/point-geometry": ("1.1.0", "ISC"),
    "@mapbox/tiny-sdf": ("2.2.0", "BSD-2-Clause"),
    "@mapbox/unitbezier": ("0.0.1", "BSD-2-Clause"),
    "@mapbox/vector-tile": ("2.0.5", "BSD-3-Clause"),
    "@mapbox/whoots-js": ("3.1.0", "ISC"),
    "@maplibre/geojson-vt": ("6.1.1", "ISC"),
    "@maplibre/maplibre-gl-style-spec": ("24.10.0", "ISC"),
    "@maplibre/maplibre-gl-style-spec/node_modules/@mapbox/unitbezier": ("1.0.0", "BSD-2-Clause"),
    "@maplibre/mlt": ("1.1.12", "(MIT OR Apache-2.0)"),
    "@maplibre/vt-pbf": ("4.3.2", "MIT"),
    "@maplibre/vt-pbf/node_modules/pbf": ("5.1.2", "BSD-3-Clause"),
    "@types/geojson": ("7946.0.16", "MIT"),
    "cookie": ("1.1.1", "MIT"),
    "earcut": ("3.2.3", "ISC"),
    "events": ("3.3.0", "MIT"),
    "gl-matrix": ("3.4.4", "MIT"),
    "graphology": ("0.26.0", "MIT"),
    "graphology-types": ("0.24.8", "MIT"),
    "graphology-utils": ("2.5.2", "MIT"),
    "json-stringify-pretty-compact": ("4.0.0", "MIT"),
    "kdbush": ("4.1.0", "ISC"),
    "maplibre-gl": ("5.24.0", "BSD-3-Clause"),
    "minimist": ("1.2.8", "MIT"),
    "murmurhash-js": ("1.0.0", "MIT"),
    "pbf": ("4.0.2", "BSD-3-Clause"),
    "potpack": ("2.1.0", "ISC"),
    "protocol-buffers-schema": ("3.6.1", "MIT"),
    "quickselect": ("3.0.0", "ISC"),
    "react": ("19.2.7", "MIT"),
    "react-dom": ("19.2.7", "MIT"),
    "react-router": ("7.18.1", "MIT"),
    "react-router-dom": ("7.18.1", "MIT"),
    "resolve-protobuf-schema": ("2.1.0", "MIT"),
    "scheduler": ("0.27.0", "MIT"),
    "set-cookie-parser": ("2.7.2", "MIT"),
    "sigma": ("3.0.3", "MIT"),
    "tinyqueue": ("3.0.0", "ISC"),
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

    def test_lock_records_complete_license_provenance_for_every_shipped_package(self) -> None:
        production = {
            path.removeprefix("node_modules/"): metadata
            for path, metadata in self.lock["packages"].items()
            if path.startswith("node_modules/") and metadata.get("dev") is not True
        }
        self.assertEqual(
            {name: (item["version"], item["license"]) for name, item in production.items()},
            EXPECTED_PRODUCTION_PACKAGES,
        )
        for name, metadata in production.items():
            with self.subTest(package=name):
                self.assertRegex(metadata.get("resolved", ""), rf"^https://registry\.npmjs\.org/.+/{re.escape(name.split('/')[-1])}-.+\.tgz$")
                self.assertTrue(metadata.get("integrity", "").startswith("sha512-"))

    def test_shipped_notice_covers_every_production_package_and_version(self) -> None:
        notice = (ROOT / "public" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Museum-Codex project code is all rights reserved", notice)
        self.assertIn("MIT License text", notice)
        for name, (version, _license) in EXPECTED_PRODUCTION_PACKAGES.items():
            with self.subTest(package=name):
                self.assertIn(f"`{name}`", notice)
                self.assertIn(version, notice)

    def test_project_remains_private_and_has_no_project_license_file(self) -> None:
        self.assertIs(self.package["private"], True)
        self.assertFalse(any((ROOT / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")))


if __name__ == "__main__":
    unittest.main()
