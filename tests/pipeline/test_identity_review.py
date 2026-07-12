from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from museum_pipeline.adapters import get_adapter
from museum_pipeline.adapters.base import ResponseContract
from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.identity.merges import create_merge_record, reverse_merge_record
from museum_pipeline.identity.proposals import propose_identities
from museum_pipeline.identity.signals import special_identity_mapping_issues
from museum_pipeline.normalization.provenance import provenance_entry
from museum_pipeline.review.bundles import build_review_bundle
from museum_pipeline.review.decisions import apply_decisions, decision_is_stale
from museum_pipeline.validation.dispatch import validate_record
from museum_pipeline.validation.physical import validate_review_bundle_file


ROOT = Path(__file__).resolve().parents[2]
VALID = ROOT / "fixtures" / "pipeline" / "valid"


def candidate(source_id: str) -> dict:
    filenames = {
        "wikidata": "adapter-wikidata-response.json",
        "getty_ulan": "adapter-getty-ulan-response.json",
    }
    object_ids = {"wikidata": "Q42", "getty_ulan": "500115493"}
    adapter = get_adapter(source_id)
    body = (VALID / filenames[source_id]).read_bytes()
    response = ResponseContract(200, {"content-type": "application/json"}, body, adapter.build_request(object_ids[source_id]).url)
    document = adapter.validate_response_contract(response)
    return adapter.normalize(document, snapshot_id=f"snapshot:{source_id}:fixture", observed_at="2026-07-12T00:00:00Z")


def rehash(value: dict) -> dict:
    value["input_hash"] = canonical_sha256({key: item for key, item in value.items() if key != "input_hash"})
    return value


def add_viaf_external_id(value: dict) -> None:
    source = value["source_records"][0]
    value["fields"]["external_ids"] = {"viaf": ["113230702"]}
    value["field_provenance"].append(provenance_entry(
        candidate_id=value["id"], field_pointer="/fields/external_ids/viaf/0",
        source_id=source["source_id"], source_object_id=source["source_object_id"],
        snapshot_id=source["raw_snapshot_id"], raw_locator="/fixture/external_ids/viaf/0",
        raw_value="113230702", normalized_value="113230702",
        rule_id=get_adapter(source["source_id"]).rule("data")["rule_id"], content_class="data",
        observed_at=value["observed_at"],
    ))


def decision(bundle: dict, proposal: dict, survivor: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "decision_schema_version": "1.0.0",
        "id": "review-decision:66666666-6666-5666-8666-666666666666",
        "entity_type": "review_decision",
        "target_id": proposal["id"],
        "decision_type": "approve_same",
        "reviewer": "fixture-reviewer",
        "reviewer_role": "identity_reviewer",
        "decided_at": "2026-07-12T00:00:00Z",
        "rationale": "Exact identifier manually reviewed.",
        "input_hashes": bundle["exact_input_hashes"],
        "survivor_candidate_id": survivor,
        "supersedes": None,
        "status": "active",
        "status_history": [{"from": None, "to": "active", "changed_at": "2026-07-12T00:00:00Z", "changed_by": "fixture-reviewer", "role": "identity_reviewer", "reason": "Fixture review."}],
    }


class IdentityTests(unittest.TestCase):
    def test_exact_external_id_generates_same_proposal_but_no_auto_merge(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        add_viaf_external_id(right)
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertEqual("same", proposal["proposed_status"])
        self.assertFalse(proposal["auto_merge"])
        self.assertEqual([], validate_record(proposal))

    def test_name_only_signal_remains_uncertain(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        right["fields"]["names"] = deepcopy(left["fields"]["names"])
        right["fields"]["same_as"] = []
        right["fields"].pop("external_ids", None)
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertEqual("uncertain", proposal["proposed_status"])
        self.assertTrue(any(signal["signal_type"] == "name_or_alias" for signal in proposal["signals"]))

    def test_birth_date_conflict_forces_distinct_even_with_exact_id(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        add_viaf_external_id(right)
        right["fields"]["birth_observations"] = [{"display_text": "2000"}]
        left["fields"]["birth_observations"] = [{"display_text": "1900"}]
        rehash(left)
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertEqual("distinct", proposal["proposed_status"])
        self.assertTrue(proposal["hard_conflicts"])

    def test_artwork_and_individual_kind_mismatch_is_always_distinct(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        right["candidate_kind"] = "artwork"
        add_viaf_external_id(right)
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertEqual("distinct", proposal["proposed_status"])
        self.assertIn("identity_kind_mismatch", {item["conflict_type"] for item in proposal["hard_conflicts"]})

    def test_special_identities_cannot_be_coerced_to_individuals(self) -> None:
        for source_kind in ("anonymous", "workshop", "collective", "traditional_attribution", "conventional_identity"):
            with self.subTest(source_kind=source_kind):
                self.assertEqual(["special_identity_coercion"], special_identity_mapping_issues(source_kind, "individual"))

    def test_same_source_lineage_is_not_marked_independent(self) -> None:
        left = candidate("wikidata")
        right = deepcopy(left)
        right["id"] = "candidate:99999999-9999-5999-8999-999999999999"
        right["source_records"][0]["source_object_id"] = "Q1"
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertFalse(proposal["source_independence"]["independent"])

    def test_copied_cross_source_records_share_upstream_lineage(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        left["source_records"][0]["upstream_lineage_id"] = "upstream:shared-authority-export"
        right["source_records"][0]["upstream_lineage_id"] = "upstream:shared-authority-export"
        rehash(left)
        rehash(right)
        proposal = propose_identities([left, right])[0]
        self.assertFalse(proposal["source_independence"]["independent"])

    def test_context_signals_cover_transliteration_life_place_period_institution_and_collection(self) -> None:
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        left["fields"]["names"].append({
            "text": "Albrecht Durer", "original_text": "Albrecht Durer", "language": "de",
            "script": "Latn", "name_type": "transliteration",
        })
        right["fields"]["names"].append({
            "text": "Albrecht Durer", "original_text": "Albrecht Durer", "language": "de",
            "script": "Latn", "name_type": "alternate",
        })
        for value in (left, right):
            value["fields"]["birth_observations"] = [{"display_text": "1471"}]
            value["fields"]["activity_places"] = [{"id": "tgn:7004334", "label": "Nürnberg"}]
            value["fields"]["activity_periods"] = ["1490-1528"]
            value["fields"]["institutions"] = ["institution:fixture"]
            value["fields"]["collection_clues"] = ["accession:fixture"]
            rehash(value)
        proposal = propose_identities([left, right])[0]
        signal_types = {item["signal_type"] for item in proposal["signals"]}
        self.assertTrue({
            "script_or_transliteration", "life_dates", "place_period", "institution", "collection_clue",
        } <= signal_types)

    def test_merge_record_retains_loser_alias_and_is_schema_valid(self) -> None:
        proposal = json.loads((VALID / "identity-proposal-external-id.json").read_text(encoding="utf-8"))
        bundle = {"exact_input_hashes": {"candidate.json": "sha256:" + "0" * 64}}
        survivor = proposal["candidate_ids"][0]
        record = create_merge_record(proposal, decision(bundle, proposal, survivor), survivor_candidate_id=survivor)
        self.assertTrue(record["loser_ids_retained"])
        self.assertEqual(set(record["loser_candidate_ids"]), {item["alias_id"] for item in record["alias_mappings"]})
        self.assertEqual([], validate_record(record))

    def test_merge_reversal_preserves_all_ids_and_history(self) -> None:
        record = json.loads((VALID / "merge-record-reversible.json").read_text(encoding="utf-8"))
        reversed_record = reverse_merge_record(record, actor="reviewer", role="identity_reviewer", rationale="Mistaken identity", at="2026-07-12T01:00:00Z")
        self.assertEqual("reversed", reversed_record["status"])
        self.assertFalse(reversed_record["alias_mappings"][0]["active"])
        self.assertEqual(record["loser_candidate_ids"], reversed_record["loser_candidate_ids"])
        self.assertEqual(2, len(reversed_record["status_history"]))

    def test_merge_semantics_reject_deleted_loser_alias(self) -> None:
        record = json.loads((VALID / "merge-record-reversible.json").read_text(encoding="utf-8"))
        record["alias_mappings"] = []
        self.assertIn("merge_loser_deleted", {issue.code for issue in validate_record(record)})


class ReviewTests(unittest.TestCase):
    def _run_dir(self, temporary: str) -> tuple[Path, dict, dict]:
        run_dir = Path(temporary)
        left = candidate("wikidata")
        right = candidate("getty_ulan")
        add_viaf_external_id(right)
        rehash(right)
        proposals = propose_identities([left, right])
        write_canonical_json(run_dir / "candidate-left.json", left)
        write_canonical_json(run_dir / "candidate-right.json", right)
        write_canonical_json(run_dir / "identity-proposals.json", proposals)
        bundle = build_review_bundle(run_dir)
        return run_dir, bundle, proposals[0]

    def test_review_bundle_contains_provenance_conflicts_rights_and_exact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, bundle, _ = self._run_dir(temporary)
            self.assertEqual(2, len(bundle["candidate_records"]))
            self.assertTrue(bundle["field_provenance"])
            self.assertTrue(bundle["rights_warnings"])
            self.assertIn("rights_reviewer", bundle["required_reviewer_roles"])
            self.assertFalse(bundle["candidate_data_publicly_exposed"])
            self.assertEqual([], validate_record(bundle))

    def test_review_bundle_hash_change_is_detected_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, bundle, _ = self._run_dir(temporary)
            bundle_path = run_dir / "review-bundle.json"
            write_canonical_json(bundle_path, bundle)
            self.assertEqual([], validate_review_bundle_file(bundle_path))
            (run_dir / "candidate-left.json").write_text("{}", encoding="utf-8")
            self.assertIn("review_input_hash_mismatch", {issue.code for issue in validate_review_bundle_file(bundle_path)})

    def test_stale_decision_is_not_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, bundle, proposal = self._run_dir(temporary)
            record = decision(bundle, proposal, proposal["candidate_ids"][0])
            record["input_hashes"] = {"candidate-left.json": "sha256:" + "f" * 64}
            self.assertTrue(decision_is_stale(bundle, record))
            result = apply_decisions(bundle, [record])
            self.assertFalse(result["results"][0]["applied"])
            self.assertEqual([], result["merge_records"])

    def test_active_approve_same_creates_only_reversible_merge_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, bundle, proposal = self._run_dir(temporary)
            record = decision(bundle, proposal, proposal["candidate_ids"][0])
            result = apply_decisions(bundle, [record])
            self.assertTrue(result["results"][0]["applied"])
            self.assertEqual(1, len(result["merge_records"]))
            self.assertFalse(result["publishable_records_created"])

    def test_hard_conflict_cannot_be_overridden_by_approve_same(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, bundle, proposal = self._run_dir(temporary)
            proposal["proposed_status"] = "distinct"
            proposal["hard_conflicts"] = [{"conflict_type": "birth_date_conflict"}]
            bundle["identity_proposals"] = [proposal]
            record = decision(bundle, proposal, proposal["candidate_ids"][0])
            with self.assertRaises(PipelineError) as raised:
                apply_decisions(bundle, [record])
            self.assertEqual("merge_hard_conflict", raised.exception.code)

    def test_missing_target_and_unauthorized_role_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, bundle, proposal = self._run_dir(temporary)
            missing = decision(bundle, proposal, proposal["candidate_ids"][0])
            missing["target_id"] = "identity-proposal:99999999-9999-5999-8999-999999999999"
            with self.assertRaises(PipelineError) as raised:
                apply_decisions(bundle, [missing])
            self.assertEqual("decision_target_missing", raised.exception.code)
            wrong_role = decision(bundle, proposal, proposal["candidate_ids"][0])
            wrong_role["reviewer_role"] = "rights_reviewer"
            with self.assertRaises(PipelineError) as raised:
                apply_decisions(bundle, [wrong_role])
            self.assertEqual("reviewer_role_invalid", raised.exception.code)

    def test_decision_status_history_must_match_current_status(self) -> None:
        record = json.loads((VALID / "review-decision.json").read_text(encoding="utf-8"))
        record["status"] = "stale"
        self.assertIn("decision_history_mismatch", {issue.code for issue in validate_record(record)})


if __name__ == "__main__":
    unittest.main()
