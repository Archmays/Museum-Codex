from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from museum_pipeline.cli import build_parser, main
from museum_pipeline.curation.bundle import build_selection_bundle, validate_selection_bundle
from museum_pipeline.curation.decision_application import apply_selection_decision, validate_committed_selection_application
from museum_pipeline.curation.fixtures import evaluate_curation_invalid_fixture
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.scan_public_artifact_for_candidate_data import candidate_terms_from_bundle, scan_public_artifact
from scripts.validate_artist_selection_preflight import validate_artist_selection_preflight


ROOT = Path(__file__).resolve().parents[2]
VALID = ROOT / "fixtures" / "curation" / "valid"
INVALID = ROOT / "fixtures" / "curation" / "invalid"


def load(name: str) -> dict:
    return json.loads((VALID / name).read_text(encoding="utf-8"))


def run_cli(argv: list[str]) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = main(argv)
    lines = [line for line in output.getvalue().splitlines() if line.strip().startswith("{")]
    return code, json.loads(lines[-1])


def synthetic_input() -> dict:
    base_candidate = load("artist-candidate-qualified.json")
    base_artwork = load("artwork-rights-clear.json")
    base_lead = load("relationship-lead-b.json")
    base_scenario = load("selection-scenario-twelve.json")
    candidates = []
    artworks = []
    leads = []
    for index in range(1, 19):
        candidate = deepcopy(base_candidate)
        candidate_id = f"artist-candidate:10000000-0000-5000-8000-{index:012d}"
        candidate["id"] = candidate_id
        candidate["preferred_labels"][0]["text"] = f"合成候选{index}"
        candidate["preferred_labels"][1]["text"] = f"Synthetic Candidate {index}"
        candidate["external_ids"] = {"fixture": [str(index)]}
        candidate["potential_artwork_ids"] = []
        for artwork_index in range(1, 5):
            serial = index * 100 + artwork_index
            artwork = deepcopy(base_artwork)
            artwork_id = f"artwork-preflight:20000000-0000-5000-8000-{serial:012d}"
            artwork.update({
                "id": artwork_id, "candidate_id": candidate_id,
                "official_object_id": f"fixture-{serial}", "title": f"Synthetic Object {serial}",
                "official_object_url": f"https://example.invalid/objects/{serial}",
                "rights_page_url": f"https://example.invalid/objects/{serial}/rights",
            })
            artwork["rights_evidence"][0]["url"] = artwork["rights_page_url"]
            candidate["potential_artwork_ids"].append(artwork_id)
            artworks.append(artwork)
        lead = deepcopy(base_lead)
        lead_id = f"relationship-lead:30000000-0000-5000-8000-{index:012d}"
        target_index = 1 if index == 18 else index + 1
        lead.update({
            "id": lead_id, "source_candidate_id": candidate_id,
            "target_candidate_id": f"artist-candidate:10000000-0000-5000-8000-{target_index:012d}",
        })
        candidate["relationship_lead_ids"] = [lead_id]
        leads.append(lead)
        candidates.append(candidate)

    selected = [item["id"] for item in candidates[:12]]
    scenarios = {}
    definitions = {
        "a": (1, "global_cross_cultural_balance", "Scenario A"),
        "b": (2, "relationships_learning_paths", "Scenario B"),
        "c": (3, "data_rights_readiness", "Scenario C"),
        "recommended": (4, "recommended_slate", "Recommended Slate"),
    }
    for key, (number, kind, title) in definitions.items():
        scenario = deepcopy(base_scenario)
        scenario["id"] = f"selection-scenario:40000000-0000-5000-8000-{number:012d}"
        scenario["scenario_kind"] = kind
        scenario["title"] = title
        scenario["candidate_ids"] = selected
        for row, candidate_id in zip(scenario["coverage_matrix"], selected, strict=True):
            row["candidate_id"] = candidate_id
        scenarios[key] = scenario
    alternates = [{
        "candidate_id": candidates[12 + index]["id"], "replaces_candidate_id": candidates[index]["id"],
        "replacement_reason": "Synthetic replacement contract.", "improves": "fixture diversity",
        "harms": "fixture connectivity", "rights_difference": "equivalent synthetic rights",
        "relationship_change": "one synthetic edge changes", "adapter_change": "none",
        "research_needed": "rerun synthetic validation", "full_slate_reaudit": True,
    } for index in range(6)]
    return {
        "candidate_pool": candidates, "artwork_rights_preflight": artworks,
        "relationship_leads": leads, "scenarios": scenarios, "alternates": alternates,
        "source_snapshots": [{
            "source_id": "source:synthetic-museum", "url": "https://example.invalid/source",
            "retrieved_at": "2026-07-13T00:00:00Z",
            "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }],
        "review_log": [{"reviewer": "fixture-reviewer", "status": "synthetic"}],
        "adapter_versions": {"source:synthetic-museum": "manual-preflight-1"},
        "generated_at": "2026-07-13T00:00:00Z",
    }


class CurationSchemaFixtureTests(unittest.TestCase):
    def test_all_six_valid_synthetic_fixtures_validate(self) -> None:
        for path in sorted(VALID.glob("*.json")):
            with self.subTest(path=path.name):
                self.assertEqual([], validate_record(json.loads(path.read_text(encoding="utf-8"))))

    def test_every_expected_invalid_fixture_hits_its_error(self) -> None:
        self.assertGreaterEqual(len(list(INVALID.glob("*.json"))), 12)
        for path in sorted(INVALID.glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.name):
                self.assertIn(case["expected_error"], evaluate_curation_invalid_fixture(case))

    def test_schema_manifest_registers_all_eight_curation_schemas(self) -> None:
        environment = load_schema_environment()
        curation = [path for path in environment.by_path if path.startswith("schemas/curation/")]
        self.assertEqual(8, len(curation))
        self.assertEqual(68, len(environment.by_path))

    def test_readiness_scores_are_not_art_value_rankings(self) -> None:
        candidate = load("artist-candidate-qualified.json")
        candidate["greatness_score"] = 3
        self.assertIn("art_value_or_release_field_forbidden", {item.code for item in validate_record(candidate)})

    def test_hard_gate_failure_cannot_be_offset_by_scores(self) -> None:
        candidate = load("artist-candidate-qualified.json")
        candidate["hard_gate_results"]["death_claim_reliable"] = False
        self.assertIn("qualified_hard_gate_failed", {item.code for item in validate_record(candidate)})

    def test_relationship_lead_never_becomes_formal(self) -> None:
        lead = load("relationship-lead-b.json")
        lead["formal_relationship_created"] = True
        self.assertIn("formal_relationship_in_lead", {item.code for item in validate_record(lead)})

    def test_decision_template_is_pending_and_unfilled(self) -> None:
        decision = load("selection-decision-pending.json")
        self.assertEqual("pending_user_decision", decision["status"])
        self.assertEqual([], validate_record(decision))


class SelectionBundleTests(unittest.TestCase):
    def test_build_and_validate_physical_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            manifest = build_selection_bundle(synthetic_input(), root)
            self.assertEqual(18, manifest["candidate_pool_count"])
            self.assertEqual(18, manifest["qualified_candidate_count"])
            self.assertEqual([], validate_selection_bundle(root))
            self.assertEqual(13, len(manifest["files"]))

    def test_stale_file_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            build_selection_bundle(synthetic_input(), root)
            (root / "review-log.json").write_text("[]", encoding="utf-8")
            self.assertIn("selection_bundle_stale", {item.code for item in validate_selection_bundle(root)})

    def test_unregistered_file_fails_exact_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            build_selection_bundle(synthetic_input(), root)
            (root / "extra.json").write_text("{}", encoding="utf-8")
            self.assertIn("bundle_file_set_mismatch", {item.code for item in validate_selection_bundle(root)})

    def test_media_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            build_selection_bundle(synthetic_input(), root)
            (root / "image.jpg").write_bytes(b"not-media")
            codes = {item.code for item in validate_selection_bundle(root)}
            self.assertIn("media_bytes_in_selection_bundle", codes)

    def test_candidate_labels_can_be_scanned_against_public_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            public = Path(temporary) / "public"
            public.mkdir()
            build_selection_bundle(synthetic_input(), root)
            (public / "index.html").write_text("Synthetic Candidate 1", encoding="utf-8")
            findings = scan_public_artifact(public, private_candidate_terms=candidate_terms_from_bundle(root))
            self.assertIn("candidate_name_publicly_exposed", {item["code"] for item in findings})

    def test_handoff_and_decision_bind_same_bundle_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            manifest = build_selection_bundle(synthetic_input(), root)
            decision = json.loads((root / "selection-decision-template.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["bundle_hash"], decision["input_bundle_hash"])
            self.assertIn(manifest["bundle_hash"], (root / "selection-handoff.md").read_text(encoding="utf-8"))


class CurationCliTests(unittest.TestCase):
    def test_help_lists_curation_commands_and_no_approve_command(self) -> None:
        help_text = build_parser().format_help()
        for command in ("build-selection-pool", "validate-selection-bundle", "compare-scenarios", "render-selection-handoff", "explain-candidate", "selection-decision-template", "apply-selection-decision"):
            self.assertIn(command, help_text)
        self.assertNotIn("approve-selection", help_text)

    def test_validate_compare_render_explain_and_decision_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            build_selection_bundle(synthetic_input(), root)
            for argv in (
                ["validate-selection-bundle", str(root), "--json"],
                ["compare-scenarios", str(root), "--json"],
                ["render-selection-handoff", str(root), "--json"],
                ["explain-candidate", "artist-candidate:10000000-0000-5000-8000-000000000001", "--bundle", str(root), "--json"],
                ["selection-decision-template", str(root), "--json"],
            ):
                with self.subTest(command=argv[0]):
                    code, payload = run_cli(argv)
                    self.assertEqual(0, code, payload)
                    self.assertTrue(payload["ok"])

    def test_public_preflight_validator_is_offline_and_passes(self) -> None:
        result = validate_artist_selection_preflight(verbose=False)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(6, result["valid_fixtures"])
        self.assertGreaterEqual(result["invalid_fixtures"], 12)

    def test_apply_recommended_decision_is_idempotent_and_conflict_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            build_selection_bundle(synthetic_input(), bundle)
            decision = json.loads((bundle / "selection-decision-template.json").read_text(encoding="utf-8"))
            recommended = json.loads((bundle / "recommended-slate.json").read_text(encoding="utf-8"))
            decision.update({
                "status": "submitted",
                "decision_type": "approve_recommended_slate",
                "decision_authority": "Mays",
                "decision_date": "2026-07-13T12:00:00+08:00",
                "selected_scenario_id": recommended["id"],
                "selected_candidate_ids": recommended["candidate_ids"],
                "media_strategy": "mixed",
                "public_scope": {"artist_metadata": True, "artwork_metadata": True, "media": "mixed"},
                "rationale": "Synthetic approval for application testing.",
                "acknowledged_limitations": ["fixture"] * 5,
                "additional_constraints": ["no automatic artist replacement"],
            })
            decision_path = root / "decision.json"
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            output = root / "application.json"
            receipt, repeated = apply_selection_decision(
                bundle_root=bundle, decision_path=decision_path, output_path=output,
                resulting_batch_id="art-batch:synthetic-first-slate-v1",
                applied_at="2026-07-13T04:00:00Z", code_commit="a" * 40,
            )
            self.assertFalse(repeated)
            self.assertEqual([], validate_record(receipt))
            before = output.read_bytes()
            repeated_receipt, repeated = apply_selection_decision(
                bundle_root=bundle, decision_path=decision_path, output_path=output,
                resulting_batch_id="art-batch:synthetic-first-slate-v1",
                applied_at="2026-07-13T05:00:00Z", code_commit="b" * 40,
            )
            self.assertTrue(repeated)
            self.assertEqual(receipt, repeated_receipt)
            self.assertEqual(before, output.read_bytes())
            self.assertEqual([], validate_committed_selection_application(decision_path, output))
            with self.assertRaisesRegex(PipelineError, "different inputs"):
                apply_selection_decision(
                    bundle_root=bundle, decision_path=decision_path, output_path=output,
                    resulting_batch_id="art-batch:conflicting-v2",
                    applied_at="2026-07-13T05:00:00Z", code_commit="b" * 40,
                )

    def test_apply_rejects_wrong_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            build_selection_bundle(synthetic_input(), bundle)
            decision = json.loads((bundle / "selection-decision-template.json").read_text(encoding="utf-8"))
            recommended = json.loads((bundle / "recommended-slate.json").read_text(encoding="utf-8"))
            decision.update({
                "status": "submitted", "decision_type": "approve_recommended_slate",
                "decision_authority": "Someone Else", "decision_date": "2026-07-13T12:00:00+08:00",
                "selected_scenario_id": recommended["id"], "selected_candidate_ids": recommended["candidate_ids"],
                "media_strategy": "mixed", "public_scope": {"artist_metadata": True, "artwork_metadata": True, "media": "mixed"},
                "rationale": "Synthetic invalid authority.",
            })
            decision_path = root / "decision.json"
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "does not match"):
                apply_selection_decision(
                    bundle_root=bundle, decision_path=decision_path, output_path=root / "application.json",
                    resulting_batch_id="art-batch:synthetic-first-slate-v1",
                    applied_at="2026-07-13T04:00:00Z", code_commit="a" * 40,
                )


if __name__ == "__main__":
    unittest.main()
