from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from museum_pipeline.art.ux_release import (
    DEFAULT_OUTPUT,
    PREDECESSOR,
    PREDECESSOR_MANIFEST_SHA256,
    build_museum_09b_ux_release,
    validate_museum_09b_ux_release,
)
from museum_pipeline.hashing import sha256_file
from scripts.generate_release_integrity_ledger import physical_tree


class Museum09BUXReleaseTests(unittest.TestCase):
    def test_committed_successor_has_complete_narratives_and_zero_default_nodes(self) -> None:
        result = validate_museum_09b_ux_release(DEFAULT_OUTPUT)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(result["counts"], {"artists": 62, "artworks": 532, "relationships": 60, "episodes": 110, "tours": 18})
        self.assertEqual(result["audit"]["banned_primary_hits"], 0)
        self.assertEqual(result["audit"]["duplicate_full_intro_count"], 0)
        self.assertEqual(result["physical_tree"], physical_tree(DEFAULT_OUTPUT))
        config = json.loads((DEFAULT_OUTPUT / "relationship-explorer-config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["default_global_graph_node_count"], 0)
        self.assertLessEqual(len(config["starter_rotation"]["artist_ids"]), 9)

    def test_predecessor_is_still_byte_identical(self) -> None:
        self.assertEqual(sha256_file(PREDECESSOR / "manifest.json"), PREDECESSOR_MANIFEST_SHA256)

    def test_builder_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-09b-ux-test-") as temporary:
            output = Path(temporary) / "release"
            rebuilt = build_museum_09b_ux_release(output, update_ledger=False)
            committed = validate_museum_09b_ux_release(DEFAULT_OUTPUT)
            self.assertEqual(rebuilt["content_hash"], committed["content_hash"])
            self.assertEqual(rebuilt["manifest_sha256"], committed["manifest_sha256"])

    def test_expected_invalid_narrative_fixture_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-09b-ux-invalid-") as temporary:
            invalid = Path(temporary) / "release"
            shutil.copytree(DEFAULT_OUTPUT, invalid)
            document = json.loads((invalid / "artists.json").read_text(encoding="utf-8"))
            document["artists"][0]["public_intro"]["zh-Hans"] = "本公开档案只有元数据。"
            (invalid / "artists.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = validate_museum_09b_ux_release(invalid)
            self.assertFalse(result["ok"])
            self.assertTrue(any(item["code"] == "manifest_file_hash" for item in result["failures"]))


if __name__ == "__main__":
    unittest.main()
