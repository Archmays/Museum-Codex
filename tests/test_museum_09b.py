from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from museum_pipeline.art.formal_candidate import (
    BATCH_ID,
    DEFAULT_OUTPUT,
    DEFAULT_REFRESH_RECEIPT,
    DEFAULT_REGISTRY,
    M09A_ROOT,
    _directory_bytes_equal,
    _load_artworks,
    validate_formal_candidate,
)
from scripts.classify_ci_impact import Change, classify_changes


ROOT = Path(__file__).resolve().parents[1]
INVALID_CASES = ROOT / "fixtures" / "museum-09b" / "invalid-cases.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_artworks(root: Path, artworks: list[dict]) -> None:
    manifest = _read(root / "artworks.json")
    cursor = 0
    for shard in manifest["shards"]:
        count = shard["record_count"]
        document = _read(root / shard["path"])
        document["artworks"] = artworks[cursor:cursor + count]
        document["artwork_count"] = len(document["artworks"])
        _write(root / shard["path"], document)
        cursor += count


class Museum09BFormalCandidateTests(unittest.TestCase):
    def test_committed_formal_candidate_closes_exact_batch(self) -> None:
        result = validate_formal_candidate()
        self.assertTrue(result["ok"], result["failures"][:12])
        self.assertEqual(50, result["counts"]["artists"])
        self.assertEqual(488, result["counts"]["artworks"])
        self.assertEqual(12, result["counts"]["gallery_artists"])
        self.assertEqual(38, result["counts"]["collection_artists"])
        self.assertEqual(738, result["counts"]["claims"])
        self.assertEqual(738, result["counts"]["evidence"])
        self.assertEqual(10, result["counts"]["sources"])
        self.assertEqual(162, result["counts"]["contexts"])
        self.assertEqual(74, result["counts"]["place_time_episodes"])
        self.assertEqual(24, result["counts"]["relationships"])

    def test_source_drift_is_bounded_and_preserves_unchanged_records(self) -> None:
        receipt = _read(DEFAULT_REFRESH_RECEIPT)
        self.assertEqual(538, receipt["checked_count"])
        self.assertEqual(87, receipt["changed_count"])
        self.assertEqual(451, receipt["unchanged_count"])
        self.assertEqual(0, receipt["unavailable_count"])
        self.assertEqual(0, receipt["new_media_bytes"])
        self.assertEqual(14, receipt["network_request_count"])
        self.assertEqual(
            "source_refresh_unavailable_reused_last_complete_receipt",
            receipt["transport_history"][0]["outcome"],
        )
        unchanged = [item for item in receipt["records"] if item["status"] == "unchanged"]
        changed = [item for item in receipt["records"] if item["status"] == "changed"]
        self.assertTrue(all(item["old_hash"] == item["new_hash"] for item in unchanged))
        self.assertTrue(all(item["old_hash"] != item["new_hash"] for item in changed))
        self.assertTrue(all(len(item["affected_closure"]) == 2 for item in changed))

    def test_artist_depth_claims_media_and_wave_partitions(self) -> None:
        artists = _read(DEFAULT_OUTPUT / "artists.json")["artists"]
        claims = {item["id"] for item in _read(DEFAULT_OUTPUT / "claims.json")["claims"]}
        review = _read(DEFAULT_OUTPUT / "batch-review-summary.json")
        media = _read(DEFAULT_OUTPUT / "media-feasibility.json")
        self.assertEqual([10] * 5, [item["artist_count"] for item in review["waves"]])
        self.assertEqual(488, sum(item["artwork_count"] for item in review["waves"]))
        self.assertTrue(all(
            artist["overview"]["sentence_claim_ids"]
            and set(artist["overview"]["sentence_claim_ids"]) <= claims
            for artist in artists
        ))
        self.assertTrue(all(not artist["documented_activity_places"] for artist in artists))
        self.assertEqual(
            {
                "approved_external_iiif_candidate": 25,
                "approved_self_hosted_candidate": 40,
                "metadata_only_ready": 423,
            },
            media["status_counts"],
        )
        self.assertEqual(488, len(media["decisions"]))
        self.assertFalse(set(media["m09b_media_allowlist"]) & set(media["metadata_only_or_blocked_list"]))
        self.assertEqual(0, sum(item["bytes_downloaded"] for item in media["decisions"]))
        self.assertEqual(0, sum(item["derivatives_created"] for item in media["decisions"]))

    def test_sealed_package_copy_and_single_record_impact_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-09b-test-build-") as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            shutil.copytree(DEFAULT_OUTPUT, first)
            shutil.copytree(DEFAULT_OUTPUT, second)
            self.assertTrue(_directory_bytes_equal(first, second))

            impacted = root / "impacted"
            shutil.copytree(first, impacted)
            dossier_index = _read(first / "artist-dossier-index.json")["dossiers"]
            changed_dossier = dossier_index[0]
            changed_artist_id = changed_dossier["artist_id"]
            dossier_path = impacted / changed_dossier["path"]
            dossier_path.write_text(
                dossier_path.read_text(encoding="utf-8") + "\n<!-- local impact probe -->\n",
                encoding="utf-8",
                newline="\n",
            )

            first_artworks = _read(first / "artworks.json")
            changed_shard = first_artworks["shards"][0]["path"]
            shard_document = _read(impacted / changed_shard)
            shard_document["artworks"][0]["preferred_title"] += " [local impact probe]"
            _write(impacted / changed_shard, shard_document)

            changed_dossiers = [
                item["artist_id"] for item in dossier_index
                if (first / item["path"]).read_bytes() != (impacted / item["path"]).read_bytes()
            ]
            self.assertEqual([changed_artist_id], changed_dossiers)
            changed_shards = [
                item["path"] for item in first_artworks["shards"]
                if (first / item["path"]).read_bytes() != (impacted / item["path"]).read_bytes()
            ]
            self.assertEqual([changed_shard], changed_shards)

    def test_changed_paths_are_phase_scoped_without_release_or_deploy(self) -> None:
        result = classify_changes([
            Change(status="A", path="museum_pipeline/art/formal_candidate.py"),
            Change(status="A", path="scripts/build_museum_09b.py"),
            Change(
                status="A",
                path="data/reviewed/art/museum-09b/batch-01-formal-candidate-v1/build-manifest.json",
            ),
            Change(status="M", path="governance/museum-09-batch-registry.json"),
            Change(status="A", path="tests/test_museum_09b.py"),
        ])
        self.assertEqual("phase-scoped", result["impact_level"])
        self.assertFalse(result["public_changed"])
        self.assertFalse(result["runtime_changed"])
        self.assertFalse(result["deploy_required"])
        self.assertFalse(result["full_required"])
        self.assertEqual([], result["browser_suites"])
        self.assertEqual([], result["releases_to_rebuild"])

    def test_named_invalid_fixtures_are_rejected_by_real_validator(self) -> None:
        fixture_registry = _read(INVALID_CASES)
        self.assertEqual(30, fixture_registry["case_count"])
        self.assertEqual(30, len(fixture_registry["cases"]))
        self.assertEqual(30, len({item["case_id"] for item in fixture_registry["cases"]}))
        expected = {item["expected_failure_code"] for item in fixture_registry["cases"]}
        actual: set[str] = set()

        with tempfile.TemporaryDirectory(prefix="museum-09b-invalid-") as temporary:
            root = Path(temporary) / "package"
            shutil.copytree(DEFAULT_OUTPUT, root)
            artists_doc = _read(root / "artists.json")
            artists = artists_doc["artists"]
            artists[-1] = {**copy.deepcopy(artists[0]), "id": "artist:extra-invalid"}
            artists[1]["id"] = artists[0]["id"]
            artists[2]["tier"] = "collection"
            coverage_artist = next(
                item for item in artists if item["primary_coverage_bucket"] != "europe"
            )
            coverage_artist["primary_coverage_bucket"] = "invalid-region"
            artists[4]["deceased_status"] = "living"
            artists[5]["death"]["year"] = None
            artists[6]["artist_kind"] = "workshop"
            artists[7]["official_source_identities"] = []
            artists[8]["chinese_label_status"] = "authoritative_zh_label"
            artists[8]["chinese_label"] = None
            artists[9]["overview"]["sentence_claim_ids"] = []
            artists[10]["overview"]["en"] += " This is the most important artist."
            artists[11]["inferred_ethnicity"] = "forbidden"
            _write(root / "artists.json", artists_doc)

            artworks = _load_artworks(root)
            artworks[-1] = {**copy.deepcopy(artworks[0]), "id": "artwork:extra-invalid",
                            "m09a_candidate_work_id": "candidate-work:extra-invalid"}
            artworks[1]["id"] = artworks[0]["id"]
            artworks[2]["attribution_qualifier"] = "attribution_conflict"
            artworks[3]["duplicate_cluster_id"] = artworks[2]["duplicate_cluster_id"]
            artworks[4]["creation_place"] = "inferred"
            artworks[5]["holding_institution_used_as_creation_place"] = True
            artworks[6]["artist_id"] = "artist:outside-batch"
            artworks[7]["source_id"] = "source:unclosed"
            artworks[8]["claim_ids"] = []
            _write_artworks(root, artworks)

            claims_doc = _read(root / "claims.json")
            claims_doc["claims"][0]["evidence_ids"] = []
            _write(root / "claims.json", claims_doc)
            sources_doc = _read(root / "sources.json")
            sources_doc["sources"][0]["official_host"] = None
            _write(root / "sources.json", sources_doc)
            episodes_doc = _read(root / "place-time-episodes.json")
            episodes_doc["episodes"][0]["place_label"] = "holding institution"
            episodes_doc["episodes"][0]["place_source_status"] = "unsupported"
            episodes_doc["episodes"][0]["holding_institution_used_as_creation_or_activity_place"] = True
            _write(root / "place-time-episodes.json", episodes_doc)

            media_doc = _read(root / "media-feasibility.json")
            approved = next(
                item for item in media_doc["decisions"]
                if item["delivery_decision"].startswith("approved_")
            )
            approved["reason_codes"] = ["general_policy_only"]
            media_doc["decisions"][0]["media_bytes_present"] = True
            media_doc["decisions"][1]["decision_status"] = "waiting_for_manual_review"
            _write(root / "media-feasibility.json", media_doc)
            (root / "invalid-downloaded-media.png").write_bytes(b"fixture sentinel")

            leakage_doc = _read(root / "public-leakage-label-set.json")
            leakage_doc["candidate_public_leakage_count"] = 1
            _write(root / "public-leakage-label-set.json", leakage_doc)
            replacement_doc = _read(root / "replacement-ledger.json")
            replacement_doc["reserve_order_respected"] = False
            _write(root / "replacement-ledger.json", replacement_doc)
            drift_doc = _read(root / "source-drift-manifest.json")
            drift_doc["checked_count"] = 537
            _write(root / "source-drift-manifest.json", drift_doc)
            manifest_doc = _read(root / "build-manifest.json")
            manifest_doc["input_release_content_hash"] = "sha256:invalid"
            manifest_doc["pages_artifact_count"] = 1
            _write(root / "build-manifest.json", manifest_doc)

            result = validate_formal_candidate(root)
            actual |= {item["code"] for item in result["failures"]}

            registry = _read(DEFAULT_REGISTRY)
            registry["batches"][1]["status"] = "formal_candidate_ready"
            registry["batches"][1]["artist_ids"][0] = registry["batches"][0]["artist_ids"][0]
            registry_path = Path(temporary) / "registry.json"
            _write(registry_path, registry)
            registry_result = validate_formal_candidate(DEFAULT_OUTPUT, registry_path=registry_path)
            actual |= {item["code"] for item in registry_result["failures"]}

            m09a_root = Path(temporary) / "m09a"
            m09a_root.mkdir()
            shutil.copy2(M09A_ROOT / "museum-09b-first-batch.json", m09a_root)
            (m09a_root / "mutation-sentinel.txt").write_text("invalid fixture", encoding="utf-8")
            m09a_result = validate_formal_candidate(DEFAULT_OUTPUT, m09a_root=m09a_root)
            actual |= {item["code"] for item in m09a_result["failures"]}

        self.assertEqual(set(), expected - actual, sorted(expected - actual))


if __name__ == "__main__":
    unittest.main()
