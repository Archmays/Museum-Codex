from __future__ import annotations

import unittest

from museum_pipeline.art.candidate import (
    run_rollback_rehearsal,
    run_withdrawal_rehearsal,
    simulate_synthetic_withdrawals,
)


class Museum08WithdrawalAndRollbackTests(unittest.TestCase):
    def test_four_synthetic_withdrawals_cascade_without_broken_references(self) -> None:
        simulation = simulate_synthetic_withdrawals()
        self.assertTrue(simulation["before_unchanged"])
        self.assertNotEqual(simulation["before_hash"], simulation["after_hash"])
        self.assertEqual(
            {
                "media_asset": True,
                "relationship": True,
                "place_episode": True,
                "artwork_metadata": True,
            },
            simulation["closure"],
        )
        after = simulation["after"]
        self.assertEqual([], after["relationships"])
        self.assertEqual([], after["paths"])
        self.assertEqual([], after["episodes"])
        self.assertTrue(after["artworks"][0]["no_image"])
        self.assertEqual(4, len(after["notices"]))

    def test_candidate_rehearsal_record_is_derived_from_the_closed_simulation(self) -> None:
        record = run_withdrawal_rehearsal()
        self.assertEqual("pass", record["status"])
        self.assertTrue(record["reference_closure"])
        self.assertTrue(record["old_release_immutable"])
        self.assertTrue(all(item["removed_from_new_release"] for item in record["scenarios"]))
        self.assertTrue(all(item["notice_updated"] for item in record["scenarios"]))

    def test_predecessor_rollback_closes_loader_routes_media_paths_map_and_hashes(self) -> None:
        record = run_rollback_rehearsal()
        self.assertEqual("pass", record["status"])
        for key in ("loader", "routes", "media", "paths", "map", "hash_closure"):
            self.assertEqual("pass", record[key], key)
        self.assertFalse(record["private_data"])
        self.assertLessEqual(record["rto_minutes"], 15)
        self.assertEqual("zero_published_release_mutation", record["rpo"])


if __name__ == "__main__":
    unittest.main()
