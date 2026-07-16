from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from museum_pipeline.art.pathways import (
    ALGORITHM_VERSION,
    DEFAULT_OUTPUT,
    INPUT_RELEASE_HASH,
    INPUT_RELEASE_ID,
    MAX_EXPANSIONS,
    RELEASE_ID,
    build_graph_input,
    default_query,
    find_paths,
    review_ab_leads,
    validate_museum_06_release,
    _build_artifacts,
    _validate_path_semantics,
)
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import canonical_schema_path, validate_record


ARTISTS = ["artist:a", "artist:b", "artist:c", "artist:d", "artist:e"]


def graph(*edges: dict, artist_ids: list[str] | None = None) -> dict:
    artist_ids = artist_ids or ARTISTS
    artists = [
        {
            "id": artist_id,
            "labels": {"zh-Hans": artist_id, "en": artist_id},
            "aliases": [],
            "periods": ["Modern"],
            "regions": ["Paris"],
            "life_span": {"birth_year": 1800 + index * 20, "death_year": 1880 + index * 20},
            "public_display": True,
            "review_status": "publishable",
            "lifecycle_status": "publishable",
            "withdrawn": False,
        }
        for index, artist_id in enumerate(artist_ids)
    ]
    payload = {"artists": artists, "relationships": list(edges)}
    return {
        "schema_version": "1.0.0",
        "id": "path-graph-input:test",
        "entity_type": "art_path_graph_input",
        "release_id": RELEASE_ID,
        "input_release_id": INPUT_RELEASE_ID,
        "input_release_hash": INPUT_RELEASE_HASH,
        "graph_hash": canonical_sha256(payload),
        **payload,
        "counts": {},
    }


def edge(
    suffix: str,
    source: str,
    target: str,
    *,
    level: str = "C",
    relation_type: str = "shared_material",
    directed: bool = False,
    confidence: float = 0.9,
    **overrides,
) -> dict:
    item = {
        "id": f"art-rel:{suffix}",
        "release_id": RELEASE_ID,
        "source_artist_id": source,
        "target_artist_id": target,
        "type": relation_type,
        "level": level,
        "directed": directed,
        "is_algorithmic": False,
        "computational_similarity": None,
        "public_display": True,
        "review_status": "publishable",
        "lifecycle_status": "publishable",
        "withdrawn": False,
        "deprecated": False,
        "rights_visibility": "public",
        "periods": ["Modern"],
        "regions": ["Paris"],
        "context_ids": ["material:test"],
        "claim_ids": [f"claim:{suffix}"],
        "evidence_ids": [f"evidence:{suffix}"],
        "source_ids": ["source:test"],
        "supporting_artwork_ids": ["artwork:test"],
        "evidence_confidence": confidence,
        "why_connected": {"zh-Hans": "经审核的连接。", "en": "Reviewed connection."},
        "does_not_prove": {"zh-Hans": "不证明影响。", "en": "Does not prove influence."},
        "rights_attribution": ["Test source"],
    }
    item.update(overrides)
    return item


def query(start: str = "artist:a", end: str = "artist:d", mode: str = "comparison", **overrides) -> dict:
    item = default_query(start, end, mode)
    item.update(overrides)
    return item


class PathAlgorithmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = graph(
            edge("ab", "artist:a", "artist:b", confidence=0.9),
            edge("bd", "artist:b", "artist:d", confidence=0.9),
            edge("ac", "artist:a", "artist:c", confidence=0.8),
            edge("cd", "artist:c", "artist:d", confidence=0.8),
            edge("bc", "artist:b", "artist:c", confidence=0.7),
        )

    def test_same_endpoint_is_rejected(self) -> None:
        self.assertEqual(find_paths(self.base, query(end="artist:a"))["status"], "same_endpoint")

    def test_invalid_endpoints_are_distinct(self) -> None:
        self.assertEqual(find_paths(self.base, query(start="artist:missing"))["status"], "invalid_start")
        self.assertEqual(find_paths(self.base, query(end="artist:missing"))["status"], "invalid_end")

    def test_bidirectional_bfs_prefers_shortest_then_confidence(self) -> None:
        result = find_paths(self.base, query(k=1))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["paths"][0]["artist_ids"], ["artist:a", "artist:b", "artist:d"])

    def test_directed_edge_respects_direction(self) -> None:
        directed = graph(edge("ab", "artist:a", "artist:b", level="A", directed=True), artist_ids=["artist:a", "artist:b"])
        self.assertEqual(find_paths(directed, query(end="artist:b", mode="historical"))["status"], "ready")
        self.assertEqual(find_paths(directed, query(start="artist:b", end="artist:a", mode="historical"))["status"], "no_path_for_current_release_and_filters")

    def test_symmetric_edge_traverses_both_directions(self) -> None:
        symmetric = graph(edge("ab", "artist:a", "artist:b"), artist_ids=["artist:a", "artist:b"])
        self.assertEqual(find_paths(symmetric, query(start="artist:b", end="artist:a"))["status"], "ready")

    def test_max_hops_is_enforced(self) -> None:
        self.assertEqual(find_paths(self.base, query(max_hops=1))["status"], "no_path_for_current_release_and_filters")

    def test_k_is_bounded_and_alternatives_are_loopless_and_unique(self) -> None:
        result = find_paths(self.base, query(k=3))
        self.assertEqual(len(result["paths"]), 3)
        identities = set()
        for path in result["paths"]:
            self.assertEqual(len(path["artist_ids"]), len(set(path["artist_ids"])))
            identities.add(tuple(path["relationship_ids"]))
        self.assertEqual(len(identities), 3)
        self.assertEqual(find_paths(self.base, query(k=4))["status"], "runtime_calculation_failed")

    def test_tie_break_is_deterministic(self) -> None:
        first = find_paths(self.base, query())
        second = find_paths(deepcopy(self.base), query())
        self.assertEqual(first, second)
        self.assertEqual(first["algorithm_version"], ALGORITHM_VERSION)

    def test_budget_reached_is_not_no_path(self) -> None:
        result = find_paths(self.base, query(candidate_expansion_limit=1))
        self.assertEqual(result["status"], "search_budget_reached")
        self.assertEqual(result["expansions_used"], 1)
        empty = graph(artist_ids=["artist:a", "artist:b"])
        no_path = find_paths(empty, query(end="artist:b", candidate_expansion_limit=1))
        self.assertEqual(no_path["status"], "no_path_for_current_release_and_filters")

    def test_visibility_lifecycle_and_algorithmic_edges_are_excluded(self) -> None:
        for field, value in (("withdrawn", True), ("deprecated", True), ("public_display", False), ("is_algorithmic", True)):
            changed = edge("ab", "artist:a", "artist:b", **{field: value})
            changed_graph = graph(changed, artist_ids=["artist:a", "artist:b"])
            self.assertEqual(find_paths(changed_graph, query(end="artist:b"))["status"], "no_path_for_current_release_and_filters")

    def test_modes_never_mix_relationship_levels(self) -> None:
        mixed = graph(
            edge("ab", "artist:a", "artist:b", level="A", directed=True),
            edge("bc", "artist:b", "artist:c", level="B", relation_type="shared_institution"),
            edge("cd", "artist:c", "artist:d", level="C"),
        )
        historical = find_paths(mixed, query(mode="historical", allowed_levels=["A", "B"]))
        self.assertEqual(historical["status"], "no_path_for_current_release_and_filters")
        context = find_paths(mixed, query(end="artist:c", mode="context", allowed_levels=["B"]))
        self.assertEqual(context["status"], "no_path_for_current_release_and_filters")
        comparison = find_paths(mixed, query(start="artist:c", mode="comparison"))
        self.assertEqual(comparison["status"], "ready")
        self.assertTrue(all(step["level"] == "C" for step in comparison["paths"][0]["steps"]))

    def test_type_period_and_region_filters(self) -> None:
        filtered = graph(edge("ab", "artist:a", "artist:b", periods=["Edo period"], regions=["Edo"]), artist_ids=["artist:a", "artist:b"])
        self.assertEqual(find_paths(filtered, query(end="artist:b", period_filter=["Edo period"], region_filter=["Edo"]))["status"], "ready")
        self.assertEqual(find_paths(filtered, query(end="artist:b", period_filter=["Modern"]))["status"], "no_path_for_current_release_and_filters")
        self.assertEqual(find_paths(filtered, query(end="artist:b", allowed_relationship_types=["shared_subject"]))["status"], "no_path_for_current_release_and_filters")

    def test_temporal_coherence_is_exposed(self) -> None:
        result = find_paths(self.base, query(k=1))
        self.assertIn(result["paths"][0]["time_coherence"], {"coherent", "mixed", "discontinuous"})
        self.assertEqual(result["paths"][0]["ranking_tuple"]["time_coherence_penalty"], 0)


class RelationshipReviewTests(unittest.TestCase):
    def test_existing_ab_leads_close_without_human_dependency(self) -> None:
        review = review_ab_leads()
        self.assertEqual(review["input_lead_count"], 9)
        self.assertEqual(review["level_counts"], {"A": 1, "B": 8})
        self.assertEqual(review["disposition_counts"]["promoted_to_formal_relationship"], 0)
        self.assertEqual(review["disposition_counts"]["retained_for_more_evidence"], 1)
        self.assertEqual(review["disposition_counts"]["out_of_scope"], 8)
        self.assertFalse(review["human_review_dependency"])
        self.assertNotIn("waiting for human review", json.dumps(review))

    def test_in_scope_b_lead_fails_exact_time_and_independent_source_gate(self) -> None:
        retained = [item for item in review_ab_leads()["entries"] if item["terminal_disposition"] == "retained_for_more_evidence"]
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["automated_gate_result"], "exact_time_overlap_and_independent_source_closure_missing")
        self.assertFalse(retained[0]["source_lineage_independence_closed"])


class PathSchemaAndGraphTests(unittest.TestCase):
    def test_path_entity_dispatch_is_canonical(self) -> None:
        self.assertEqual(canonical_schema_path({"entity_type": "art_path_result"}), "schemas/art/release/path-result.schema.json")
        self.assertEqual(canonical_schema_path({"entity_type": "art_path_graph_input"}), "schemas/art/release/art-pathways-artifact.schema.json")

    def test_current_graph_is_c_only_and_stable(self) -> None:
        first = build_graph_input()
        second = build_graph_input()
        self.assertEqual(first, second)
        self.assertEqual(first["counts"], {"artists": 12, "relationships": 36, "levels": {"C": 36}, "directed": 0, "algorithmic": 0})
        self.assertEqual(first["graph_hash"], canonical_sha256({"artists": first["artists"], "relationships": first["relationships"]}))

    def test_default_query_and_result_validate(self) -> None:
        current = build_graph_input()
        result = find_paths(current, default_query(current["artists"][0]["id"], current["artists"][1]["id"], "comparison"))
        self.assertEqual(validate_record(result, requested_schema="schemas/art/release/path-result.schema.json"), [])
        self.assertLessEqual(result["expansions_used"], MAX_EXPANSIONS)


class Museum06ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_root = DEFAULT_OUTPUT
        cls.graph = json.loads((cls.release_root / "path-graph-input.json").read_text(encoding="utf-8"))
        cls.index = json.loads((cls.release_root / "path-index.json").read_text(encoding="utf-8"))
        cls.explanations = json.loads((cls.release_root / "path-explanations.json").read_text(encoding="utf-8"))
        cls.ab = json.loads((cls.release_root / "ab-review-summary.json").read_text(encoding="utf-8"))

    def semantic_codes(self, graph_input=None, path_index=None, explanations=None, ab=None) -> set[str]:
        failures: list[dict[str, str]] = []
        _validate_path_semantics(
            self.release_root,
            graph_input or self.graph,
            path_index or self.index,
            explanations or self.explanations,
            ab or self.ab,
            failures,
        )
        return {item["code"] for item in failures}

    def test_formal_release_is_physically_closed(self) -> None:
        result = validate_museum_06_release(self.release_root)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(result["counts"], {
            "artist_count": 12, "relationship_count": 36, "default_pair_count": 66, "precomputed_path_count": 198,
        })

    def test_predecessor_and_graph_hash_are_exact(self) -> None:
        manifest = json.loads((self.release_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["predecessor"], INPUT_RELEASE_ID)
        self.assertEqual(self.graph["input_release_hash"], INPUT_RELEASE_HASH)
        self.assertEqual(self.index["input_graph_hash"], self.graph["graph_hash"])

    def test_index_contains_exactly_66_pairs_and_198_paths(self) -> None:
        self.assertEqual(len(self.index["pairs"]), 66)
        self.assertEqual(self.index["precomputed_path_count"], 198)
        self.assertTrue(all(pair["modes"]["historical"]["paths"] == [] for pair in self.index["pairs"]))
        self.assertTrue(all(pair["modes"]["context"]["paths"] == [] for pair in self.index["pairs"]))
        self.assertTrue(all(len(pair["modes"]["comparison"]["paths"]) == 3 for pair in self.index["pairs"]))

    def test_release_artifacts_rebuild_deterministically(self) -> None:
        rebuilt = _build_artifacts(build_graph_input(), review_ab_leads())
        for filename, document in rebuilt.items():
            self.assertEqual(
                json.loads((self.release_root / filename).read_text(encoding="utf-8")),
                document,
                filename,
            )

    def test_bad_graph_hash_is_detected(self) -> None:
        invalid = deepcopy(self.index)
        invalid["pairs"][0]["modes"]["comparison"]["input_graph_hash"] = "sha256:" + "0" * 64
        self.assertIn("result_graph_hash", self.semantic_codes(path_index=invalid))

    def test_missing_source_is_detected(self) -> None:
        invalid = deepcopy(self.graph)
        invalid["relationships"][0]["source_ids"].append("source:missing")
        self.assertIn("missing_source", self.semantic_codes(graph_input=invalid))

    def test_private_lead_leakage_is_detected(self) -> None:
        invalid = deepcopy(self.ab)
        invalid["debug"] = "relationship-lead:private"
        self.assertIn("private_lead_leakage", self.semantic_codes(ab=invalid))

    def test_unknown_edge_and_explanation_gap_are_detected(self) -> None:
        invalid_index = deepcopy(self.index)
        invalid_index["pairs"][0]["modes"]["comparison"]["paths"][0]["relationship_ids"][0] = "art-rel:missing"
        invalid_explanations = deepcopy(self.explanations)
        invalid_explanations["explanations"].pop()
        self.assertIn("unknown_edge", self.semantic_codes(path_index=invalid_index))
        self.assertIn("explanation_closure", self.semantic_codes(explanations=invalid_explanations))


if __name__ == "__main__":
    unittest.main()
