from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_museum_04_scale_fixture import (
    PROFILES,
    deterministic_sample_hash,
    iter_edges,
    iter_nodes,
    scale_plan,
    summary,
    write_fixture,
)


class Museum04ScaleFixtureTests(unittest.TestCase):
    def test_profiles_and_visible_caps_are_exact(self) -> None:
        self.assertEqual((1_000, 5_000), PROFILES["1k"])
        self.assertEqual((10_000, 60_000), PROFILES["10k"])
        self.assertEqual((50_000, 300_000), PROFILES["50k"])
        self.assertEqual((150, 600), (scale_plan("1k", "mobile").visible_vertex_cap, scale_plan("1k", "mobile").visible_edge_cap))
        self.assertEqual((300, 1_200), (scale_plan("1k", "desktop").visible_vertex_cap, scale_plan("1k", "desktop").visible_edge_cap))
        self.assertEqual("capped_progressive", scale_plan("1k", "mobile").rendering_mode)
        self.assertEqual("load_model_render_capped_progressive_neighborhood", scale_plan("1k", "mobile").strategy)

    def test_large_profiles_never_request_a_full_initial_render(self) -> None:
        for profile in PROFILES:
            for device in ("mobile", "desktop"):
                self.assertFalse(scale_plan(profile, device).full_initial_render)
        self.assertFalse(scale_plan("10k", "desktop").full_render_request_allowed)
        self.assertFalse(scale_plan("50k", "mobile").full_render_request_allowed)
        self.assertEqual("refuse_full_render_use_partition_or_list", scale_plan("50k", "mobile").strategy)

    def test_records_preserve_representative_governance_fields(self) -> None:
        node = next(iter_nodes(2))
        edge = next(iter_edges(2, 1))
        self.assertTrue(node["synthetic"])
        self.assertEqual({"zh-Hans", "en"}, set(node["labels"]))
        self.assertEqual("C", edge["evidence_level"])
        self.assertFalse(edge["is_algorithmic"])
        self.assertIsNone(edge["historical_relationship_strength"])
        self.assertIsNone(edge["computational_similarity"])
        for field in (
            "evidence_confidence",
            "curatorial_relevance",
            "claim_ids",
            "evidence_ids",
            "source_ids",
            "limitations",
            "what_it_does_not_mean",
        ):
            self.assertIn(field, edge)

    def test_one_thousand_profile_is_deterministic_unique_and_connected(self) -> None:
        vertices, edge_count = PROFILES["1k"]
        edges = list(iter_edges(vertices, edge_count))
        pairs = {(edge["source_artist_id"], edge["target_artist_id"]) for edge in edges}
        touched = {endpoint for pair in pairs for endpoint in pair}
        self.assertEqual(edge_count, len(edges))
        self.assertEqual(edge_count, len(pairs))
        self.assertEqual(vertices, len(touched))
        self.assertEqual(deterministic_sample_hash("1k"), deterministic_sample_hash("1k"))

    def test_full_fixture_writer_emits_exact_counts_and_is_not_shipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "scale.json"
            write_fixture("1k", target)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertTrue(payload["synthetic"])
        self.assertFalse(payload["shipped"])
        self.assertEqual(1_000, len(payload["nodes"]))
        self.assertEqual(5_000, len(payload["edges"]))

    def test_summary_declares_non_shipping_and_field_preservation(self) -> None:
        payload = summary("50k")
        self.assertFalse(payload["shipped"])
        self.assertEqual({"vertices": 50_000, "edges": 300_000}, payload["counts"])
        self.assertIn("computational_similarity", payload["governance_fields_preserved"])


if __name__ == "__main__":
    unittest.main()
