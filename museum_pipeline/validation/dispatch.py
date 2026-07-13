from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from museum_pipeline.config import ROOT, source_configuration, source_license_rules
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256


PIPELINE_SCHEMA_BY_ENTITY_TYPE = {
    "adapter_contract": "schemas/pipeline/adapter-contract.schema.json",
    "acquisition_request": "schemas/pipeline/acquisition-request.schema.json",
    "raw_snapshot_manifest": "schemas/pipeline/raw-snapshot-manifest.schema.json",
    "field_provenance": "schemas/pipeline/field-provenance.schema.json",
    "normalized_candidate": "schemas/pipeline/normalized-candidate.schema.json",
    "identity_proposal": "schemas/pipeline/identity-proposal.schema.json",
    "merge_record": "schemas/pipeline/merge-record.schema.json",
    "review_decision": "schemas/pipeline/review-decision.schema.json",
    "pipeline_run": "schemas/pipeline/pipeline-run.schema.json",
    "review_bundle": "schemas/pipeline/review-bundle.schema.json",
    "artist_candidate_preflight": "schemas/curation/artist-candidate-preflight.schema.json",
    "artwork_rights_preflight": "schemas/curation/artwork-rights-preflight.schema.json",
    "relationship_lead": "schemas/curation/relationship-lead.schema.json",
    "selection_scenario": "schemas/curation/selection-scenario.schema.json",
    "selection_decision": "schemas/curation/selection-decision.schema.json",
    "selection_decision_application": "schemas/curation/selection-decision-application.schema.json",
    "selection_review_bundle": "schemas/curation/selection-review-bundle.schema.json",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    location: str = "$"


@dataclass(frozen=True)
class SchemaEnvironment:
    by_path: dict[str, dict[str, Any]]
    registry: Registry


def load_schema_environment(root: Path = ROOT) -> SchemaEnvironment:
    by_path: dict[str, dict[str, Any]] = {}
    registry: Registry = Registry()
    for path in sorted((root / "schemas").rglob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        relative = path.relative_to(root).as_posix()
        by_path[relative] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return SchemaEnvironment(by_path, registry)


def canonical_schema_path(record: dict[str, Any]) -> str | None:
    return PIPELINE_SCHEMA_BY_ENTITY_TYPE.get(str(record.get("entity_type")))


def validate_record(
    record: dict[str, Any],
    *,
    requested_schema: str | None = None,
    environment: SchemaEnvironment | None = None,
) -> list[ValidationIssue]:
    target = canonical_schema_path(record)
    if target is None:
        return [ValidationIssue("canonical_dispatch_unknown", "No canonical pipeline schema for entity_type")]
    if requested_schema is not None and requested_schema != target:
        return [ValidationIssue("schema_target_mismatch", f"Canonical dispatch requires {target}", "$.target_schema")]
    env = environment or load_schema_environment()
    schema = env.by_path[target]
    validator = Draft202012Validator(schema, registry=env.registry, format_checker=FormatChecker())
    issues = [ValidationIssue("schema", error.message, _json_path(error.absolute_path)) for error in validator.iter_errors(record)]
    issues.extend(_semantic_issues(record))
    return sorted(issues, key=lambda item: (item.location, item.code, item.message))


def _semantic_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    entity_type = record.get("entity_type")
    issues: list[ValidationIssue] = []
    if entity_type == "normalized_candidate":
        expected_hash = canonical_sha256({key: value for key, value in record.items() if key != "input_hash"})
        if record.get("input_hash") != expected_hash:
            issues.append(ValidationIssue("candidate_input_hash_mismatch", "Candidate input hash does not match canonical bytes", "$.input_hash"))
        candidate_id = record.get("id")
        source_records = record.get("source_records", [])
        source_keys = {(item.get("source_id"), item.get("source_object_id"), item.get("raw_snapshot_id")) for item in source_records if isinstance(item, dict)}
        for index, provenance in enumerate(record.get("field_provenance", [])):
            if provenance.get("candidate_id") != candidate_id:
                issues.append(ValidationIssue("provenance_candidate_mismatch", "Field provenance points to a different candidate", f"$.field_provenance[{index}].candidate_id"))
            key = (provenance.get("source_id"), provenance.get("source_object_id"), provenance.get("raw_snapshot_id"))
            if key not in source_keys:
                issues.append(ValidationIssue("provenance_source_record_missing", "Field provenance cannot resolve its source record", f"$.field_provenance[{index}]"))
            issues.extend(_license_binding_issues(provenance, f"$.field_provenance[{index}]"))
            try:
                expected_tier = source_configuration(str(provenance.get("source_id")))["tier"]
            except PipelineError:
                expected_tier = None
            if expected_tier is None or provenance.get("source_tier") != expected_tier:
                issues.append(ValidationIssue("source_tier_mismatch", "Field provenance tier does not match the canonical source registry", f"$.field_provenance[{index}].source_tier"))
            if provenance.get("review_state") != "candidate":
                issues.append(ValidationIssue("field_mapping_promoted", "Normalized field provenance must remain candidate in MUSEUM-02", f"$.field_provenance[{index}].review_state"))
        provenance_pointers = [str(item.get("field_pointer", "")) for item in record.get("field_provenance", [])]
        for field_name, value in record.get("fields", {}).items():
            if value is None or value == "" or value == [] or value == {}:
                continue
            escaped = str(field_name).replace("~", "~0").replace("/", "~1")
            prefix = f"/fields/{escaped}"
            if not any(pointer == prefix or pointer.startswith(prefix + "/") for pointer in provenance_pointers):
                issues.append(ValidationIssue("field_provenance_missing", "A non-empty normalized field has no field-level provenance", f"$.fields.{field_name}"))
        for index, claim in enumerate(record.get("candidate_claims", [])):
            if claim.get("subject_candidate_id") != candidate_id:
                issues.append(ValidationIssue("candidate_claim_subject_mismatch", "Candidate claim subject differs from candidate", f"$.candidate_claims[{index}]"))
            evidence = claim.get("evidence", {})
            key = (evidence.get("source_id"), evidence.get("source_object_id"), evidence.get("raw_snapshot_id"))
            if key not in source_keys:
                issues.append(ValidationIssue("candidate_claim_evidence_missing", "Candidate claim evidence cannot resolve its raw source", f"$.candidate_claims[{index}].evidence"))
            if claim.get("source_tier") == 3 and claim.get("status") != "candidate":
                issues.append(ValidationIssue("tier3_claim_promoted", "Tier 3 claim left candidate state", f"$.candidate_claims[{index}].status"))
            if claim.get("inferred") is True and not claim.get("algorithm_or_rule_version"):
                issues.append(ValidationIssue("inferred_rule_version_missing", "Inferred claim requires an algorithm or rule version", f"$.candidate_claims[{index}].algorithm_or_rule_version"))
            issues.extend(_license_binding_issues({
                **claim,
                "source_id": evidence.get("source_id"),
                "raw_locator": evidence.get("raw_locator"),
            }, f"$.candidate_claims[{index}]"))
        for index, media in enumerate(record.get("media_candidates", [])):
            key = (media.get("source_id"), media.get("source_object_id"))
            if not any(source[0:2] == key for source in source_keys):
                issues.append(ValidationIssue("media_source_record_missing", "Media candidate cannot resolve its source record", f"$.media_candidates[{index}]"))
            issues.extend(_license_binding_issues(media, f"$.media_candidates[{index}]"))
            if media.get("bytes_downloaded") is not False or media.get("development_only") is not True or media.get("rights_status") != "unknown":
                issues.append(ValidationIssue("media_candidate_rights_escalation", "Media candidate exceeded the MUSEUM-02 boundary", f"$.media_candidates[{index}]"))
            hints = media.get("rights_hints", {})
            if media.get("source_id") == "met_open_access" and hints.get("primary_image_is_rights_proof") is True:
                issues.append(ValidationIssue("met_image_not_rights_proof", "A Met image URL cannot prove media permission", f"$.media_candidates[{index}].rights_hints"))
            if media.get("source_id") == "aic_api" and hints.get("iiif_access_is_license") is True:
                issues.append(ValidationIssue("iiif_not_rights_proof", "AIC IIIF reachability cannot prove media permission", f"$.media_candidates[{index}].rights_hints"))
        if record.get("contract_drift"):
            issues.append(ValidationIssue("candidate_contract_drift_unresolved", "A candidate with adapter contract drift cannot enter a run", "$.contract_drift"))
    elif entity_type == "identity_proposal":
        strong = any(signal.get("strength") == "strong" for signal in record.get("signals", []))
        name_only = bool(record.get("signals")) and all(signal.get("signal_type") == "name_or_alias" for signal in record.get("signals", []))
        if record.get("proposed_status") == "same" and (not strong or name_only):
            issues.append(ValidationIssue("name_only_merge", "Same proposal requires a non-name strong signal", "$.proposed_status"))
        if record.get("hard_conflicts") and record.get("proposed_status") != "distinct":
            issues.append(ValidationIssue("hard_conflict_ignored", "Hard conflicts require a distinct proposal", "$.proposed_status"))
        expected_hash = canonical_sha256({
            "inputs": record.get("input_record_hashes"),
            "status": record.get("proposed_status"),
            "version": record.get("proposal_version"),
        })
        if record.get("proposal_hash") != expected_hash:
            issues.append(ValidationIssue("proposal_hash_mismatch", "Identity proposal hash does not match its inputs and version", "$.proposal_hash"))
    elif entity_type == "merge_record":
        survivor = record.get("survivor_candidate_id")
        losers = record.get("loser_candidate_ids", [])
        if survivor in losers:
            issues.append(ValidationIssue("merge_survivor_is_loser", "Survivor may not be listed as a loser", "$.loser_candidate_ids"))
        alias_ids = {item.get("alias_id") for item in record.get("alias_mappings", [])}
        if alias_ids != set(losers) or record.get("loser_ids_retained") is not True:
            issues.append(ValidationIssue("merge_loser_deleted", "Every loser ID must remain as an alias mapping", "$.alias_mappings"))
        if record.get("mapping_after_hash") != canonical_sha256(record.get("alias_mappings", [])):
            issues.append(ValidationIssue("merge_mapping_hash_mismatch", "Merge alias mapping hash is not closed", "$.mapping_after_hash"))
    elif entity_type == "review_decision":
        history = record.get("status_history", [])
        if history and history[-1].get("to") != record.get("status"):
            issues.append(ValidationIssue("decision_history_mismatch", "Decision status does not match its latest history event", "$.status_history"))
    elif entity_type == "review_bundle":
        candidates = record.get("candidate_records", [])
        candidate_ids = {item.get("id") for item in candidates}
        expected_provenance = sorted(
            canonical_sha256(item)
            for candidate in candidates for item in candidate.get("field_provenance", [])
        )
        observed_provenance = sorted(canonical_sha256(item) for item in record.get("field_provenance", []))
        if expected_provenance != observed_provenance:
            issues.append(ValidationIssue("review_provenance_closure_mismatch", "Bundle provenance is not the exact candidate provenance union", "$.field_provenance"))
        for index, proposal in enumerate(record.get("identity_proposals", [])):
            if not set(proposal.get("candidate_ids", [])) <= candidate_ids:
                issues.append(ValidationIssue("review_proposal_candidate_missing", "Identity proposal references a candidate outside the bundle", f"$.identity_proposals[{index}]"))
        for collection in ("rights_warnings", "adapter_drift", "conflicts"):
            for index, item in enumerate(record.get(collection, [])):
                if item.get("candidate_id") not in candidate_ids:
                    issues.append(ValidationIssue("review_candidate_reference_missing", "Review finding references a candidate outside the bundle", f"$.{collection}[{index}]"))
        expected_roles = sorted({
            "identity_reviewer", "discipline_reviewer",
            *(["rights_reviewer"] if record.get("rights_warnings") else []),
        })
        if record.get("required_reviewer_roles") != expected_roles:
            issues.append(ValidationIssue("review_roles_mismatch", "Reviewer roles do not match bundle risks", "$.required_reviewer_roles"))
        input_files = record.get("input_files", [])
        expected_input_hashes = {item.get("path"): item.get("sha256") for item in input_files}
        if record.get("exact_input_hashes") != expected_input_hashes:
            issues.append(ValidationIssue("review_input_manifest_mismatch", "Input files and exact input hashes differ", "$.exact_input_hashes"))
        expected_bundle_hash = canonical_sha256({
            "input_hashes": record.get("exact_input_hashes", {}),
            "candidates": [item.get("input_hash") for item in candidates],
        })
        if record.get("bundle_hash") != expected_bundle_hash:
            issues.append(ValidationIssue("review_bundle_hash_mismatch", "Review bundle hash does not match its exact inputs", "$.bundle_hash"))
    if str(entity_type) in {
        "artist_candidate_preflight", "artwork_rights_preflight", "relationship_lead",
        "selection_scenario", "selection_decision", "selection_decision_application", "selection_review_bundle",
    }:
        from museum_pipeline.curation.validation import curation_semantic_issues

        issues.extend(ValidationIssue(code, message, location) for code, message, location in curation_semantic_issues(record))
    return issues


def _json_path(path: Iterable[Any]) -> str:
    result = "$"
    for part in path:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _license_binding_issues(binding: dict[str, Any], location: str) -> list[ValidationIssue]:
    source_id = str(binding.get("source_id", ""))
    rule_id = binding.get("license_rule_id")
    try:
        rules = source_license_rules(source_id)
    except PipelineError:
        return [ValidationIssue("source_rule_missing", "No canonical license rules exist for the bound source", f"{location}.license_rule_id")]
    matches = [rule for rule in rules if rule.get("rule_id") == rule_id]
    if len(matches) != 1:
        return [ValidationIssue("source_rule_missing", "Bound license rule is not in the canonical registry", f"{location}.license_rule_id")]
    rule = matches[0]
    issues: list[ValidationIssue] = []
    if rule.get("content_class") != binding.get("content_class"):
        issues.append(ValidationIssue("license_content_class_mismatch", "License rule content class does not match the bound value", f"{location}.content_class"))
    if source_id == "aic_api" and binding.get("content_class") == "data":
        raw_locator = str(binding.get("raw_locator", binding.get("source_locator", "")))
        expected_policy = "include" if raw_locator == "/data/description" else "exclude"
        if rule.get("scope_match", {}).get("field_policy") != expected_policy:
            issues.append(ValidationIssue("aic_license_rule_mismatch", "AIC field did not bind its exact field-level rule", f"{location}.license_rule_id"))
    return issues
