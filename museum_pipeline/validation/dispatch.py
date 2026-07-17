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


ART_CONTEXT_ENTITY_TYPES = {
    "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
    "exhibition_event", "material", "technique", "subject", "time_period", "person",
}


ART_MEDIA_SCHEMA_BY_ENTITY_TYPE = {
    "media_acquisition_request": ("schemas/art/media/acquisition-request.schema.json", "media-request:"),
    "media_acquisition_event": ("schemas/art/media/acquisition-event.schema.json", "media-event:"),
    "media_byte_record": ("schemas/art/media/byte-record.schema.json", "media-byte:"),
    "media_automated_review": ("schemas/art/media/automated-review.schema.json", "media-review:"),
    "media_identity_rights_cross_check": (
        "schemas/art/media/identity-rights-cross-check.schema.json",
        "media-cross-check:",
    ),
    "media_quality_assessment": ("schemas/art/media/quality-assessment.schema.json", "media-quality:"),
    "media_derivative_record": ("schemas/art/media/derivative-record.schema.json", "media-derivative:"),
    "media_source_ledger": ("schemas/art/media/media-source-ledger.schema.json", "media-ledger:"),
    "media_bundle_manifest": ("schemas/art/media/media-bundle-manifest.schema.json", "media-bundle:"),
    "media_alternative_source_search": (
        "schemas/art/media/alternative-source-search.schema.json",
        "alternative-search:",
    ),
    "media_withdrawal_mapping": ("schemas/art/media/withdrawal-mapping.schema.json", "withdrawal-map:"),
    "media_retry_record": ("schemas/art/media/media-retry.schema.json", "media-retry:"),
}


PIPELINE_SCHEMA_BY_ENTITY_TYPE = {
    "claim": "schemas/common/claim.schema.json",
    "evidence": "schemas/common/evidence.schema.json",
    "source": "schemas/common/source.schema.json",
    "media_asset": "schemas/common/media-asset.schema.json",
    "dataset_release": "schemas/common/dataset-release.schema.json",
    "art_gallery_interaction_index": "schemas/art/release/art-gallery-interaction-index.schema.json",
    "art_path_result": "schemas/art/release/path-result.schema.json",
    **{
        entity_type: "schemas/art/release/art-pathways-artifact.schema.json"
        for entity_type in (
            "art_path_algorithm_contract", "art_path_graph_input", "art_path_index",
            "art_path_explanation_collection", "art_path_ab_review_summary",
            "art_path_performance_contract", "art_path_route_config",
        )
    },
    "place_name_collection": "schemas/art/map/place-name.schema.json",
    "place_identity_collection": "schemas/art/map/place-identity.schema.json",
    "geospatial_claim_collection": "schemas/art/map/geospatial-claim.schema.json",
    "artist_place_episode_collection": "schemas/art/map/artist-place-episode.schema.json",
    "artwork_place_claim_collection": "schemas/art/map/artwork-place-claim.schema.json",
    "holding_location_collection": "schemas/art/map/holding-location.schema.json",
    "map_layer_config": "schemas/art/map/map-layer-config.schema.json",
    "map_style_contract": "schemas/art/map/map-style-contract.schema.json",
    "map_release_index": "schemas/art/map/map-release-index.schema.json",
    "map_timeline_index": "schemas/art/map/map-release-index.schema.json",
    "map_filter_index": "schemas/art/map/map-release-index.schema.json",
    "map_view_state_contract": "schemas/art/map/map-view-state.schema.json",
    "map_basemap_manifest": "schemas/art/map/map-basemap-manifest.schema.json",
    "map_source_attribution_collection": "schemas/art/map/map-source-attribution.schema.json",
    "place_research_disposition_collection": "schemas/art/map/place-research-disposition.schema.json",
    "map_decision_snapshot": "schemas/art/map/map-decision-snapshot.schema.json",
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
    "review_signoff": "schemas/art/batch/review-signoff.schema.json",
    "approved_identity_basis": "schemas/art/batch/approved-identity-basis.schema.json",
    "snapshot_receipt_ledger": "schemas/art/batch/snapshot-receipt-ledger.schema.json",
    "artwork_selection_basis": "schemas/art/batch/artwork-selection-basis.schema.json",
    "manual_evidence_capture": "schemas/art/batch/manual-evidence-capture.schema.json",
    "relationship_research_disposition": "schemas/art/batch/relationship-research-disposition.schema.json",
    "media_eligibility_assessment": "schemas/art/batch/media-eligibility-assessment.schema.json",
    "formal_art_batch_manifest": "schemas/art/batch/formal-art-batch-manifest.schema.json",
    "reviewed_package_manifest": "schemas/art/batch/reviewed-package-manifest.schema.json",
    "graph_input": "schemas/art/batch/graph-input.schema.json",
    "replacement_review_request": "schemas/art/batch/replacement-review-request.schema.json",
    "public_leakage_label_set": "schemas/art/batch/public-leakage-label-set.schema.json",
    "artist": "schemas/art/artist.schema.json",
    "artwork": "schemas/art/artwork.schema.json",
    **{
        entity_type: "schemas/art/context/art-context.schema.json"
        for entity_type in (
            "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
            "exhibition_event", "material", "technique", "subject", "time_period", "person",
        )
    },
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
    entity_type = str(record.get("entity_type"))
    media_schema = ART_MEDIA_SCHEMA_BY_ENTITY_TYPE.get(entity_type)
    if media_schema is not None:
        schema_path, id_prefix = media_schema
        record_id = str(record.get("id", ""))
        if record.get("branch_id") != "art" or not record_id.startswith(id_prefix):
            return None
        return schema_path
    if entity_type in ART_CONTEXT_ENTITY_TYPES:
        if record.get("branch_id") == "art":
            return "schemas/art/context/art-context.schema.json"
        return "schemas/common/entity.schema.json"
    if record.get("entity_type") == "relationship":
        record_id = str(record.get("id", ""))
        branch = record.get("branch_id")
        if record_id.startswith("art-rel:") or branch == "art":
            return "schemas/art/artist-relationship.schema.json"
        if record_id.startswith("bio-rel:") or branch == "biology":
            return "schemas/biology/ecosystem-interaction.schema.json"
        return "schemas/common/relationship.schema.json"
    return PIPELINE_SCHEMA_BY_ENTITY_TYPE.get(entity_type)


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
    elif entity_type == "media_eligibility_assessment":
        issues.extend(_media_assessment_semantic_issues(record))
    if str(entity_type) in {
        "artist_candidate_preflight", "artwork_rights_preflight", "relationship_lead",
        "selection_scenario", "selection_decision", "selection_decision_application", "selection_review_bundle",
    }:
        from museum_pipeline.curation.validation import curation_semantic_issues

        issues.extend(ValidationIssue(code, message, location) for code, message, location in curation_semantic_issues(record))
    return issues


def _media_assessment_semantic_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    source_record_id = str(record.get("source_id", ""))
    source_key = source_record_id.removeprefix("source:")
    bindings = [item for item in record.get("source_license_bindings", []) if isinstance(item, dict)]
    try:
        media_rules = [rule for rule in source_license_rules(source_key) if rule.get("content_class") == "media"]
    except PipelineError:
        media_rules = []
    if len(media_rules) != 1:
        issues.append(ValidationIssue("media_assessment_canonical_media_rule_missing", "Source must have exactly one canonical media rule", "$.source_license_bindings"))
    if len(bindings) != 1:
        issues.append(ValidationIssue("media_assessment_source_binding_count", "Media assessment requires exactly one canonical media binding", "$.source_license_bindings"))
    elif media_rules:
        binding = bindings[0]
        rule = media_rules[0]
        expected_fields = {
            "met_open_access": ["isPublicDomain", "primaryImage"],
            "aic_api": ["is_public_domain", "image_id"],
        }.get(source_key)
        if binding.get("source_id") != source_record_id:
            issues.append(ValidationIssue("media_assessment_binding_source_mismatch", "Media binding source differs from assessment source", "$.source_license_bindings[0].source_id"))
        if binding.get("rule_id") != rule.get("rule_id") or binding.get("content_class") != "media":
            issues.append(ValidationIssue("media_assessment_source_rule_mismatch", "Media binding must use the canonical source media rule", "$.source_license_bindings[0].rule_id"))
        if binding.get("scope_locator") != rule.get("applies_to") or (expected_fields is not None and binding.get("scope_fields") != expected_fields):
            issues.append(ValidationIssue("media_assessment_source_scope_mismatch", "Media binding scope must match the canonical object-media decision contract", "$.source_license_bindings[0].scope_locator"))
        if binding.get("permission_resolution") != "object_level":
            issues.append(ValidationIssue("media_assessment_permission_resolution_invalid", "Mixed source media rules require object_level resolution", "$.source_license_bindings[0].permission_resolution"))

    outcome = record.get("outcome")
    future_public = record.get("future_public_media_eligible") is True
    open_candidate = future_public or outcome in {"external_iiif_candidate", "self_hosted_open_media_eligible"}
    rights_status = record.get("media_rights_status")
    media_license = record.get("media_license")
    permissions = record.get("permissions") if isinstance(record.get("permissions"), dict) else {}
    withdrawal = record.get("withdrawal_or_revocation") if isinstance(record.get("withdrawal_or_revocation"), dict) else {}
    open_statuses = {"public_domain", "cc0", "cc_by", "cc_by_sa", "licensed"}
    if open_candidate:
        if rights_status not in open_statuses:
            issues.append(ValidationIssue("media_assessment_open_status_invalid", "Future-public media requires a coherent open or approved licensed status", "$.media_rights_status"))
        if not isinstance(media_license, dict):
            issues.append(ValidationIssue("media_assessment_license_missing", "Future-public media requires a resolved object media license", "$.media_license"))
        if permissions.get("redistribution") != "allowed":
            issues.append(ValidationIssue("media_assessment_redistribution_blocked", "Future-public media must allow redistribution", "$.permissions.redistribution"))
        if record.get("permission_status") not in {"approved", "not_applicable"}:
            issues.append(ValidationIssue("media_assessment_permission_status_invalid", "Future-public media cannot have pending, denied, revoked, or expired permission", "$.permission_status"))
        if withdrawal.get("status") != "active":
            issues.append(ValidationIssue("media_assessment_withdrawal_inactive", "Future-public media requires an active non-revoked decision", "$.withdrawal_or_revocation.status"))
        if record.get("risk") not in {"low", "medium"}:
            issues.append(ValidationIssue("media_assessment_risk_unbounded", "Future-public media risk must remain low or medium", "$.risk"))
        if not record.get("rights_evidence"):
            issues.append(ValidationIssue("media_assessment_rights_evidence_missing", "Future-public media requires object-level rights evidence", "$.rights_evidence"))
        if record.get("block_reasons"):
            issues.append(ValidationIssue("media_assessment_block_reason_conflict", "Future-public media cannot retain a blocking reason", "$.block_reasons"))

    if isinstance(media_license, dict):
        if not _media_license_matches_status(str(rights_status), media_license):
            issues.append(ValidationIssue("media_assessment_license_status_mismatch", "Resolved media license does not match media_rights_status", "$.media_license"))
        permission_pairs = {
            "redistribution": ("redistribution_allowed", "allowed", "prohibited"),
            "modification": ("modification_allowed", "allowed", "prohibited"),
            "commercial_use": ("commercial_use_allowed", "allowed", "prohibited"),
            "share_alike": ("share_alike", "required", "not_required"),
        }
        for permission_name, (license_name, true_value, false_value) in permission_pairs.items():
            expected = true_value if media_license.get(license_name) is True else false_value
            if permissions.get(permission_name) != expected:
                issues.append(ValidationIssue("media_assessment_license_permission_mismatch", f"permissions.{permission_name} disagrees with media_license.{license_name}", f"$.permissions.{permission_name}"))
        if media_license.get("attribution_required") is True and not str(record.get("attribution", "")).strip():
            issues.append(ValidationIssue("media_assessment_attribution_missing", "Resolved media license requires non-empty attribution", "$.attribution"))
    elif rights_status in open_statuses:
        issues.append(ValidationIssue("media_assessment_license_missing", "Open media status requires a resolved media license", "$.media_license"))

    if rights_status == "licensed":
        if not isinstance(record.get("license_scope"), dict) or record.get("permission_status") != "approved":
            issues.append(ValidationIssue("media_assessment_license_scope_invalid", "Licensed media requires an approved explicit license scope", "$.license_scope"))
    elif rights_status in {"public_domain", "cc0", "cc_by", "cc_by_sa"} and record.get("license_scope") is not None:
        issues.append(ValidationIssue("media_assessment_license_scope_unexpected", "Canonical open licenses do not use a separate permission scope", "$.license_scope"))
    if rights_status == "unknown" and media_license is not None:
        issues.append(ValidationIssue("media_assessment_unknown_rights_escalation", "Unknown rights cannot carry a resolved media license", "$.media_license"))
    if record.get("metadata_inherited_as_media_rights") is True:
        issues.append(ValidationIssue("media_assessment_metadata_inheritance_forbidden", "Metadata rights cannot be inherited as media rights", "$.metadata_inherited_as_media_rights"))
    if record.get("bytes_downloaded") is not False or record.get("media_bytes_present") is not False or (record.get("technical_delivery") or {}).get("cache_bytes") is not False:
        issues.append(ValidationIssue("media_assessment_bytes_forbidden", "MUSEUM-03B assessments cannot download, cache, or include media bytes", "$.technical_delivery"))
    return issues


def _media_license_matches_status(status: str, descriptor: dict[str, Any]) -> bool:
    identifier = descriptor.get("identifier")
    version = descriptor.get("version")
    url = descriptor.get("url")
    if status == "cc0":
        return (identifier, version, url) == (
            "CC0-1.0",
            "1.0",
            "https://creativecommons.org/publicdomain/zero/1.0/",
        )
    if status == "public_domain":
        return (identifier, version, url) == (
            "PDM-1.0",
            "1.0",
            "https://creativecommons.org/publicdomain/mark/1.0/",
        )
    allowed_versions = {"1.0", "2.0", "2.5", "3.0", "4.0"}
    if status == "cc_by" and version in allowed_versions:
        return identifier == f"CC-BY-{version}" and url == f"https://creativecommons.org/licenses/by/{version}/"
    if status == "cc_by_sa" and version in allowed_versions:
        return identifier == f"CC-BY-SA-{version}" and url == f"https://creativecommons.org/licenses/by-sa/{version}/"
    return status == "licensed"


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
