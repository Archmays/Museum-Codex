from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.scan_museum_08_hardcoded_counts import scan_hardcoded_counts
from scripts.scan_museum_08_privacy import scan_privacy

ROOT = Path(__file__).resolve().parents[1]


class Museum08PrivacyScannerTests(unittest.TestCase):
    def test_production_source_uses_only_explicit_local_preferences(self) -> None:
        result = scan_privacy(ROOT / "src")
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(
            ["museum-locale", "museum-low-bandwidth"],
            result["observed_local_storage_keys"],
        )
        self.assertFalse(result["analytics_used"])
        self.assertFalse(result["query_history_stored"])
        self.assertFalse(result["user_geolocation_used"])

    def test_rejects_query_history_and_geolocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "bad.ts"
            fixture.write_text(
                'localStorage.setItem("museum-search-history", query); '
                "navigator.geolocation.getCurrentPosition(usePosition);\n",
                encoding="utf-8",
            )
            result = scan_privacy(fixture, include_dependencies=False)
        self.assertFalse(result["ok"])
        self.assertEqual(
            {"forbidden_local_storage_key", "geolocation_api"},
            {failure["code"] for failure in result["failures"]},
        )

    def test_resolves_minified_local_preference_constants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "bundle.js"
            fixture.write_text(
                "x=0,Qn=`museum-locale`;localStorage.getItem(Qn);"
                "var rr=`museum-low-bandwidth`;localStorage.setItem(rr,`true`);\n",
                encoding="utf-8",
            )
            result = scan_privacy(fixture, include_dependencies=False)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(
            ["museum-locale", "museum-low-bandwidth"],
            result["observed_local_storage_keys"],
        )


class Museum08HardcodedCountScannerTests(unittest.TestCase):
    def test_shared_runtime_has_no_current_release_limits(self) -> None:
        result = scan_hardcoded_counts()
        self.assertTrue(result["ok"], result["failures"])

    def test_rejects_semantic_runtime_limit_but_not_layout_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "loader.ts"
            bad_copy = root / "copy.ts"
            good = root / "layout.ts"
            bad.write_text("if (artistCount !== 12) throw new Error('limit');\n", encoding="utf-8")
            bad_copy.write_text('const intro = "Twelve artists appear as nodes";\n', encoding="utf-8")
            good.write_text("const cardGap = 12;\n", encoding="utf-8")
            result = scan_hardcoded_counts([root])
        self.assertFalse(result["ok"])
        self.assertEqual(2, len(result["failures"]))
        self.assertTrue(any("artistCount !== 12" in item["excerpt"] for item in result["failures"]))
        self.assertTrue(any("Twelve artists" in item["excerpt"] for item in result["failures"]))


if __name__ == "__main__":
    unittest.main()
