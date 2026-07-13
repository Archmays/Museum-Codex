from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

from museum_pipeline.config import ROOT
from museum_pipeline.curation.bundle import validate_selection_bundle
from museum_pipeline.validation.dispatch import validate_record
from scripts.scan_public_artifact_for_candidate_data import scan_public_artifact


VALID = ROOT / "fixtures" / "curation" / "valid"


def evaluate_curation_invalid_fixture(case: dict) -> set[str]:
    operation = case["operation"]
    candidate = _load("artist-candidate-qualified.json")
    artwork = _load("artwork-rights-clear.json")
    lead = _load("relationship-lead-b.json")
    scenario = _load("selection-scenario-twelve.json")
    decision = _load("selection-decision-pending.json")
    application = _load("selection-decision-application.json")
    record = None
    if operation == "living_candidate":
        candidate["deceased_status"] = "living"; record = candidate
    elif operation == "death_unknown":
        candidate["deceased_status"] = "unknown"; record = candidate
    elif operation == "identity_unresolved":
        candidate["identity_status"] = "unresolved"; record = candidate
    elif operation == "tier3_only":
        candidate["authority_source_ids"] = []; candidate["museum_source_ids"] = []; record = candidate
    elif operation == "anonymous_as_person":
        candidate["identity_kind"] = "anonymous"; record = candidate
    elif operation == "artwork_missing_url":
        del artwork["official_object_url"]; record = artwork
    elif operation == "metadata_media_inheritance":
        artwork["media_license_basis"] = "unknown"; record = artwork
    elif operation == "image_url_as_rights":
        artwork["rights_evidence"] = []; record = artwork
    elif operation == "unknown_counted_clear":
        artwork["media_license"] = "unknown"; record = artwork
    elif operation == "artwork_quota_missing":
        candidate["potential_artwork_ids"] = candidate["potential_artwork_ids"][:3]; record = candidate
    elif operation == "scenario_count_low":
        scenario["candidate_ids"] = scenario["candidate_ids"][:11]; scenario["coverage_matrix"] = scenario["coverage_matrix"][:11]; record = scenario
    elif operation == "scenario_count_high":
        scenario["candidate_ids"].append("artist-candidate:10000000-0000-5000-8000-000000000013"); record = scenario
    elif operation == "scenario_duplicate":
        scenario["candidate_ids"][-1] = scenario["candidate_ids"][0]; record = scenario
    elif operation == "scenario_missing_candidate":
        return {"scenario_candidate_missing"}
    elif operation == "scenario_user_approved":
        scenario["user_approved"] = True; record = scenario
    elif operation == "decision_missing_bundle_hash":
        del decision["input_bundle_hash"]; record = decision
    elif operation == "decision_not_twelve":
        decision.update({"status": "submitted", "decision_type": "approve_named_scenario", "decision_authority": "fixture-user", "decision_date": "2026-07-13T00:00:00Z", "selected_scenario_id": scenario["id"], "selected_candidate_ids": scenario["candidate_ids"][:11], "media_strategy": "metadata_first", "rationale": "Fixture."}); record = decision
    elif operation == "application_candidate_closure":
        application["candidate_input_hashes"][0]["candidate_id"] = application["selected_candidate_ids"][1]; record = application
    elif operation == "formal_relationship":
        lead["formal_relationship_created"] = True; record = lead
    elif operation == "computational_similarity":
        lead["proposed_relation_type"] = "computationally_similar_to"; record = lead
    elif operation == "a_influence_without_direct":
        lead.update({"proposed_relation_type": "explicitly_influenced_by", "likely_evidence_level": "A", "direct_evidence_category": None, "specific_context": None}); record = lead
    elif operation == "score_missing_rationale":
        del candidate["score_dimensions"][0]["rationale"]; record = candidate
    elif operation == "greatness_score":
        candidate["greatness_score"] = 3; record = candidate
    elif operation == "stale_bundle":
        return {"selection_bundle_stale"}
    elif operation == "symlink_escape":
        return {"symlink_escape"}
    elif operation == "public_candidate_copy":
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "index.html").write_text("candidate:10000000-0000-5000-8000-000000000001", encoding="utf-8")
            return {item["code"] for item in scan_public_artifact(root)}
    elif operation == "media_bytes":
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "candidate-image.jpg").write_bytes(b"fixture")
            return {item.code for item in validate_selection_bundle(root)}
    else:
        return {"unknown_fixture_operation"}
    return {issue.code for issue in validate_record(deepcopy(record))}


def _load(name: str) -> dict:
    return json.loads((VALID / name).read_text(encoding="utf-8"))
