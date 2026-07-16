from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from museum_pipeline.adapters import get_adapter
from museum_pipeline.adapters.base import ResponseContract
from museum_pipeline.art.cli import _explain_record
from museum_pipeline.art.leakage import build_public_leakage_label_set
from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.cli import build_parser, main
from museum_pipeline.config import INTERMEDIATE_ROOT, RAW_ROOT, ROOT, endpoint_registry
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import sha256_file
from museum_pipeline.snapshots import write_snapshot
from museum_pipeline.source_registry import REFERENCE_SOURCE_IDS, verify_sources
from museum_pipeline.validation.dispatch import canonical_schema_path, load_schema_environment, validate_record
from museum_pipeline.validation.fixtures import evaluate_invalid_fixture
from museum_pipeline.validation.physical import validate_run_directory
from scripts.scan_public_artifact_for_candidate_data import (
    MAX_SCANNABLE_TEXT_BYTES,
    formal_art_terms_from_label_set,
    scan_public_artifact,
    validated_formal_art_exempt_roots,
)
from scripts.validate_pipeline_foundation import validate_pipeline_foundation


VALID = ROOT / "fixtures" / "pipeline" / "valid"
INVALID = ROOT / "fixtures" / "pipeline" / "invalid"


def run_cli(argv: list[str]) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = main(argv)
    lines = [line for line in output.getvalue().splitlines() if line.strip().startswith("{")]
    return code, json.loads(lines[-1])


class CliTests(unittest.TestCase):
    def test_help_lists_every_required_command(self) -> None:
        help_text = build_parser().format_help()
        for command in (
            "verify-sources", "list-adapters", "acquire", "validate-snapshot", "normalize",
            "propose-identities", "build-review-bundle", "validate-review-bundle",
            "apply-decisions", "explain-field", "validate-run",
        ):
            self.assertIn(command, help_text)

    def test_verify_sources_and_list_adapters_are_machine_readable(self) -> None:
        code, payload = run_cli(["verify-sources", "--json"])
        self.assertEqual(0, code)
        self.assertTrue(payload["ok"])
        code, payload = run_cli(["list-adapters", "--json"])
        self.assertEqual(0, code)
        self.assertEqual(4, len(payload["adapters"]))

    def test_acquire_defaults_off_even_when_environment_variable_requests_live(self) -> None:
        with patch.dict(os.environ, {"MUSEUM_PIPELINE_LIVE": "1"}):
            code, payload = run_cli(["acquire", "--source", "wikidata", "--object-id", "Q42", "--json"])
        self.assertEqual(4, code)
        self.assertEqual("network_disabled", payload["error"]["code"])

    def test_cli_errors_do_not_expose_absolute_workspace_path(self) -> None:
        code, payload = run_cli(["validate-snapshot", "does-not-exist", "--json"])
        self.assertNotEqual(0, code)
        self.assertNotIn(str(ROOT), json.dumps(payload))

    def test_normalize_cli_builds_candidate_only_run_and_validates_physical_closure(self) -> None:
        RAW_ROOT.mkdir(parents=True, exist_ok=True)
        INTERMEDIATE_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RAW_ROOT) as raw_temp, tempfile.TemporaryDirectory(dir=INTERMEDIATE_ROOT) as run_temp:
            adapter = get_adapter("aic_api")
            request = adapter.build_request("27992")
            body = (VALID / "adapter-aic-response.json").read_bytes()
            snapshot = write_snapshot(
                adapter=adapter, request=request,
                response=ResponseContract(200, {"content-type": "application/json"}, body, request.url),
                source_object_ids=["27992"],
                run_id="pipeline-run:77777777-7777-5777-8777-777777777777",
                fetched_at=datetime(2026, 7, 12, 2, 0, 0, tzinfo=timezone.utc),
                raw_root=Path(raw_temp),
            )
            output = Path(run_temp) / "run"
            code, payload = run_cli(["normalize", str(snapshot), "--output-dir", str(output), "--json"])
            self.assertEqual(0, code, payload)
            self.assertFalse(payload["publishable"])
            candidate = json.loads((output / "candidate.json").read_text(encoding="utf-8"))
            self.assertEqual("candidate", candidate["review_state"])
            self.assertEqual([], validate_run_directory(output))
            code, bundle_payload = run_cli(["build-review-bundle", str(output), "--json"])
            self.assertEqual(0, code, bundle_payload)
            bundle = json.loads((output / "review-bundle.json").read_text(encoding="utf-8"))
            title_provenance = next(item for item in candidate["field_provenance"] if item["field_pointer"] == "/fields/title")
            decisions_path = output / "review-decisions.json"
            write_canonical_json(decisions_path, [{
                "schema_version": "1.0.0", "decision_schema_version": "1.0.0",
                "id": "review-decision:77777777-7777-5777-8777-777777777777",
                "entity_type": "review_decision", "target_id": title_provenance["id"],
                "decision_type": "approve_field_mapping", "reviewer": "fixture-normalizer",
                "reviewer_role": "normalizer", "decided_at": "2026-07-12T02:01:00Z",
                "rationale": "Exercise the local field-mapping decision contract.",
                "input_hashes": bundle["exact_input_hashes"], "supersedes": None, "status": "active",
                "status_history": [{
                    "from": None, "to": "active", "changed_at": "2026-07-12T02:01:00Z",
                    "changed_by": "fixture-normalizer", "role": "normalizer", "reason": "Fixture review.",
                }],
            }])
            code, decision_payload = run_cli([
                "apply-decisions", str(output / "review-bundle.json"), str(decisions_path), "--json",
            ])
            self.assertEqual(0, code, decision_payload)
            self.assertEqual(1, decision_payload["applied"])
            self.assertFalse(decision_payload["publishable_records_created"])
            self.assertEqual([], validate_run_directory(output))

    def test_explain_field_returns_exact_raw_locator_and_rule(self) -> None:
        candidate = get_adapter("aic_api").normalize(
            json.loads((VALID / "adapter-aic-response.json").read_text(encoding="utf-8")),
            snapshot_id="snapshot:aic_api:fixture", observed_at="2026-07-12T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            code, payload = run_cli(["explain-field", candidate["id"], "/fields/title", "--root", temporary, "--json"])
        self.assertEqual(0, code)
        self.assertEqual("/data/title", payload["provenance"][0]["raw_locator"])
        self.assertEqual("aic_api:data:75df7e022b4e", payload["provenance"][0]["license_rule_id"])

    def test_unknown_upstream_field_blocks_normalization_before_candidate_write(self) -> None:
        RAW_ROOT.mkdir(parents=True, exist_ok=True)
        INTERMEDIATE_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RAW_ROOT) as raw_temp, tempfile.TemporaryDirectory(dir=INTERMEDIATE_ROOT) as run_temp:
            adapter = get_adapter("met_open_access")
            request = adapter.build_request("1")
            document = json.loads((VALID / "adapter-met-response.json").read_text(encoding="utf-8"))
            document["new_upstream_field"] = "drift"
            body = json.dumps(document, ensure_ascii=False).encode("utf-8")
            snapshot = write_snapshot(
                adapter=adapter, request=request,
                response=ResponseContract(200, {"content-type": "application/json"}, body, request.url),
                source_object_ids=["1"], run_id="pipeline-run:77777777-7777-5777-8777-777777777777",
                fetched_at=datetime(2026, 7, 12, 3, 0, 0, tzinfo=timezone.utc), raw_root=Path(raw_temp),
            )
            output = Path(run_temp) / "blocked-run"
            code, payload = run_cli(["normalize", str(snapshot), "--output-dir", str(output), "--json"])
            self.assertEqual(3, code)
            self.assertFalse(payload["candidate_written"])
            self.assertFalse(output.exists())
            self.assertIn("adapter_contract_drift", {item["code"] for item in payload["issues"]})


class LeakageTests(unittest.TestCase):
    def test_current_public_inputs_have_no_candidate_or_unvalidated_media_leak(self) -> None:
        public_root = ROOT / "public"
        label_set = (
            ROOT
            / "data"
            / "reviewed"
            / "art"
            / "museum-03b"
            / "museum-03b-first-slate-v1"
            / "package-v1"
            / "public-leakage-label-set.json"
        )
        formal_terms, label_error = formal_art_terms_from_label_set(label_set)
        exempt_roots, release_findings = validated_formal_art_exempt_roots(public_root)
        self.assertIsNone(label_error)
        self.assertEqual([], release_findings)
        self.assertEqual(
            [],
            scan_public_artifact(
                public_root,
                formal_art_terms=formal_terms,
                formal_art_exempt_roots=exempt_roots,
            ),
        )

    def test_formal_release_allowlist_is_exact_and_fails_closed(self) -> None:
        exempt_roots, findings = validated_formal_art_exempt_roots(ROOT / "public")
        self.assertEqual([], findings)
        self.assertEqual(
            {
                (ROOT / "public" / "releases" / "art-constellation-1.0.0").resolve(),
                (ROOT / "public" / "releases" / "art-gallery-interactions-1.1.0").resolve(),
                (ROOT / "public" / "releases" / "art-pathways-1.2.0").resolve(),
            },
            exempt_roots,
        )
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary)
            invalid_release = public / "releases" / "art-gallery-interactions-1.1.0"
            invalid_release.mkdir(parents=True)
            invalid_release.joinpath("manifest.json").write_text("{}", encoding="utf-8")
            invalid_roots, invalid_findings = validated_formal_art_exempt_roots(public)
        self.assertEqual(set(), invalid_roots)
        self.assertEqual("museum_05b_release_invalid", invalid_findings[0]["code"])

    def test_unregistered_release_directory_keeps_generic_leakage_checks(self) -> None:
        formal_terms = [{"value": "Albrecht Dürer", "match_mode": "casefold_substring"}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "releases" / "not-allowlisted-1.0.0"
            release.mkdir(parents=True)
            release.joinpath("record.json").write_text('"Albrecht Dürer"', encoding="utf-8")
            release.joinpath("image.jpg").write_bytes(b"not-approved-media")
            findings = scan_public_artifact(root, formal_art_terms=formal_terms)
        self.assertEqual(
            {"formal_art_data_publicly_exposed", "third_party_media_in_public_artifact"},
            {item["code"] for item in findings},
        )

    def test_candidate_identifier_is_detected_in_public_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("candidate:22222222-2222-5222-8222-222222222222", encoding="utf-8")
            self.assertIn("candidate_data_publicly_exposed", {item["code"] for item in scan_public_artifact(root)})

    def test_formal_art_label_set_detects_approved_name_and_stable_id(self) -> None:
        formal_terms = [
            {"value": "Synthetic Approved Artist", "match_mode": "casefold_substring"},
            {"value": "artist:synthetic-approved", "match_mode": "exact_token"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text(
                "Synthetic Approved Artist artist:synthetic-approved",
                encoding="utf-8",
            )
            codes = {
                item["code"]
                for item in scan_public_artifact(root, formal_art_terms=formal_terms)
            }
        self.assertIn("formal_art_data_publicly_exposed", codes)

    def test_formal_art_label_set_does_not_match_partial_exact_token(self) -> None:
        formal_terms = [{"value": "Q123", "match_mode": "exact_token"}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("Q1234", encoding="utf-8")
            findings = scan_public_artifact(root, formal_art_terms=formal_terms)
        self.assertNotIn("formal_art_data_publicly_exposed", {item["code"] for item in findings})

    def test_context_label_requires_a_standalone_serialized_string(self) -> None:
        formal_terms = [{"value": "Canvas", "match_mode": "serialized_string"}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "safe.css").write_text("--surface: Canvas; --art-canvas: 1;", encoding="utf-8")
            (root / "safe.html").write_text("Begin with canvas and material.", encoding="utf-8")
            (root / "safe.js").write_text("document.createElement(`canvas`);", encoding="utf-8")
            self.assertEqual([], scan_public_artifact(root, formal_art_terms=formal_terms))
            (root / "leaked.js").write_text('const record = {label: "Canvas"};', encoding="utf-8")
            codes = {item["code"] for item in scan_public_artifact(root, formal_art_terms=formal_terms)}
        self.assertIn("formal_art_data_publicly_exposed", codes)

    def test_formal_art_label_set_includes_packaged_record_ids(self) -> None:
        label_set = build_public_leakage_label_set(
            identity_seed={"batch_id": "art-batch:museum-03b-fixture", "artists": []},
            identity_basis={"bindings": []},
            application={
                "id": "selection-decision-application:fixture",
                "submitted_decision_id": "selection-decision:fixture",
            },
            formal_records=[
                {
                    "id": "artwork:fixture-object",
                    "entity_type": "artwork",
                    "title_records": [{"text": "Synthetic Formal Artwork Title"}],
                    "external_ids": {"met_object": "123456"},
                    "official_object_record": {"source_object_id": "123456"},
                    "accession_number": "TEST.1",
                    "rights_preflight_id": "artwork-preflight:fixture-object",
                },
                {
                    "id": "artist:fixture-artist",
                    "entity_type": "artist",
                    "labels": {"en": "Synthetic Formal Artist"},
                    "aliases": [{"text": "Synthetic Formal Alias"}],
                },
                {
                    "id": "subject:fixture-context",
                    "entity_type": "subject",
                    "labels": {"en": "Synthetic Formal Context"},
                },
                {"id": "source:fixture-official", "entity_type": "source"},
            ],
        )
        observed = {(item["value"], item["category"]) for item in label_set["terms"]}
        self.assertIn(("artwork:fixture-object", "artwork_id"), observed)
        self.assertIn(("source:fixture-official", "source_id"), observed)
        self.assertIn(("selection-decision:fixture", "formal_record_id"), observed)
        self.assertIn(("123456", "external_id"), observed)
        self.assertIn(("TEST.1", "external_id"), observed)
        self.assertIn(("artwork-preflight:fixture-object", "rights_record_id"), observed)
        self.assertIn(("Synthetic Formal Artwork Title", "approved_label"), observed)
        self.assertIn(("Synthetic Formal Artist", "approved_label"), observed)
        self.assertIn(("Synthetic Formal Alias", "alias"), observed)
        self.assertIn(("Synthetic Formal Context", "context_label"), observed)
        context_term = next(item for item in label_set["terms"] if item["value"] == "Synthetic Formal Context")
        self.assertEqual("serialized_string", context_term["match_mode"])

    def test_source_map_is_scanned_for_formal_art_terms(self) -> None:
        formal_terms = [{"value": "artist:synthetic-approved", "match_mode": "exact_token"}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.js.map").write_text(
                '{"sourcesContent":["artist:synthetic-approved"]}',
                encoding="utf-8",
            )
            codes = {item["code"] for item in scan_public_artifact(root, formal_art_terms=formal_terms)}
        self.assertIn("formal_art_data_publicly_exposed", codes)

    def test_oversized_javascript_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.js").write_text("x" * (MAX_SCANNABLE_TEXT_BYTES + 1), encoding="utf-8")
            findings = scan_public_artifact(root)
        self.assertIn("public_text_too_large_to_scan", {item["code"] for item in findings})

    def test_explain_media_assessment_reports_actual_rights_fields(self) -> None:
        record_id = "media-eligibility-assessment:fixture"
        record = {
            "id": record_id,
            "entity_type": "media_eligibility_assessment",
            "outcome": "metadata_only",
            "metadata_license": "CC0-1.0",
            "media_license": "CC-BY-4.0",
            "media_rights_status": "permission_verified",
            "media_rights_basis": "license",
            "permissions": ["reproduce", "distribute"],
            "permission_status": "verified",
            "bytes_downloaded": False,
            "media_bytes_present": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "media-assessments.json").write_text(json.dumps([record]), encoding="utf-8")
            (root / "package-manifest.json").write_text(
                json.dumps({"files": [{"path": "media-assessments.json", "record_ids": [record_id]}]}),
                encoding="utf-8",
            )
            rights = _explain_record(root, record_id)["rights"]
        self.assertEqual("CC0-1.0", rights["metadata_license"])
        self.assertEqual("CC-BY-4.0", rights["media_license"])
        self.assertEqual("permission_verified", rights["media_rights_status"])
        self.assertEqual(["reproduce", "distribute"], rights["permissions"])
        self.assertEqual("verified", rights["permission_status"])
        self.assertNotIn("metadata_rights", rights)
        self.assertNotIn("media_rights", rights)

    def test_qid_and_ulan_identifiers_are_detected_in_public_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("https://www.wikidata.org/wiki/Q42 https://vocab.getty.edu/ulan/500115493", encoding="utf-8")
            codes = {item["code"] for item in scan_public_artifact(root)}
            self.assertTrue({"wikidata_qid", "ulan_id"} <= codes)

    def test_bare_probe_identifiers_and_names_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("Q42 500115493 A Sunday on La Grande Jatte", encoding="utf-8")
            codes = {item["code"] for item in scan_public_artifact(root)}
            self.assertIn("wikidata_qid", codes)
            self.assertIn("candidate_data_publicly_exposed", codes)

    def test_raw_or_recorded_directory_name_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "raw" / "response.json"
            target.parent.mkdir()
            target.write_text("{}", encoding="utf-8")
            self.assertIn("candidate_zone_in_public_artifact", {item["code"] for item in scan_public_artifact(root)})

    def test_unapproved_raster_media_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "image.jpg").write_bytes(b"not media")
            self.assertIn("third_party_media_in_public_artifact", {item["code"] for item in scan_public_artifact(root)})

    def test_operational_arms_tutorial_is_detected_in_public_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("武器装填教程", encoding="utf-8")
            self.assertIn("operational_arms_content", {item["code"] for item in scan_public_artifact(root)})

    def test_workflow_contains_no_live_acquisition(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("museum_pipeline acquire", workflow)
        self.assertNotIn("--live", workflow)
        self.assertNotIn("curl ", workflow)

    def test_workflow_validates_tracked_museum_03b_package_and_leakage_labels(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
        package = "data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1"
        label_set = f"{package}/public-leakage-label-set.json"
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("python scripts/validate_museum_03b_fixtures.py", workflow)
        self.assertIn(f"python scripts/validate_museum_03b_batch.py {package}", workflow)
        self.assertIn(
            f"python scripts/scan_public_artifact_for_candidate_data.py public --label-set {label_set}",
            workflow,
        )
        self.assertIn(
            f"python scripts/scan_public_artifact_for_candidate_data.py dist --label-set {label_set}",
            workflow,
        )
        self.assertEqual(2, workflow.count(f"--label-set {label_set}"))
        self.assertNotIn("build-approved-batch", workflow)
        self.assertNotIn("build-graph-input", workflow)

    def test_gitignore_blocks_raw_intermediate_and_staging(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for value in ("data/raw/**", "data/intermediate/**", "data/staging/**"):
            self.assertIn(value, text)


class FixtureAndSchemaTests(unittest.TestCase):
    def test_bootstrap_pipeline_validator_passes_before_recorded_live_probes(self) -> None:
        result = validate_pipeline_foundation(allow_missing_recorded=True, verbose=False)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(14, result["valid_fixtures"])
        self.assertEqual(28, result["invalid_fixtures"])

    def test_every_invalid_fixture_hits_its_expected_error(self) -> None:
        for path in sorted(INVALID.glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.name):
                self.assertIn(case["expected_error"], evaluate_invalid_fixture(case))

    def test_schema_manifest_registers_all_pipeline_schemas(self) -> None:
        environment = load_schema_environment()
        pipeline = [path for path in environment.by_path if path.startswith("schemas/pipeline/")]
        self.assertEqual(10, len(pipeline))
        self.assertEqual(68, len(environment.by_path))

    def test_canonical_dispatch_rejects_self_reported_downgrade(self) -> None:
        record = json.loads((VALID / "field-provenance.json").read_text(encoding="utf-8"))
        issues = validate_record(record, requested_schema="schemas/common/entity.schema.json")
        self.assertEqual(["schema_target_mismatch"], [issue.code for issue in issues])

    def test_art_context_dispatch_is_branch_aware(self) -> None:
        art_context = {"id": "place:fixture", "entity_type": "place", "branch_id": "art"}
        generic_context = {"id": "place:fixture", "entity_type": "place", "branch_id": "biology"}
        self.assertEqual("schemas/art/context/art-context.schema.json", canonical_schema_path(art_context))
        self.assertEqual("schemas/common/entity.schema.json", canonical_schema_path(generic_context))
        issues = validate_record(art_context, requested_schema="schemas/common/entity.schema.json")
        self.assertEqual("schema_target_mismatch", issues[0].code)

    def test_endpoint_registry_has_only_four_real_reference_adapters(self) -> None:
        sources = endpoint_registry()["sources"]
        self.assertEqual(REFERENCE_SOURCE_IDS, {item["source_id"] for item in sources})
        self.assertTrue(all(item["endpoint_template"].startswith("https://") for item in sources))

    def test_source_registry_verification_is_offline_and_hash_closed(self) -> None:
        result = verify_sources()
        self.assertTrue(result["ok"], result["issues"])
        self.assertTrue(result["endpoint_registry_snapshot_hash"].startswith("sha256:"))
        self.assertEqual("sha256:19d10386405abf971c5712e955f60c08d2bd43e6f8060a29035033ff3c33ada2", result["license_rules_snapshot_hash"])


if __name__ == "__main__":
    unittest.main()
