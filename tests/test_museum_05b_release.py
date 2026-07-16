from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from museum_pipeline.art.interactions import (
    DEFAULT_OUTPUT,
    INPUT_RELEASE_HASH,
    RELEASE_ID,
    _validate_index_semantics,
    _validate_interaction_schema,
    _validate_retry_semantics,
    build_museum_05b_release,
    validate_museum_05b_release,
)
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import validate_record


class Museum05BReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_root = DEFAULT_OUTPUT
        cls.index = json.loads((cls.release_root / "interaction-index.json").read_text(encoding="utf-8"))

    def test_formal_release_is_physically_closed(self) -> None:
        result = validate_museum_05b_release(self.release_root)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(RELEASE_ID, result["release_id"])
        self.assertEqual(44, result["counts"]["observation_cards"])
        self.assertEqual(24, result["counts"]["detail_regions"])

    def test_deterministic_rebuild_matches_committed_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "art-gallery-interactions-1.1.0"
            rebuilt = build_museum_05b_release(output)
            self.assertTrue(rebuilt["ok"], rebuilt["failures"])
            self.assertEqual(
                (self.release_root / "manifest.json").read_bytes(),
                (output / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                (self.release_root / "interaction-index.json").read_bytes(),
                (output / "interaction-index.json").read_bytes(),
            )

    def test_schema_rejects_missing_observation_card(self) -> None:
        invalid = deepcopy(self.index)
        invalid["observation_cards"].pop()
        with self.assertRaisesRegex(ValueError, "too short|44"):
            _validate_interaction_schema(invalid)

    def test_semantics_reject_no_image_visual_prompt(self) -> None:
        invalid = deepcopy(self.index)
        card = next(item for item in invalid["observation_cards"] if item["image_availability"] == "metadata_only")
        card["prompts"][0]["en"] = "Inspect the visible line and composition."
        failures: list[dict[str, str]] = []
        _validate_index_semantics(self.release_root, invalid, failures)
        self.assertIn("metadata_only_visual_prompt", {item["code"] for item in failures})

    def test_semantics_reject_dangling_evidence_and_source(self) -> None:
        invalid = deepcopy(self.index)
        invalid["observation_cards"][0]["evidence_ids"].append("evidence:missing")
        invalid["observation_cards"][0]["source_ids"].append("source:missing")
        failures: list[dict[str, str]] = []
        _validate_index_semantics(self.release_root, invalid, failures)
        codes = {item["code"] for item in failures}
        self.assertIn("observation_evidence_reference", codes)
        self.assertIn("observation_source_reference", codes)

    def test_semantics_reject_cross_artwork_visual_hero_and_region(self) -> None:
        invalid = deepcopy(self.index)
        visual = next(item for item in invalid["hero_selections"] if item["status"] == "visual_detail_path")
        textual = next(item for item in invalid["hero_selections"] if item["status"] == "textual_observation_path")
        visual["artwork_id"] = textual["artwork_id"]
        failures: list[dict[str, str]] = []
        _validate_index_semantics(self.release_root, invalid, failures)
        codes = {item["code"] for item in failures}
        self.assertIn("hero_reference", codes)
        self.assertIn("visual_hero_media", codes)
        self.assertIn("detail_owner_reference", codes)

    def test_semantics_reject_no_image_description_causal_wording_and_count_drift(self) -> None:
        invalid = deepcopy(self.index)
        card = next(item for item in invalid["observation_cards"] if item["image_availability"] == "metadata_only")
        card["directly_observable"][0]["en"] = "A figure's eye and light are clearly visible."
        card["interpretation_requires_sources"][0]["en"] = "This work clearly influenced another artist."
        invalid["counts"]["detail_regions"] -= 1
        failures: list[dict[str, str]] = []
        _validate_index_semantics(self.release_root, invalid, failures)
        codes = {item["code"] for item in failures}
        self.assertIn("metadata_only_visual_prompt", codes)
        self.assertIn("causal_algorithmic_wording", codes)
        self.assertIn("count_closure", codes)

    def test_semantics_reject_duplicated_tours_and_lenses(self) -> None:
        invalid = deepcopy(self.index)
        invalid["artist_tours"] = [deepcopy(invalid["artist_tours"][0]) for _ in range(12)]
        invalid["thematic_tours"] = [deepcopy(invalid["thematic_tours"][0]) for _ in range(6)]
        invalid["lenses"] = [deepcopy(invalid["lenses"][0]) for _ in range(3)]
        failures: list[dict[str, str]] = []
        _validate_index_semantics(self.release_root, invalid, failures)
        codes = {item["code"] for item in failures}
        self.assertIn("artist_tour_closure", codes)
        self.assertIn("thematic_tour_closure", codes)
        self.assertIn("lens_closure", codes)

    def test_detail_regions_are_hash_bound_in_bounds_and_nonsemantic(self) -> None:
        for region in self.index["detail_regions"]:
            asset = region["source_asset"]
            rect = region["rect"]
            self.assertLessEqual(rect["x"] + rect["width"], asset["width"])
            self.assertLessEqual(rect["y"] + rect["height"], asset["height"])
            self.assertEqual(INPUT_RELEASE_HASH, region["algorithm"]["input_release_hash"])
            self.assertIsNone(region["semantic_label"])

    def test_tours_lenses_and_heroes_close_exactly(self) -> None:
        self.assertEqual(12, len(self.index["artist_tours"]))
        self.assertEqual(6, len(self.index["thematic_tours"]))
        self.assertEqual(12, len(self.index["hero_selections"]))
        self.assertEqual(8, sum(item["status"] == "visual_detail_path" for item in self.index["hero_selections"]))
        self.assertEqual(4, sum(item["status"] == "textual_observation_path" for item in self.index["hero_selections"]))
        self.assertEqual({"material", "technique", "subject"}, {item["type"] for item in self.index["lenses"]})
        self.assertTrue(all(item["pathfinding"] is False for item in self.index["thematic_tours"]))
        self.assertTrue(all(item["metadata_only_artwork_ids"] for item in self.index["thematic_tours"]))
        self.assertEqual(
            {"material": 4, "technique": 4, "subject": 4},
            {kind: sum(tour["focus"]["type"] == kind for tour in self.index["artist_tours"]) for kind in ("material", "technique", "subject")},
        )
        reasons = {step["reason"]["en"] for tour in self.index["artist_tours"] for step in tour["artwork_steps"]}
        self.assertGreaterEqual(len(reasons), 20)

    def test_overlay_contract_and_bilingual_dates_are_explicit(self) -> None:
        self.assertEqual("immutable_overlay", self.index["release_composition"]["mode"])
        self.assertEqual(["interaction-index.json", "media-retry.json"], self.index["release_composition"]["overlay_files"])
        self.assertTrue(all(card["release_version"] == "1.1.0" for card in self.index["observation_cards"]))
        self.assertTrue(all(card["date"]["zh-Hans"] != card["date"]["en"] or card["date"]["en"].isdigit() for card in self.index["observation_cards"]))
        self.assertTrue(all("《《" not in card["title"]["zh-Hans"] for card in self.index["observation_cards"]))
        self.assertTrue(all(tour["time_place_context"]["zh-Hans"] != tour["time_place_context"]["en"] for tour in self.index["artist_tours"]))
        self.assertTrue(all(
            label["zh-Hans"] != label["en"]
            for tour in self.index["thematic_tours"]
            for label in [*tour["period_labels"], *tour["region_labels"]]
        ))

    def test_media_retry_is_canonically_dispatched_and_hashed(self) -> None:
        path = ROOT / "data" / "reviewed" / "art" / "museum-05b" / "media-retry-v1.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            record["content_hash"],
            canonical_sha256({key: value for key, value in record.items() if key != "content_hash"}),
        )
        issues = validate_record(record, requested_schema="schemas/art/media/media-retry.schema.json")
        self.assertEqual([], issues)
        self.assertEqual(0, record["download_attempt_count"])
        self.assertFalse(record["human_review_dependency"])

    def test_media_retry_rejects_duplicate_artworks_and_changed_terminal_decision(self) -> None:
        record = json.loads((self.release_root / "media-retry.json").read_text(encoding="utf-8"))
        invalid = deepcopy(record)
        invalid["results"][1] = deepcopy(invalid["results"][0])
        invalid["results"][2]["final_decision"] = "metadata_only_after_automated_review"
        invalid["content_hash"] = canonical_sha256({key: value for key, value in invalid.items() if key != "content_hash"})
        media_decisions = {item["artwork_id"]: item["decision"] for item in json.loads((self.release_root / "media-index.json").read_text(encoding="utf-8"))["artworks"]}
        no_image_ids = {artwork_id for artwork_id, decision in media_decisions.items() if decision != "approved_self_hosted"}
        failures: list[dict[str, str]] = []
        _validate_retry_semantics(invalid, no_image_ids, media_decisions, failures)
        codes = {item["code"] for item in failures}
        self.assertIn("retry_schema", codes)
        self.assertIn("retry_record_closure", codes)
        self.assertIn("retry_decision_closure", codes)


if __name__ == "__main__":
    unittest.main()
