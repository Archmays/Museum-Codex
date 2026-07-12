from __future__ import annotations

from typing import Any


SCORE_DIMENSIONS = {
    "identity_readiness", "death_evidence_readiness", "source_quality",
    "artwork_record_availability", "object_level_media_rights_readiness",
    "multilingual_identity_readiness", "relationship_evidence_potential",
    "geographic_tradition_contribution", "period_contribution",
    "medium_material_contribution", "public_learning_value",
    "interaction_potential", "adapter_pipeline_readiness",
}

HARD_GATES = {
    "individual_artist", "confirmed_deceased", "identity_resolved",
    "birth_claim_reliable", "death_claim_reliable", "authority_source_present",
    "museum_or_scholarly_source_present", "not_tier3_only",
    "verified_work_or_art_history_record", "object_level_display_path",
    "attribution_uncertainty_expressible", "special_identity_not_coerced",
    "no_ai_fact_source", "public_learning_entry_present",
}

FORBIDDEN_VALUE_FIELDS = {
    "greatness_score", "importance_score", "influence_score", "canonical_rank",
    "popularity_rank", "market_value_score", "computational_similarity",
    "media_license_inherited_from_metadata", "publishable", "approved", "released",
}

CLEAR_PREFLIGHT = {"rights_path_clear_candidate", "external_iiif_candidate"}


def curation_semantic_issues(record: dict[str, Any]) -> list[tuple[str, str, str]]:
    issues: list[tuple[str, str, str]] = []
    entity_type = record.get("entity_type")
    for location, key in _walk_keys(record):
        if key in FORBIDDEN_VALUE_FIELDS:
            issues.append(("art_value_or_release_field_forbidden", "Curation preflight cannot contain ranking, release, or inherited-rights fields", location))

    if entity_type == "artist_candidate_preflight":
        dimensions = [item.get("dimension") for item in record.get("score_dimensions", []) if isinstance(item, dict)]
        if set(dimensions) != SCORE_DIMENSIONS or len(dimensions) != len(set(dimensions)):
            issues.append(("score_dimension_closure", "All readiness dimensions must appear exactly once", "$.score_dimensions"))
        gates = record.get("hard_gate_results", {})
        if set(gates) != HARD_GATES:
            issues.append(("hard_gate_contract_mismatch", "Hard-gate keys must match the MUSEUM-03A contract", "$.hard_gate_results"))
        if record.get("candidate_status") == "qualified":
            if record.get("identity_kind") != "individual":
                issues.append(("candidate_not_individual", "Qualified candidate must be an individual", "$.identity_kind"))
            if record.get("identity_status") != "resolved":
                issues.append(("identity_unresolved", "Qualified candidate identity must be resolved", "$.identity_status"))
            if record.get("deceased_status") != "confirmed_deceased":
                code = "living_candidate" if record.get("deceased_status") == "living" else "death_unknown"
                issues.append((code, "Qualified candidate must be confirmed deceased", "$.deceased_status"))
            if set(gates) == HARD_GATES and not all(gates.values()):
                issues.append(("qualified_hard_gate_failed", "A failed hard gate cannot be offset by readiness scores", "$.hard_gate_results"))
            if not record.get("authority_source_ids") or not record.get("museum_source_ids"):
                issues.append(("tier3_only_candidate", "Qualified candidate requires authority and museum or scholarly coverage", "$.authority_source_ids"))
            if not record.get("source_independence"):
                issues.append(("source_independence_missing", "Qualified candidate requires an independent source path", "$.source_independence"))
            if len(record.get("potential_artwork_ids", [])) < 4 and not record.get("artwork_quota_rationale"):
                issues.append(("artwork_quota_not_met", "Fewer than four works requires a specific quota rationale", "$.potential_artwork_ids"))
        if record.get("identity_kind") != "individual" and record.get("hard_gate_results", {}).get("special_identity_not_coerced") is True:
            issues.append(("special_identity_coercion", "Anonymous, workshop, collective, traditional, or conventional identities cannot pass as individuals", "$.identity_kind"))

    elif entity_type == "artwork_rights_preflight":
        status = record.get("preflight_status")
        if status in CLEAR_PREFLIGHT:
            if record.get("media_license_basis") != "object_level" or not record.get("rights_evidence"):
                issues.append(("object_rights_evidence_missing", "A clear media path requires object-level rights evidence", "$.rights_evidence"))
            if record.get("media_license") in {"unknown", "restricted"}:
                issues.append(("rights_unknown_counted_clear", "Unknown or restricted rights cannot count as clear", "$.preflight_status"))
        if record.get("media_license_basis") == "unknown" and status in CLEAR_PREFLIGHT:
            issues.append(("media_license_inherited", "Metadata or technical access cannot supply a media license", "$.media_license_basis"))
        if record.get("delivery_mode") == "iiif_external" and not record.get("technical_availability", {}).get("iiif_present"):
            issues.append(("iiif_delivery_without_service", "External IIIF delivery requires an observed IIIF service", "$.delivery_mode"))

    elif entity_type == "relationship_lead":
        level = record.get("likely_evidence_level")
        relation = record.get("proposed_relation_type")
        if level == "A" and not record.get("direct_evidence_category"):
            issues.append(("a_lead_direct_evidence_category_missing", "A-level lead must name the direct evidence category to seek", "$.direct_evidence_category"))
        if level == "B" and not record.get("specific_context"):
            issues.append(("b_lead_context_missing", "B-level lead must name a place, time, institution, group, or exhibition context", "$.specific_context"))
        if relation == "explicitly_influenced_by" and level != "A":
            issues.append(("influence_lead_not_a", "Explicit influence can only be researched as an A-level lead", "$.likely_evidence_level"))
        if record.get("formal_relationship_created") is not False or record.get("public_display") is not False:
            issues.append(("formal_relationship_in_lead", "A research lead is never a formal or public relationship", "$"))

    elif entity_type == "selection_scenario":
        ids = record.get("candidate_ids", [])
        coverage_ids = [item.get("candidate_id") for item in record.get("coverage_matrix", []) if isinstance(item, dict)]
        if set(ids) != set(coverage_ids) or len(coverage_ids) != 12:
            issues.append(("scenario_coverage_mismatch", "Coverage matrix must cover the exact twelve candidates", "$.coverage_matrix"))
        if record.get("user_approved") is not False:
            issues.append(("scenario_user_approved", "MUSEUM-03A scenarios must remain unapproved", "$.user_approved"))

    elif entity_type == "selection_decision":
        if record.get("status") == "pending_user_decision":
            pending_fields = ("decision_type", "decision_authority", "decision_date", "selected_scenario_id", "media_strategy", "rationale")
            if any(record.get(field) is not None for field in pending_fields) or record.get("selected_candidate_ids") or record.get("replacements"):
                issues.append(("pending_decision_prefilled", "Pending template cannot contain a fabricated user decision", "$"))
        elif record.get("decision_type") in {"approve_recommended_slate", "approve_named_scenario", "approve_with_replacements"}:
            if len(record.get("selected_candidate_ids", [])) != 12:
                issues.append(("decision_selection_count", "An approval decision must select exactly twelve candidates", "$.selected_candidate_ids"))

    return sorted(set(issues), key=lambda item: (item[2], item[0], item[1]))


def _walk_keys(value: Any, location: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            yield child_location, key
            yield from _walk_keys(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{location}[{index}]")
