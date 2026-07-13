from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.curation.bundle import validate_selection_bundle
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.validation.dispatch import validate_record


TOOL_NAME = "museum_pipeline.curation.apply_selection_decision"
TOOL_VERSION = "1.0.0"
REQUIRED_PUBLIC_SCOPE = {"artist_metadata": True, "artwork_metadata": True, "media": "mixed"}


def apply_selection_decision(
    *,
    bundle_root: Path,
    decision_path: Path,
    output_path: Path,
    resulting_batch_id: str,
    applied_at: str | None = None,
    code_commit: str | None = None,
) -> tuple[dict[str, Any], bool]:
    bundle_issues = validate_selection_bundle(bundle_root)
    if bundle_issues:
        raise PipelineError("selection_bundle_invalid", f"Selection bundle has {len(bundle_issues)} validation issue(s)")

    manifest = _load_json(bundle_root / "bundle-manifest.json")
    recommended = _load_json(bundle_root / "recommended-slate.json")
    template = _load_json(bundle_root / "selection-decision-template.json")
    candidates = _load_json(bundle_root / "candidate-pool.json")
    decision = _load_json(decision_path)
    schema_issues = validate_record(decision)
    if schema_issues:
        raise PipelineError("selection_decision_invalid", f"Submitted decision has {len(schema_issues)} validation issue(s)")
    _validate_decision_closure(decision, template=template, manifest=manifest, recommended=recommended)

    selected_ids = list(recommended["candidate_ids"])
    candidates_by_id = {item["id"]: item for item in candidates}
    candidate_hashes = [
        {"candidate_id": candidate_id, "canonical_hash": canonical_sha256(candidates_by_id[candidate_id])}
        for candidate_id in selected_ids
    ]
    resolved_artists = [
        {"candidate_id": candidate_id, "labels": _preferred_labels(candidates_by_id[candidate_id])}
        for candidate_id in selected_ids
    ]
    decision_hash = canonical_sha256(decision)
    basis = {
        "submitted_decision_id": decision["id"],
        "submitted_decision_hash": decision_hash,
        "input_bundle_id": manifest["id"],
        "input_bundle_hash": manifest["bundle_hash"],
        "recommended_slate_id": recommended["id"],
        "recommended_slate_hash": sha256_file(bundle_root / "recommended-slate.json"),
        "selected_candidate_ids": selected_ids,
        "candidate_input_hashes": candidate_hashes,
        "resulting_batch_id": resulting_batch_id,
        "authority": decision["decision_authority"],
        "media_strategy": decision["media_strategy"],
        "public_scope": decision["public_scope"],
    }
    basis_hash = canonical_sha256(basis)
    if output_path.exists():
        existing = _load_json(output_path)
        if existing.get("application_basis_hash") != basis_hash:
            raise PipelineError("selection_decision_application_conflict", "An application receipt already exists for different inputs")
        existing_issues = validate_record(existing)
        if existing_issues:
            raise PipelineError("selection_decision_application_invalid", "Existing application receipt is invalid")
        return existing, True

    timestamp = applied_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    commit = code_commit or _git_commit()
    receipt = {
        "schema_version": "1.0.0",
        "id": f"selection-decision-application:{uuid.uuid5(uuid.NAMESPACE_URL, basis_hash)}",
        "entity_type": "selection_decision_application",
        "phase_id": "MUSEUM-03B",
        "application_status": "applied",
        **{key: basis[key] for key in (
            "submitted_decision_id", "submitted_decision_hash", "input_bundle_id", "input_bundle_hash",
            "recommended_slate_id", "recommended_slate_hash", "selected_candidate_ids", "candidate_input_hashes",
        )},
        "resolved_artists": resolved_artists,
        "application_timestamp": timestamp,
        "applying_tool": {"name": TOOL_NAME, "version": TOOL_VERSION, "code_commit": commit},
        "validation_result": "pass",
        "stale_check": {"status": "fresh", "bundle_revalidated": True, "decision_hash_verified": True},
        "replacement_count": 0,
        "media_strategy": "mixed",
        "media_execution_default": "metadata_first",
        "public_scope": REQUIRED_PUBLIC_SCOPE,
        "authority": "Mays",
        "resulting_batch_id": resulting_batch_id,
        "application_basis_hash": basis_hash,
        "audit_log": [
            {"event": event, "status": "pass", "recorded_at": timestamp}
            for event in ("bundle_validated", "decision_validated", "selection_locked", "decision_applied")
        ],
    }
    issues = validate_record(receipt)
    if issues:
        raise PipelineError("selection_decision_application_invalid", f"Generated application receipt has {len(issues)} validation issue(s)")
    write_canonical_json(output_path, receipt)
    return receipt, False


def validate_committed_selection_application(decision_path: Path, receipt_path: Path) -> list[str]:
    try:
        decision = _load_json(decision_path)
        receipt = _load_json(receipt_path)
    except PipelineError as error:
        return [error.code]
    issues = [f"decision:{item.code}" for item in validate_record(decision)]
    issues.extend(f"application:{item.code}" for item in validate_record(receipt))
    expected_pairs = {
        "application_decision_id_mismatch": receipt.get("submitted_decision_id") == decision.get("id"),
        "application_decision_hash_mismatch": receipt.get("submitted_decision_hash") == canonical_sha256(decision),
        "application_bundle_hash_mismatch": receipt.get("input_bundle_hash") == decision.get("input_bundle_hash"),
        "application_scenario_mismatch": receipt.get("recommended_slate_id") == decision.get("selected_scenario_id"),
        "application_selected_ids_mismatch": receipt.get("selected_candidate_ids") == decision.get("selected_candidate_ids"),
        "application_authority_mismatch": receipt.get("authority") == decision.get("decision_authority"),
        "application_media_strategy_mismatch": receipt.get("media_strategy") == decision.get("media_strategy"),
        "application_public_scope_mismatch": receipt.get("public_scope") == decision.get("public_scope"),
    }
    issues.extend(code for code, passed in expected_pairs.items() if not passed)
    basis = {
        key: receipt.get(key)
        for key in (
            "submitted_decision_id", "submitted_decision_hash", "input_bundle_id", "input_bundle_hash",
            "recommended_slate_id", "recommended_slate_hash", "selected_candidate_ids", "candidate_input_hashes",
            "resulting_batch_id", "authority", "media_strategy", "public_scope",
        )
    }
    if receipt.get("application_basis_hash") != canonical_sha256(basis):
        issues.append("selection_application_basis_hash_mismatch")
    return sorted(set(issues))


def _validate_decision_closure(
    decision: dict[str, Any], *, template: dict[str, Any], manifest: dict[str, Any], recommended: dict[str, Any]
) -> None:
    checks = {
        "selection_decision_id_mismatch": decision.get("id") == template.get("id"),
        "selection_decision_not_submitted": decision.get("status") == "submitted",
        "selection_decision_type_mismatch": decision.get("decision_type") == "approve_recommended_slate",
        "selection_decision_authority_mismatch": decision.get("decision_authority") == "Mays",
        "selection_decision_scenario_mismatch": decision.get("selected_scenario_id") == recommended.get("id"),
        "selection_decision_candidates_mismatch": decision.get("selected_candidate_ids") == recommended.get("candidate_ids"),
        "selection_decision_replacement_forbidden": decision.get("replacements") == [],
        "selection_decision_media_strategy_mismatch": decision.get("media_strategy") == "mixed",
        "selection_decision_public_scope_mismatch": decision.get("public_scope") == REQUIRED_PUBLIC_SCOPE,
        "selection_decision_bundle_hash_mismatch": decision.get("input_bundle_hash") == manifest.get("bundle_hash"),
    }
    for code, passed in checks.items():
        if not passed:
            raise PipelineError(code, "Submitted decision does not match the validated Recommended Slate approval")


def _preferred_labels(candidate: dict[str, Any]) -> dict[str, str]:
    labels = {item["language"]: item["text"] for item in candidate.get("preferred_labels", [])}
    if "en" not in labels or not any(language.startswith("zh") for language in labels):
        raise PipelineError("selection_candidate_labels_incomplete", "Approved candidate requires English and Chinese labels")
    return labels


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PipelineError("selection_application_input_invalid", "Selection application input is missing or invalid") from error


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True, encoding="utf-8"
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) != 40:
        raise PipelineError("selection_application_commit_unavailable", "Current Git commit could not be resolved")
    return value
