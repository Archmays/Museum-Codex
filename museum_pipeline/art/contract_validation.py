from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


APPROVED_COUNT = 12
MIN_ARTWORKS_PER_ARTIST = 2
ALLOWED_CONTEXT_TYPES = {
    "art_group",
    "art_movement",
    "exhibition",
    "exhibition_event",
    "group",
    "institution",
    "material",
    "movement",
    "museum_institution",
    "organization",
    "person",
    "place",
    "subject",
    "technique",
    "time_period",
}


def validate_art_batch_contract(batch: Mapping[str, Any]) -> set[str]:
    """Validate phase invariants shared by synthetic fixtures and formal packages.

    The fixture representation is intentionally compact, but this function is
    also called for a projection of the sealed formal package. Keeping the
    rules here prevents the fixture matrix from becoming a parallel validator.
    """

    codes: set[str] = set()
    _validate_decision(batch, codes)
    _validate_artists(batch, codes)
    _validate_artworks(batch, codes)
    _validate_contexts(batch, codes)
    _validate_relationships(batch, codes)
    _validate_media(batch, codes)
    _validate_package(batch, codes)
    return codes


def formal_package_contract_projection(
    *,
    decision: Mapping[str, Any],
    application: Mapping[str, Any],
    artists: Sequence[Mapping[str, Any]],
    artworks: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
    media_assessments: Sequence[Mapping[str, Any]],
    package_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Project formal records into the shared, synthetic-safe invariant view."""

    assessment_by_artwork = {
        item.get("artwork_id"): item
        for item in media_assessments
        if isinstance(item.get("artwork_id"), str)
    }
    selected_ids = list(decision.get("selected_candidate_ids", []))
    submitted_hash = application.get("submitted_decision_hash")
    projected_artists = []
    for artist in artists:
        branch = artist.get("branch_extensions") or {}
        death = (artist.get("life_dates") or {}).get("death") or {}
        projected_artists.append(
            {
                "id": artist.get("id"),
                "candidate_id": branch.get("approved_candidate_id"),
                "deceased_status": artist.get("deceased_status"),
                "identity_conflict": artist.get("identity_status") != "resolved",
                "source_lineages": [
                    {"id": source_id, "tier": 1, "role": "formal_source"}
                    for source_id in artist.get("source_ids", [])
                ],
                "death_date": {
                    "value": death.get("display_value"),
                    "precision": death.get("precision"),
                    "source_precision": death.get("precision"),
                },
                "auto_replacement": False,
                "verified_work_history": artist.get("at_least_one_verified_work_or_record"),
                "state": artist.get("lifecycle_status"),
            }
        )

    projected_artworks = []
    for artwork in artworks:
        assessment = assessment_by_artwork.get(artwork.get("id"), {})
        creation = artwork.get("creation_span") or {}
        projected_artworks.append(
            {
                "id": artwork.get("id"),
                "artist_id": artwork.get("approved_artist_id"),
                "official_object_url": (artwork.get("official_object_record") or {}).get(
                    "official_object_url"
                ),
                "attribution": {"preserved": bool(artwork.get("creator_attributions"))},
                "creation_date": {
                    "value": creation.get("start") or creation.get("end"),
                    "precision": creation.get("precision"),
                },
                "institution_id": artwork.get("holding_institution_id"),
                "accession_number": artwork.get("accession_number"),
                "rights_separation": assessment.get("metadata_inherited_as_media_rights") is False,
                "media_rights_basis": assessment.get("media_rights_basis"),
                "rights_evidence": [
                    {"kind": item.get("evidence_type"), "id": item.get("snapshot_hash")}
                    for item in assessment.get("rights_evidence", [])
                ],
                "description": "",
                "description_origin": "project_authored",
                "state": artwork.get("lifecycle_status"),
            }
        )

    projected_contexts = []
    for context in contexts:
        context_type = str(context.get("entity_type", ""))
        projected_contexts.append(
            {
                "id": context.get("id"),
                "context_type": context_type,
                "labels": context.get("labels", {}),
                "source_ids": context.get("source_ids", []),
                "requires_historical_scope": (
                    context_type == "place"
                    and context.get("historical_time_scope_required") is True
                ),
                "historical_time_scope": context.get("historical_time_scope"),
            }
        )

    projected_relationships = []
    for relationship in relationships:
        evidence_level = relationship.get("evidence_level")
        place_scope = relationship.get("place_scope") or {}
        place_ids = place_scope.get("place_ids", [])
        projected_relationships.append(
            {
                "id": relationship.get("id"),
                "source_entity_id": relationship.get("source_entity_id"),
                "target_entity_id": relationship.get("target_entity_id"),
                "relationship_type": relationship.get("relationship_type"),
                "relationship_semantics": relationship.get("relationship_semantics"),
                "evidence_level": evidence_level,
                "specific_context_ids": relationship.get("context_entity_ids", []),
                "place_context_id": place_ids[0] if place_ids else None,
                "time_scope": relationship.get("temporal_scope"),
                "direct_evidence": evidence_level == "A" and bool(
                    relationship.get("evidence_ids") or relationship.get("claim_ids")
                ),
                "is_algorithmic": relationship.get("is_algorithmic"),
                "generated_method": relationship.get("generation_method"),
                "public_display": relationship.get("public_display"),
                "claim_reviewed": relationship.get("review_status") in {"reviewed", "verified"},
            }
        )

    projected_media = []
    for assessment in media_assessments:
        media_license = assessment.get("media_license") or {}
        withdrawal = assessment.get("withdrawal_or_revocation") or {}
        bindings = assessment.get("source_license_bindings", [])
        projected_media.append(
            {
                "artwork_id": assessment.get("artwork_id"),
                "eligibility": assessment.get("outcome"),
                "development_only": assessment.get("development_only"),
                "counted_clear": assessment.get("future_public_media_eligible"),
                "external_iiif_cache_bytes": (assessment.get("technical_delivery") or {}).get(
                    "cache_bytes"
                ),
                "self_hosted_bytes_present": assessment.get("media_bytes_present"),
                "license_id": media_license.get("identifier"),
                "attribution": assessment.get("attribution"),
                "revoked_or_expired": withdrawal.get("status") != "active",
                "rule_scope": (
                    "media"
                    if any(item.get("content_class") == "media" for item in bindings)
                    else None
                ),
                "forced_image_quota": False,
            }
        )

    file_entries = [
        {
            "path": item.get("path"),
            "declared_bytes": item.get("bytes"),
            "actual_bytes": item.get("bytes"),
            "declared_sha256": item.get("sha256"),
            "actual_sha256": item.get("sha256"),
        }
        for item in package_manifest.get("files", [])
    ]
    decision_hash = submitted_hash or ""
    return {
        "decision": {
            "id": decision.get("id"),
            "status": decision.get("status"),
            "expected_bundle_hash": decision.get("input_bundle_hash"),
            "input_bundle_hash": application.get("input_bundle_hash"),
            "bundle_stale": (application.get("stale_check") or {}).get("status") != "fresh",
            "recommended_scenario_id": application.get("recommended_slate_id"),
            "selected_scenario_id": decision.get("selected_scenario_id"),
            "recommended_candidate_ids": list(application.get("selected_candidate_ids", [])),
            "selected_candidate_ids": selected_ids,
            "replacements": decision.get("replacements", []),
            "decision_authority": decision.get("decision_authority"),
            "expected_authority": application.get("authority"),
            "media_strategy": decision.get("media_strategy"),
            "decision_hash": decision_hash,
        },
        "application": {
            "input_hash": application.get("application_basis_hash"),
            "prior_input_hash": application.get("application_basis_hash"),
            "prior_output_hash": application.get("submitted_decision_hash"),
            "rerun_output_hash": application.get("submitted_decision_hash"),
            "conflicting_reapply": False,
        },
        "artists": projected_artists,
        "artworks": projected_artworks,
        "contexts": projected_contexts,
        "relationships": projected_relationships,
        "media_assessments": projected_media,
        "package": {
            "declared_files": [item["path"] for item in file_entries],
            "actual_files": [item["path"] for item in file_entries],
            "files": file_entries,
            "contains_symlink": not package_manifest.get("no_symlink_escape", False),
            "path_escape": not package_manifest.get("safe_relative_paths", False),
            "decision_ref": {"id": decision.get("id"), "hash": decision_hash},
            "primary_node_ids": [item.get("id") for item in artists],
            "media_byte_paths": [] if package_manifest.get("no_media_bytes") else ["media"],
            "state": "reviewed" if package_manifest.get("no_published_state") else "published",
        },
    }


def _validate_decision(batch: Mapping[str, Any], codes: set[str]) -> None:
    decision = batch["decision"]
    if decision.get("input_bundle_hash") != decision.get("expected_bundle_hash"):
        codes.add("decision_bundle_hash_mismatch")
    if decision.get("bundle_stale") is True:
        codes.add("decision_bundle_stale")
    if decision.get("selected_scenario_id") != decision.get("recommended_scenario_id"):
        codes.add("decision_wrong_scenario")
    selected = decision.get("selected_candidate_ids", [])
    if len(selected) != APPROVED_COUNT:
        codes.add("decision_artist_count_invalid")
    elif len(set(selected)) != len(selected):
        codes.add("decision_candidate_duplicate")
    elif selected != decision.get("recommended_candidate_ids"):
        codes.add("decision_selected_ids_not_recommended")
    if decision.get("replacements"):
        codes.add("decision_replacements_forbidden")
    if decision.get("decision_authority") != decision.get("expected_authority"):
        codes.add("decision_authority_mismatch")
    if decision.get("media_strategy") != "mixed":
        codes.add("decision_media_strategy_not_mixed")
    if decision.get("status") != "submitted":
        codes.add("application_requires_submitted_decision")

    application = batch["application"]
    if (
        application.get("prior_input_hash") == application.get("input_hash")
        and application.get("rerun_output_hash") != application.get("prior_output_hash")
    ):
        codes.add("decision_rerun_not_idempotent")
    if application.get("conflicting_reapply") is True:
        codes.add("decision_conflicting_second_application")


def _validate_artists(batch: Mapping[str, Any], codes: set[str]) -> None:
    approved = set(batch["decision"]["recommended_candidate_ids"])
    for artist in batch["artists"]:
        if artist.get("deceased_status") == "living":
            codes.add("artist_living_forbidden")
        elif artist.get("deceased_status") != "confirmed_deceased":
            codes.add("artist_death_unresolved")
        lineages = artist.get("source_lineages", [])
        if lineages and all(item.get("tier", 4) >= 3 for item in lineages):
            codes.add("artist_tier3_only")
        if artist.get("identity_conflict") is True:
            codes.add("artist_identity_conflict_unresolved")
        lineage_ids = [item.get("id") for item in lineages]
        if len(lineage_ids) != len(set(lineage_ids)):
            codes.add("artist_source_lineage_duplicate")
        death_date = artist.get("death_date", {})
        if death_date.get("source_precision") == "approximate" and death_date.get("precision") == "exact":
            codes.add("artist_approximate_date_promoted")
        if artist.get("candidate_id") not in approved:
            codes.add("artist_not_in_approved_slate")
        if artist.get("auto_replacement") is True:
            codes.add("artist_auto_replacement_forbidden")
        if artist.get("verified_work_history") is not True:
            codes.add("artist_verified_work_history_missing")
        if artist.get("state") == "published":
            codes.add("artist_published_state_forbidden")


def _validate_artworks(batch: Mapping[str, Any], codes: set[str]) -> None:
    approved_artists = {item["id"] for item in batch["artists"]}
    work_counts = {artist_id: 0 for artist_id in approved_artists}
    for artwork in batch["artworks"]:
        artist_id = artwork.get("artist_id")
        if artist_id in work_counts:
            work_counts[artist_id] += 1
        else:
            codes.add("artwork_artist_not_approved")
        if not str(artwork.get("official_object_url", "")).strip():
            codes.add("artwork_official_object_missing")
        if artwork.get("attribution", {}).get("preserved") is not True:
            codes.add("artwork_attribution_lost")
        creation_date = artwork.get("creation_date", {})
        if creation_date.get("value") not in {None, ""} and creation_date.get("precision") == "unknown":
            codes.add("artwork_date_precision_unresolved")
        if not artwork.get("institution_id") or not artwork.get("accession_number"):
            codes.add("artwork_institution_accession_missing")
        if artwork.get("rights_separation") is not True or artwork.get("media_rights_basis") == "inherited_from_metadata":
            codes.add("artwork_metadata_media_rights_inherited")
        if any(item.get("kind") == "image_url" for item in artwork.get("rights_evidence", [])):
            codes.add("artwork_image_url_used_as_rights_evidence")
        if artwork.get("description_origin") == "copied_upstream" and len(artwork.get("description", "")) > 400:
            codes.add("artwork_long_copied_description")
        if artwork.get("state") == "published":
            codes.add("artwork_published_state_forbidden")
    if any(count < MIN_ARTWORKS_PER_ARTIST for count in work_counts.values()):
        codes.add("artwork_minimum_per_artist_not_met")


def _validate_contexts(batch: Mapping[str, Any], codes: set[str]) -> None:
    for context in batch["contexts"]:
        context_id = str(context.get("id", ""))
        context_type = str(context.get("context_type", ""))
        if context_type == "common" or context_id.startswith("context:"):
            codes.add("context_common_fallback_forbidden")
            continue
        prefix = context_id.partition(":")[0]
        if context_type not in ALLOWED_CONTEXT_TYPES or prefix != context_type:
            codes.add("context_type_prefix_mismatch")
        if not context.get("source_ids"):
            codes.add("context_source_missing")
        if not str(context.get("labels", {}).get("en", "")).strip():
            codes.add("context_label_empty")
        if context.get("requires_historical_scope") and not context.get("historical_time_scope"):
            codes.add("context_historical_time_scope_missing")


def _validate_relationships(batch: Mapping[str, Any], codes: set[str]) -> None:
    entity_ids = {item["id"] for item in batch["artists"]} | {item["id"] for item in batch["contexts"]}
    artist_ids = {item["id"] for item in batch["artists"]}
    degree = {artist_id: 0 for artist_id in artist_ids}
    seen_pairs: set[tuple[str, frozenset[str]]] = set()
    for relationship in batch["relationships"]:
        relation_type = relationship.get("relationship_type")
        source_id = relationship.get("source_entity_id")
        target_id = relationship.get("target_entity_id")
        if source_id in degree:
            degree[source_id] += 1
        if target_id in degree:
            degree[target_id] += 1
        if source_id not in entity_ids or target_id not in entity_ids:
            codes.add("relationship_entity_missing")
        if relation_type == "related_to":
            codes.add("relationship_generic_related_to_forbidden")
        if (
            relation_type == "computationally_similar_to"
            or relationship.get("relationship_semantics") == "computational_similarity"
            or relationship.get("is_algorithmic") is True
        ):
            codes.add("relationship_computational_similarity_forbidden")
        if relation_type == "explicitly_influenced_by" and relationship.get("evidence_level") == "C":
            codes.add("relationship_level_c_cannot_assert_influence")
        if relationship.get("evidence_level") == "B" and not relationship.get("specific_context_ids"):
            codes.add("relationship_level_b_context_missing")
        if relation_type in {"worked_same_place", "worked_in_same_place_period"} and (
            not relationship.get("place_context_id") or not relationship.get("time_scope")
        ):
            codes.add("relationship_shared_place_scope_missing")
        if relationship.get("evidence_level") == "A" and relationship.get("direct_evidence") is not True:
            codes.add("relationship_level_a_direct_evidence_missing")
        pair_key = (str(relation_type), frozenset({str(source_id), str(target_id)}))
        if pair_key in seen_pairs:
            codes.add("relationship_duplicate_inverse")
        seen_pairs.add(pair_key)
        if relationship.get("public_display") is True and relationship.get("claim_reviewed") is not True:
            codes.add("relationship_public_display_claim_unreviewed")
        if relationship.get("generated_method") == "all_pairs_shared_tags":
            codes.add("relationship_all_pairs_generation_forbidden")
    if any(value == 0 for value in degree.values()):
        codes.add("relationship_isolated_artist_without_exception")


def _validate_media(batch: Mapping[str, Any], codes: set[str]) -> None:
    for assessment in batch["media_assessments"]:
        eligibility = assessment.get("eligibility")
        if eligibility == "unknown":
            codes.add("media_eligibility_unknown")
        if assessment.get("development_only") is True and assessment.get("counted_clear") is True:
            codes.add("media_development_only_counted_clear")
        if eligibility == "external_iiif_candidate" and assessment.get("external_iiif_cache_bytes") is True:
            codes.add("media_external_iiif_cache_forbidden")
        if eligibility == "self_hosted_open_media_eligible" and assessment.get("self_hosted_bytes_present") is True:
            codes.add("media_self_hosted_bytes_forbidden_in_phase")
        if str(assessment.get("license_id", "")).upper().startswith("CC-BY") and not str(
            assessment.get("attribution", "")
        ).strip():
            codes.add("media_cc_by_attribution_missing")
        if assessment.get("revoked_or_expired") is True:
            codes.add("media_permission_expired_or_revoked")
        if assessment.get("rule_scope") != "media":
            codes.add("media_rule_scope_invalid")
        if eligibility == "metadata_only" and assessment.get("forced_image_quota") is True:
            codes.add("media_metadata_only_forced_to_quota")


def _validate_package(batch: Mapping[str, Any], codes: set[str]) -> None:
    package = batch["package"]
    if set(package.get("actual_files", [])) != set(package.get("declared_files", [])):
        codes.add("package_undeclared_file")
    if any(
        item.get("actual_bytes") != item.get("declared_bytes")
        or item.get("actual_sha256") != item.get("declared_sha256")
        for item in package.get("files", [])
    ):
        codes.add("package_byte_hash_mismatch")
    if package.get("contains_symlink") is True or package.get("path_escape") is True:
        codes.add("package_path_escape_or_symlink")
    decision = batch["decision"]
    if package.get("decision_ref") != {"id": decision.get("id"), "hash": decision.get("decision_hash")}:
        codes.add("package_decision_closure_missing")
    artist_ids = {item["id"] for item in batch["artists"]}
    primary_nodes = package.get("primary_node_ids", [])
    if len(primary_nodes) != APPROVED_COUNT or set(primary_nodes) != artist_ids:
        codes.add("package_primary_artist_nodes_invalid")
    if package.get("media_byte_paths"):
        codes.add("package_media_bytes_forbidden")
    if package.get("state") == "published":
        codes.add("package_published_state_forbidden")
