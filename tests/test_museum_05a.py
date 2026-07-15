from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from museum_pipeline.art.public_release import DEFAULT_OUTPUT
from scripts.validate_museum_05a import ROOT, validate_museum_05a


class Museum05AValidationTests(unittest.TestCase):
    def test_formal_gallery_release_and_routes_pass(self) -> None:
        result = validate_museum_05a(DEFAULT_OUTPUT, ROOT)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(12, result["counts"]["artist_pages"])
        self.assertEqual(44, result["counts"]["artwork_routes"])
        self.assertEqual(0, result["counts"]["blocked_runtime_assets"])

    def test_invalid_or_selectively_edited_release_fails_at_the_m04_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / "release"
            release.mkdir()
            # The formal M04 validator must fail closed before the M05A consumer
            # can accept a copied or selectively edited bundle.
            (release / "manifest.json").write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")
            result = validate_museum_05a(release, ROOT)
            self.assertFalse(result["ok"])
            self.assertEqual("m05a_release_invalid", result["failures"][0]["code"])


if __name__ == "__main__":
    unittest.main()
