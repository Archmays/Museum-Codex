from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from museum_pipeline.hashing import canonical_sha256, sha256_file


def load_records(directory: Path, entity_type: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        values = value if isinstance(value, list) else [value]
        records.extend(item for item in values if isinstance(item, dict) and item.get("entity_type") == entity_type)
    return sorted(records, key=lambda item: item["id"])


def build_review_bundle(run_dir: Path) -> dict[str, Any]:
    candidates = load_records(run_dir, "normalized_candidate")
    proposals = load_records(run_dir, "identity_proposal")
    input_files = []
    ignored_inputs = {"pipeline-run.json", "review-bundle.json", "decision-results.json"}
    for path in sorted(run_dir.rglob("*.json")):
        if path.name in ignored_inputs:
            continue
        relative = path.relative_to(run_dir).as_posix()
        input_files.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    input_hashes = {item["path"]: item["sha256"] for item in input_files}
    rights_warnings = [
        {"candidate_id": candidate["id"], "source_locator": media["source_locator"], "code": "media_rights_unverified"}
        for candidate in candidates for media in candidate.get("media_candidates", [])
        if media.get("rights_status") == "unknown" or media.get("development_only") is True
    ]
    drift = [
        {"candidate_id": candidate["id"], **finding}
        for candidate in candidates for finding in candidate.get("contract_drift", [])
    ]
    bundle_hash = canonical_sha256({"input_hashes": input_hashes, "candidates": [item["input_hash"] for item in candidates]})
    generated_values = [candidate.get("observed_at") for candidate in candidates if candidate.get("observed_at")]
    generated_at = max(generated_values) if generated_values else "1970-01-01T00:00:00Z"
    return {
        "schema_version": "1.0.0",
        "id": f"review-bundle:{uuid.uuid5(uuid.NAMESPACE_URL, bundle_hash)}",
        "entity_type": "review_bundle",
        "candidate_records": candidates,
        "field_provenance": [entry for candidate in candidates for entry in candidate.get("field_provenance", [])],
        "conflicts": [{"candidate_id": candidate["id"], **conflict} for candidate in candidates for conflict in candidate.get("conflicts", [])],
        "identity_proposals": proposals,
        "rights_warnings": rights_warnings,
        "adapter_drift": drift,
        "required_reviewer_roles": sorted({"identity_reviewer", "discipline_reviewer", *( ["rights_reviewer"] if rights_warnings else [] )}),
        "input_files": input_files,
        "exact_input_hashes": input_hashes,
        "generated_at": generated_at,
        "bundle_hash": bundle_hash,
        "candidate_data_publicly_exposed": False,
    }
