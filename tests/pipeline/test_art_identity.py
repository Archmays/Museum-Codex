from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from museum_pipeline.art.identity import DEFAULT_APPLICATION, DEFAULT_SEED, build_identity_stage
from museum_pipeline.art.validation import validate_identity_stage
from museum_pipeline.errors import PipelineError


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ArtIdentityStageTests(unittest.TestCase):
    def _build(self, root: Path) -> Path:
        package = root / "identity-stage"
        result = build_identity_stage(output_dir=package)
        self.assertTrue(result["ok"])
        self.assertEqual(12, result["artist_count"])
        return package

    def test_exact_identity_stage_builds_validates_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self._build(Path(temporary))
            first = validate_identity_stage(package_dir=package)
            self.assertTrue(first["ok"], first["failures"])
            self.assertEqual((12, 108, 88, 24, 4), (
                first["artist_count"], first["claim_count"], first["evidence_count"],
                first["review_signoff_count"], first["source_count"],
            ))
            second = build_identity_stage(output_dir=package)
            self.assertEqual([], second["written"])
            self.assertEqual(6, len(second["reused"]))

    def test_builder_rejects_replacement_count_and_substitution(self) -> None:
        application = _load(DEFAULT_APPLICATION)
        seed = _load(DEFAULT_SEED)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad_replacement = root / "replacement.json"
            replacement = deepcopy(application)
            replacement["replacement_count"] = 1
            _write(bad_replacement, replacement)
            with self.assertRaises(PipelineError) as raised:
                build_identity_stage(application_path=bad_replacement, output_dir=root / "replacement-stage")
            self.assertEqual("auto_replacement_forbidden", raised.exception.code)

            bad_seed = root / "substitution.json"
            substituted = deepcopy(seed)
            substituted["artists"][0]["approved_candidate_id"] = substituted["artists"][1]["approved_candidate_id"]
            _write(bad_seed, substituted)
            with self.assertRaises(PipelineError) as raised:
                build_identity_stage(seed_path=bad_seed, output_dir=root / "substitution-stage")
            self.assertEqual("approved_artist_identity_basis_mismatch", raised.exception.code)

    def test_validator_rejects_application_with_replacement_count(self) -> None:
        application = _load(DEFAULT_APPLICATION)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._build(root)
            application["replacement_count"] = 1
            application_path = root / "application.json"
            _write(application_path, application)
            failures = validate_identity_stage(package_dir=package, application_path=application_path)["failures"]
            self.assertIn("auto_replacement_present", failures)
            self.assertTrue(any(item.startswith("selection_application:schema:") for item in failures))

    def test_validator_rejects_broken_evidence_backlink_and_signoff_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self._build(Path(temporary))
            evidence_path = package / "identity-evidence.json"
            evidence = _load(evidence_path)
            original_claim = evidence[0]["claim_ids"][0]
            claims = _load(package / "identity-claims.json")
            replacement_claim = next(item["id"] for item in claims if item["id"] != original_claim)
            evidence[0]["claim_ids"] = [replacement_claim]
            _write(evidence_path, evidence)

            signoff_path = package / "review-signoffs.json"
            signoffs = _load(signoff_path)
            signoffs[0]["record_ids"][0] = "artist:missing"
            _write(signoff_path, signoffs)

            failures = validate_identity_stage(package_dir=package)["failures"]
            self.assertTrue(any(item.startswith("evidence_support_backlink_missing:") for item in failures))
            self.assertTrue(any(item.startswith("signoff_record_missing:") for item in failures))

    def test_ai_signoff_cannot_verify_or_promote_artist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self._build(Path(temporary))
            signoff_path = package / "review-signoffs.json"
            signoffs = _load(signoff_path)
            signoffs[0]["decision"] = "accepted_verified"
            _write(signoff_path, signoffs)

            artist_path = package / "artists.json"
            artists = _load(artist_path)
            artists[0]["review_status"] = "verified"
            _write(artist_path, artists)

            failures = validate_identity_stage(package_dir=package)["failures"]
            self.assertTrue(any(item.startswith("ai_signoff_cannot_verify:") for item in failures))
            self.assertTrue(any(item.startswith("artist_verified_without_human_signoff:") for item in failures))

    def test_identity_conflicts_and_license_scope_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self._build(Path(temporary))
            artist_path = package / "artists.json"
            artists = _load(artist_path)
            next(item for item in artists if item["id"] == "artist:raja-ravi-varma")["life_dates"]["death"]["display_value"] = "1907"
            _write(artist_path, artists)

            claim_path = package / "identity-claims.json"
            claims = _load(claim_path)
            next(item for item in claims if item["id"] == "claim:kitagawa-utamaro-birth")["counter_evidence_ids"] = []
            next(item for item in claims if item["id"] == "claim:henry-ossawa-tanner-wikidata-crosswalk")["counter_evidence_ids"] = []
            _write(claim_path, claims)

            evidence_path = package / "identity-evidence.json"
            evidence = _load(evidence_path)
            evidence[0]["source_license_bindings"][0]["scope_locator"] = "invented scope"
            _write(evidence_path, evidence)

            failures = validate_identity_stage(package_dir=package)["failures"]
            self.assertIn("identity_life_projection_mismatch:artist:raja-ravi-varma:death", failures)
            self.assertIn("identity_competing_claim_missing:artist:kitagawa-utamaro:birth", failures)
            self.assertIn("identity_external_conflict_not_quarantined:artist:henry-ossawa-tanner", failures)
            self.assertTrue(any("governance:source_license_scope_mismatch:" in item for item in failures))

    def test_reviewed_files_are_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self._build(Path(temporary))
            artist_path = package / "artists.json"
            artist_path.write_text(artist_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(PipelineError) as raised:
                build_identity_stage(output_dir=package)
            self.assertEqual("reviewed_identity_conflict", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
