from __future__ import annotations

from copy import deepcopy
from typing import Any

from museum_pipeline.errors import PipelineError
from museum_pipeline.identity.merges import create_merge_record


ALLOWED_DECISIONS = {
    "approve_same", "approve_distinct", "defer_uncertain", "reject_bad_source_record",
    "request_more_evidence", "approve_field_mapping", "reject_field_mapping",
}


def decision_is_stale(bundle: dict[str, Any], decision: dict[str, Any]) -> bool:
    expected = bundle.get("exact_input_hashes", {})
    supplied = decision.get("input_hashes", {})
    return supplied != expected


def apply_decisions(bundle: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    proposal_by_id = {item["id"]: item for item in bundle.get("identity_proposals", [])}
    candidate_ids = {item["id"] for item in bundle.get("candidate_records", [])}
    provenance_ids = {item["id"] for item in bundle.get("field_provenance", [])}
    seen_targets: set[str] = set()
    results: list[dict[str, Any]] = []
    merge_records: list[dict[str, Any]] = []
    for raw_decision in sorted(decisions, key=lambda item: item.get("id", "")):
        if raw_decision.get("decision_type") not in ALLOWED_DECISIONS:
            raise PipelineError("decision_type_invalid", "Review decision type is not supported")
        decision = deepcopy(raw_decision)
        if decision.get("status") != "active":
            raise PipelineError("decision_status_invalid", "Only an active review decision may be evaluated")
        if decision_is_stale(bundle, decision):
            decision["status"] = "stale"
            decision.setdefault("status_history", []).append({
                "from": "active", "to": "stale", "changed_at": decision["decided_at"],
                "changed_by": "pipeline", "role": "release_manager", "reason": "Input hashes changed",
            })
            results.append({"decision": decision, "applied": False, "reason": "stale_input_hashes"})
            continue
        decision["status"] = "active"
        decision_type = decision["decision_type"]
        target_id = decision.get("target_id")
        if not isinstance(target_id, str):
            raise PipelineError("decision_target_missing", "Review decision target is missing")
        if target_id in seen_targets:
            raise PipelineError("decision_target_conflict", "One application batch cannot contain competing active decisions for the same target")
        seen_targets.add(target_id)
        allowed_roles = {
            "approve_same": {"identity_reviewer", "discipline_reviewer"},
            "approve_distinct": {"identity_reviewer", "discipline_reviewer"},
            "defer_uncertain": {"identity_reviewer", "discipline_reviewer"},
            "reject_bad_source_record": {"discipline_reviewer", "rights_reviewer"},
            "request_more_evidence": {"identity_reviewer", "discipline_reviewer", "rights_reviewer"},
            "approve_field_mapping": {"normalizer", "discipline_reviewer"},
            "reject_field_mapping": {"normalizer", "discipline_reviewer"},
        }[decision_type]
        if decision.get("reviewer_role") not in allowed_roles:
            raise PipelineError("reviewer_role_invalid", "Reviewer role is not authorized for this decision type")
        if decision_type in {"approve_same", "approve_distinct", "defer_uncertain"} and target_id not in proposal_by_id:
            raise PipelineError("decision_target_missing", "Identity decision target proposal is missing")
        if decision_type == "reject_bad_source_record" and target_id not in candidate_ids:
            raise PipelineError("decision_target_missing", "Source-record rejection target candidate is missing")
        if decision_type in {"approve_field_mapping", "reject_field_mapping"} and target_id not in provenance_ids:
            raise PipelineError("decision_target_missing", "Field-mapping decision target provenance is missing")
        if decision_type == "request_more_evidence" and target_id not in proposal_by_id and target_id not in candidate_ids and target_id not in provenance_ids:
            raise PipelineError("decision_target_missing", "Evidence request target is missing from the bundle")
        if decision_type == "approve_same":
            proposal = proposal_by_id.get(target_id)
            if proposal is None:
                raise PipelineError("decision_target_missing", "approve_same target proposal is missing")
            if proposal.get("hard_conflicts") or proposal.get("proposed_status") == "distinct":
                raise PipelineError("merge_hard_conflict", "A distinct or hard-conflict proposal cannot be approved as the same identity")
            survivor = decision.get("survivor_candidate_id")
            if not isinstance(survivor, str):
                raise PipelineError("merge_survivor_missing", "approve_same requires survivor_candidate_id")
            merge_records.append(create_merge_record(proposal, decision, survivor_candidate_id=survivor))
        results.append({"decision": decision, "applied": True, "reason": "accepted_for_local_review_state"})
    return {
        "bundle_id": bundle["id"],
        "results": results,
        "merge_records": merge_records,
        "publishable_records_created": False,
    }
