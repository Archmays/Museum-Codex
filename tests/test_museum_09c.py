from __future__ import annotations

import json
import unittest
from pathlib import Path

from museum_pipeline.art.expansion_batch_factory import (
    load_batch_inputs,
    validate_registry_lifecycle,
    validate_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "release:art-expansion-batch-02-1.6.0"
PREDECESSOR_ID = "release:art-expansion-batch-01-1.5.1"
RELEASE = ROOT / "public" / "releases" / "art-expansion-batch-02-1.6.0"
RESEARCH = ROOT / "data" / "reviewed" / "art" / "museum-09c" / "batch-02-formal-candidate-v1"
MEDIA = ROOT / "data" / "reviewed" / "art" / "museum-09c-media" / "batch-02-media-bundle-v1"


class Museum09CReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_batch_inputs("museum-09-batch-02")
        cls.registry = json.loads(
            (ROOT / "governance" / "museum-09-batch-registry.json").read_text(encoding="utf-8")
        )
        cls.sealed = json.loads(
            (
                ROOT
                / "data"
                / "reviewed"
                / "art"
                / "museum-09a"
                / "global-expansion-universe-v1"
                / "batch-registry-snapshot.json"
            ).read_text(encoding="utf-8")
        )

    def test_batch_assignment_and_input_closure_are_exact(self) -> None:
        batch = self.inputs.batch
        self.assertEqual(49, len(self.inputs.artists))
        self.assertEqual(485, len(self.inputs.artworks))
        self.assertEqual("sha256:02b962ad03917cac733f8be584c0f710f624f3039c04c869b92772bb31b2681d", batch["input_closure_hash"])
        self.assertEqual((12, 37), (batch["gallery_tier_count"], batch["collection_tier_count"]))

    def test_unentered_batch_assignments_remain_sealed(self) -> None:
        immutable = {
            "id",
            "sequence",
            "planned_phase",
            "artist_count",
            "work_count",
            "artist_ids",
            "coverage_delta",
            "gallery_tier_count",
            "collection_tier_count",
            "input_closure_hash",
            "source_set",
        }
        canonical = {item["id"]: item for item in self.registry["batches"]}
        sealed = {item["id"]: item for item in self.sealed["batches"]}
        for sequence in range(3, 11):
            batch_id = f"museum-09-batch-{sequence:02d}"
            self.assertEqual("registered_not_started", canonical[batch_id]["status"])
            self.assertEqual(
                {key: canonical[batch_id][key] for key in immutable},
                {key: sealed[batch_id][key] for key in immutable},
            )

    def test_batch_01_and_batch_02_are_published_without_next_phase(self) -> None:
        by_sequence = {item["sequence"]: item for item in self.registry["batches"]}
        self.assertEqual("published", by_sequence[1]["status"])
        self.assertEqual(PREDECESSOR_ID, by_sequence[1]["current_release"]["id"])
        self.assertIsNone(by_sequence[1]["next_authorized_phase"])
        self.assertEqual("published", by_sequence[2]["status"])
        self.assertEqual(RELEASE_ID, by_sequence[2]["current_release"]["id"])
        self.assertIsNone(by_sequence[2]["next_authorized_phase"])
        self.assertEqual(
            "docs/qa/museum-09c/closeout-evidence.json",
            by_sequence[2]["runtime_binding"]["evidence_path"],
        )
        self.assertEqual(
            "docs/qa/museum-09c/closeout-evidence.json",
            by_sequence[2]["deployment_binding"]["evidence_path"],
        )
        self.assertEqual(
            "docs/qa/museum-09c/closeout-evidence.json",
            by_sequence[2]["online_closure"]["evidence_path"],
        )
        self.assertEqual(
            ["research_in_progress", "formal_candidate_ready", "media_bundle_ready", "published"],
            [item["to"] for item in by_sequence[2]["status_history"]],
        )
        self.assertEqual([], validate_registry_lifecycle(self.registry))

    def test_registry_lifecycle_rejects_regression(self) -> None:
        invalid = json.loads(json.dumps(self.registry))
        batch = next(item for item in invalid["batches"] if item["sequence"] == 2)
        batch["status_history"][2]["to"] = "research_in_progress"
        self.assertTrue(validate_registry_lifecycle(invalid))

    def test_research_media_and_release_transactions_are_independent(self) -> None:
        research = json.loads((RESEARCH / "transaction-manifest.json").read_text(encoding="utf-8"))
        media = json.loads((MEDIA / "transaction-manifest.json").read_text(encoding="utf-8"))
        release = json.loads((RELEASE / "batch-transaction-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(["research", "media", "release"], [research["stage"], media["stage"], release["stage"]])
        self.assertTrue(all(item["status"] == "committed" for item in (research, media, release)))

    def test_research_and_media_hard_gates_close(self) -> None:
        research = json.loads((RESEARCH / "validation-summary.json").read_text(encoding="utf-8"))
        media = json.loads((MEDIA / "validation-summary.json").read_text(encoding="utf-8"))
        self.assertEqual("pass", research["status"])
        self.assertEqual(49, research["counts"]["narratives"])
        self.assertEqual(49, research["counts"]["distinct_template_signatures"])
        self.assertEqual(0, research["counts"]["duplicate_intros"])
        self.assertEqual(0, research["counts"]["banned_term_hits"])
        self.assertEqual(485, media["counts"]["terminal_decisions"])
        self.assertEqual(485, media["counts"]["metadata_only_after_media_review"])
        self.assertEqual(0, media["counts"]["originals"])
        self.assertEqual(0, media["counts"]["derivatives"])

    def test_release_physical_and_semantic_closure(self) -> None:
        result = validate_release(
            RELEASE,
            release_id=RELEASE_ID,
            predecessor_id=PREDECESSOR_ID,
            expected_artists=111,
            expected_artworks=1017,
        )
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(60, result["counts"]["relationships"])
        self.assertEqual(183, result["counts"]["episodes"])
        self.assertEqual(13, result["counts"]["sources"])

    def test_historical_release_bytes_remain_unchanged(self) -> None:
        expected = {
            "art-expansion-batch-01-1.5.0": "sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9",
            "art-expansion-batch-01-1.5.1": "sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5",
        }
        import hashlib

        for directory, digest in expected.items():
            body = (ROOT / "public" / "releases" / directory / "manifest.json").read_bytes()
            self.assertEqual(digest, "sha256:" + hashlib.sha256(body).hexdigest())


if __name__ == "__main__":
    unittest.main()
