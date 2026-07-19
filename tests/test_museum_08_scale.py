from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from museum_pipeline.art.scale_fixture import (
    SYNTHETIC_PREFIX,
    build_scale_fixture,
    rebuild_search_shards,
    tree_files,
    validate_scale_fixture,
)
from scripts.scan_museum_08_synthetic_leakage import scan

ROOT = Path(__file__).resolve().parents[1]


class Museum08SyntheticScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="museum-08-scale-test-")
        cls.fixture = Path(cls.temporary.name) / "fixture"
        cls.result = build_scale_fixture(cls.fixture)
        cls.manifest = json.loads((cls.fixture / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_exact_scale_contract_and_physical_closure(self) -> None:
        self.assertTrue(self.result["ok"], self.result["failures"])
        self.assertEqual(
            {
                "artists": 500,
                "artworks": 5000,
                "search_records": 20000,
                "typed_relationships": 10000,
                "path_index_records": 50000,
            },
            self.result["counts"],
        )
        self.assertTrue(validate_scale_fixture(self.fixture)["ok"])
        self.assertEqual(0, self.manifest["media_files"])

    def test_bilingual_alias_transliteration_long_same_name_and_withdrawal_variants(self) -> None:
        search_paths = [self.fixture / item["path"] for item in self.manifest["shards"] if item["dataset"] == "search"]
        text = "\n".join(path.read_text(encoding="utf-8") for path in search_paths)
        self.assertIn('"zh-Hans"', text)
        self.assertIn('"approved_alias"', text)
        self.assertIn('"transliteration"', text)
        self.assertIn('"source_language"', text)
        self.assertIn("intentionally extended synthetic title", text)
        self.assertIn('"withdrawn":true', text)
        self.assertIn("Synthetic Artist 000000", text)
        self.assertGreaterEqual(text.count("Synthetic Artist 000000"), 2)

    def test_partial_search_rebuild_touches_only_affected_shard(self) -> None:
        before = tree_files(self.fixture)
        rebuilt = rebuild_search_shards(self.fixture, [f"{SYNTHETIC_PREFIX}artist:0000120"])
        after = tree_files(self.fixture)
        self.assertEqual(1, len(rebuilt))
        self.assertTrue(all(before[path] == after[path] for path in before if path not in rebuilt))

    def test_scale_fixture_is_excluded_from_public_bytes(self) -> None:
        result = scan([ROOT / "public"])
        self.assertTrue(result["ok"], result["failures"])

    def test_asset_reuse_prototype_uses_one_digest_for_two_release_references(self) -> None:
        prototype = json.loads((self.fixture / "asset-reuse-prototype.json").read_text(encoding="utf-8"))
        self.assertEqual("sha256", prototype["identity"])
        self.assertEqual(2, len(prototype["release_references"]))
        self.assertEqual(1, prototype["stored_byte_copies"])
        self.assertTrue(prototype["withdrawal_disables_reference_not_history"])


if __name__ == "__main__":
    unittest.main()
