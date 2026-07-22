from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from museum_pipeline.art.global_expansion import (
    DEFAULT_BATCH_REGISTRY,
    DEFAULT_OUTPUT,
    SHARDED_DOCUMENTS,
    _is_person_name,
    _write_sharded_document,
    names_equivalent,
    normalize_name,
    registry_preserves_assignment_snapshot,
    validate_global_expansion,
)
from museum_pipeline.canonical_json import write_canonical_json
from scripts.classify_ci_impact import Change, classify_changes


ROOT = Path(__file__).resolve().parents[1]
INVALID_CASES = ROOT / "fixtures" / "museum-09a" / "invalid-cases.json"


def _read(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _read_collection(root: Path, relative: str) -> dict:
    manifest = _read(root, relative)
    config = SHARDED_DOCUMENTS[relative]
    records = []
    for shard in manifest["shards"]:
        records.extend(_read(root, shard["path"])[config["collection_field"]])
    return {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-09A",
        config["count_field"]: len(records),
        config["collection_field"]: records,
    }


class Museum09AGlobalExpansionTests(unittest.TestCase):
    def test_committed_candidate_universe_closes_exact_program_counts(self) -> None:
        result = validate_global_expansion(DEFAULT_OUTPUT)
        self.assertTrue(result["ok"], result["failures"][:12])
        self.assertGreaterEqual(result["counts"]["raw_discovered_artists"], 900)
        self.assertGreaterEqual(result["counts"]["deduplicated_artists"], 700)
        self.assertEqual(500, result["counts"]["program_target_artists"])
        self.assertEqual(12, result["counts"]["existing_target_artists"])
        self.assertEqual(488, result["counts"]["new_target_artists"])
        self.assertGreaterEqual(result["counts"]["reserve_artists"], 100)
        self.assertGreaterEqual(result["counts"]["candidate_artworks"], 7_500)
        self.assertEqual(5_000, result["counts"]["program_target_artworks"])
        self.assertEqual(44, result["counts"]["existing_target_artworks"])
        self.assertEqual(4_956, result["counts"]["new_target_artworks"])
        self.assertLessEqual(result["maximum_single_source_target_work_share"], 0.30)
        self.assertEqual(0, result["candidate_public_leakage_count"])
        self.assertEqual(0, result["new_media_download_count"])
        self.assertFalse(result["museum_09b_entered"])

    def test_coverage_batches_and_governance_snapshot_are_closed(self) -> None:
        coverage = _read(DEFAULT_OUTPUT, "coverage-matrix.json")
        self.assertEqual(
            {
                "africa": 40,
                "east-asia": 65,
                "europe": 170,
                "latin-america-caribbean": 55,
                "north-america": 75,
                "oceania": 15,
                "south-asia": 30,
                "southeast-asia": 25,
                "west-central-asia": 25,
            },
            coverage["primary_bucket_counts"],
        )
        batches = _read(DEFAULT_OUTPUT, "batch-registry-snapshot.json")
        self.assertTrue(
            registry_preserves_assignment_snapshot(
                batches,
                json.loads(DEFAULT_BATCH_REGISTRY.read_text(encoding="utf-8")),
            )
        )
        self.assertEqual([50, 49, 49, 49, 49, 49, 49, 48, 48, 48], [
            batch["artist_count"] for batch in batches["batches"]
        ])
        assigned = [artist_id for batch in batches["batches"] for artist_id in batch["artist_ids"]]
        self.assertEqual(488, len(assigned))
        self.assertEqual(488, len(set(assigned)))
        first_batch = _read(DEFAULT_OUTPUT, "museum-09b-first-batch.json")
        self.assertEqual("recommended_not_started", first_batch["status"])
        self.assertEqual(50, first_batch["artist_count"])
        self.assertGreaterEqual(first_batch["work_count"], 450)
        self.assertLessEqual(first_batch["work_count"], 550)

    def test_candidate_package_has_no_media_or_oversized_files(self) -> None:
        media_suffixes = {".gif", ".jpeg", ".jpg", ".mp3", ".mp4", ".png", ".tif", ".tiff", ".webp"}
        files = [path for path in DEFAULT_OUTPUT.rglob("*") if path.is_file()]
        self.assertFalse([path for path in files if path.suffix.casefold() in media_suffixes])
        self.assertFalse([path for path in files if path.stat().st_size >= 100_000_000])

    def test_single_artist_update_changes_exactly_one_candidate_shard(self) -> None:
        relative = "normalized-candidates.json"
        before = _read(DEFAULT_OUTPUT, relative)
        with tempfile.TemporaryDirectory(prefix="museum-09a-local-impact-") as temporary:
            root = Path(temporary)
            shutil.copy2(DEFAULT_OUTPUT / relative, root / relative)
            shutil.copytree(
                DEFAULT_OUTPUT / Path(relative).with_suffix(""),
                root / Path(relative).with_suffix(""),
            )
            document = _read_collection(root, relative)
            document["candidates"][0]["aliases"] = sorted(
                [*document["candidates"][0]["aliases"], "__local_impact_probe__"]
            )
            _write_sharded_document(
                root,
                relative,
                document,
                **SHARDED_DOCUMENTS[relative],
            )
            after = _read(root, relative)
            before_hashes = {item["path"]: item["sha256"] for item in before["shards"]}
            after_hashes = {item["path"]: item["sha256"] for item in after["shards"]}
            changed = [path for path in before_hashes if before_hashes[path] != after_hashes[path]]
            self.assertEqual(1, len(changed))

    def test_identity_helpers_do_not_merge_substring_names_or_nonpersons(self) -> None:
        self.assertEqual("albrecht durer", normalize_name(" Albrecht DÜRER "))
        self.assertTrue(names_equivalent("Dürer, Albrecht", "Albrecht Dürer"))
        self.assertFalse(names_equivalent("Dürer, Albrecht", "Albrecht Duerer"))
        self.assertFalse(names_equivalent("Bodo", "Bodo Sándor"))
        self.assertFalse(_is_person_name("Workshop of Utagawa Hiroshige"))
        self.assertFalse(_is_person_name("Anonymous"))
        self.assertTrue(_is_person_name("Raja Ravi Varma"))

    def test_changed_path_contract_classifies_museum_09a_without_release_or_deploy(self) -> None:
        result = classify_changes(
            [
                Change(status="A", path="museum_pipeline/art/global_expansion.py"),
                Change(status="A", path="data/reviewed/art/museum-09a/global-expansion-universe-v1/build-manifest.json"),
                Change(status="A", path="tests/test_museum_09a.py"),
            ]
        )
        self.assertEqual("phase-scoped", result["impact_level"])
        self.assertEqual([], result["affected_phases"])
        self.assertEqual([], result["releases_to_rebuild"])
        self.assertFalse(result["deploy_required"])
        self.assertFalse(result["full_required"])

    def test_named_invalid_cases_are_rejected_by_the_real_validator(self) -> None:
        registry = json.loads(INVALID_CASES.read_text(encoding="utf-8"))
        self.assertEqual(21, registry["case_count"])
        self.assertEqual(21, len(registry["cases"]))
        self.assertEqual(21, len({case["case_id"] for case in registry["cases"]}))
        expected = {case["expected_failure_code"] for case in registry["cases"]}

        with tempfile.TemporaryDirectory(prefix="museum-09a-invalid-") as temporary:
            root = Path(temporary) / "package"
            shutil.copytree(DEFAULT_OUTPUT, root)
            artists_doc = _read_collection(root, "normalized-candidates.json")
            candidate_works_doc = _read_collection(root, "candidate-artworks.json")
            target_works_doc = _read_collection(root, "target-artworks.json")
            batches_doc = _read(root, "batch-registry-snapshot.json")
            leakage_doc = _read(root, "public-leakage-label-set.json")
            build_doc = _read(root, "build-manifest.json")

            candidates = artists_doc["candidates"]
            targets = [artist for artist in candidates if artist["status"] == "program_target"]
            reserves = [artist for artist in candidates if artist["status"] == "reserve"]
            rejected = [artist for artist in candidates if artist["status"] == "rejected"]

            targets[1]["id"] = targets[0]["id"]
            targets[2]["deceased_status"] = "living"
            targets[3]["death"]["year"] = None
            targets[4]["artist_kind"] = "workshop"
            targets[5]["source_identities"] = []
            targets[6]["deceased_verification_evidence_ids"] = []
            targets[7]["inferred_ethnicity"] = "not_permitted"
            targets[8]["popularity_score"] = 1
            africa_target = next(
                artist for artist in targets if artist["primary_coverage_bucket"] == "africa"
            )
            africa_target["primary_coverage_bucket"] = "europe"
            reserves[0]["selection_reason_codes"] = []
            rejected[0]["status"] = "waiting_for_manual_review"
            candidates.reverse()

            candidate_works = candidate_works_doc["artworks"]
            target_works = target_works_doc["artworks"]
            candidate_works[1]["id"] = candidate_works[0]["id"]
            target_works[0]["attribution_qualifier"] = "attribution_conflict"
            target_works[1]["duplicate_cluster_id"] = target_works[0]["duplicate_cluster_id"]
            work_counts = Counter(work["artist_id"] for work in target_works)
            underfilled_artist_id = next(
                artist_id for artist_id, count in work_counts.items() if count == 3
            )
            replacement_artist_id = next(
                artist_id for artist_id in work_counts if artist_id != underfilled_artist_id
            )
            for work in target_works:
                if work["artist_id"] == underfilled_artist_id:
                    work["artist_id"] = replacement_artist_id
            for work in target_works[:1_501]:
                work["source_id"] = "forced_dominant_source"

            batches_doc["batches"][1]["artist_ids"][0] = batches_doc["batches"][0]["artist_ids"][0]
            leakage_doc["candidate_public_leakage_count"] = 1
            build_doc["public_release_changed"] = True

            _write_sharded_document(
                root,
                "normalized-candidates.json",
                artists_doc,
                **SHARDED_DOCUMENTS["normalized-candidates.json"],
            )
            _write_sharded_document(
                root,
                "candidate-artworks.json",
                candidate_works_doc,
                **SHARDED_DOCUMENTS["candidate-artworks.json"],
            )
            _write_sharded_document(
                root,
                "target-artworks.json",
                target_works_doc,
                **SHARDED_DOCUMENTS["target-artworks.json"],
            )
            write_canonical_json(root / "batch-registry-snapshot.json", batches_doc)
            write_canonical_json(root / "public-leakage-label-set.json", leakage_doc)
            write_canonical_json(root / "build-manifest.json", build_doc)
            (root / "forbidden-candidate-image.png").write_bytes(b"not-image-media-byte-sentinel")

            result = validate_global_expansion(root)
            actual = {failure["code"] for failure in result["failures"]}
            self.assertFalse(result["ok"])
            self.assertEqual(set(), expected - actual, sorted(expected - actual))


if __name__ == "__main__":
    unittest.main()
