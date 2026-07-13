from __future__ import annotations

import json
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

from museum_pipeline.art.artworks import (
    DEFAULT_SELECTION_BASIS,
    DEFAULT_SNAPSHOT_RECEIPTS,
    EXPECTED_EXCLUDED_CANDIDATE_COUNT,
    EXPECTED_EXCLUDED_CANDIDATE_SET_HASH,
    EXPECTED_MEDIA_DISTRIBUTION,
    EXPECTED_SELECTION,
    _contains_mojibake,
    _evidence_record,
    _formal_selection_basis,
    _media_assessment,
    _media_binding,
    _validate_basis,
)
from museum_pipeline.config import source_license_rules
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import reference_graph_issues


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ArtworkStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.basis = _load(DEFAULT_SELECTION_BASIS)
        cls.ledger = _load(DEFAULT_SNAPSHOT_RECEIPTS)

    def test_tracked_basis_is_exact_reviewed_44_with_clean_zh_titles(self) -> None:
        _validate_basis(self.basis)
        observed = tuple(
            (item["approved_artist_id"], item["source_id"], item["source_object_id"])
            for item in self.basis["entries"]
        )
        self.assertEqual(EXPECTED_SELECTION, observed)
        self.assertEqual(44, len(observed))
        self.assertEqual(44, len({item["rights_preflight_id"] for item in self.basis["entries"]}))
        self.assertEqual(EXPECTED_EXCLUDED_CANDIDATE_COUNT, self.basis["excluded_candidate_count"])
        self.assertEqual(EXPECTED_EXCLUDED_CANDIDATE_SET_HASH, self.basis["excluded_candidate_set_hash"])
        self.assertEqual(
            ["111442", "13506", "26650", "28826"],
            [object_id for artist_id, source_id, object_id in observed if artist_id == "artist:mary-cassatt" and source_id == "aic_api"],
        )
        self.assertTrue(all(not _contains_mojibake(item["title_translation"]["text"]) for item in self.basis["entries"]))

    def test_tracked_snapshot_ledger_hash_and_exact_receipt_set(self) -> None:
        self.assertEqual(
            self.ledger["content_hash"],
            canonical_sha256({key: value for key, value in self.ledger.items() if key != "content_hash"}),
        )
        observed = [
            (item["source_id"], item["source_object_ids"][0])
            for item in self.ledger["entries"]
        ]
        self.assertEqual([(source_id, object_id) for _, source_id, object_id in EXPECTED_SELECTION], observed)
        self.assertEqual(44, len({item["snapshot_id"] for item in self.ledger["entries"]}))
        self.assertTrue(all(item["verification"] == {"body_present": True, "byte_count_match": True, "hash_match": True} for item in self.ledger["entries"]))

    def test_basis_rejects_question_mark_translation(self) -> None:
        altered = deepcopy(self.basis)
        altered["entries"][0]["title_translation"]["text"] = "?"
        altered["content_hash"] = canonical_sha256({key: value for key, value in altered.items() if key != "content_hash"})
        with self.assertRaises(PipelineError) as raised:
            _validate_basis(altered)
        self.assertEqual("artwork_title_translation_invalid", raised.exception.code)

    def test_formal_selection_basis_and_all_media_assessments_are_schema_valid(self) -> None:
        artworks = [
            {"id": f"artwork:{'met' if item['source_id'] == 'met_open_access' else 'aic'}-{item['source_object_id']}"}
            for item in self.basis["entries"]
        ]
        signoffs = [
            {"id": f"review-signoff:test-{index}"}
            for index in range(1, 177)
        ]
        formal_basis = _formal_selection_basis(self.basis, artworks, signoffs)
        environment = load_schema_environment()
        self.assertEqual([], validate_record(formal_basis, environment=environment))
        self.assertEqual(
            formal_basis["content_hash"],
            canonical_sha256({key: value for key, value in formal_basis.items() if key != "content_hash"}),
        )

        assessments = []
        for decision, receipt, artwork in zip(self.basis["entries"], self.ledger["entries"], artworks, strict=True):
            slug = artwork["id"].split(":", 1)[1]
            assessment = _media_assessment(
                decision,
                receipt,
                decision["expected_source_fields"],
                artwork["id"],
                slug,
                self.basis,
                f"review-signoff:{slug}-rights",
            )
            self.assertEqual([], validate_record(assessment, environment=environment), assessment["id"])
            assessments.append(assessment)
        self.assertEqual(Counter(EXPECTED_MEDIA_DISTRIBUTION), Counter(item["outcome"] for item in assessments))
        self.assertTrue(all(not item["bytes_downloaded"] and not item["media_bytes_present"] for item in assessments))
        self.assertTrue(all(not item["technical_delivery"]["cache_bytes"] for item in assessments))
        for assessment, decision in zip(assessments, self.basis["entries"], strict=True):
            self.assertEqual([_media_binding(decision["source_id"])], assessment["source_license_bindings"])
            binding = assessment["source_license_bindings"][0]
            self.assertEqual("media", binding["content_class"])
            self.assertEqual("object_level", binding["permission_resolution"])
            if assessment["future_public_media_eligible"]:
                self.assertEqual("cc0", assessment["media_rights_status"])
                self.assertEqual("CC0-1.0", assessment["media_license"]["identifier"])
                self.assertEqual("allowed", assessment["permissions"]["redistribution"])
                self.assertIn(assessment["permission_status"], {"approved", "not_applicable"})
                self.assertEqual("active", assessment["withdrawal_or_revocation"]["status"])
                self.assertIn(assessment["risk"], {"low", "medium"})
            else:
                self.assertEqual("metadata_only", assessment["outcome"])
                self.assertEqual("unknown", assessment["media_rights_status"])
                self.assertIsNone(assessment["media_license"])
                self.assertFalse(assessment["future_public_media_eligible"])

    def test_self_hosted_media_contract_rejects_contradictory_permissions_and_rules(self) -> None:
        index = next(
            index
            for index, item in enumerate(self.basis["entries"])
            if item["media_eligibility_class"] == "self_hosted_open_media_eligible"
        )
        decision = self.basis["entries"][index]
        receipt = self.ledger["entries"][index]
        slug = f"contract-{decision['source_object_id']}"
        assessment = _media_assessment(
            decision,
            receipt,
            decision["expected_source_fields"],
            f"artwork:{slug}",
            slug,
            self.basis,
            f"review-signoff:{slug}-rights",
        )
        environment = load_schema_environment()
        self.assertEqual([], validate_record(assessment, environment=environment))

        def set_wrong_license(record):
            record["media_license"]["identifier"] = "PDM-1.0"

        def prohibit_redistribution(record):
            record["permissions"]["redistribution"] = "prohibited"

        def deny_permission(record):
            record["permission_status"] = "denied"

        def revoke_decision(record):
            record["withdrawal_or_revocation"]["status"] = "revoked"

        def raise_risk(record):
            record["risk"] = "high"

        def bind_data_rule(record):
            data_rule = next(rule for rule in source_license_rules(decision["source_id"]) if rule["content_class"] == "data")
            record["source_license_bindings"][0]["rule_id"] = data_rule["rule_id"]

        def remove_binding(record):
            record["source_license_bindings"] = []

        cases = {
            "license/status mismatch": (set_wrong_license, "media_assessment_license_status_mismatch"),
            "redistribution prohibited": (prohibit_redistribution, "media_assessment_redistribution_blocked"),
            "permission denied": (deny_permission, "media_assessment_permission_status_invalid"),
            "withdrawal revoked": (revoke_decision, "media_assessment_withdrawal_inactive"),
            "risk high": (raise_risk, "media_assessment_risk_unbounded"),
            "data rule substituted": (bind_data_rule, "media_assessment_source_rule_mismatch"),
            "binding missing": (remove_binding, "media_assessment_source_binding_count"),
        }
        for label, (mutate, expected_code) in cases.items():
            with self.subTest(label=label):
                altered = deepcopy(assessment)
                mutate(altered)
                codes = {issue.code for issue in validate_record(altered, environment=environment)}
                self.assertIn(expected_code, codes)

    def test_media_assessment_binding_closes_against_selected_source_media_rule(self) -> None:
        index = next(
            index
            for index, item in enumerate(self.basis["entries"])
            if item["media_eligibility_class"] == "self_hosted_open_media_eligible"
        )
        decision = self.basis["entries"][index]
        receipt = self.ledger["entries"][index]
        source_rules = source_license_rules(decision["source_id"])
        source = {
            "id": f"source:{decision['source_id']}",
            "entity_type": "source",
            "license_rules": source_rules,
            "selected_license_rule_ids": [rule["rule_id"] for rule in source_rules],
        }
        slug = f"closure-{decision['source_object_id']}"
        assessment = _media_assessment(
            decision,
            receipt,
            decision["expected_source_fields"],
            f"artwork:{slug}",
            slug,
            self.basis,
            f"review-signoff:{slug}-rights",
        )
        codes = {issue.code for issue in reference_graph_issues([{"data": source}, {"data": assessment}])}
        forbidden_prefixes = (
            "source_license_binding_",
            "source_license_scope_",
            "media_source_rule_",
            "media_mixed_rule_",
            "media_object_level_",
            "factual_",
        )
        self.assertFalse([code for code in codes if code.startswith(forbidden_prefixes)], sorted(codes))

    def test_aic_evidence_human_locator_does_not_expand_license_scope(self) -> None:
        decision = next(item for item in self.basis["entries"] if item["source_id"] == "aic_api")
        receipt = next(item for item in self.ledger["entries"] if item["source_id"] == "aic_api")
        evidence = _evidence_record(
            "evidence:test-aic-scope",
            ["claim:test-aic-scope"],
            "aic_api",
            decision["source_object_id"],
            {
                "snapshot_id": receipt["snapshot_id"],
                "body_sha256": receipt["body_sha256"],
                "source_object_id": decision["source_object_id"],
            },
            ["/data/title", "/data/date_display"],
            "Exact AIC fields support this scope regression fixture.",
            "collection_record",
            "api_field",
            self.basis["reviewed_at"],
        )
        claim = {
            "id": "claim:test-aic-scope",
            "entity_type": "claim",
            "predicate": "official_object_record",
            "evidence_ids": [evidence["id"]],
            "counter_evidence_ids": [],
            "status": "reviewed",
        }
        rules = source_license_rules("aic_api")
        source = {
            "id": "source:aic_api",
            "entity_type": "source",
            "license_rules": rules,
            "selected_license_rule_ids": [rule["rule_id"] for rule in rules],
        }
        issues = reference_graph_issues([{"data": source}, {"data": claim}, {"data": evidence}])
        self.assertNotIn("source_license_scope_mismatch", {issue.code for issue in issues})
        self.assertTrue(evidence["locator"]["section"].startswith("raw fields: "))


if __name__ == "__main__":
    unittest.main()
