from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.validate_governance_foundation import (
    ROOT,
    canonical_source_identities,
    canonical_release_path,
    expected_target_schema,
    fixture_paths,
    load_schema_environment,
    media_publish_issues,
    policy_issues,
    reference_graph_issues,
    record_is_publishable,
    release_bundle_issues,
    release_content_hash,
    schema_manifest_entries,
    schema_issues,
    source_publish_issues,
    target_schema_binding_issues,
    validate_release_directory,
    validate_fixture,
)
from scripts.validate_publishable_media_rights import scan
from scripts.validate_source_registry import REQUIRED_SOURCE_IDS, validate as validate_registry


class GovernanceFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = load_schema_environment(ROOT)

    def test_all_required_schemas_are_well_formed(self) -> None:
        required = {
            "schemas/common/entity.schema.json",
            "schemas/common/relationship.schema.json",
            "schemas/common/claim.schema.json",
            "schemas/common/evidence.schema.json",
            "schemas/common/source.schema.json",
            "schemas/common/media-asset.schema.json",
            "schemas/common/dataset-release.schema.json",
            "schemas/common/attribution-manifest.schema.json",
            "schemas/common/third-party-notices.schema.json",
            "schemas/common/license-decision-registry.schema.json",
            "schemas/common/source-rules-snapshot.schema.json",
            "schemas/art/artist.schema.json",
            "schemas/art/artwork.schema.json",
            "schemas/art/artist-relationship.schema.json",
            "schemas/art/release/art-constellation-artifact.schema.json",
            "schemas/art/release/media-asset-collection.schema.json",
            "schemas/art/release/public-constellation-record.schema.json",
            "schemas/art/release/release-withdrawal-mapping.schema.json",
            "schemas/art/release/runtime-media-index.schema.json",
            "schemas/art/release/art-gallery-interaction-index.schema.json",
            "schemas/art/batch/review-signoff.schema.json",
            "schemas/art/batch/approved-identity-basis.schema.json",
            "schemas/art/batch/snapshot-receipt-ledger.schema.json",
            "schemas/art/context/art-context.schema.json",
            "schemas/art/batch/artwork-selection-basis.schema.json",
            "schemas/art/batch/manual-evidence-capture.schema.json",
            "schemas/art/batch/relationship-research-disposition.schema.json",
            "schemas/art/batch/media-eligibility-assessment.schema.json",
            "schemas/art/batch/formal-art-batch-manifest.schema.json",
            "schemas/art/batch/reviewed-package-manifest.schema.json",
            "schemas/art/batch/graph-input.schema.json",
            "schemas/art/batch/replacement-review-request.schema.json",
            "schemas/art/batch/public-leakage-label-set.schema.json",
            "schemas/art/media/acquisition-request.schema.json",
            "schemas/art/media/acquisition-event.schema.json",
            "schemas/art/media/byte-record.schema.json",
            "schemas/art/media/automated-review.schema.json",
            "schemas/art/media/identity-rights-cross-check.schema.json",
            "schemas/art/media/quality-assessment.schema.json",
            "schemas/art/media/derivative-record.schema.json",
            "schemas/art/media/media-source-ledger.schema.json",
            "schemas/art/media/media-bundle-manifest.schema.json",
            "schemas/art/media/alternative-source-search.schema.json",
            "schemas/art/media/media-retry.schema.json",
            "schemas/art/media/withdrawal-mapping.schema.json",
            "schemas/art/release/public-constellation-record.schema.json",
            "schemas/art/release/art-constellation-artifact.schema.json",
            "schemas/curation/curation-common.schema.json",
            "schemas/curation/artist-candidate-preflight.schema.json",
            "schemas/curation/artwork-rights-preflight.schema.json",
            "schemas/curation/relationship-lead.schema.json",
            "schemas/curation/selection-scenario.schema.json",
            "schemas/curation/selection-decision.schema.json",
            "schemas/curation/selection-decision-application.schema.json",
            "schemas/curation/selection-review-bundle.schema.json",
            "schemas/pipeline/adapter-contract.schema.json",
            "schemas/pipeline/acquisition-request.schema.json",
            "schemas/pipeline/raw-snapshot-manifest.schema.json",
            "schemas/pipeline/field-provenance.schema.json",
            "schemas/pipeline/normalized-candidate.schema.json",
            "schemas/pipeline/identity-proposal.schema.json",
            "schemas/pipeline/merge-record.schema.json",
            "schemas/pipeline/review-decision.schema.json",
            "schemas/pipeline/pipeline-run.schema.json",
            "schemas/pipeline/review-bundle.schema.json",
            "schemas/biology/taxon.schema.json",
            "schemas/biology/ecosystem-interaction.schema.json",
        }
        self.assertEqual(required, set(self.environment.by_path))

    def test_schema_manifest_tracks_all_dependencies(self) -> None:
        entries = {entry["path"]: entry for entry in schema_manifest_entries(ROOT)}
        self.assertEqual(set(self.environment.by_path), set(entries))
        self.assertEqual(
            ["schemas/common/relationship.schema.json", "schemas/common/entity.schema.json"],
            entries["schemas/art/artist-relationship.schema.json"]["depends_on"],
        )
        self.assertEqual("1.1.0", entries["schemas/common/entity.schema.json"]["version"])
        self.assertEqual("1.1.0", entries["schemas/art/artwork.schema.json"]["version"])
        self.assertEqual("1.1.0", entries["schemas/art/artist-relationship.schema.json"]["version"])

    def test_open_decisions_register_exactly_four_unresolved_items(self) -> None:
        text = (ROOT / "docs" / "05_roadmap" / "open-decisions.md").read_text(encoding="utf-8")
        unresolved = text.split("## 已关闭事项", 1)[0]
        ids = re.findall(r"^\| (OD-\d{3}) \|", unresolved, flags=re.MULTILINE)
        self.assertEqual(["OD-006", "OD-008", "OD-009", "OD-011"], ids)

    def test_museum_04_rights_decisions_are_closed_without_open_license(self) -> None:
        registry = json.loads((ROOT / "governance" / "license-decisions.json").read_text(encoding="utf-8"))
        decisions = {item["decision_id"]: item for item in registry["decisions"]}
        for decision_id, subject in (
            ("license-decision:od-001", "code"),
            ("license-decision:od-002", "original_content"),
        ):
            decision = decisions[decision_id]
            self.assertEqual(subject, decision["subject"])
            self.assertEqual("decided", decision["status"])
            self.assertEqual(
                {
                    "identifier": "ALL-RIGHTS-RESERVED",
                    "version": None,
                    "url": "https://archmays.github.io/Museum-Codex/#/about",
                },
                decision["license"],
            )
            self.assertEqual("Mays", decision["approver"])
            self.assertEqual("2026-07-14", decision["effective_at"])
            self.assertEqual("project", decision["scope_constraint"]["release_kind"])
        self.assertTrue((ROOT / "RIGHTS.md").is_file())
        self.assertFalse((ROOT / "LICENSE").exists())
        self.assertFalse((ROOT / "LICENSE.md").exists())

    def test_rights_issue_form_does_not_request_sensitive_proof(self) -> None:
        text = (ROOT / ".github" / "ISSUE_TEMPLATE" / "rights-or-attribution.yml").read_text(encoding="utf-8")
        self.assertIn("id: contact_preference", text)
        self.assertIn("Do not attach identity documents, contracts, authorization originals", text)
        self.assertIn("non-public channel", text)
        for forbidden in ("type: file", "id: email", "id: phone", "id: address", "id: upload"):
            self.assertNotIn(forbidden, text)

    def test_arms_branch_is_registered_but_concrete_dispatch_fails_closed(self) -> None:
        record = {
            "schema_version": "1.1.0",
            "id": "arms_artifact:fixture-unimplemented",
            "entity_type": "arms_artifact",
            "branch_id": "arms",
            "labels": {"en": "Unimplemented arms branch probe"},
            "lifecycle_status": "candidate",
            "data_version": "0.1.0",
        }
        self.assertEqual(
            [],
            schema_issues("schemas/common/entity.schema.json", record, self.environment, "$.data"),
        )
        self.assertIsNone(expected_target_schema(record))
        issues = target_schema_binding_issues("schemas/common/entity.schema.json", record, "$.data")
        self.assertEqual(["arms_branch_schema_not_implemented"], [issue.code for issue in issues])
        self.assertIn("fallback to the common entity schema is forbidden", issues[0].message)

    def test_existing_art_and_biology_dispatch_is_unchanged(self) -> None:
        self.assertEqual(
            "schemas/art/artist-relationship.schema.json",
            expected_target_schema({"entity_type": "relationship", "branch_id": "art", "id": "art-rel:probe"}),
        )
        self.assertEqual(
            "schemas/biology/ecosystem-interaction.schema.json",
            expected_target_schema({"entity_type": "relationship", "branch_id": "biology", "id": "bio-rel:probe"}),
        )

    def test_museum_03b_context_and_batch_dispatch_is_concrete(self) -> None:
        for entity_type in (
            "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
            "exhibition_event", "material", "technique", "subject", "time_period", "person",
        ):
            self.assertEqual(
                "schemas/art/context/art-context.schema.json",
                expected_target_schema({"entity_type": entity_type, "branch_id": "art", "id": f"{entity_type}:probe"}),
            )
        self.assertEqual(
            "schemas/art/batch/formal-art-batch-manifest.schema.json",
            expected_target_schema({"entity_type": "formal_art_batch_manifest", "id": "art-batch-manifest:probe"}),
        )

    def test_all_valid_fixtures_pass(self) -> None:
        paths = fixture_paths(ROOT / "fixtures" / "governance" / "valid")
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertEqual([], validate_fixture(path, self.environment))

    def test_all_invalid_fixtures_fail_for_expected_reasons(self) -> None:
        paths = fixture_paths(ROOT / "fixtures" / "governance" / "invalid")
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            fixture = json.loads(path.read_text(encoding="utf-8"))
            issues = validate_fixture(path, self.environment)
            codes = {issue.code for issue in issues}
            with self.subTest(path=path.name):
                self.assertTrue(issues, "Expected invalid fixture to be rejected")
                self.assertTrue(set(fixture.get("expected_error_codes", [])).issubset(codes))

    def test_publishable_media_rights_accepts_valid_fixture_directory(self) -> None:
        failures, _, media_count = scan([ROOT / "fixtures" / "governance" / "valid"])
        self.assertEqual([], failures)
        self.assertGreaterEqual(media_count, 1)

    def test_publishable_media_rights_blocks_unknown_and_development_only(self) -> None:
        paths = [
            ROOT / "fixtures" / "governance" / "invalid" / "media-unknown-rights-publish.json",
            ROOT / "fixtures" / "governance" / "invalid" / "media-development-only-publish.json",
        ]
        failures, _, media_count = scan(paths)
        codes = {failure[2].code for failure in failures}
        self.assertEqual(2, media_count)
        self.assertIn("unknown_rights_publish", codes)
        self.assertIn("development_only_publish", codes)

    def test_publishable_media_cli_fails_closed_for_missing_path(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_publishable_media_rights.py", "fixtures/does-not-exist"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("path_missing", result.stdout)

    def test_physical_release_bundle_verifies_files_hashes_and_ids(self) -> None:
        release_root = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        self.assertEqual([], validate_release_directory(release_root, self.environment))

    def test_physical_release_bundle_detects_tampered_file(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            with (target / "records.json").open("ab") as handle:
                handle.write(b"\n")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("manifest_hash_mismatch", codes)
        self.assertIn("manifest_size_mismatch", codes)

    @staticmethod
    def _refresh_physical_manifest_file(root: Path, relative: str) -> None:
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = (root / relative).read_bytes()
        item = next(item for item in manifest["manifest_files"] if item["path"] == relative)
        item["bytes"] = len(payload)
        item["sha256"] = hashlib.sha256(payload).hexdigest()
        if relative == manifest.get("source_registry_manifest", {}).get("path"):
            manifest["source_registry_manifest"]["sha256"] = item["sha256"]
        if relative == manifest.get("license_decisions", {}).get("registry_path"):
            manifest["license_decisions"]["registry_sha256"] = item["sha256"]
        if relative == manifest.get("third_party_notices_manifest", {}).get("path"):
            manifest["third_party_notices_manifest"]["sha256"] = item["sha256"]
        if relative == manifest.get("attribution_manifest", {}).get("path"):
            manifest["attribution_manifest"]["sha256"] = item["sha256"]
        manifest["content_hash"] = release_content_hash(manifest["manifest_files"])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_physical_release_rejects_unmanifested_file(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            (target / "unmanifested-public-file.txt").write_text("not declared", encoding="utf-8")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("release_file_set_mismatch", codes)

    def test_physical_release_requires_self_hosted_media_bytes(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            media_item = next(item for item in manifest["manifest_files"] if item["record_type"] == "media")
            (target / media_item["path"]).unlink()
            manifest["manifest_files"] = [item for item in manifest["manifest_files"] if item is not media_item]
            manifest["content_hash"] = release_content_hash(manifest["manifest_files"])
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("media_manifest_ids_mismatch", codes)
        self.assertIn("self_hosted_media_file_unbound", codes)

    def test_physical_release_rejects_synchronized_empty_media(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            media_item = next(item for item in manifest["manifest_files"] if item["record_type"] == "media")
            (target / media_item["path"]).write_bytes(b"")
            empty_hash = hashlib.sha256(b"").hexdigest()
            media_item.update({"bytes": 0, "sha256": empty_hash})
            records_path = target / "records.json"
            records = json.loads(records_path.read_text(encoding="utf-8"))
            media = next(record["data"] for record in records["records"] if record["data"].get("entity_type") == "media_asset")
            media["content_hash"] = f"sha256:{empty_hash}"
            records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            records_payload = records_path.read_bytes()
            records_item = next(item for item in manifest["manifest_files"] if item["path"] == "records.json")
            records_item.update({"bytes": len(records_payload), "sha256": hashlib.sha256(records_payload).hexdigest()})
            manifest["content_hash"] = release_content_hash(manifest["manifest_files"])
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("self_hosted_media_empty", codes)

    def test_physical_release_parses_attribution_contents(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            (target / "attributions.json").write_text('{"assets": []}\n', encoding="utf-8")
            self._refresh_physical_manifest_file(target, "attributions.json")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("attribution_file_incomplete", codes)
        self.assertIn("artifact_file_record_ids_mismatch", codes)

    def test_physical_release_missing_record_id_reports_without_crashing(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            records_path = target / "records.json"
            document = json.loads(records_path.read_text(encoding="utf-8"))
            document["records"][0]["data"].pop("id")
            records_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._refresh_physical_manifest_file(target, "records.json")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("release_record_id_invalid", codes)
        self.assertIn("record_id_missing", codes)

    def test_release_bundle_rejects_non_publishable_record(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        artist = next(record["data"] for record in records if record["data"].get("entity_type") == "artist")
        artist["lifecycle_status"] = "candidate"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("release_record_not_publishable", codes)

    def test_release_bundle_requires_bidirectional_evidence_links(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        evidence = next(record["data"] for record in records if record["data"].get("id") == "evidence:fixture-artist-death")
        evidence["claim_ids"] = ["claim:fixture-artist-birth"]
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("evidence_claim_backlink_missing", codes)
        self.assertIn("claim_evidence_forward_link_missing", codes)

    def test_schema_dispatch_blocks_artist_downgrade(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        artist_wrapper = next(record for record in records if record["data"].get("entity_type") == "artist")
        artist_wrapper["target_schema"] = "schemas/common/entity.schema.json"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("schema_target_mismatch", codes)

    def test_artist_life_claim_must_match_semantics_and_display(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        birth = next(record["data"] for record in records if record["data"].get("id") == "claim:fixture-artist-birth")
        birth["predicate"] = "born_on"
        birth["object"]["value"] = "1841"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("artist_life_claim_semantics_mismatch", codes)

    def test_artist_birth_death_chronology_and_future_death(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        artist = next(record["data"] for record in records if record["data"].get("entity_type") == "artist")
        birth = next(record["data"] for record in records if record["data"].get("id") == "claim:fixture-artist-birth")
        death = next(record["data"] for record in records if record["data"].get("id") == "claim:fixture-artist-death")
        birth["object"]["value"] = "2100"
        artist["life_dates"]["birth"]["display_value"] = "2100"
        death["object"]["value"] = "2099"
        artist["life_dates"]["death"]["display_value"] = "2099"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("artist_life_dates_not_chronological", codes)
        self.assertIn("artist_death_in_future", codes)

    def test_publishable_claim_requires_supporting_evidence(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        evidence = next(record["data"] for record in records if record["data"].get("id") == "evidence:fixture-artist-work")
        evidence["stance"] = "contextualizes"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("publishable_claim_requires_support", codes)
        self.assertIn("artist_work_claim_requires_tier_1_or_2", codes)

    def test_factual_evidence_cannot_bind_restricted_rule(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        source = next(record["data"] for record in records if record["data"].get("entity_type") == "source")
        rule = source["license_rules"][0]
        rule["rights_status"] = "restricted"
        rule["redistribution"] = "prohibited"
        source["license_rules_snapshot_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(source["license_rules"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("factual_source_rule_not_publishable", codes)

    def test_aic_description_scope_must_bind_dedicated_rule(self) -> None:
        registry = json.loads((ROOT / "research" / "source-registry" / "source-license-rules.json").read_text(encoding="utf-8"))
        rules = next(item["rules"] for item in registry["sources"] if item["source_id"] == "aic_api")
        default_rule = next(rule for rule in rules if rule["content_class"] == "data" and "excluding /description" in rule["applies_to"])
        description_rule = next(rule for rule in rules if rule["content_class"] == "data" and rule["applies_to"] == "/api/v1/artworks/description")
        initial_scope = "/api/v1/artworks/123?fields=description"
        records = [
            {"data": {"id": "source:aic_api", "entity_type": "source", "registry_source_id": "aic_api", "tier": 1, "license_rules": rules, "selected_license_rule_ids": [default_rule["rule_id"]]}},
            {"data": {"id": "evidence:aic-description", "entity_type": "evidence", "claim_ids": ["claim:aic-description"], "stance": "supports", "evidence_kind": "dataset_record", "source_ids": ["source:aic_api"], "source_license_bindings": [{"source_id": "source:aic_api", "rule_id": default_rule["rule_id"], "content_class": "data", "scope_locator": initial_scope, "scope_fields": ["description"], "permission_resolution": "rule_direct"}], "locator": {"fragment": initial_scope}}},
            {"data": {"id": "claim:aic-description", "entity_type": "claim", "subject_id": "artwork:test", "predicate": "description", "object": {"value": "text", "datatype": "string"}, "evidence_ids": ["evidence:aic-description"], "counter_evidence_ids": [], "status": "publishable"}},
            {"data": {"id": "artwork:test", "entity_type": "artwork", "claim_ids": [], "source_ids": []}},
        ]
        self.assertIn("source_license_scope_mismatch", {issue.code for issue in reference_graph_issues(records)})
        evidence = records[1]["data"]
        for scope in (
            "/api/v1/articles/content?fields=description",
            "/api/v1/artworks/123?fields=%64escription",
            "/api/v1/artworks/123?fields=%2564escription",
            "/api/v1/artworks/123",
            "/api/v1/artworks/search?fields=description",
            "/api/v1/artworks/search?q=monet&fields=id,description",
            "https://evil.example/api/v1/artworks/123?fields=description",
            "https://api.artic.edu.evil.example/api/v1/artworks/123?fields=description",
            "//evil.example/api/v1/artworks/123?fields=description",
            "file:///api/v1/artworks/123?fields=description",
            "javascript:/api/v1/artworks/123?fields=description",
        ):
            evidence["source_license_bindings"][0]["scope_locator"] = scope
            evidence["source_license_bindings"][0]["scope_fields"] = ["description"] if "id,description" not in scope else ["id", "description"]
            evidence["locator"]["fragment"] = scope
            with self.subTest(scope=scope):
                self.assertIn("source_license_scope_mismatch", {issue.code for issue in reference_graph_issues(records)})
        records[0]["data"]["selected_license_rule_ids"] = [description_rule["rule_id"]]
        evidence["source_license_bindings"][0]["rule_id"] = description_rule["rule_id"]
        for scope in (
            "https://evil.example/api/v1/artworks/123?fields=description",
            "https://api.artic.edu.evil.example/api/v1/artworks/123?fields=description",
            "//api.artic.edu/api/v1/artworks/123?fields=description",
            "file:///api/v1/artworks/123?fields=description",
        ):
            evidence["source_license_bindings"][0]["scope_locator"] = scope
            evidence["source_license_bindings"][0]["scope_fields"] = ["description"]
            evidence["locator"]["fragment"] = scope
            with self.subTest(dedicated_rule_foreign_scope=scope):
                self.assertIn("source_license_scope_mismatch", {issue.code for issue in reference_graph_issues(records)})
        evidence["source_license_bindings"][0]["scope_locator"] = "https://api.artic.edu/api/v1/artworks/123?fields=id,description"
        evidence["source_license_bindings"][0]["scope_fields"] = ["id", "description"]
        evidence["locator"]["fragment"] = "https://api.artic.edu/api/v1/artworks/123?fields=id,description"
        self.assertNotIn("source_license_scope_mismatch", {issue.code for issue in reference_graph_issues(records)})
        records[0]["data"]["selected_license_rule_ids"] = [default_rule["rule_id"]]
        evidence["source_license_bindings"][0].update({"rule_id": default_rule["rule_id"], "scope_locator": "/api/v1/artworks/search?fields=id,title", "scope_fields": ["id", "title"]})
        evidence["locator"]["fragment"] = "/api/v1/artworks/search?fields=id,title"
        self.assertNotIn("source_license_scope_mismatch", {issue.code for issue in reference_graph_issues(records)})

    def test_tier_4_source_cannot_support_public_artist_inclusion(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "governance" / "valid" / "artist-claim-evidence-release-closure.json").read_text(encoding="utf-8")
        )
        records = deepcopy(fixture["records"])
        source = next(record["data"] for record in records if record["data"].get("entity_type") == "source")
        source["tier"] = 4
        source["source_type"] = "unverified_web"
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("tier_4_source_not_publishable", codes)
        self.assertIn("artist_work_claim_requires_tier_1_or_2", codes)

    def test_counter_evidence_forces_disputed_workflow(self) -> None:
        claim = {
            "entity_type": "claim", "counter_evidence_ids": ["evidence:counter"],
            "disputed": False, "status": "publishable",
        }
        codes = {issue.code for issue in policy_issues(claim, "publish", "$.claim")}
        self.assertIn("counter_evidence_requires_disputed_status", codes)

    def test_artwork_attribution_and_domain_references_are_semantic(self) -> None:
        records = [
            {"data": {"id": "artwork:test", "entity_type": "artwork", "claim_ids": ["claim:creator"], "source_ids": [], "creator_attributions": [{"attribution_type": "confirmed", "creator_entity_id": "artist:creator", "claim_id": "claim:creator"}], "holding_institution_id": "museum_institution:missing", "material_ids": ["material:missing"], "technique_ids": ["technique:missing"], "media_asset_ids": ["media:missing"]}},
            {"data": {"id": "artist:creator", "entity_type": "artist", "claim_ids": [], "source_ids": []}},
            {"data": {"id": "claim:creator", "entity_type": "claim", "subject_id": "artist:creator", "predicate": "creator_attribution", "object": {"entity_id": "artist:other"}, "evidence_ids": [], "counter_evidence_ids": [], "status": "candidate"}},
        ]
        codes = {issue.code for issue in reference_graph_issues(records)}
        self.assertIn("artwork_attribution_claim_invalid", codes)
        self.assertIn("artwork_holding_institution_missing", codes)
        self.assertIn("artwork_material_missing", codes)
        self.assertIn("artwork_technique_missing", codes)
        self.assertIn("artwork_media_missing", codes)

    def test_publishable_artwork_requires_publishable_review(self) -> None:
        artwork = {"entity_type": "artwork", "lifecycle_status": "publishable", "review_status": "candidate"}
        self.assertFalse(record_is_publishable(artwork))

    def test_relationship_and_biology_reference_types_are_closed(self) -> None:
        records = [
            {"data": {"id": "artist:source", "entity_type": "artist", "claim_ids": [], "source_ids": []}},
            {"data": {"id": "art_group:target", "entity_type": "person", "claim_ids": [], "source_ids": []}},
            {"data": {"id": "art-rel:membership", "entity_type": "relationship", "branch_id": "art", "relationship_type": "member_of", "source_entity_id": "artist:source", "target_entity_id": "art_group:target", "context_entity_ids": [], "place_scope": {"place_ids": []}, "claim_ids": [], "source_ids": [], "source_license_bindings": []}},
            {"data": {"id": "bio-rel:animation", "entity_type": "relationship", "branch_id": "biology", "relationship_type": "pollination", "source_entity_id": "taxon:a", "target_entity_id": "taxon:b", "context_entity_ids": [], "place_scope": {"place_ids": []}, "claim_ids": [], "source_ids": [], "source_license_bindings": [], "behavior_animation": {"animation_evidence_ids": ["evidence:missing"]}}},
        ]
        codes = {issue.code for issue in reference_graph_issues(records)}
        self.assertIn("record_id_entity_type_mismatch", codes)
        self.assertIn("artist_relationship_target_invalid_type", codes)
        self.assertIn("biology_animation_evidence_missing", codes)

    def test_artist_self_relationship_is_blocked(self) -> None:
        relationship = {
            "entity_type": "relationship", "branch_id": "art", "source_entity_id": "artist:same",
            "target_entity_id": "artist:same", "relationship_type": "student_of",
        }
        self.assertIn("artist_self_relationship", {issue.code for issue in policy_issues(relationship, "publish", "$.relationship")})

    def test_computational_claim_requires_computational_evidence(self) -> None:
        records = [
            {"data": {"id": "claim:similar", "entity_type": "claim", "subject_id": "artist:a", "predicate": "computationally_similar_to", "object": {"entity_id": "artist:b"}, "evidence_ids": ["evidence:manual"], "counter_evidence_ids": [], "status": "publishable"}},
            {"data": {"id": "evidence:manual", "entity_type": "evidence", "claim_ids": ["claim:similar"], "stance": "supports", "evidence_kind": "scholarly_analysis", "source_ids": ["source:study"], "source_license_bindings": []}},
            {"data": {"id": "source:study", "entity_type": "source", "tier": 2, "license_rules": [], "selected_license_rule_ids": []}},
            {"data": {"id": "artist:a", "entity_type": "artist", "claim_ids": [], "source_ids": []}},
            {"data": {"id": "artist:b", "entity_type": "artist", "claim_ids": [], "source_ids": []}},
        ]
        self.assertIn("computational_claim_requires_computation", {issue.code for issue in reference_graph_issues(records)})

    def test_source_revocation_and_finite_permission_block_indefinite_release(self) -> None:
        records = json.loads((ROOT / "fixtures" / "release-bundles" / "valid" / "minimal" / "records.json").read_text(encoding="utf-8"))["records"]
        source = deepcopy(next(record["data"] for record in records if record["data"].get("entity_type") == "source"))
        source["permission_status"] = "approved"
        source["permission_reference"] = "fixture-permission-2026"
        source["permission_scope"] = {"platforms": ["github_pages"], "purposes": ["public_education"], "territories": ["worldwide"], "starts_at": "2026-07-01"}
        source["permission_expires_at"] = "2026-07-12"
        source["permission_revoked_at"] = "2026-07-10"
        codes = {issue.code for issue in source_publish_issues(source, "$.source", None)}
        self.assertIn("source_permission_revoked", codes)
        self.assertIn("release_outlives_source_permission", codes)

    def test_canonical_iucn_rules_cannot_be_self_declared_open(self) -> None:
        records = json.loads((ROOT / "fixtures" / "release-bundles" / "valid" / "minimal" / "records.json").read_text(encoding="utf-8"))["records"]
        source = deepcopy(next(record["data"] for record in records if record["data"].get("entity_type") == "source"))
        source["id"] = "source:iucn_red_list"
        source["registry_source_id"] = "iucn_red_list"
        source["official_url"] = "https://www.iucnredlist.org/"
        codes = {issue.code for issue in source_publish_issues(source, "$.source")}
        self.assertIn("canonical_source_rules_mismatch", codes)
        self.assertIn("iucn_public_redistribution_blocked", codes)

    def test_canonical_source_identity_rejects_spoofed_origin(self) -> None:
        source = deepcopy(
            json.loads(
                (ROOT / "fixtures" / "governance" / "valid" / "dataset-release.json").read_text(encoding="utf-8")
            )["records"][0]["data"]
        )
        registry = json.loads(
            (ROOT / "research" / "source-registry" / "source-license-rules.json").read_text(encoding="utf-8")
        )
        rules = next(item["rules"] for item in registry["sources"] if item["source_id"] == "aic_api")
        registry_config = json.loads(
            (ROOT / "research" / "source-registry" / "minimum-source-set.json").read_text(encoding="utf-8")
        )
        source.update(
            {
                "id": "source:aic_api",
                "registry_source_id": "aic_api",
                "publisher": "Evil Mirror",
                "official_url": "https://evil.example/not-aic",
                "license_rules": rules,
                "selected_license_rule_ids": [rules[0]["rule_id"]],
                "license_rules_snapshot_hash": "sha256:"
                + hashlib.sha256(
                    json.dumps(rules, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "registry_identity": {
                    **canonical_source_identities()["aic_api"],
                    "snapshot_hash": registry_config["source_matrix_snapshot_hash"],
                },
            }
        )
        codes = {issue.code for issue in source_publish_issues(source, "$.source")}
        self.assertIn("source_registry_identity_mismatch", codes)

    def test_fake_sharealike_identifier_and_missing_parent_are_blocked(self) -> None:
        media = json.loads((ROOT / "fixtures" / "governance" / "valid" / "media-cc-by.json").read_text(encoding="utf-8"))["data"]
        media = deepcopy(media)
        media["rights_status"] = "cc_by_sa"
        media["media_license"]["identifier"] = "CC-BY-SA-FAKE"
        media["reuse_mode"] = "adaptation"
        media["derivation"] = {
            "derived_from_media_id": "media:missing-parent", "source_content_hash": media["content_hash"],
            "transform_recipe": "fixture transform", "transform_version": "1",
            "output_content_hash": media["content_hash"], "output_license_identifier": "CC-BY-SA-FAKE",
            "share_alike_compatibility_decision": "compatible",
        }
        codes = {issue.code for issue in media_publish_issues(media, "$.media")}
        self.assertIn("media_license_not_canonical", codes)
        records = [{"data": media}]
        self.assertIn("media_derivation_parent_missing", {issue.code for issue in reference_graph_issues(records)})

    def test_media_license_must_match_bound_source_media_rule(self) -> None:
        records = deepcopy(json.loads((ROOT / "fixtures" / "release-bundles" / "valid" / "minimal" / "records.json").read_text(encoding="utf-8"))["records"])
        media = next(record["data"] for record in records if record["data"].get("entity_type") == "media_asset")
        media["rights_status"] = "cc0"
        media["media_license"].update({"identifier": "CC0-1.0", "version": "1.0", "url": "https://creativecommons.org/publicdomain/zero/1.0/", "attribution_required": False})
        self.assertIn("media_source_rule_license_mismatch", {issue.code for issue in reference_graph_issues(records)})

    def test_media_permissions_cannot_exceed_bound_source_rule(self) -> None:
        records = deepcopy(json.loads((ROOT / "fixtures" / "release-bundles" / "valid" / "minimal" / "records.json").read_text(encoding="utf-8"))["records"])
        source = next(record["data"] for record in records if record["data"].get("entity_type") == "source")
        media = next(record["data"] for record in records if record["data"].get("entity_type") == "media_asset")
        rule_id = media["source_license_bindings"][0]["rule_id"]
        rule = next(item for item in source["license_rules"] if item["rule_id"] == rule_id)
        rule["modification"] = "prohibited"
        rule["commercial_use"] = "prohibited"
        codes = {issue.code for issue in reference_graph_issues(records)}
        self.assertIn("media_source_rule_permission_mismatch", codes)
        rule["rights_status"] = "mixed"
        rule["identifier"] = "OBJECT-SPECIFIC"
        rule["redistribution"] = "conditional"
        media["source_license_bindings"][0]["permission_resolution"] = "object_level"
        codes = {issue.code for issue in reference_graph_issues(records)}
        self.assertIn("media_source_rule_permission_mismatch", codes)

    def test_sharealike_adaptation_cannot_downgrade_parent_version(self) -> None:
        template = deepcopy(json.loads((ROOT / "fixtures" / "governance" / "valid" / "media-cc-by.json").read_text(encoding="utf-8"))["data"])
        parent = deepcopy(template)
        parent["id"] = "media:sa-parent"
        parent["rights_status"] = "cc_by_sa"
        parent["media_license"].update({"identifier": "CC-BY-SA-4.0", "version": "4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0/", "share_alike": True})
        child = deepcopy(parent)
        child["id"] = "media:sa-child"
        child["media_license"].update({"identifier": "CC-BY-SA-1.0", "version": "1.0", "url": "https://creativecommons.org/licenses/by-sa/1.0/"})
        child["reuse_mode"] = "adaptation"
        child["derivation"] = {"derived_from_media_id": "media:sa-parent", "source_content_hash": parent["content_hash"], "transform_recipe": "crop", "transform_version": "1", "output_content_hash": child["content_hash"], "output_license_identifier": "CC-BY-SA-1.0", "share_alike_compatibility_decision": "compatible"}
        records = [{"data": parent}, {"data": child}]
        self.assertIn("share_alike_version_mismatch", {issue.code for issue in reference_graph_issues(records)})

    def test_future_and_stale_media_rights_reviews_are_blocked(self) -> None:
        media = deepcopy(json.loads((ROOT / "fixtures" / "governance" / "valid" / "media-cc-by.json").read_text(encoding="utf-8"))["data"])
        media["reviewed_at"] = "2099-01-01"
        media["rights_evidence"]["verified_at"] = "2000-01-01"
        codes = {issue.code for issue in media_publish_issues(media, "$.media")}
        self.assertIn("governance_date_in_future", codes)
        self.assertIn("governance_review_stale", codes)

    def test_public_release_rejects_unregistered_license_decision(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "governance" / "valid" / "dataset-release.json").read_text(encoding="utf-8"))
        records = deepcopy(fixture["records"])
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        release["license_decisions"]["code_license_decision_id"] = "license-decision:invented"
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("license_decision_unresolved", codes)

    def test_synthetic_license_decision_cannot_cover_production_release_id(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "governance" / "valid" / "dataset-release.json").read_text(encoding="utf-8"))
        records = deepcopy(fixture["records"])
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        release["id"] = "release:production-0.1.0"
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("license_decision_scope_mismatch", codes)

    def test_release_schema_versions_must_match_consumed_schemas(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "governance" / "valid" / "dataset-release.json").read_text(encoding="utf-8"))
        records = deepcopy(fixture["records"])
        release = next(record["data"] for record in records if record["data"].get("entity_type") == "dataset_release")
        release["schema_versions"]["common/source"] = "9.9.9"
        codes = {issue.code for issue in release_bundle_issues(records, release)}
        self.assertIn("release_schema_versions_mismatch", codes)

    def test_physical_notice_rights_holder_must_match_media(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            notice_path = target / "third-party-notices.json"
            document = json.loads(notice_path.read_text(encoding="utf-8"))
            media_notice = next(item for item in document["notices"] if item["record_id"].startswith("media:"))
            media_notice["rights_holder"] = "Wrong Holder"
            notice_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._refresh_physical_manifest_file(target, "third-party-notices.json")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("third_party_notice_media_mismatch", codes)

    def test_physical_source_notice_covers_every_used_rule_exactly(self) -> None:
        source = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release"
            shutil.copytree(source, target)
            records_path = target / "records.json"
            document = json.loads(records_path.read_text(encoding="utf-8"))
            source_record = next(
                record["data"] for record in document["records"] if record["data"].get("entity_type") == "source"
            )
            data_rule = next(rule for rule in source_record["license_rules"] if rule["content_class"] == "data")
            document["records"].append(
                {
                    "target_schema": "schemas/common/entity.schema.json",
                    "data": {
                        "schema_version": "1.1.0",
                        "id": "concept:notice-probe",
                        "entity_type": "concept",
                        "branch_id": "global",
                        "labels": {"en": "Notice probe"},
                        "claim_ids": [],
                        "source_ids": [source_record["id"]],
                        "source_license_bindings": [
                            {
                                "source_id": source_record["id"],
                                "rule_id": data_rule["rule_id"],
                                "content_class": "data",
                                "scope_locator": "physical fixture records",
                                "scope_fields": ["labels"],
                                "permission_resolution": "rule_direct",
                            }
                        ],
                        "lifecycle_status": "publishable",
                        "data_version": "0.1.0",
                    },
                }
            )
            records_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_versions"]["common/entity"] = "1.1.0"
            manifest["included_entity_ids"] = ["concept:notice-probe"]
            records_item = next(item for item in manifest["manifest_files"] if item["path"] == "records.json")
            records_item["record_ids"].append("concept:notice-probe")
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._refresh_physical_manifest_file(target, "records.json")
            codes = {issue.code for issue in validate_release_directory(target, self.environment)}
        self.assertIn("third_party_notice_source_mismatch", codes)

    def test_release_paths_reject_windows_and_parent_escape(self) -> None:
        root = ROOT / "fixtures" / "release-bundles" / "valid" / "minimal"
        self.assertIsNotNone(canonical_release_path(root, "C:\\outside.json")[1])
        self.assertIsNotNone(canonical_release_path(root, "../outside.json")[1])
        self.assertIsNone(canonical_release_path(root, "records.json")[1])

    def test_source_registry_is_complete(self) -> None:
        issues, rows = validate_registry()
        self.assertEqual([], issues)
        self.assertEqual(REQUIRED_SOURCE_IDS, {row["source_id"] for row in rows})


if __name__ == "__main__":
    unittest.main()
