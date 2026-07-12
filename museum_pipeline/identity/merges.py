from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256


def create_merge_record(
    proposal: dict[str, Any],
    decision: dict[str, Any],
    *,
    survivor_candidate_id: str,
) -> dict[str, Any]:
    candidate_ids = set(proposal["candidate_ids"])
    if decision.get("decision_type") != "approve_same":
        raise PipelineError("merge_decision_invalid", "Only approve_same may create a merge record")
    if decision.get("target_id") != proposal.get("id"):
        raise PipelineError("merge_decision_target_mismatch", "Merge decision does not target this proposal")
    if decision.get("status") != "active":
        raise PipelineError("merge_decision_stale", "Only an active, non-stale decision may create a merge record")
    if survivor_candidate_id not in candidate_ids:
        raise PipelineError("merge_survivor_invalid", "Merge survivor is not one of the proposal candidates")
    loser_ids = sorted(candidate_ids - {survivor_candidate_id})
    if not loser_ids:
        raise PipelineError("merge_loser_missing", "Merge record requires at least one retained loser ID")
    if proposal.get("hard_conflicts") or proposal.get("proposed_status") == "distinct":
        raise PipelineError("merge_hard_conflict", "A proposal with hard conflicts cannot be merged")
    decided_at = decision["decided_at"]
    identity = f"{proposal['id']}|{decision['id']}|{survivor_candidate_id}"
    aliases = [{"alias_id": loser, "survivor_id": survivor_candidate_id, "active": True} for loser in loser_ids]
    return {
        "schema_version": "1.0.0",
        "id": f"merge-record:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
        "entity_type": "merge_record",
        "proposal_id": proposal["id"],
        "decision_id": decision["id"],
        "status": "applied",
        "survivor_candidate_id": survivor_candidate_id,
        "loser_candidate_ids": loser_ids,
        "alias_mappings": aliases,
        "loser_ids_retained": True,
        "reversible": True,
        "input_record_hashes": proposal["input_record_hashes"],
        "mapping_before_hash": canonical_sha256([]),
        "mapping_after_hash": canonical_sha256(aliases),
        "status_history": [{
            "from": None, "to": "applied", "changed_at": decided_at,
            "changed_by": decision["reviewer"], "role": decision["reviewer_role"],
            "reason": decision["rationale"],
        }],
    }


def reverse_merge_record(record: dict[str, Any], *, actor: str, role: str, rationale: str, at: str | None = None) -> dict[str, Any]:
    if record.get("status") != "applied" or record.get("reversible") is not True:
        raise PipelineError("merge_not_reversible", "Only an applied reversible merge may be reversed")
    timestamp = at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    updated = {**record, "status": "reversed"}
    updated["alias_mappings"] = [{**mapping, "active": False} for mapping in record["alias_mappings"]]
    updated["status_history"] = [*record["status_history"], {
        "from": "applied", "to": "reversed", "changed_at": timestamp,
        "changed_by": actor, "role": role, "reason": rationale,
    }]
    updated["mapping_after_hash"] = canonical_sha256(updated["alias_mappings"])
    return updated
