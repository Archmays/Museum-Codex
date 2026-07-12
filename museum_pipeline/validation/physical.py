from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from museum_pipeline.config import ROOT, license_rules_snapshot_hash, source_registry_snapshot_hash
from museum_pipeline.adapters import get_adapter
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.paths import resolve_within
from museum_pipeline.snapshots import validate_snapshot
from museum_pipeline.validation.dispatch import (
    PIPELINE_SCHEMA_BY_ENTITY_TYPE,
    ValidationIssue,
    load_schema_environment,
    validate_record,
)


def validate_review_bundle_file(path: Path) -> list[ValidationIssue]:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    environment = load_schema_environment()
    issues = validate_record(bundle, environment=environment)
    root = path.parent
    declared_bytes = {item.get("path"): item.get("bytes") for item in bundle.get("input_files", [])}
    input_candidates: list[dict[str, Any]] = []
    input_proposals: list[dict[str, Any]] = []
    for relative, expected_hash in bundle.get("exact_input_hashes", {}).items():
        try:
            target = resolve_within(root, relative, must_exist=True)
        except Exception:
            issues.append(ValidationIssue("review_input_missing", "Review input path is missing or unsafe", f"$.exact_input_hashes.{relative}"))
            continue
        if sha256_file(target) != expected_hash:
            issues.append(ValidationIssue("review_input_hash_mismatch", "Review input changed after bundle creation", f"$.exact_input_hashes.{relative}"))
        if target.stat().st_size != declared_bytes.get(relative):
            issues.append(ValidationIssue("review_input_bytes_mismatch", "Review input byte count changed after bundle creation", f"$.input_files.{relative}"))
        try:
            document = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = document if isinstance(document, list) else [document]
        input_candidates.extend(item for item in records if isinstance(item, dict) and item.get("entity_type") == "normalized_candidate")
        input_proposals.extend(item for item in records if isinstance(item, dict) and item.get("entity_type") == "identity_proposal")
    for candidate in bundle.get("candidate_records", []):
        issues.extend(validate_record(candidate, environment=environment))
    for proposal in bundle.get("identity_proposals", []):
        issues.extend(validate_record(proposal, environment=environment))
    if sorted(map(canonical_sha256, input_candidates)) != sorted(map(canonical_sha256, bundle.get("candidate_records", []))):
        issues.append(ValidationIssue("review_candidate_closure_mismatch", "Embedded candidates differ from the exact input records", "$.candidate_records"))
    if sorted(map(canonical_sha256, input_proposals)) != sorted(map(canonical_sha256, bundle.get("identity_proposals", []))):
        issues.append(ValidationIssue("review_proposal_closure_mismatch", "Embedded proposals differ from the exact input records", "$.identity_proposals"))
    return sorted(issues, key=lambda item: (item.code, item.location))


def validate_run_directory(run_dir: Path) -> list[ValidationIssue]:
    manifest_path = run_dir / "pipeline-run.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [ValidationIssue("run_manifest_invalid", "pipeline-run.json is missing or invalid")]
    environment = load_schema_environment()
    issues = validate_record(manifest, environment=environment)
    if manifest.get("source_registry_snapshot_hash") != source_registry_snapshot_hash():
        issues.append(ValidationIssue("source_registry_snapshot_hash_mismatch", "Run registry hash is not current", "$.source_registry_snapshot_hash"))
    if manifest.get("license_rules_snapshot_hash") != license_rules_snapshot_hash():
        issues.append(ValidationIssue("license_rules_snapshot_hash_mismatch", "Run license-rule hash is not current", "$.license_rules_snapshot_hash"))
    if manifest.get("status") == "completed" and (manifest.get("finished_at") is None or manifest.get("errors")):
        issues.append(ValidationIssue("run_completion_inconsistent", "Completed runs require finished_at and no errors", "$.status"))
    for index, adapter_run in enumerate(manifest.get("adapter_runs", [])):
        try:
            adapter = get_adapter(str(adapter_run.get("source_id")))
        except PipelineError:
            issues.append(ValidationIssue("adapter_unknown", "Run references an unknown adapter", f"$.adapter_runs[{index}].source_id"))
            continue
        if adapter_run.get("adapter_version") != adapter.adapter_version or adapter_run.get("contract_version") != adapter.contract_version:
            issues.append(ValidationIssue("unknown_adapter_version", "Run adapter version is not current", f"$.adapter_runs[{index}].adapter_version"))
        if manifest.get("status") == "completed" and adapter_run.get("status") != "pass":
            issues.append(ValidationIssue("run_adapter_not_passed", "A completed run requires every adapter contract to pass", f"$.adapter_runs[{index}].status"))
    declared_outputs: set[str] = set()
    local_input_files: set[str] = set()
    input_snapshot_ids: set[str] = set()
    output_records: list[dict[str, Any]] = []
    for collection_name in ("inputs", "outputs"):
        governed_root = ROOT if collection_name == "inputs" else run_dir
        for index, artifact in enumerate(manifest.get(collection_name, [])):
            relative = artifact.get("path")
            try:
                target = resolve_within(governed_root, str(relative), must_exist=True)
            except Exception:
                issues.append(ValidationIssue("run_artifact_missing", "Run artifact is missing or unsafe", f"$.{collection_name}[{index}].path"))
                continue
            if target.stat().st_size != artifact.get("bytes"):
                issues.append(ValidationIssue("run_artifact_bytes_mismatch", "Run artifact byte count changed", f"$.{collection_name}[{index}].bytes"))
            if sha256_file(target) != artifact.get("sha256"):
                issues.append(ValidationIssue("run_artifact_hash_mismatch", "Run artifact hash changed", f"$.{collection_name}[{index}].sha256"))
            if target.suffix == ".json":
                try:
                    document = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    issues.append(ValidationIssue("run_artifact_json_invalid", "Declared JSON artifact is invalid", f"$.{collection_name}[{index}].path"))
                    document = None
                records = document if isinstance(document, list) else [document]
                typed_records = [item for item in records if isinstance(item, dict) and item.get("entity_type") in PIPELINE_SCHEMA_BY_ENTITY_TYPE]
                all_typed_records = _collect_typed_records(document)
                for item in all_typed_records:
                    issues.extend(validate_record(item, environment=environment))
                if collection_name == "outputs" and any(item.get("entity_type") == "review_bundle" for item in typed_records):
                    issues.extend(validate_review_bundle_file(target))
                top_ids = {
                    str(item.get("id") or item.get("snapshot_id"))
                    for item in typed_records if item.get("id") or item.get("snapshot_id")
                }
                nested_ids = {
                    str(item.get("id") or item.get("snapshot_id"))
                    for item in all_typed_records if item.get("id") or item.get("snapshot_id")
                }
                declared_ids = set(artifact.get("record_ids", []))
                expected_ids = top_ids or nested_ids
                if expected_ids != declared_ids:
                    issues.append(ValidationIssue("run_record_ids_mismatch", "Artifact record IDs do not match its canonical top-level records", f"$.{collection_name}[{index}].record_ids"))
                if collection_name == "inputs" and typed_records and typed_records[0].get("entity_type") == "raw_snapshot_manifest":
                    input_snapshot_ids.update(top_ids)
                    issues.extend(
                        ValidationIssue(code, "Raw snapshot input failed physical validation", f"$.inputs[{index}]")
                        for code in validate_snapshot(target.parent)
                    )
                if collection_name == "outputs":
                    output_records.extend(all_typed_records)
            if collection_name == "outputs":
                declared_outputs.add(str(relative))
            elif collection_name == "inputs":
                try:
                    local_input_files.add(target.relative_to(run_dir.resolve(strict=True)).as_posix())
                except ValueError:
                    pass
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "pipeline-run.json" and path.relative_to(run_dir).as_posix() not in local_input_files
    }
    if actual != declared_outputs:
        issues.append(ValidationIssue("run_output_set_mismatch", f"Run outputs differ; missing={sorted(declared_outputs - actual)}, extra={sorted(actual - declared_outputs)}", "$.outputs"))
    declared_adapter_snapshots = {
        snapshot_id
        for adapter_run in manifest.get("adapter_runs", [])
        for snapshot_id in adapter_run.get("snapshot_ids", [])
    }
    if declared_adapter_snapshots != input_snapshot_ids:
        issues.append(ValidationIssue("run_snapshot_closure_mismatch", "Adapter snapshot IDs do not exactly match physical raw-manifest inputs", "$.adapter_runs"))
    for record in output_records:
        if record.get("entity_type") != "normalized_candidate":
            continue
        candidate_snapshots = {item.get("raw_snapshot_id") for item in record.get("source_records", [])}
        if not candidate_snapshots <= input_snapshot_ids:
            issues.append(ValidationIssue("candidate_snapshot_input_missing", "Candidate references a snapshot outside the run input closure", "$.outputs"))
    return sorted(issues, key=lambda item: (item.code, item.location))


def _collect_typed_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("entity_type") in PIPELINE_SCHEMA_BY_ENTITY_TYPE:
            records.append(value)
        for child in value.values():
            records.extend(_collect_typed_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_collect_typed_records(child))
    return records
