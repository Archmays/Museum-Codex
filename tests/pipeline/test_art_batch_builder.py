from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import museum_pipeline.art.batch_validation as batch_validation
from museum_pipeline.art.batch import (
    _directories_equal,
    _exclusive_lock,
    _formal_exclusions,
    _load_batch_review_signoffs,
    _normalize_components,
    _publish_directory,
    _validate_batch_review_basis,
    _verify_code_commit,
    build_artwork_selection_basis,
    build_formal_batch_manifest,
    build_graph_input,
)
from museum_pipeline.art.batch_validation import (
    _read_root_manifest,
    _validate_artwork_selection_basis,
    _validate_decision_closure,
    _validate_graph,
    _validate_physical_package,
    _validate_relationship_dispositions,
    _validate_shared_contract,
    _validate_tracked_batch_signoffs,
    validate_approved_batch,
)
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import record_identity_issues, source_license_binding_issues


class ArtBatchBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        root = Path(__file__).resolve().parents[2]
        package = root / "data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1"

        def load(name: str):
            return json.loads((package / name).read_text(encoding="utf-8"))

        raw = {
            "decision": load("selection-decision.json"),
            "application": load("selection-application.json"),
            "identity_basis": load("identity-basis.json"),
            "artwork_selection_basis": json.loads(
                (root / "research/art/museum-03b-artwork-selection-basis.json").read_text(encoding="utf-8")
            ),
            "artists": load("artists.json"),
            "artworks": load("artworks.json"),
            "contexts": load("contexts.json"),
            "relationships": load("relationships.json"),
            "claims": load("claims.json"),
            "evidence": load("evidence.json"),
            "sources": load("sources.json"),
            "media_assessments": load("media-assessments.json"),
            "relationship_dispositions": load("relationship-dispositions.json"),
            "signoffs": load("review-signoffs.json"),
            "snapshot_receipt_ledgers": load("snapshot-receipt-ledgers.json"),
        }
        cls.components = _normalize_components(raw)
        cls.sealed_formal_artwork_basis = load("artwork-selection-basis.json")
        cls.sealed_graph = load("graph-input.json")
        cls.formal_artwork_basis = build_artwork_selection_basis(
            research_basis=cls.components["artwork_research_basis"],
            artworks=cls.components["artworks"],
            approved_artist_ids=[item["artist_id"] for item in cls.components["identity_basis"]["bindings"]],
            selection_application_id=cls.components["application"]["id"],
            review_signoff_ids=["review-signoff:museum-03b-batch-data"],
            generated_at="2026-07-13T15:32:00+08:00",
        )
        cls.graph = build_graph_input(
            artists=cls.components["artists"],
            contexts=cls.components["contexts"],
            relationships=cls.components["relationships"],
            claims=cls.components["claims"],
            evidence=cls.components["evidence"],
            sources=cls.components["sources"],
            review_signoff_ids=[
                "review-signoff:museum-03b-batch-data",
                "review-signoff:museum-03b-batch-relationship",
            ],
            generated_at="2026-07-13T15:32:00+08:00",
        )

    def test_rebuilt_aggregates_equal_the_sealed_package(self) -> None:
        self.assertEqual(self.sealed_formal_artwork_basis, self.formal_artwork_basis)
        self.assertEqual(self.sealed_graph, self.graph)

    def test_batch_aggregate_records_use_governed_identity_without_factual_binding_duplication(self) -> None:
        self.assertEqual(
            [],
            record_identity_issues(
                {
                    "id": "selection-decision:00000000-0000-5000-8000-000000000001",
                    "entity_type": "selection_decision",
                },
                "$.decision",
            ),
        )
        self.assertEqual(
            [],
            source_license_binding_issues(
                {
                    "id": "graph-input:fixture",
                    "entity_type": "graph_input",
                    "source_ids": ["source:fixture"],
                },
                {},
                "$.graph",
            ),
        )

    def test_physical_validator_pins_exact_user_selection(self) -> None:
        root = Path(__file__).resolve().parents[2]
        decision = json.loads(
            (root / "governance/decisions/museum-03b-selection-decision.json").read_text(encoding="utf-8")
        )
        application = json.loads(
            (root / "governance/decisions/museum-03b-selection-application.json").read_text(encoding="utf-8")
        )
        identity_basis = json.loads(
            (root / "research/art/museum-03b-approved-identity-basis.json").read_text(encoding="utf-8")
        )
        indexed = {item["id"]: item for item in (decision, application, identity_basis)}
        failures: list[dict[str, str]] = []
        _validate_decision_closure(indexed, failures)
        self.assertEqual([], failures)

        decision["selected_candidate_ids"][-1] = "artist-candidate:00000000-0000-5000-8000-000000000000"
        application["selected_candidate_ids"] = list(decision["selected_candidate_ids"])
        failures = []
        _validate_decision_closure(indexed, failures)
        self.assertIn("approved_candidate_set_mismatch", {item["code"] for item in failures})

    def test_rich_artwork_research_is_projected_to_formal_schema(self) -> None:
        artist_ids = [f"artist:synthetic-{index:02d}" for index in range(1, 13)]
        artworks = []
        entries = []
        for index in range(1, 45):
            artist_id = artist_ids[(index - 1) % len(artist_ids)]
            object_id = str(1000 + index)
            artworks.append(
                {
                    "id": f"artwork:synthetic-{index:02d}",
                    "approved_artist_id": artist_id,
                    "official_object_record": {
                        "source_id": "source:met_open_access",
                        "source_object_id": object_id,
                        "official_object_url": f"https://example.invalid/objects/{object_id}",
                    },
                }
            )
            entries.append(
                {
                    "approved_artist_id": artist_id,
                    "source_id": "met_open_access",
                    "source_object_id": object_id,
                    "selection_note": "Selected for a bounded comparative question using the official object record.",
                    "creation_span": {"precision": "year"},
                    "material_ids": ["material:paper"],
                    "technique_ids": ["technique:printmaking"],
                    "subject_ids": ["subject:portraiture"],
                    "rights_preflight_id": f"artwork-preflight:{uuid.uuid5(uuid.NAMESPACE_URL, object_id)}",
                }
            )
        projected = build_artwork_selection_basis(
            research_basis={"entries": entries},
            artworks=artworks,
            approved_artist_ids=artist_ids,
            selection_application_id="selection-decision-application:00000000-0000-0000-0000-000000000001",
            review_signoff_ids=["review-signoff:data"],
            generated_at="2026-07-13T14:35:00+08:00",
        )

        self.assertEqual(44, len(projected["selections"]))
        self.assertEqual(set(artist_ids), set(projected["approved_artist_ids"]))
        self.assertEqual([], validate_record(projected))

    def test_graph_has_exact_primary_slate_and_no_media_dependency(self) -> None:
        artists = [
            {
                "id": f"artist:synthetic-{index:02d}",
                "labels": {"en": f"Artist {index:02d}", "zh-Hans": f"艺术家{index:02d}"},
                "claim_ids": [f"claim:artist-{index:02d}"],
                "source_ids": ["source:synthetic"],
            }
            for index in range(1, 13)
        ]
        context = {
            "id": "subject:synthetic-subject",
            "entity_type": "subject",
            "labels": {"en": "Synthetic subject", "zh-Hans": "合成主题"},
            "claim_ids": ["claim:context"],
            "source_ids": ["source:synthetic"],
        }
        relationship = {
            "id": "art-rel:synthetic-01",
            "source_entity_id": artists[0]["id"],
            "target_entity_id": artists[1]["id"],
            "relationship_type": "shared_subject",
            "directed": False,
            "evidence_level": "C",
            "educational_rationale": {"en": "Compare the reviewed subject.", "zh-Hans": "比较已审主题。"},
            "context_entity_ids": [context["id"]],
            "temporal_scope": {"start": None, "end": None, "precision": "unknown", "uncertain": True, "description": "No shared time asserted."},
            "place_scope": {"place_ids": [], "description": "No shared place asserted."},
            "historical_relationship_strength": None,
            "evidence_confidence": 0.9,
            "computational_similarity": None,
            "curatorial_relevance": 0.8,
            "claim_ids": ["claim:relationship"],
            "source_ids": ["source:synthetic"],
            "is_algorithmic": False,
        }
        claims = [
            {
                "id": claim_id,
                "evidence_ids": [f"evidence:{claim_id.removeprefix('claim:')}"]
            }
            for claim_id in [
                *(item["claim_ids"][0] for item in artists),
                "claim:context",
                "claim:relationship",
            ]
        ]
        evidence = [
            {"id": item["evidence_ids"][0], "source_ids": ["source:synthetic"]}
            for item in claims
        ]
        graph = build_graph_input(
            artists=artists,
            contexts=[context],
            relationships=[relationship],
            claims=claims,
            evidence=evidence,
            sources=[{"id": "source:synthetic"}],
            review_signoff_ids=["review-signoff:data", "review-signoff:release"],
            generated_at="2026-07-13T14:35:00+08:00",
        )

        expected_ids = sorted(item["id"] for item in artists)
        self.assertEqual(expected_ids, graph["approved_artist_ids"])
        self.assertEqual(expected_ids, [item["artist_id"] for item in graph["primary_nodes"]])
        self.assertEqual({context["id"]}, {item["context_id"] for item in graph["context_nodes"]})
        self.assertEqual({relationship["id"]}, {item["relationship_id"] for item in graph["edges"]})
        self.assertTrue(graph["no_algorithmic_edges"])
        self.assertTrue(graph["no_media_dependency"])
        self.assertFalse(graph["public_release"])
        self.assertTrue(all(edge["media_dependency"] is False for edge in graph["edges"]))
        self.assertEqual(canonical_sha256({key: value for key, value in graph.items() if key != "content_hash"}), graph["content_hash"])
        self.assertNotIn("media_asset", json.dumps(graph, ensure_ascii=False).lower())

    def test_formal_manifest_is_deterministic_and_declares_boundaries(self) -> None:
        components = {
            "decision": {"id": "selection-decision:00000000-0000-0000-0000-000000000001"},
            "application": {
                "id": "selection-decision-application:00000000-0000-0000-0000-000000000001",
                "input_bundle_hash": "sha256:" + "a" * 64,
            },
            "artwork_research_basis": {
                "excluded_candidates": [
                    {"source_id": "met_open_access", "source_object_id": "123", "reason": "Not selected."}
                ]
            },
            "snapshot_receipt_ledgers": [
                {
                    "entries": [
                        {"snapshot_id": "snapshot:synthetic:one", "body_sha256": "sha256:" + "1" * 64},
                        {"snapshot_id": "snapshot:synthetic:two", "body_sha256": "sha256:" + "2" * 64},
                    ]
                },
                {
                    "entries": [
                        {"snapshot_id": "snapshot:synthetic:one", "body_sha256": "sha256:" + "1" * 64}
                    ]
                },
            ],
            "artists": [{"id": "artist:one"}],
            "artworks": [{"id": "artwork:one"}],
            "contexts": [{"id": "subject:one"}],
            "relationships": [{"id": "art-rel:one"}],
            "claims": [{"id": "claim:one"}],
            "evidence": [{"id": "evidence:one"}],
            "sources": [
                {"id": "source:met_open_access"},
                {"id": "source:getty_ulan"},
            ],
            "media_assessments": [{"id": "media-assessment:one"}],
            "signoffs": [{"id": "review-signoff:one"}],
        }
        first = build_formal_batch_manifest(
            components=components,
            code_commit="a" * 40,
            reviewer_signoff_ids=["review-signoff:one"],
            generated_at="2026-07-13T14:35:00+08:00",
        )
        second = build_formal_batch_manifest(
            components=components,
            code_commit="a" * 40,
            reviewer_signoff_ids=["review-signoff:one"],
            generated_at="2026-07-13T14:35:00+08:00",
        )

        self.assertEqual(first, second)
        self.assertEqual(2, first["counts"]["raw_snapshots"])
        self.assertFalse(first["no_media_declaration"]["media_bytes_downloaded"])
        self.assertFalse(first["no_public_release_declaration"]["formal_public_release_created"])
        self.assertEqual(
            {
                "source:getty_ulan": "0.1.1",
                "source:met_open_access": "0.1.0",
            },
            {item["source_id"]: item["version"] for item in first["adapter_versions"]},
        )
        self.assertEqual(canonical_sha256({key: value for key, value in first.items() if key != "content_hash"}), first["content_hash"])

    def test_formal_exclusions_publish_only_the_aggregate_omission(self) -> None:
        exclusions = _formal_exclusions(self.components["artwork_research_basis"])
        self.assertEqual("artwork-exclusion-set:museum-03b-held-out-alternates", exclusions[0]["record_id"])
        self.assertRegex(exclusions[0]["record_id"], r"^[a-z][a-z0-9_-]*:[a-z0-9][a-z0-9._-]*$")
        self.assertIn("4 held-out alternatives", exclusions[0]["reason"])
        self.assertIn(self.components["artwork_research_basis"]["excluded_candidate_set_hash"], exclusions[0]["reason"])
        self.assertNotIn("source_object_id", json.dumps(exclusions))

    def test_relationship_dispositions_pin_exact_status_mapping_and_backlinks(self) -> None:
        failures: list[dict[str, str]] = []
        _validate_relationship_dispositions(
            self.components["relationship_dispositions"],
            self.components["relationships"],
            failures,
        )
        self.assertEqual([], failures)

        mutated = deepcopy(self.components["relationship_dispositions"])
        promoted = next(item for item in mutated if item.get("disposition") == "promoted_to_formal_relationship")
        promoted["formal_relationship_id"] = "art-rel:m03b-036"
        failures = []
        _validate_relationship_dispositions(mutated, self.components["relationships"], failures)
        codes = {item["code"] for item in failures}
        self.assertIn("relationship_inherited_disposition_mismatch", codes)
        self.assertIn("relationship_disposition_backlink_mismatch", codes)

    def test_artwork_selection_basis_rejects_coordinated_semantic_drift(self) -> None:
        failures: list[dict[str, str]] = []
        _validate_artwork_selection_basis(self.formal_artwork_basis, self.components["artworks"], failures)
        self.assertEqual([], failures)

        mutated = deepcopy(self.formal_artwork_basis)
        mutated["selections"][0]["official_object_url"] = "https://example.invalid/coordinated-reseal"
        mutated["content_hash"] = canonical_sha256({key: value for key, value in mutated.items() if key != "content_hash"})
        failures = []
        _validate_artwork_selection_basis(mutated, self.components["artworks"], failures)
        codes = {item["code"] for item in failures}
        self.assertIn("artwork_selection_projection_mismatch", codes)
        self.assertIn("artwork_selection_set_hash_mismatch", codes)

    def test_graph_rejects_resealed_aggregate_and_edge_truncation(self) -> None:
        failures: list[dict[str, str]] = []
        _validate_graph(
            self.graph,
            self.components["artists"],
            self.components["contexts"],
            self.components["relationships"],
            self.components["claims"],
            self.components["evidence"],
            self.components["sources"],
            failures,
        )
        self.assertEqual([], failures)

        mutated = deepcopy(self.graph)
        mutated["claim_ids"] = mutated["claim_ids"][:-1]
        mutated["edges"][0]["source_ids"] = []
        mutated["content_hash"] = canonical_sha256({key: value for key, value in mutated.items() if key != "content_hash"})
        failures = []
        _validate_graph(
            mutated,
            self.components["artists"],
            self.components["contexts"],
            self.components["relationships"],
            self.components["claims"],
            self.components["evidence"],
            self.components["sources"],
            failures,
        )
        codes = {item["code"] for item in failures}
        self.assertIn("graph_claim_aggregate_mismatch", codes)
        self.assertIn("graph_edge_projection_mismatch", codes)

    def test_root_manifest_and_descendant_namespace_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package-v1"
            root.mkdir()
            manifest_path = root / "package-manifest.json"
            manifest_path.write_text(json.dumps({"files": []}, indent=2), encoding="utf-8")
            failures: list[dict[str, str]] = []
            _read_root_manifest(root, manifest_path, failures)
            self.assertIn("package_manifest_not_canonical_json", {item["code"] for item in failures})

            nested = root / "nested"
            nested.mkdir()
            (nested / "package-manifest.json").write_bytes(canonical_json_bytes({"nested": True}))
            failures = []
            _validate_physical_package(
                root,
                {"files": [], "declared_file_count": 0, "total_bytes": 0},
                failures,
                load_schema_environment(),
            )
            codes = {item["code"] for item in failures}
            self.assertIn("nested_package_manifest_name_forbidden", codes)
            self.assertIn("package_file_set_mismatch", codes)

    def test_symlink_root_and_descendant_escape_are_rejected_without_os_privileges(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "package-v1"
            root.mkdir()
            outside = workspace / "outside.json"
            outside.write_bytes(b"{}")
            descendant = root / "escaped.json"
            descendant.write_bytes(b"{}")

            original_is_symlink = Path.is_symlink
            original_resolve = Path.resolve

            def simulated_is_symlink(path: Path) -> bool:
                return path == descendant or original_is_symlink(path)

            def simulated_resolve(path: Path, *args: object, **kwargs: object) -> Path:
                if path == descendant:
                    return outside
                return original_resolve(path, *args, **kwargs)

            failures: list[dict[str, str]] = []
            with (
                patch.object(Path, "is_symlink", autospec=True, side_effect=simulated_is_symlink),
                patch.object(Path, "resolve", autospec=True, side_effect=simulated_resolve),
            ):
                _validate_physical_package(
                    root,
                    {"files": [], "declared_file_count": 0, "total_bytes": 0},
                    failures,
                    load_schema_environment(),
                )
            codes = {item["code"] for item in failures}
            self.assertIn("package_symlink_forbidden", codes)
            self.assertIn("package_path_escape", codes)

            def root_is_symlink(path: Path) -> bool:
                return path == root or original_is_symlink(path)

            with patch.object(Path, "is_symlink", autospec=True, side_effect=root_is_symlink):
                result = validate_approved_batch(root)
            self.assertIn("package_root_symlink_forbidden", {item["code"] for item in result["failures"]})

    def test_code_commit_must_exist_and_match_current_implementation_inputs(self) -> None:
        with patch("museum_pipeline.art.batch.subprocess.run", return_value=Mock(returncode=1, stdout=b"", stderr=b"missing")):
            with self.assertRaises(PipelineError) as unknown:
                _verify_code_commit("a" * 40)
        self.assertEqual("code_commit_unknown", unknown.exception.code)

        def mismatching_git(args: list[str], **_: object) -> Mock:
            if args[1] == "cat-file":
                return Mock(returncode=0, stdout=b"", stderr=b"")
            return Mock(returncode=0, stdout=b"not-current-bytes", stderr=b"")

        with patch("museum_pipeline.art.batch.subprocess.run", side_effect=mismatching_git):
            with self.assertRaises(PipelineError) as mismatch:
                _verify_code_commit("a" * 40)
        self.assertEqual("code_commit_implementation_mismatch", mismatch.exception.code)

    def test_sealed_package_code_anchor_requires_known_ancestor_commit(self) -> None:
        commit = "a" * 40
        failures: list[dict[str, str]] = []
        with patch.object(
            batch_validation.subprocess,
            "run",
            side_effect=[Mock(returncode=0), Mock(returncode=0)],
        ) as run:
            batch_validation._validate_code_commit(commit, failures)
        self.assertEqual([], failures)
        self.assertEqual(["git", "merge-base", "--is-ancestor", commit, "HEAD"], run.call_args_list[1].args[0])

        failures = []
        with patch.object(batch_validation.subprocess, "run", return_value=Mock(returncode=1)):
            batch_validation._validate_code_commit(commit, failures)
        self.assertEqual({"code_commit_unknown"}, {item["code"] for item in failures})

        failures = []
        with patch.object(
            batch_validation.subprocess,
            "run",
            side_effect=[Mock(returncode=0), Mock(returncode=1)],
        ):
            batch_validation._validate_code_commit(commit, failures)
        self.assertEqual({"code_commit_not_ancestor"}, {item["code"] for item in failures})

    def test_builder_consumes_tracked_hash_bound_signoffs(self) -> None:
        review_set, signoffs = _load_batch_review_signoffs(self.components)
        self.assertEqual(
            [
                "2026-07-13T15:30:00+08:00",
                "2026-07-13T15:31:00+08:00",
                "2026-07-13T15:32:00+08:00",
            ],
            [item["reviewed_at"] for item in signoffs],
        )
        _validate_batch_review_basis(review_set, self.components, self.formal_artwork_basis)

        mutated = deepcopy(self.components)
        mutated["contexts"][0]["id"] = "subject:coordinated-reseal"
        with self.assertRaises(PipelineError) as drift:
            _validate_batch_review_basis(review_set, mutated, self.formal_artwork_basis)
        self.assertEqual("batch_review_basis_drift", drift.exception.code)

        mutated_signoffs = deepcopy(signoffs)
        mutated_signoffs[0]["decision_note"] = "Coordinated post-review mutation."
        failures: list[dict[str, str]] = []
        _validate_tracked_batch_signoffs(
            [*self.components["signoffs"], *mutated_signoffs],
            artists=self.components["artists"],
            artworks=self.components["artworks"],
            contexts=self.components["contexts"],
            relationships=self.components["relationships"],
            claims=self.components["claims"],
            evidence=self.components["evidence"],
            sources=self.components["sources"],
            assessments=self.components["media_assessments"],
            dispositions=self.components["relationship_dispositions"],
            artwork_selection_basis=self.formal_artwork_basis,
            failures=failures,
        )
        self.assertIn("batch_review_signoff_records_mismatch", {item["code"] for item in failures})

    def test_formal_package_is_constrained_by_shared_fixture_contract(self) -> None:
        records = [
            self.components["decision"],
            self.components["application"],
            *self.components["artists"],
            *self.components["artworks"],
            *self.components["contexts"],
            *self.components["relationships"],
            *self.components["media_assessments"],
        ]
        indexed = {item["id"]: item for item in records}
        package_manifest = {
            "files": [],
            "no_symlink_escape": True,
            "safe_relative_paths": True,
            "no_media_bytes": True,
            "no_published_state": True,
        }
        failures: list[dict[str, str]] = []
        _validate_shared_contract(indexed, package_manifest, failures)
        self.assertEqual([], failures)

        with patch.object(batch_validation, "validate_art_batch_contract", return_value={"sentinel_mutation"}) as shared:
            failures = []
            _validate_shared_contract(indexed, package_manifest, failures)
        shared.assert_called_once()
        self.assertIn("shared_contract_sentinel_mutation", {item["code"] for item in failures})

    def test_atomic_publish_reuses_identical_and_rejects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "staged"
            output = root / "package-v1"
            staged.mkdir()
            (staged / "records.json").write_bytes(b"{}")

            self.assertFalse(_publish_directory(staged, output))
            self.assertTrue(output.is_dir())

            identical = root / "identical"
            identical.mkdir()
            (identical / "records.json").write_bytes(b"{}")
            self.assertTrue(_publish_directory(identical, output))
            self.assertTrue(_directories_equal(identical, output))

            different = root / "different"
            different.mkdir()
            (different / "records.json").write_bytes(b'{"different":true}')
            with self.assertRaisesRegex(PipelineError, "Refusing to overwrite"):
                _publish_directory(different, output)
            self.assertEqual(b"{}", (output / "records.json").read_bytes())

    def test_lock_rejects_overlap_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / ".package-v1.lock"
            with _exclusive_lock(lock):
                self.assertTrue(lock.exists())
                with self.assertRaisesRegex(PipelineError, "owns the lock"):
                    with _exclusive_lock(lock):
                        pass
            self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
