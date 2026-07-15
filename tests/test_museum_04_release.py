from __future__ import annotations

import gzip
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from museum_pipeline.art.batch_validation import DEFAULT_PACKAGE
from museum_pipeline.art.public_release import (
    DEFAULT_OUTPUT,
    EXPECTED_FILES,
    EXPECTED_GRAPH_HASH,
    EXPECTED_PACKAGE_HASH,
    M03C_BUNDLE,
    _load_media_bundle,
    _load_package,
    _replace_owned_directory,
    _validate_museum_04_projection_with_validated_sources,
    build_museum_04_release,
    validate_museum_04_release,
)
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment
from scripts.scan_public_artifact_for_candidate_data import (
    scan_public_artifact,
    validated_museum_04_exempt_roots,
)
from scripts.validate_governance_foundation import validate_release_directory
from scripts.validate_museum_04_fixtures import run as run_fixtures


ROOT = Path(__file__).resolve().parents[1]


class Museum04ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validation = validate_museum_04_release(DEFAULT_OUTPUT)
        cls.prevalidated_sources = (_load_package(DEFAULT_PACKAGE), _load_media_bundle(M03C_BUNDLE))
        cls.documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in DEFAULT_OUTPUT.glob("*.json")
        }

    def test_local_bundle_is_formal_media_aware_release(self) -> None:
        self.assertTrue(self.validation["ok"], self.validation["failures"])
        self.assertEqual(
            {
                "artists": 12,
                "contexts": 31,
                "relationships": 36,
                "artworks": 44,
                "media": 242,
                "media_bytes": 35_907_176,
                "approved_media_artworks": 31,
                "no_image_artworks": 13,
            },
            {
                key: self.validation["counts"][key]
                for key in (
                    "artists", "contexts", "relationships", "artworks", "media", "media_bytes",
                    "approved_media_artworks", "no_image_artworks",
                )
            },
        )
        self.assertEqual({"manifest.json", *EXPECTED_FILES}, {path.name for path in DEFAULT_OUTPUT.iterdir() if path.is_file()})
        self.assertEqual(273, len(self.documents["manifest.json"]["included_media_asset_ids"]))
        self.assertEqual("publishable", self.documents["manifest.json"]["status"])
        self.assertTrue(self.documents["manifest.json"]["public_release"])
        self.assertTrue(all(item["review_status"] == "publishable" for item in self.documents["artists.json"]["artists"]))
        self.assertTrue(all(item["lifecycle_status"] == "publishable" for item in self.documents["artists.json"]["artists"]))
        self.assertTrue(all(item["summary_provenance"]["human_reviewed"] is False for item in self.documents["artists.json"]["artists"]))
        signoff = self.documents["release-signoff.json"]
        self.assertEqual("accepted_for_public_release", signoff["decision"])
        self.assertEqual("automated_pass", signoff["editorial_review_status"])
        self.assertFalse(signoff["human_review_dependency"])
        self.assertFalse(signoff["human_reviewer_claimed"])
        self.assertEqual("automated_release_validation_pipeline", signoff["reviewer_kind"])
        self.assertEqual(242, sum(path.suffix.lower() in {".jpg", ".jpeg", ".webp"} for path in DEFAULT_OUTPUT.rglob("*")))
        source_rule_snapshots = self.documents["source-rules-snapshot.json"]["sources"]
        self.assertEqual(
            {
                "source:aic_api": {"data"},
                "source:getty_ulan": {"data"},
                "source:met_open_access": {"data", "media"},
                "source:wikidata": {"data"},
            },
            {
                item["source_id"]: {rule["content_class"] for rule in item["license_rules"]}
                for item in source_rule_snapshots
            },
        )

    def test_actual_dtos_match_frontend_release_contract(self) -> None:
        evidence = self.documents["evidence.json"]["evidence"]
        self.assertTrue(all(set(item["summary"]) == {"zh-Hans", "en"} for item in evidence))
        self.assertTrue(all(set(item["reliability_note"]) == {"zh-Hans", "en"} for item in evidence))
        sources = self.documents["sources.json"]["sources"]
        self.assertTrue(all(item["locator"]["url"] == item["official_url"] for item in sources))
        search = self.documents["search-index.json"]["entries"]
        self.assertEqual(12, len(search))
        self.assertEqual({"artist"}, {item["type"] for item in search})
        self.assertTrue(all(set(item) == {"id", "type", "labels", "aliases", "normalized_keys"} for item in search))
        self.assertIn("traditions", self.documents["facets.json"]["facets"])
        rights = self.documents["rights.json"]
        for statement in (
            rights["code_rights"]["statement"], rights["original_content_rights"]["statement"],
            rights["third_party_metadata"]["statement"], rights["media"]["statement"],
        ):
            self.assertEqual({"zh-Hans", "en"}, set(statement))

    def test_media_parent_child_runtime_and_withdrawal_closure(self) -> None:
        media_records = self.documents["media-assets.json"]["assets"]
        parents = {item["id"]: item for item in media_records if item["delivery_mode"] == "external_link"}
        children = {item["id"]: item for item in media_records if item["delivery_mode"] == "self_hosted"}
        runtime_assets = {item["id"]: item for item in self.documents["media-index.json"]["assets"]}
        withdrawals = {item["media_id"]: item for item in self.documents["withdrawal-mapping.json"]["mappings"]}
        self.assertEqual(31, len(parents))
        self.assertEqual(242, len(children))
        self.assertEqual(set(children), set(runtime_assets))
        self.assertEqual(set(children), set(withdrawals))
        self.assertEqual(set(media_records_item["id"] for media_records_item in media_records), set(self.documents["manifest.json"]["included_media_asset_ids"]))
        self.assertTrue(all(item["development_only"] is False and item["publish_status"] == "publishable" for item in media_records))
        for media_id, runtime in runtime_assets.items():
            child = children[media_id]
            parent_id = runtime["parent_media_id"]
            self.assertIn(parent_id, parents)
            self.assertEqual(parent_id, child["derivation"]["derived_from_media_id"])
            self.assertEqual(runtime["sha256"], child["content_hash"])
            self.assertEqual("active", withdrawals[media_id]["status"])
            self.assertTrue((DEFAULT_OUTPUT / runtime["src"]).is_file())

    def test_relationship_chinese_explanations_are_specific_and_noncausal(self) -> None:
        artists = {item["id"]: item for item in self.documents["artists.json"]["artists"]}
        contexts = {item["id"]: item for item in self.documents["contexts.json"]["contexts"]}
        relation_labels = {
            "shared_material": "共同材料",
            "shared_subject": "共同题材",
            "shared_technique": "共同技法",
        }
        explanations = []
        for relationship in self.documents["relationships.json"]["relationships"]:
            explanation = relationship["short_explanation"]["zh-Hans"]
            explanations.append(explanation)
            required_terms = [
                artists[relationship["source_artist_id"]]["labels"]["zh-Hans"],
                artists[relationship["target_artist_id"]]["labels"]["zh-Hans"],
                relation_labels[relationship["type"]],
                *(contexts[context_id]["labels"]["zh-Hans"] for context_id in relationship["context_ids"]),
                "不表示",
                "因果关系",
            ]
            self.assertTrue(all(term in explanation for term in required_terms), relationship["id"])
        self.assertEqual(36, len(explanations))
        self.assertEqual(36, len(set(explanations)))

    def test_generic_physical_validator_accepts_media_aware_bundle(self) -> None:
        self.assertEqual([], validate_release_directory(DEFAULT_OUTPUT, load_schema_environment(ROOT)))

    def test_formal_release_gate_accepts_automated_cross_validation(self) -> None:
        result = _validate_museum_04_projection_with_validated_sources(
            DEFAULT_OUTPUT,
            self.prevalidated_sources[0],
            self.prevalidated_sources[1],
            [],
            require_public=True,
        )
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual([], result["codes"])

    def test_malformed_manifest_returns_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-04-malformed-manifest-") as temporary:
            release_root = Path(temporary) / "art-constellation-1.0.0"
            shutil.copytree(DEFAULT_OUTPUT, release_root)
            (release_root / "manifest.json").write_bytes(canonical_json_bytes([]))
            result = _validate_museum_04_projection_with_validated_sources(
                release_root,
                self.prevalidated_sources[0],
                self.prevalidated_sources[1],
                [],
            )
            self.assertFalse(result["ok"])
            self.assertIn("m04_document_type", result["codes"])

    def test_builder_is_deterministic_against_committed_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-04-determinism-") as temporary:
            generated = Path(temporary) / "art-constellation-1.0.0"
            result = build_museum_04_release(generated)
            self.assertTrue(result["ok"])
            expected = {
                path.relative_to(DEFAULT_OUTPUT).as_posix(): path.read_bytes()
                for path in DEFAULT_OUTPUT.rglob("*") if path.is_file()
            }
            observed = {
                path.relative_to(generated).as_posix(): path.read_bytes()
                for path in generated.rglob("*") if path.is_file()
            }
            self.assertEqual(expected, observed)

    def test_versioned_install_is_noop_when_equal_and_rejects_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-04-immutability-") as temporary:
            root = Path(temporary)
            output = root / "output"
            staged = root / "staged"
            output.mkdir()
            staged.mkdir()
            (output / "manifest.json").write_bytes(b"same")
            (staged / "manifest.json").write_bytes(b"same")
            _replace_owned_directory(staged, output)
            self.assertEqual(b"same", (output / "manifest.json").read_bytes())
            (staged / "manifest.json").write_bytes(b"drift")
            with self.assertRaisesRegex(ValueError, "immutable release"):
                _replace_owned_directory(staged, output)
            self.assertEqual(b"same", (output / "manifest.json").read_bytes())

    def test_graph_budget_and_sealed_baseline_hashes(self) -> None:
        performance_contract = self.documents["performance-contract.json"]
        performance = performance_contract["budgets"]
        self.assertEqual(100 * 1024, performance["graph_summary_gzip_bytes_max"])
        self.assertEqual(450 * 1024, performance["route_assets_gzip_bytes_max"])
        self.assertEqual(
            {
                "vertices": 1000,
                "edges": 5000,
                "full_initial_render": False,
                "rendering_mode": "capped_progressive",
                "initial_visible_vertices": 150,
                "initial_visible_edges": 600,
            },
            performance_contract["scale_boundaries"]["one_k"],
        )
        self.assertLessEqual(
            len(gzip.compress((DEFAULT_OUTPUT / "graph-summary.json").read_bytes(), mtime=0)),
            performance["graph_summary_gzip_bytes_max"],
        )
        self.assertEqual("sha256:70a1e28a8bc94e0397fb9617e3d912061a39e0580b48fc905fa45dcb0503b13e", sha256_file(DEFAULT_PACKAGE / "package-manifest.json"))
        self.assertEqual("sha256:77960c11ced4df5080f16631175ba68725cf4a8c6c21e5d8fc9c4f2b07886084", sha256_file(DEFAULT_PACKAGE / "graph-input.json"))
        self.assertEqual(EXPECTED_PACKAGE_HASH, self.documents["release-signoff.json"]["m03b_package_hash"])
        self.assertEqual(EXPECTED_GRAPH_HASH, self.documents["release-signoff.json"]["m03b_graph_hash"])

    def test_projection_exemption_keeps_generic_scans_active(self) -> None:
        exempt_roots, findings = validated_museum_04_exempt_roots(ROOT / "public")
        self.assertEqual([], findings)
        formal_terms = [{"value": "Albrecht Dürer", "match_mode": "casefold_substring"}]
        release_findings = scan_public_artifact(
            DEFAULT_OUTPUT,
            formal_art_terms=formal_terms,
            formal_art_exempt_roots=exempt_roots,
        )
        self.assertEqual([], release_findings)
        with tempfile.TemporaryDirectory(prefix="museum-04-scanner-") as temporary:
            root = Path(temporary)
            (root / "outside.json").write_text('"Albrecht Dürer"', encoding="utf-8")
            self.assertIn("formal_art_data_publicly_exposed", {item["code"] for item in scan_public_artifact(root, formal_art_terms=formal_terms)})
            (root / "outside.json").write_text('"Q42"', encoding="utf-8")
            self.assertIn("wikidata_qid", {item["code"] for item in scan_public_artifact(root, formal_art_terms=formal_terms, formal_art_exempt_roots={root})})

    def test_expected_invalid_fixture_matrix(self) -> None:
        result = run_fixtures(
            DEFAULT_OUTPUT,
            _base_validation=self.validation,
            _prevalidated_sources=self.prevalidated_sources,
        )
        self.assertTrue(result["ok"], result["results"])
        self.assertEqual(28, result["count"])


if __name__ == "__main__":
    unittest.main()
