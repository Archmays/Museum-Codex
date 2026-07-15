from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from museum_pipeline.config import ROOT
from museum_pipeline.validation.dispatch import (
    ART_MEDIA_SCHEMA_BY_ENTITY_TYPE,
    canonical_schema_path,
    load_schema_environment,
    validate_record,
)


SCHEMA_ROOT = ROOT / "schemas" / "art" / "media"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "media"

MEDIA_SCHEMA_CASES = {
    "media_acquisition_request": ("acquisition-request.schema.json", "media-request:"),
    "media_acquisition_event": ("acquisition-event.schema.json", "media-event:"),
    "media_byte_record": ("byte-record.schema.json", "media-byte:"),
    "media_automated_review": ("automated-review.schema.json", "media-review:"),
    "media_identity_rights_cross_check": (
        "identity-rights-cross-check.schema.json",
        "media-cross-check:",
    ),
    "media_quality_assessment": ("quality-assessment.schema.json", "media-quality:"),
    "media_derivative_record": ("derivative-record.schema.json", "media-derivative:"),
    "media_source_ledger": ("media-source-ledger.schema.json", "media-ledger:"),
    "media_bundle_manifest": ("media-bundle-manifest.schema.json", "media-bundle:"),
    "media_alternative_source_search": ("alternative-source-search.schema.json", "alternative-search:"),
    "media_withdrawal_mapping": ("withdrawal-mapping.schema.json", "withdrawal-map:"),
}

FINAL_DECISIONS = {
    "approved_self_hosted",
    "approved_external_delivery",
    "metadata_only_after_automated_review",
    "blocked_rights_conflict",
    "blocked_identity_conflict",
    "blocked_quality_failure",
    "blocked_source_unavailable",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def object_nodes(value: object, path: str = "$"):
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield path, value
        for key, child in value.items():
            yield from object_nodes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from object_nodes(child, f"{path}[{index}]")


class MediaSchemaDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = load_schema_environment()
        cls.valid_review = load_json(FIXTURE_ROOT / "valid" / "approved-self-hosted-review.json")

    def test_all_eleven_media_schemas_are_registered_and_manifested(self) -> None:
        self.assertEqual(MEDIA_SCHEMA_CASES, {
            entity_type: (Path(schema_path).name, prefix)
            for entity_type, (schema_path, prefix) in ART_MEDIA_SCHEMA_BY_ENTITY_TYPE.items()
        })
        manifest = load_json(ROOT / "schemas" / "schema-manifest.json")
        entries = {entry["path"]: entry for entry in manifest["schemas"]}
        self.assertEqual(11, len(MEDIA_SCHEMA_CASES))
        for filename, _prefix in MEDIA_SCHEMA_CASES.values():
            path = f"schemas/art/media/{filename}"
            self.assertIn(path, self.environment.by_path)
            self.assertIn(path, entries)
            self.assertEqual("art", entries[path]["branch"])

    def test_every_declared_object_is_closed(self) -> None:
        for filename, _prefix in MEDIA_SCHEMA_CASES.values():
            schema = load_json(SCHEMA_ROOT / filename)
            nodes = list(object_nodes(schema))
            self.assertTrue(nodes, filename)
            for path, node in nodes:
                self.assertIs(node.get("additionalProperties"), False, f"{filename}:{path}")

    def test_executor_and_human_review_are_fixed_for_every_record(self) -> None:
        for filename, _prefix in MEDIA_SCHEMA_CASES.values():
            schema = load_json(SCHEMA_ROOT / filename)
            self.assertEqual("automated_cross_validation_pipeline", schema["properties"]["executor"]["const"])
            self.assertIs(schema["properties"]["human_review_dependency"]["const"], False)
            self.assertIn("executor", schema["required"])
            self.assertIn("human_review_dependency", schema["required"])

    def test_canonical_dispatch_requires_entity_branch_and_id_prefix(self) -> None:
        for entity_type, (filename, prefix) in MEDIA_SCHEMA_CASES.items():
            record = {"entity_type": entity_type, "branch_id": "art", "id": f"{prefix}fixture"}
            self.assertEqual(f"schemas/art/media/{filename}", canonical_schema_path(record))
            self.assertIsNone(canonical_schema_path({**record, "branch_id": "biology"}))
            self.assertIsNone(canonical_schema_path({**record, "id": "entity:wrong-prefix"}))

    def test_requested_schema_cannot_downgrade_canonical_dispatch(self) -> None:
        record = {
            "entity_type": "media_automated_review",
            "branch_id": "art",
            "id": "media-review:downgrade-attempt",
        }
        issues = validate_record(
            record,
            requested_schema="schemas/common/entity.schema.json",
            environment=self.environment,
        )
        self.assertEqual(["schema_target_mismatch"], [issue.code for issue in issues])

    def test_positive_fixture_passes_canonical_validation(self) -> None:
        self.assertEqual([], validate_record(self.valid_review, environment=self.environment))

    def test_manual_review_and_non_terminal_decision_fixture_are_rejected(self) -> None:
        record = load_json(FIXTURE_ROOT / "invalid" / "forbidden-manual-review.json")
        issues = validate_record(record, environment=self.environment)
        self.assertGreaterEqual(len(issues), 2)
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("False was expected", messages)
        self.assertIn("pending_curator", messages)

    def test_terminal_outcome_vocabulary_is_exact(self) -> None:
        review = load_json(SCHEMA_ROOT / "automated-review.schema.json")
        alternative = load_json(SCHEMA_ROOT / "alternative-source-search.schema.json")
        ledger = load_json(SCHEMA_ROOT / "media-source-ledger.schema.json")
        self.assertEqual(FINAL_DECISIONS, set(review["$defs"]["finalDecision"]["enum"]))
        self.assertEqual(FINAL_DECISIONS, set(alternative["$defs"]["finalDecision"]["enum"]))
        self.assertEqual(FINAL_DECISIONS, set(ledger["$defs"]["finalDecision"]["enum"]))

        for decision in FINAL_DECISIONS:
            record = copy.deepcopy(self.valid_review)
            record["decision"] = decision
            self.assertEqual([], validate_record(record, environment=self.environment), decision)
        for forbidden in ("waiting_for_manual_review", "pending_curator", "unknown_passed"):
            record = copy.deepcopy(self.valid_review)
            record["decision"] = forbidden
            self.assertIn("schema", {issue.code for issue in validate_record(record, environment=self.environment)})

    def test_approved_self_hosted_requires_full_closure_and_a_derivative(self) -> None:
        failed_rights = copy.deepcopy(self.valid_review)
        failed_rights["mandatory_closure"]["rights"] = "fail"
        self.assertIn("schema", {issue.code for issue in validate_record(failed_rights, environment=self.environment)})

        no_derivative = copy.deepcopy(self.valid_review)
        no_derivative["derivative_ids"] = []
        self.assertIn("schema", {issue.code for issue in validate_record(no_derivative, environment=self.environment)})

        extra_field = copy.deepcopy(self.valid_review)
        extra_field["manual_reviewer"] = "forbidden"
        self.assertIn("schema", {issue.code for issue in validate_record(extra_field, environment=self.environment)})

    def test_acquisition_request_binds_m03b_identity_rights_and_live_mode(self) -> None:
        schema = load_json(SCHEMA_ROOT / "acquisition-request.schema.json")
        candidate_variants = schema["properties"]["candidate_media_url"]["oneOf"]
        self.assertIn({"type": "null"}, candidate_variants)
        self.assertEqual(
            {
                "official_object_id", "accession", "artist", "title", "date", "institution",
                "object_url", "source_snapshot_id", "source_snapshot_hash",
            },
            set(schema["properties"]["expected_identity"]["required"]),
        )
        baseline = schema["properties"]["baseline_media_assessment"]
        self.assertEqual(
            {"self_hosted_open_media_eligible", "external_iiif_candidate", "metadata_only"},
            set(baseline["properties"]["outcome"]["enum"]),
        )
        self.assertEqual(1, schema["properties"]["concurrency"]["const"])
        self.assertIs(schema["properties"]["arbitrary_url_allowed"]["const"], False)
        self.assertIs(schema["properties"]["cookies_allowed"]["const"], False)

    def test_ledger_bundle_and_derivative_contracts_are_fail_closed(self) -> None:
        ledger = load_json(SCHEMA_ROOT / "media-source-ledger.schema.json")
        self.assertEqual(44, ledger["properties"]["total_artworks"]["const"])
        self.assertEqual(44, ledger["properties"]["entries"]["minItems"])
        self.assertEqual(44, ledger["properties"]["entries"]["maxItems"])

        bundle = load_json(SCHEMA_ROOT / "media-bundle-manifest.schema.json")
        self.assertEqual("boolean", bundle["properties"]["release_allowed"]["type"])
        self.assertIn("release_allowed", bundle["required"])
        self.assertEqual(44, bundle["properties"]["counts"]["properties"]["artworks_reviewed"]["const"])

        derivative = load_json(SCHEMA_ROOT / "derivative-record.schema.json")
        for forbidden_flag in ("upscaled", "ai_used", "content_altered", "watermark_removed"):
            self.assertIs(derivative["properties"][forbidden_flag]["const"], False)
        self.assertEqual(1600, derivative["properties"]["width"]["maximum"])


if __name__ == "__main__":
    unittest.main()
