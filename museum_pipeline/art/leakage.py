from __future__ import annotations

from typing import Any

from museum_pipeline.hashing import canonical_sha256


def build_public_leakage_label_set(
    *,
    identity_seed: dict[str, Any],
    identity_basis: dict[str, Any],
    application: dict[str, Any],
    formal_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the tracked deny-list used only against public/Pages artifacts."""

    terms: dict[tuple[str, str], dict[str, str]] = {}

    def add(value: Any, category: str, match_mode: str) -> None:
        if not isinstance(value, str) or len(value.strip()) < 2:
            return
        normalized = value.strip()
        key = (normalized.casefold(), category)
        candidate = {
            "value": normalized,
            "category": category,
            "match_mode": match_mode,
        }
        current = terms.get(key)
        priority = {"serialized_string": 0, "exact_token": 1, "casefold_substring": 2}
        if current is None or priority[match_mode] > priority[current["match_mode"]]:
            terms[key] = candidate

    add(identity_seed.get("batch_id"), "batch_id", "exact_token")
    add(application.get("id"), "batch_id", "exact_token")
    add(application.get("submitted_decision_id"), "formal_record_id", "exact_token")
    add("public-leakage-label-set:museum-03b-first-slate-v1", "formal_record_id", "exact_token")
    add("reviewed-package-manifest:museum-03b-first-slate-v1", "formal_record_id", "exact_token")
    for binding in identity_basis.get("bindings", []):
        add(binding.get("approved_candidate_id"), "candidate_id", "exact_token")
        add(binding.get("artist_id"), "artist_id", "exact_token")
        for value in binding.get("approved_labels", {}).values():
            add(value, "approved_label", "casefold_substring")
        for value in binding.get("external_ids", {}).values():
            add(value, "external_id", "exact_token")
    for artist in identity_seed.get("artists", []):
        for value in artist.get("labels", {}).values():
            add(value, "approved_label", "casefold_substring")
        for alias in artist.get("aliases", []):
            add(alias.get("text"), "alias", "casefold_substring")
    context_entity_types = {
        "art_movement", "art_group", "museum_institution", "organization", "place",
        "exhibition", "exhibition_event", "material", "technique", "subject", "time_period", "person",
    }
    id_categories = {
        "artwork": "artwork_id",
        "relationship": "relationship_id",
        "art_movement": "context_id",
        "art_group": "context_id",
        "museum_institution": "context_id",
        "organization": "context_id",
        "place": "context_id",
        "exhibition": "context_id",
        "exhibition_event": "context_id",
        "material": "context_id",
        "technique": "context_id",
        "subject": "context_id",
        "time_period": "context_id",
        "person": "context_id",
        "source": "source_id",
        "media_eligibility_assessment": "rights_record_id",
        "graph_input": "batch_id",
        "formal_art_batch_manifest": "batch_id",
    }
    for record in formal_records or []:
        entity_type = str(record.get("entity_type"))
        add(record.get("id"), id_categories.get(entity_type, "formal_record_id"), "exact_token")
        label_category = "context_label" if entity_type in context_entity_types else "approved_label"
        label_mode = "serialized_string" if entity_type in context_entity_types else "casefold_substring"
        alias_category = "context_label" if entity_type in context_entity_types else "alias"
        for value in (record.get("labels") or {}).values():
            add(value, label_category, label_mode)
        for alias in record.get("aliases") or []:
            add(alias.get("text") if isinstance(alias, dict) else alias, alias_category, label_mode)
        for title in record.get("title_records") or []:
            add(title.get("text") if isinstance(title, dict) else title, "approved_label", "casefold_substring")
        for value in (record.get("external_ids") or {}).values():
            add(value, "external_id", "exact_token")
        official = record.get("official_object_record") or {}
        add(official.get("source_object_id"), "external_id", "exact_token")
        add(record.get("accession_number"), "external_id", "exact_token")
        add(record.get("rights_preflight_id"), "rights_record_id", "exact_token")
        for entry in record.get("entries", []):
            if isinstance(entry, dict):
                add(entry.get("snapshot_id"), "formal_record_id", "exact_token")
                add(entry.get("receipt_id"), "formal_record_id", "exact_token")

    payload = {
        "schema_version": "1.1.0",
        "id": "public-leakage-label-set:museum-03b-first-slate-v1",
        "entity_type": "public_leakage_label_set",
        "batch_id": identity_seed["batch_id"],
        "terms": sorted(terms.values(), key=lambda item: (item["category"], item["value"].casefold())),
    }
    payload["content_hash"] = canonical_sha256(payload)
    return payload
