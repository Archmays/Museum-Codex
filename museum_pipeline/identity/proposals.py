from __future__ import annotations

import itertools
import uuid
from typing import Any

from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.identity.signals import compare_candidates


PROPOSAL_VERSION = "1.0.0"


def propose_identities(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    ordered = sorted(candidates, key=lambda candidate: candidate["id"])
    for left, right in itertools.combinations(ordered, 2):
        comparison = compare_candidates(left, right)
        strong = [signal for signal in comparison["signals"] if signal["strength"] == "strong"]
        if comparison["hard_conflicts"]:
            status = "distinct"
            rationale = "One or more hard identity conflicts require a distinct proposal."
        elif strong:
            status = "same"
            rationale = "An exact authority or source-declared same-as signal supports review as the same identity."
        else:
            status = "uncertain"
            rationale = "Available signals are insufficient; name overlap alone never authorizes a merge."
        input_hashes = {left["id"]: left["input_hash"], right["id"]: right["input_hash"]}
        identity = "|".join(f"{key}={input_hashes[key]}" for key in sorted(input_hashes))
        source_ids = [record["source_id"] for candidate in (left, right) for record in candidate.get("source_records", [])]
        left_lineage = {
            record.get("upstream_lineage_id") or record["source_id"]
            for record in left.get("source_records", [])
        }
        right_lineage = {
            record.get("upstream_lineage_id") or record["source_id"]
            for record in right.get("source_records", [])
        }
        proposals.append({
            "schema_version": "1.0.0",
            "id": f"identity-proposal:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
            "entity_type": "identity_proposal",
            "candidate_ids": sorted(input_hashes),
            "proposed_status": status,
            "signals": comparison["signals"],
            "hard_conflicts": comparison["hard_conflicts"],
            "source_independence": {
                "source_ids": sorted(set(source_ids)),
                "independent": left_lineage.isdisjoint(right_lineage),
                "note": "Canonical source and optional upstream lineage are compared; copied records are not independent evidence.",
            },
            "rationale": rationale,
            "input_record_hashes": input_hashes,
            "proposal_version": PROPOSAL_VERSION,
            "generated_at": max(left["observed_at"], right["observed_at"]),
            "review_status": "pending",
            "auto_merge": False,
            "proposal_hash": canonical_sha256({"inputs": input_hashes, "status": status, "version": PROPOSAL_VERSION}),
        })
    return proposals
