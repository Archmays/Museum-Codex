from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from museum_pipeline.art.relationships import build_relationship_stage
from museum_pipeline.config import ROOT
from museum_pipeline.errors import PipelineError
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import reference_graph_issues


IDENTITY_DIR = ROOT / "data" / "reviewed" / "art" / "museum-03b" / "museum-03b-first-slate-v1"
PACKAGE_DIR = IDENTITY_DIR / "package-v1"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class ArtRelationshipStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        artworks = _load(PACKAGE_DIR / "artworks.json")
        claims = _load(PACKAGE_DIR / "claims.json")
        evidence = _load(PACKAGE_DIR / "evidence.json")
        artwork_claim_ids = {claim_id for artwork in artworks for claim_id in artwork["claim_ids"]}
        artwork_claims = [item for item in claims if item["id"] in artwork_claim_ids]
        artwork_evidence_prefixes = tuple(
            f"evidence:{artwork['id'].split(':', 1)[1]}-"
            for artwork in artworks
        )
        artwork_evidence = [item for item in evidence if item["id"].startswith(artwork_evidence_prefixes)]
        if (len(artworks), len(artwork_claims), len(artwork_evidence)) != (44, 413, 134):
            raise AssertionError("Sealed artwork-stage projection is not the reviewed 44/413/134 set")
        cls.artwork_stage = {
            "payloads": {
                "artworks.json": artworks,
                "artwork-claims.json": artwork_claims,
                "artwork-evidence.json": artwork_evidence,
            }
        }
        cls.sources = _load(PACKAGE_DIR / "sources.json")
        cls.artists = _load(PACKAGE_DIR / "artists.json")
        cls.result = build_relationship_stage(
            artwork_stage=cls.artwork_stage,
            sources=cls.sources,
            artists=cls.artists,
        )

    def test_exact_counts_levels_and_graph_degrees(self) -> None:
        self.assertEqual(
            self.result["counts"],
            {
                "contexts": 31,
                "claims": 67,
                "evidence": 67,
                "relationships": 36,
                "dispositions": 69,
                "signoffs": 5,
            },
        )
        levels = Counter(item["evidence_level"] for item in self.result["relationships"])
        self.assertEqual(levels, Counter({"C": 36}))
        relationship_types = Counter(item["relationship_type"] for item in self.result["relationships"])
        self.assertEqual(
            relationship_types,
            Counter({"shared_subject": 17, "shared_material": 11, "shared_technique": 8}),
        )
        degrees: Counter[str] = Counter()
        for relationship in self.result["relationships"]:
            degrees[relationship["source_entity_id"]] += 1
            degrees[relationship["target_entity_id"]] += 1
        self.assertEqual(
            dict(sorted(degrees.items())),
            {
                "artist:albrecht-durer": 8,
                "artist:francisco-de-goya": 4,
                "artist:henry-ossawa-tanner": 7,
                "artist:jose-guadalupe-posada": 5,
                "artist:julia-margaret-cameron": 6,
                "artist:kathe-kollwitz": 8,
                "artist:katsushika-hokusai": 9,
                "artist:kitagawa-utamaro": 6,
                "artist:mary-cassatt": 7,
                "artist:raja-ravi-varma": 4,
                "artist:shen-zhou": 3,
                "artist:vincent-van-gogh": 5,
            },
        )

    def test_every_generated_record_passes_canonical_concrete_schema(self) -> None:
        environment = load_schema_environment()
        for group in ("contexts", "claims", "evidence", "relationships", "dispositions", "signoffs"):
            for record in self.result[group]:
                with self.subTest(group=group, record_id=record["id"]):
                    self.assertEqual(validate_record(record, environment=environment), [])

    def test_context_labels_and_artwork_reference_closure(self) -> None:
        reviewed = _load(ROOT / "research" / "art" / "museum-03b-context-decisions.json")
        context_by_id = {item["id"]: item for item in self.result["contexts"]}
        for decision in reviewed["contexts"]:
            self.assertEqual(context_by_id[decision["id"]]["labels"], decision["labels"])

        payloads = self.artwork_stage["payloads"]
        artwork_context_ids: set[str] = set()
        institution_ids: set[str] = set()
        for artwork in payloads["artworks.json"]:
            artwork_context_ids.update(artwork["material_ids"])
            artwork_context_ids.update(artwork["technique_ids"])
            artwork_context_ids.update(artwork["subject_ids"])
            institution_ids.add(artwork["holding_institution_id"])
        self.assertLessEqual(artwork_context_ids | institution_ids, set(context_by_id))
        for institution_id in institution_ids:
            self.assertIn(context_by_id[institution_id]["place_id"], context_by_id)

    def test_claim_evidence_source_and_signoff_backlinks_are_closed(self) -> None:
        identity_records = [
            *self.sources,
            *self.artists,
            *_load(IDENTITY_DIR / "identity-claims.json"),
            *_load(IDENTITY_DIR / "identity-evidence.json"),
        ]
        payloads = self.artwork_stage["payloads"]
        records = [
            *identity_records,
            *payloads["artworks.json"],
            *payloads["artwork-claims.json"],
            *payloads["artwork-evidence.json"],
            *self.result["contexts"],
            *self.result["claims"],
            *self.result["evidence"],
            *self.result["relationships"],
            *self.result["dispositions"],
            *self.result["signoffs"],
        ]
        issues = reference_graph_issues([{"data": record} for record in records])
        self.assertEqual(issues, [])
        record_ids = {record["id"] for record in records}
        for signoff in self.result["signoffs"]:
            self.assertLessEqual(set(signoff["record_ids"]), record_ids)

    def test_dispositions_preserve_honest_origin_and_full_closure(self) -> None:
        origins = Counter(item["origin_kind"] for item in self.result["dispositions"])
        self.assertEqual(origins, Counter({"inherited_lead": 45, "new_curated_candidate": 24}))
        inherited = [item for item in self.result["dispositions"] if item["origin_kind"] == "inherited_lead"]
        curated = [item for item in self.result["dispositions"] if item["origin_kind"] == "new_curated_candidate"]
        self.assertTrue(all(item["lead_id"] is not None and item["research_candidate_id"] is None for item in inherited))
        self.assertTrue(all(item["lead_id"] is None and item["research_candidate_id"] is not None for item in curated))
        self.assertTrue(
            all(item["formal_relationship_id"] is None for item in inherited if item["disposition"] == "superseded")
        )
        promoted = {
            item["formal_relationship_id"]
            for item in self.result["dispositions"]
            if item["disposition"] == "promoted_to_formal_relationship"
        }
        self.assertEqual(promoted, {item["id"] for item in self.result["relationships"]})
        dispositions = {item["id"] for item in self.result["dispositions"]}
        self.assertTrue(all(item["research_disposition_id"] in dispositions for item in self.result["relationships"]))

    def test_relationships_never_cross_algorithmic_causal_or_public_boundary(self) -> None:
        causal = {
            "explicitly_influenced",
            "explicitly_influenced_by",
            "student_of",
            "teacher_of",
            "worked_in_studio_of",
            "collaborated_with",
            "referenced_or_quoted",
        }
        context_by_id = {item["id"]: item for item in self.result["contexts"]}
        inverse_keys: set[tuple[str, str, str]] = set()
        for relationship in self.result["relationships"]:
            self.assertEqual(relationship["relationship_semantics"], "curatorial_comparison")
            self.assertNotIn(relationship["relationship_type"], causal)
            self.assertIs(relationship["is_algorithmic"], False)
            self.assertIsNone(relationship["computational_similarity"])
            self.assertIsNone(relationship["historical_relationship_strength"])
            self.assertIs(relationship["public_display"], False)
            self.assertEqual(relationship["lifecycle_status"], "reviewed")
            self.assertEqual(relationship["review_status"], "reviewed")
            self.assertNotEqual(relationship["source_entity_id"], relationship["target_entity_id"])
            expected_type = relationship["relationship_type"].removeprefix("shared_")
            self.assertTrue(
                all(context_by_id[context_id]["entity_type"] == expected_type for context_id in relationship["context_entity_ids"])
            )
            key = (
                relationship["relationship_type"],
                *sorted((relationship["source_entity_id"], relationship["target_entity_id"])),
            )
            self.assertNotIn(key, inverse_keys)
            inverse_keys.add(key)

    def test_c_level_selection_is_explicit_fixed_and_exactly_evidence_bound(self) -> None:
        research = _load(ROOT / "research" / "art" / "museum-03b-relationship-decisions.json")
        self.assertEqual(research["research_candidate_count"], 69)
        self.assertEqual(research["input_lead_count"], 45)
        self.assertEqual(research["added_candidate_count"], 24)
        self.assertEqual(research["formal_relationship_count"], 36)
        self.assertIn("all-pairs generation", research["review_sessions"]["relationship_reviewer"]["decision_note"])
        self.assertIn("zero A/B counts are conservative", self.result["evidence_level_rationale"])

        relationship_by_id = {item["id"]: item for item in self.result["relationships"]}
        evidence_by_id = {item["id"]: item for item in self.result["relationship_evidence"]}
        self.assertEqual(set(relationship_by_id), {item["relationship_id"] for item in research["decisions"]})
        observed_pairs = {
            tuple(sorted((item["source_entity_id"], item["target_entity_id"])))
            for item in self.result["relationships"]
        }
        self.assertEqual(len(observed_pairs), 36)
        self.assertLess(len(observed_pairs), 66)  # not the 12-artist all-pairs graph

        context_use: Counter[str] = Counter()
        for decision in research["decisions"]:
            relationship = relationship_by_id[decision["relationship_id"]]
            self.assertEqual(relationship["context_entity_ids"], decision["context_entity_ids"])
            self.assertIn(decision["rationale"], relationship["curatorial_note"]["en"])
            self.assertIn(decision["educational_value"], relationship["educational_rationale"]["en"])
            self.assertEqual(relationship["generation_method"], "reviewed_curatorial_synthesis")
            context_use.update(decision["context_entity_ids"])

            evidence_id = f"evidence:relationship-{decision['relationship_id'].split(':', 1)[1]}"
            evidence = evidence_by_id[evidence_id]
            expected_raw = {
                (str(binding["source_object_id"]), binding["snapshot_sha256"], locator)
                for binding in decision["evidence_bindings"]
                for locator in binding["raw_locators"]
            }
            observed_raw = {
                (raw["source_object_id"], raw["body_sha256"], raw["raw_locator"])
                for raw in evidence["raw_snapshot_refs"]
            }
            self.assertEqual(observed_raw, expected_raw)
            self.assertEqual(len(decision["evidence_bindings"]), 2)
            self.assertEqual(
                {binding["source_id"] for binding in evidence["source_license_bindings"]},
                set(evidence["source_ids"]),
            )
        self.assertEqual(len(context_use), 17)
        self.assertEqual(
            Counter(item["relationship_type"] for item in self.result["relationships"]),
            Counter({"shared_subject": 17, "shared_material": 11, "shared_technique": 8}),
        )

    def test_builder_is_deterministic_and_write_free(self) -> None:
        before = copy.deepcopy(self.artwork_stage)
        repeated = build_relationship_stage(
            artwork_stage=self.artwork_stage,
            sources=self.sources,
            artists=self.artists,
        )
        self.assertEqual(repeated, self.result)
        self.assertEqual(self.artwork_stage, before)

    def test_tampered_artwork_snapshot_evidence_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.artwork_stage)
        raw_ref = tampered["payloads"]["artwork-evidence.json"][0]["raw_snapshot_refs"][0]
        raw_ref["body_sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(PipelineError) as raised:
            build_relationship_stage(artwork_stage=tampered, sources=self.sources, artists=self.artists)
        self.assertEqual(raised.exception.code, "artwork_evidence_snapshot_hash_mismatch")


if __name__ == "__main__":
    unittest.main()
