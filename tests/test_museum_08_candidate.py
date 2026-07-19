from __future__ import annotations

import json
import unittest
from collections import Counter

from museum_pipeline.art.candidate import (
    DEFAULT_OUTPUT,
    INPUT_PHYSICAL_TREE_HASH,
    INPUT_RELEASE,
    build_search_records,
    normalize_search_text,
    run_rollback_rehearsal,
    run_withdrawal_rehearsal,
    validate_museum_08_release,
)
from scripts.generate_release_integrity_ledger import physical_tree


class Museum08CandidateTests(unittest.TestCase):
    def test_search_scope_and_public_entity_counts_are_exact_regression_fixtures(self) -> None:
        records = build_search_records()
        self.assertEqual(
            {
                "artist": 12,
                "artwork": 44,
                "context": 31,
                "tour": 18,
                "place": 23,
                "relationship": 36,
                "path": 198,
                "page": 5,
            },
            Counter(item["entity_type"] for item in records),
        )
        self.assertEqual(len(records), len({item["id"] for item in records}))
        self.assertTrue(all("/assets/" not in json.dumps(item) for item in records))
        self.assertTrue(all(item["withdrawal_status"] == "active" for item in records))

    def test_unicode_normalization_is_deterministic(self) -> None:
        self.assertEqual("albrecht durer", normalize_search_text("  Albrecht DÜRER  "))
        self.assertEqual("阿尔布雷希特 丢勒", normalize_search_text("阿尔布雷希特·丢勒"))
        self.assertEqual("cafe", normalize_search_text("Café"))

    def test_withdrawal_and_rollback_rehearsals_are_synthetic_and_closed(self) -> None:
        withdrawal = run_withdrawal_rehearsal()
        self.assertTrue(withdrawal["synthetic_only"])
        self.assertFalse(withdrawal["real_records_modified"])
        self.assertEqual(
            {"media_asset", "relationship", "place_episode", "artwork_metadata"},
            {item["kind"] for item in withdrawal["scenarios"]},
        )
        self.assertTrue(all(item["reference_closure"] for item in withdrawal["scenarios"]))
        rollback = run_rollback_rehearsal()
        self.assertTrue(rollback["synthetic_only"])
        self.assertFalse(rollback["private_data"])
        self.assertEqual("zero_published_release_mutation", rollback["rpo"])
        self.assertGreaterEqual(len(rollback["recovery_checklist"]), 8)

    def test_predecessor_remains_byte_immutable(self) -> None:
        self.assertEqual(INPUT_PHYSICAL_TREE_HASH, physical_tree(INPUT_RELEASE)["hash"])

    def test_committed_candidate_is_physically_closed(self) -> None:
        self.assertTrue(DEFAULT_OUTPUT.is_dir(), "candidate release must be built before running this test")
        result = validate_museum_08_release(DEFAULT_OUTPUT)
        self.assertTrue(result["ok"], result["failures"][:8])
        self.assertEqual(8, result["search_shard_count"])
        self.assertLessEqual(result["search_index_gzip_bytes"], 150_000)
        self.assertEqual(16, result["route_template_count"])


if __name__ == "__main__":
    unittest.main()
