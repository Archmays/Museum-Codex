from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from museum_pipeline.config import ROOT
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record


BATCH_ID = "art-batch:museum-03b-first-slate-v1"
PHASE_ID = "MUSEUM-03B"
DEFAULT_CONTEXT_DECISIONS = ROOT / "research" / "art" / "museum-03b-context-decisions.json"
DEFAULT_RELATIONSHIP_DECISIONS = ROOT / "research" / "art" / "museum-03b-relationship-decisions.json"
DEFAULT_LEAD_CLOSURE = ROOT / "research" / "art" / "museum-03b-relationship-lead-closure.json"
DEFAULT_ARTWORK_SELECTION_BASIS = ROOT / "research" / "art" / "museum-03b-artwork-selection-basis.json"
DEFAULT_ARTWORK_SNAPSHOT_RECEIPTS = ROOT / "research" / "art" / "museum-03b-artwork-snapshot-receipts.json"
DEFAULT_IDENTITY_DIR = ROOT / "data" / "reviewed" / "art" / "museum-03b" / "museum-03b-first-slate-v1"

SOURCE_RECORD_IDS = {
    "met_open_access": "source:met_open_access",
    "aic_api": "source:aic_api",
}
INSTITUTION_IDS = {
    "met_open_access": "museum_institution:metropolitan-museum-of-art",
    "aic_api": "museum_institution:art-institute-of-chicago",
}
INSTITUTION_PLACES = {
    "museum_institution:metropolitan-museum-of-art": "place:new-york-city",
    "museum_institution:art-institute-of-chicago": "place:chicago",
}
INSTITUTION_LABELS = {
    "museum_institution:metropolitan-museum-of-art": {
        "en": "The Metropolitan Museum of Art",
        "zh-Hans": "大都会艺术博物馆",
    },
    "museum_institution:art-institute-of-chicago": {
        "en": "Art Institute of Chicago",
        "zh-Hans": "芝加哥艺术博物馆",
    },
}
PLACE_LABELS = {
    "place:new-york-city": {"en": "New York City", "zh-Hans": "纽约市"},
    "place:chicago": {"en": "Chicago", "zh-Hans": "芝加哥"},
}

# These labels are used only for artwork-required contexts that have no dedicated
# context decision. The 17 reviewed context-decision labels always take priority.
ARTWORK_ONLY_CONTEXT_LABELS = {
    "material:albumen": {"en": "Albumen", "zh-Hans": "蛋白"},
    "material:silver": {"en": "Silver", "zh-Hans": "银"},
    "material:wood-panel": {"en": "Wood panel", "zh-Hans": "木质画板"},
    "technique:albumen-silver-print": {"en": "Albumen silver print", "zh-Hans": "蛋白银印相"},
    "technique:chromolithography": {"en": "Chromolithography", "zh-Hans": "彩色石版印刷"},
    "technique:drawing": {"en": "Drawing", "zh-Hans": "素描与绘画"},
    "technique:ink-painting": {"en": "Ink painting", "zh-Hans": "水墨画"},
    "technique:oil-painting": {"en": "Oil painting", "zh-Hans": "油画"},
    "technique:pastel": {"en": "Pastel", "zh-Hans": "粉彩"},
    "technique:watercolor": {"en": "Watercolor", "zh-Hans": "水彩"},
}

CONTEXT_SIGNOFF_IDS = (
    "review-signoff:museum-03b-context-taxonomy",
    "review-signoff:museum-03b-context-source",
)
RELATIONSHIP_SIGNOFF_IDS = (
    "review-signoff:museum-03b-relationship-semantics",
    "review-signoff:museum-03b-relationship-evidence",
)
DISPOSITION_SIGNOFF_ID = "review-signoff:museum-03b-relationship-dispositions"


def build_relationship_stage(
    *,
    artwork_stage: Mapping[str, Any],
    context_decisions_path: Path = DEFAULT_CONTEXT_DECISIONS,
    relationship_decisions_path: Path = DEFAULT_RELATIONSHIP_DECISIONS,
    lead_closure_path: Path = DEFAULT_LEAD_CLOSURE,
    artwork_selection_basis_path: Path = DEFAULT_ARTWORK_SELECTION_BASIS,
    artwork_snapshot_receipts_path: Path = DEFAULT_ARTWORK_SNAPSHOT_RECEIPTS,
    identity_dir: Path = DEFAULT_IDENTITY_DIR,
    sources: Sequence[dict[str, Any]] | None = None,
    artists: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build reviewed context and relationship records entirely in memory.

    ``artwork_stage`` accepts the return value from ``build_artwork_stage`` or
    its nested ``payloads`` mapping. No package or output file is written here.
    """

    context_decisions = _load_object(context_decisions_path, "context_decisions_invalid")
    relationship_decisions = _load_object(relationship_decisions_path, "relationship_decisions_invalid")
    lead_closure = _load_object(lead_closure_path, "relationship_lead_closure_invalid")
    selection_basis = _load_object(artwork_selection_basis_path, "artwork_selection_basis_invalid")
    snapshot_ledger = _load_object(artwork_snapshot_receipts_path, "artwork_snapshot_ledger_invalid")
    for label, document in (
        ("context decisions", context_decisions),
        ("relationship decisions", relationship_decisions),
        ("relationship lead closure", lead_closure),
        ("artwork selection basis", selection_basis),
        ("artwork snapshot ledger", snapshot_ledger),
    ):
        _require_content_hash(document, label)

    identity_dir = Path(identity_dir)
    source_records = list(sources) if sources is not None else _load_array(identity_dir / "sources.json", "identity_sources_invalid")
    artist_records = list(artists) if artists is not None else _load_array(identity_dir / "artists.json", "identity_artists_invalid")
    artwork_payloads = _artwork_payloads(artwork_stage)
    artworks = _payload_array(artwork_payloads, ("artworks.json", "artworks"), "artwork_stage_artworks_missing")
    artwork_claims = _payload_array(
        artwork_payloads,
        ("artwork-claims.json", "artwork_claims", "claims"),
        "artwork_stage_claims_missing",
    )
    artwork_evidence = _payload_array(
        artwork_payloads,
        ("artwork-evidence.json", "artwork_evidence", "evidence"),
        "artwork_stage_evidence_missing",
    )

    receipt_index = _receipt_index(snapshot_ledger)
    _validate_research_inputs(context_decisions, relationship_decisions, lead_closure, selection_basis)
    _validate_identity_inputs(source_records, artist_records, relationship_decisions)
    _validate_artwork_inputs(artworks, artwork_claims, artwork_evidence, selection_basis, receipt_index)
    binding_index = _artwork_binding_index(artwork_evidence, receipt_index)

    context_records, context_claims, context_evidence = _build_context_records(
        context_decisions,
        relationship_decisions,
        selection_basis,
        artworks,
        receipt_index,
        binding_index,
    )
    disposition_records = _build_dispositions(relationship_decisions, lead_closure)
    relationship_records, relationship_claims, relationship_evidence = _build_relationship_records(
        relationship_decisions,
        artist_records,
        receipt_index,
        binding_index,
    )
    signoffs = _build_signoffs(
        context_decisions,
        relationship_decisions,
        lead_closure,
        context_records,
        context_claims,
        context_evidence,
        relationship_records,
        relationship_claims,
        relationship_evidence,
        disposition_records,
    )

    claims = [*context_claims, *relationship_claims]
    evidence = [*context_evidence, *relationship_evidence]
    result = {
        "status": "pass",
        "batch_id": BATCH_ID,
        "phase_id": PHASE_ID,
        "contexts": context_records,
        "claims": claims,
        "evidence": evidence,
        "relationships": relationship_records,
        "dispositions": disposition_records,
        "signoffs": signoffs,
        "context_claims": context_claims,
        "context_evidence": context_evidence,
        "relationship_claims": relationship_claims,
        "relationship_evidence": relationship_evidence,
        "counts": {
            "contexts": len(context_records),
            "claims": len(claims),
            "evidence": len(evidence),
            "relationships": len(relationship_records),
            "dispositions": len(disposition_records),
            "signoffs": len(signoffs),
        },
        "evidence_level_counts": {"A": 0, "B": 0, "C": 36},
        "evidence_level_rationale": (
            "No direct or contextual historical evidence sufficient for A- or B-level promotion was accepted. "
            "All 36 records are explicit, evidence-bound C-level educational comparisons selected from the fixed 69-candidate research set; "
            "the zero A/B counts are conservative and were not used to meet a quota."
        ),
        "public_records_created": 0,
        "algorithmic_relationships_created": 0,
    }
    _validate_generated_records(result, source_records, artist_records)
    return result


def _validate_research_inputs(
    contexts: dict[str, Any],
    relationships: dict[str, Any],
    closure: dict[str, Any],
    selection: dict[str, Any],
) -> None:
    expected = (
        (contexts, "context_decision_set", None),
        (relationships, "relationship_decision_set", None),
        (closure, "relationship_lead_closure_set", None),
        (selection, "artwork_selection_basis", BATCH_ID),
    )
    for document, entity_type, batch_id in expected:
        if document.get("entity_type") != entity_type:
            raise PipelineError("research_entity_type_mismatch", f"Expected {entity_type}")
        if document.get("phase_id", PHASE_ID) != PHASE_ID:
            raise PipelineError("research_phase_mismatch", f"{entity_type} is not for {PHASE_ID}")
        if batch_id is not None and document.get("batch_id") != batch_id:
            raise PipelineError("research_batch_mismatch", f"{entity_type} is not for {BATCH_ID}")

    context_rows = contexts.get("contexts")
    decisions = relationships.get("decisions")
    closure_entries = closure.get("entries")
    selection_entries = selection.get("entries")
    if not isinstance(context_rows, list) or len(context_rows) != 17:
        raise PipelineError("context_decision_count_mismatch", "Expected 17 reviewed relationship contexts")
    if not isinstance(decisions, list) or len(decisions) != 36:
        raise PipelineError("relationship_decision_count_mismatch", "Expected exactly 36 reviewed relationships")
    if not isinstance(closure_entries, list) or len(closure_entries) != 45:
        raise PipelineError("relationship_lead_closure_count_mismatch", "Expected exactly 45 inherited lead dispositions")
    if not isinstance(selection_entries, list) or len(selection_entries) != 44:
        raise PipelineError("artwork_selection_count_mismatch", "Expected the exact nominal 44 artwork selections")
    if contexts.get("status") != "accepted_reviewed" or relationships.get("status") != "accepted_reviewed":
        raise PipelineError("research_review_state_invalid", "Context and relationship decisions must be accepted_reviewed")
    if closure.get("review_status") != "accepted_reviewed":
        raise PipelineError("lead_closure_review_state_invalid", "Lead closure must be accepted_reviewed")

    context_ids = [row.get("id") for row in context_rows]
    if len(context_ids) != len(set(context_ids)):
        raise PipelineError("context_decision_duplicate", "Context decision IDs must be unique")
    relationship_context_ids = {
        context_id
        for decision in decisions
        for context_id in decision.get("context_entity_ids", [])
    }
    if set(context_ids) != relationship_context_ids:
        raise PipelineError(
            "relationship_context_decision_closure_mismatch",
            "Dedicated context decisions must exactly equal contexts referenced by formal relationships",
        )

    inherited = [decision for decision in decisions if (decision.get("origin") or {}).get("kind") == "inherited_lead"]
    curated = [decision for decision in decisions if (decision.get("origin") or {}).get("kind") == "curated_new"]
    if len(inherited) != 12 or len(curated) != 24:
        raise PipelineError("relationship_origin_count_mismatch", "Expected 12 inherited and 24 newly curated formal relationships")
    seen_inverse: set[tuple[str, str, str]] = set()
    for decision in decisions:
        if (
            decision.get("evidence_level") != "C"
            or decision.get("relationship_semantics") != "curatorial_comparison"
            or decision.get("directed") is not False
            or decision.get("is_algorithmic") is not False
            or decision.get("computational_similarity") is not None
            or decision.get("review_status") != "accepted_reviewed"
        ):
            raise PipelineError("relationship_decision_semantics_invalid", f"Unsafe semantics in {decision.get('decision_id')}")
        source_id = decision.get("source_artist_id")
        target_id = decision.get("target_artist_id")
        if source_id == target_id:
            raise PipelineError("relationship_self_relation_forbidden", f"Self relation in {decision.get('decision_id')}")
        inverse_key = (str(decision.get("relationship_type")), *sorted((str(source_id), str(target_id))))
        if inverse_key in seen_inverse:
            raise PipelineError("relationship_inverse_duplicate", f"Duplicate inverse relation in {decision.get('decision_id')}")
        seen_inverse.add(inverse_key)

    closure_by_id = {entry.get("lead_id"): entry for entry in closure_entries}
    for decision in inherited:
        origin = decision["origin"]
        entry = closure_by_id.get(origin.get("inherited_lead_id"))
        if (
            entry is None
            or entry.get("lead_canonical_hash") != origin.get("inherited_lead_hash")
            or entry.get("disposition") != "promoted_to_formal_relationship"
            or entry.get("formal_relationship_id") != decision.get("relationship_id")
        ):
            raise PipelineError("inherited_relationship_closure_mismatch", f"Inherited closure differs for {decision.get('decision_id')}")


def _validate_identity_inputs(
    sources: Sequence[dict[str, Any]],
    artists: Sequence[dict[str, Any]],
    relationship_decisions: dict[str, Any],
) -> None:
    source_by_id = _unique_index(sources, "source", "identity_source_duplicate")
    artist_by_id = _unique_index(artists, "artist", "identity_artist_duplicate")
    required_sources = set(SOURCE_RECORD_IDS.values())
    if not required_sources <= set(source_by_id):
        raise PipelineError("identity_source_missing", f"Missing official source records: {sorted(required_sources - set(source_by_id))}")
    endpoints = {
        endpoint
        for decision in relationship_decisions["decisions"]
        for endpoint in (decision.get("source_artist_id"), decision.get("target_artist_id"))
    }
    if len(artist_by_id) != 12 or endpoints != set(artist_by_id):
        raise PipelineError("relationship_artist_closure_mismatch", "Relationship endpoints must exactly cover the approved 12 artists")
    for artist in artists:
        if artist.get("deceased_status") != "confirmed_deceased" or artist.get("lifecycle_status") != "reviewed":
            raise PipelineError("relationship_artist_identity_gate_failed", f"Artist is not reviewed confirmed-deceased: {artist.get('id')}")


def _validate_artwork_inputs(
    artworks: Sequence[dict[str, Any]],
    claims: Sequence[dict[str, Any]],
    evidence: Sequence[dict[str, Any]],
    selection: dict[str, Any],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
) -> None:
    if len(artworks) != 44:
        raise PipelineError("artwork_stage_count_mismatch", "Relationship build requires all 44 artwork records")
    claim_by_id = _unique_index(claims, "claim", "artwork_claim_duplicate")
    evidence_by_id = _unique_index(evidence, "evidence", "artwork_evidence_duplicate")
    expected = {
        (entry["source_id"], str(entry["source_object_id"])): entry
        for entry in selection["entries"]
    }
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for artwork in artworks:
        source_key, object_id = _artwork_source_object(artwork)
        key = (source_key, object_id)
        if key in observed:
            raise PipelineError("artwork_stage_duplicate_object", f"Duplicate artwork object: {source_key}:{object_id}")
        observed[key] = artwork
        entry = expected.get(key)
        if entry is None:
            raise PipelineError("artwork_stage_unselected_object", f"Unselected artwork object: {source_key}:{object_id}")
        if artwork.get("approved_artist_id", (artwork.get("branch_extensions") or {}).get("approved_artist_id")) != entry["approved_artist_id"]:
            raise PipelineError("artwork_stage_artist_mismatch", f"Approved artist differs for {source_key}:{object_id}")
        if set(artwork.get("material_ids", [])) != set(entry["material_ids"]):
            raise PipelineError("artwork_stage_material_mismatch", f"Material IDs differ for {source_key}:{object_id}")
        if set(artwork.get("technique_ids", [])) != set(entry["technique_ids"]):
            raise PipelineError("artwork_stage_technique_mismatch", f"Technique IDs differ for {source_key}:{object_id}")
        subject_ids = artwork.get("subject_ids")
        if subject_ids is None:
            subject_ids = (artwork.get("branch_extensions") or {}).get("subject_ids", [])
        if set(subject_ids) != set(entry["subject_ids"]):
            raise PipelineError("artwork_stage_subject_mismatch", f"Subject IDs differ for {source_key}:{object_id}")
        expected_institution = INSTITUTION_IDS[source_key]
        if artwork.get("holding_institution_id") != expected_institution:
            raise PipelineError("artwork_stage_institution_mismatch", f"Holding institution differs for {source_key}:{object_id}")
        for claim_id in artwork.get("claim_ids", []):
            claim = claim_by_id.get(claim_id)
            if claim is None or claim.get("subject_id") != artwork.get("id"):
                raise PipelineError("artwork_claim_closure_mismatch", f"Artwork claim cannot resolve: {claim_id}")
    if set(observed) != set(expected):
        raise PipelineError("artwork_stage_exact_set_mismatch", "Artwork output does not exactly match the selected nominal 44")

    for claim in claims:
        claim_id = claim.get("id")
        for evidence_id in [*claim.get("evidence_ids", []), *claim.get("counter_evidence_ids", [])]:
            record = evidence_by_id.get(evidence_id)
            if record is None or claim_id not in record.get("claim_ids", []):
                raise PipelineError("artwork_evidence_backlink_missing", f"Artwork evidence cannot resolve: {evidence_id}")
    for key, receipt in receipt_index.items():
        if key in expected and not (
            receipt.get("verification", {}).get("body_present") is True
            and receipt.get("verification", {}).get("byte_count_match") is True
            and receipt.get("verification", {}).get("hash_match") is True
        ):
            raise PipelineError("artwork_snapshot_receipt_unverified", f"Snapshot receipt is not fully verified: {key[0]}:{key[1]}")


def _artwork_binding_index(
    evidence_records: Sequence[dict[str, Any]],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_snapshot = {
        (receipt["snapshot_id"], object_id): (source_key, object_id)
        for (source_key, object_id), receipt in receipt_index.items()
    }
    bindings: dict[tuple[str, str], list[dict[str, Any]]] = {}
    observed_raw: set[tuple[str, str]] = set()
    for evidence in evidence_records:
        for raw_ref in evidence.get("raw_snapshot_refs", []):
            source_object_id = str(raw_ref.get("source_object_id"))
            key = by_snapshot.get((raw_ref.get("snapshot_id"), source_object_id))
            if key is None:
                raise PipelineError("artwork_evidence_snapshot_unknown", f"Unknown artwork evidence snapshot: {raw_ref.get('snapshot_id')}")
            receipt = receipt_index[key]
            if raw_ref.get("body_sha256") != receipt.get("body_sha256"):
                raise PipelineError("artwork_evidence_snapshot_hash_mismatch", f"Artwork evidence hash differs for {key[0]}:{key[1]}")
            source_record_id = SOURCE_RECORD_IDS[key[0]]
            if source_record_id not in evidence.get("source_ids", []):
                raise PipelineError("artwork_evidence_source_mismatch", f"Artwork evidence source differs for {key[0]}:{key[1]}")
            matching = [
                binding
                for binding in evidence.get("source_license_bindings", [])
                if binding.get("source_id") == source_record_id
            ]
            if not matching:
                raise PipelineError("artwork_evidence_binding_missing", f"Artwork evidence lacks a source-rule binding for {key[0]}:{key[1]}")
            bindings.setdefault(key, []).extend(matching)
            observed_raw.add(key)
    for key in receipt_index:
        if key not in observed_raw:
            raise PipelineError("artwork_evidence_object_missing", f"Artwork evidence lacks raw closure for {key[0]}:{key[1]}")
    return {key: _dedupe_records(value) for key, value in bindings.items()}


def _build_context_records(
    context_decisions: dict[str, Any],
    relationship_decisions: dict[str, Any],
    selection: dict[str, Any],
    artworks: Sequence[dict[str, Any]],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
    binding_index: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    del relationship_decisions  # closure was checked before this deterministic transform
    decision_by_id = {item["id"]: item for item in context_decisions["contexts"]}
    selected_context_ids = {
        context_id
        for item in selection["entries"]
        for field in ("material_ids", "technique_ids", "subject_ids")
        for context_id in item[field]
    }
    observed_context_ids = {
        context_id
        for artwork in artworks
        for context_id in (
            *artwork.get("material_ids", []),
            *artwork.get("technique_ids", []),
            *(artwork.get("subject_ids") or (artwork.get("branch_extensions") or {}).get("subject_ids", [])),
        )
    }
    if observed_context_ids != selected_context_ids:
        raise PipelineError("artwork_context_closure_mismatch", "Artwork and selection context IDs differ")
    extra_ids = sorted(selected_context_ids - set(decision_by_id))
    if set(extra_ids) != set(ARTWORK_ONLY_CONTEXT_LABELS):
        raise PipelineError("artwork_only_context_set_mismatch", f"Unexpected artwork-only contexts: {extra_ids}")

    specifications: list[dict[str, Any]] = []
    for item in context_decisions["contexts"]:
        specifications.append({
            "id": item["id"],
            "entity_type": item["entity_type"],
            "labels": item["labels"],
            "scope_note": item["scope_note"],
            "educational_value": item["educational_value"],
            "time_description": item["time_scope"]["historical_scope"],
            "source_refs": item["source_bindings"],
        })
    for context_id in extra_ids:
        entity_type = context_id.split(":", 1)[0]
        source_refs = _selection_context_refs(context_id, selection, receipt_index)
        specifications.append({
            "id": context_id,
            "entity_type": entity_type,
            "labels": ARTWORK_ONLY_CONTEXT_LABELS[context_id],
            "scope_note": (
                "This typed category is normalized only from exact official medium fields in the selected artwork records; "
                "it does not imply contact, influence, transmission, or common authorship."
            ),
            "educational_value": "Supports precise object-level comparison without expanding the category into a historical relationship.",
            "time_description": "The cited object display dates bound the examples; no origin or end date is assigned to the category itself.",
            "source_refs": source_refs,
        })
    first_by_source = {
        source_key: next(item for item in selection["entries"] if item["source_id"] == source_key)
        for source_key in SOURCE_RECORD_IDS
    }
    for source_key in ("met_open_access", "aic_api"):
        institution_id = INSTITUTION_IDS[source_key]
        source_ref = _institution_source_ref(source_key, first_by_source[source_key], receipt_index)
        specifications.append({
            "id": institution_id,
            "entity_type": "museum_institution",
            "labels": INSTITUTION_LABELS[institution_id],
            "scope_note": "Typed holding-institution context for the selected official object records; no founding date or uninterrupted operational history is asserted.",
            "educational_value": "Keeps artwork custody metadata linked to an explicit typed institution instead of an untyped display string.",
            "time_description": "No founding, closure, or continuous-operation span is asserted in MUSEUM-03B.",
            "source_refs": [source_ref],
            "active_span": _unknown_span("No founding or closure date is asserted in this MUSEUM-03B context record."),
            "place_id": INSTITUTION_PLACES[institution_id],
        })
        place_id = INSTITUTION_PLACES[institution_id]
        specifications.append({
            "id": place_id,
            "entity_type": "place",
            "labels": PLACE_LABELS[place_id],
            "scope_note": "Operational city context for the holding-institution link only; it is not evidence of shared artist activity, contact, or influence.",
            "educational_value": "Lets the institution reference resolve to a typed place while keeping historical artist geography out of scope.",
            "time_description": "No historical geographic interval is required or asserted for this operational city label.",
            "source_refs": [source_ref],
            "place_kind": "city",
            "historical_time_scope_required": False,
            "historical_time_scope": None,
        })
    if len(specifications) != 31 or len({item["id"] for item in specifications}) != 31:
        raise PipelineError("formal_context_count_mismatch", "Expected exactly 31 typed contexts for relationship and artwork closure")

    taxonomy_session = context_decisions["review_sessions"]["context_reviewer"]
    source_session = context_decisions["review_sessions"]["source_reviewer"]
    contexts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for spec in specifications:
        context_id = spec["id"]
        slug = context_id.replace(":", "-")
        claim_id = f"claim:context-{slug}"
        evidence_id = f"evidence:context-{slug}"
        source_refs = _validated_source_refs(spec["source_refs"], receipt_index)
        source_ids, bindings = _source_closure(source_refs, binding_index)
        context = {
            "schema_version": "1.0.0",
            "id": context_id,
            "entity_type": spec["entity_type"],
            "branch_id": "art",
            "labels": spec["labels"],
            "name_records": [
                {
                    "text": spec["labels"]["en"],
                    "language": "en",
                    "script": "Latn",
                    "name_type": "preferred",
                    "source_claim_id": claim_id,
                    "time_scope": None,
                },
                {
                    "text": spec["labels"]["zh-Hans"],
                    "language": "zh-Hans",
                    "script": "Hans",
                    "name_type": "translated_display",
                    "source_claim_id": claim_id,
                    "time_scope": None,
                },
            ],
            "claim_ids": [claim_id],
            "source_ids": source_ids,
            "source_license_bindings": bindings,
            "lifecycle_status": "reviewed",
            "data_version": "1.0.0",
            "review_status": "reviewed",
            "reviewed_by": source_session["reviewer_id"],
            "reviewed_at": source_session["reviewed_at"],
            "review_signoff_ids": list(CONTEXT_SIGNOFF_IDS),
            "status_history": _status_history(
                taxonomy_session["reviewed_at"],
                source_session["reviewed_at"],
                taxonomy_session["reviewer_id"],
                "context collector",
                "context taxonomy reviewer",
                "context source reviewer",
            ),
        }
        for field in ("active_span", "place_id", "place_kind", "historical_time_scope_required", "historical_time_scope"):
            if field in spec:
                context[field] = spec[field]
        claim = _claim_record(
            claim_id=claim_id,
            subject_id=context_id,
            predicate="context_classification",
            object_value={"value": spec["entity_type"], "datatype": "string", "precision": "not_applicable"},
            claim_text={
                "en": f"{spec['labels']['en']} is a reviewed {spec['entity_type'].replace('_', ' ')} context for MUSEUM-03B. {spec['scope_note']}",
                "zh-Hans": f"{spec['labels']['zh-Hans']}被审定为 MUSEUM-03B 的类型化艺术语境；该分类不表示历史接触、影响、传授或因果。",
            },
            temporal_description=spec["time_description"],
            applicability_scope=f"MUSEUM-03B internal reviewed context. {spec['scope_note']} Educational use: {spec['educational_value']}",
            evidence_id=evidence_id,
            candidate_at=taxonomy_session["reviewed_at"],
            reviewed_at=source_session["reviewed_at"],
            reviewer=source_session["reviewer_id"],
        )
        evidence_record = _evidence_record(
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_refs=source_refs,
            source_ids=source_ids,
            bindings=bindings,
            summary=(
                f"Reviewed typed context: {spec['labels']['en']}. {spec['scope_note']} "
                "Each cited field resolves to an exact selected object snapshot and registered source-rule scope."
            ),
            extracted_at=source_session["reviewed_at"],
        )
        contexts.append(context)
        claims.append(claim)
        evidence.append(evidence_record)
    return contexts, claims, evidence


def _build_dispositions(
    relationship_decisions: dict[str, Any],
    lead_closure: dict[str, Any],
) -> list[dict[str, Any]]:
    reviewer = relationship_decisions["review_sessions"]["relationship_reviewer"]["reviewer_id"]
    records: list[dict[str, Any]] = []
    for entry in lead_closure["entries"]:
        lead_id = entry["lead_id"]
        disposition = entry["disposition"]
        # A superseded lead points to the replacement lead, not directly to a
        # formal record. This follows the canonical disposition schema even
        # though the research closure also carries a convenience formal ID.
        formal_relationship_id = entry.get("formal_relationship_id") if disposition == "promoted_to_formal_relationship" else None
        evidence_gaps = []
        if disposition == "retained_for_more_evidence":
            evidence_gaps = ["Exact overlapping place-and-time evidence remains unresolved."]
        records.append({
            "schema_version": "1.0.0",
            "id": f"relationship-disposition:inherited-{lead_id.split(':', 1)[1]}",
            "entity_type": "relationship_research_disposition",
            "phase_id": PHASE_ID,
            "batch_id": BATCH_ID,
            "origin_kind": "inherited_lead",
            "lead_id": lead_id,
            "research_candidate_id": None,
            "disposition": disposition,
            "formal_relationship_id": formal_relationship_id,
            "superseded_by_lead_id": entry.get("superseded_by_lead_id") if disposition == "superseded" else None,
            "evidence_gaps": evidence_gaps,
            "rationale": entry["rationale"],
            "reviewed_by": reviewer,
            "reviewed_at": lead_closure["generated_at"],
            "review_signoff_id": DISPOSITION_SIGNOFF_ID,
            "data_version": "1.0.0",
        })
    for decision in relationship_decisions["decisions"]:
        origin = decision["origin"]
        if origin["kind"] != "curated_new":
            continue
        candidate_id = origin["curated_candidate_id"]
        records.append({
            "schema_version": "1.0.0",
            "id": f"relationship-disposition:{candidate_id.split(':', 1)[1]}",
            "entity_type": "relationship_research_disposition",
            "phase_id": PHASE_ID,
            "batch_id": BATCH_ID,
            "origin_kind": "new_curated_candidate",
            "lead_id": None,
            "research_candidate_id": candidate_id,
            "disposition": "promoted_to_formal_relationship",
            "formal_relationship_id": decision["relationship_id"],
            "superseded_by_lead_id": None,
            "evidence_gaps": [],
            "rationale": decision["rationale"],
            "reviewed_by": reviewer,
            "reviewed_at": relationship_decisions["generated_at"],
            "review_signoff_id": DISPOSITION_SIGNOFF_ID,
            "data_version": "1.0.0",
        })
    if len(records) != 69:
        raise PipelineError("relationship_disposition_count_mismatch", "Expected 45 inherited and 24 new candidate dispositions")
    return records


def _build_relationship_records(
    relationship_decisions: dict[str, Any],
    artists: Sequence[dict[str, Any]],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
    binding_index: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    artist_by_id = {artist["id"]: artist for artist in artists}
    relationship_session = relationship_decisions["review_sessions"]["relationship_reviewer"]
    source_session = relationship_decisions["review_sessions"]["source_reviewer"]
    relationships: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for decision in relationship_decisions["decisions"]:
        relationship_id = decision["relationship_id"]
        suffix = relationship_id.split(":", 1)[1]
        claim_id = f"claim:relationship-{suffix}"
        evidence_id = f"evidence:relationship-{suffix}"
        origin = decision["origin"]
        if origin["kind"] == "inherited_lead":
            disposition_id = f"relationship-disposition:inherited-{origin['inherited_lead_id'].split(':', 1)[1]}"
        else:
            disposition_id = f"relationship-disposition:{origin['curated_candidate_id'].split(':', 1)[1]}"
        source_refs = _validated_source_refs(decision["evidence_bindings"], receipt_index)
        source_ids, bindings = _source_closure(source_refs, binding_index)
        source_artist = artist_by_id[decision["source_artist_id"]]
        target_artist = artist_by_id[decision["target_artist_id"]]
        context_labels = ", ".join(context_id.replace(":", " ").replace("-", " ") for context_id in decision["context_entity_ids"])
        relationship = {
            "schema_version": "1.0.0",
            "id": relationship_id,
            "entity_type": "relationship",
            "branch_id": "art",
            "phase_id": PHASE_ID,
            "research_disposition_id": disposition_id,
            "generation_method": "reviewed_curatorial_synthesis",
            "relationship_type": decision["relationship_type"],
            "relationship_semantics": "curatorial_comparison",
            "source_entity_id": decision["source_artist_id"],
            "target_entity_id": decision["target_artist_id"],
            "directed": False,
            "temporal_scope": _unknown_span("Comparison is bounded to the cited object records; no shared historical interval is asserted."),
            "place_scope": {"place_ids": [], "description": "No shared historical place is asserted by this C-level curatorial comparison."},
            "evidence_level": "C",
            "historical_relationship_strength": None,
            "evidence_confidence": decision["evidence_confidence"],
            "computational_similarity": None,
            "curatorial_relevance": decision["curatorial_relevance"],
            "context_entity_ids": decision["context_entity_ids"],
            "claim_ids": [claim_id],
            "source_ids": source_ids,
            "source_license_bindings": bindings,
            "curatorial_note": {
                "en": f"{decision['rationale']} {decision['wording_restriction']}",
                "zh-Hans": "本记录仅表示以所选官方作品记录为依据的策展比较；不表示接触、影响、传播、师承或因果关系。",
            },
            "educational_rationale": {
                "en": f"{decision['educational_value']} The comparison is limited to the reviewed {context_labels} context.",
                "zh-Hans": "通过明确标注的材质、技法或题材语境比较所选作品，同时保持非因果、非影响关系的边界。",
            },
            "public_display": False,
            "is_algorithmic": False,
            "review_status": "reviewed",
            "reviewed_by": relationship_session["reviewer_id"],
            "reviewed_at": source_session["reviewed_at"][:10],
            "review_signoff_ids": list(RELATIONSHIP_SIGNOFF_IDS),
            "status_history": _status_history(
                relationship_session["reviewed_at"],
                source_session["reviewed_at"],
                relationship_session["reviewer_id"],
                "relationship researcher",
                "relationship semantics reviewer",
                "relationship evidence reviewer",
            ),
            "lifecycle_status": "reviewed",
            "data_version": "1.0.0",
        }
        source_en = source_artist["labels"].get("en", decision["source_artist_id"])
        target_en = target_artist["labels"].get("en", decision["target_artist_id"])
        source_zh = source_artist["labels"].get("zh-Hans", source_en)
        target_zh = target_artist["labels"].get("zh-Hans", target_en)
        claim = _claim_record(
            claim_id=claim_id,
            subject_id=decision["source_artist_id"],
            predicate=decision["relationship_type"],
            object_value={"entity_id": decision["target_artist_id"]},
            claim_text={
                "en": (
                    f"Within the selected official object records, {source_en} and {target_en} form a reviewed, non-causal "
                    f"{decision['relationship_type'].replace('_', ' ')} comparison through {context_labels}."
                ),
                "zh-Hans": f"在所选官方作品记录范围内，{source_zh}与{target_zh}仅构成经审核的非因果策展比较。",
            },
            temporal_description="No shared historical interval is asserted; only the cited object records are in scope.",
            applicability_scope=f"MUSEUM-03B internal C-level curatorial comparison. {decision['wording_restriction']}",
            evidence_id=evidence_id,
            candidate_at=relationship_session["reviewed_at"],
            reviewed_at=source_session["reviewed_at"],
            reviewer=source_session["reviewer_id"],
        )
        evidence_record = _evidence_record(
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_refs=source_refs,
            source_ids=source_ids,
            bindings=bindings,
            summary=(
                f"{decision['rationale']} The comparison is restricted to the exact official object fields and reviewed contexts. "
                f"{decision['wording_restriction']}"
            ),
            extracted_at=source_session["reviewed_at"],
        )
        relationships.append(relationship)
        claims.append(claim)
        evidence.append(evidence_record)
    return relationships, claims, evidence


def _build_signoffs(
    context_decisions: dict[str, Any],
    relationship_decisions: dict[str, Any],
    lead_closure: dict[str, Any],
    contexts: Sequence[dict[str, Any]],
    context_claims: Sequence[dict[str, Any]],
    context_evidence: Sequence[dict[str, Any]],
    relationships: Sequence[dict[str, Any]],
    relationship_claims: Sequence[dict[str, Any]],
    relationship_evidence: Sequence[dict[str, Any]],
    dispositions: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    context_session = context_decisions["review_sessions"]["context_reviewer"]
    context_source_session = context_decisions["review_sessions"]["source_reviewer"]
    relationship_session = relationship_decisions["review_sessions"]["relationship_reviewer"]
    relationship_source_session = relationship_decisions["review_sessions"]["source_reviewer"]
    return [
        _signoff(
            signoff_id=CONTEXT_SIGNOFF_IDS[0],
            role="art_history_reviewer",
            session=context_session,
            record_ids=[*[item["id"] for item in contexts], *[item["id"] for item in context_claims]],
            checklist=[
                _check("typed_context_scope", "pass", "All 31 contexts are typed, sourced, and required by artworks or formal relationships."),
                _check("no_causal_context_semantics", "pass", "Context labels are not converted into contact, influence, or transmission claims."),
            ],
            authority="Finalized MUSEUM-03B context decision set and exact approved artwork selection basis.",
        ),
        _signoff(
            signoff_id=CONTEXT_SIGNOFF_IDS[1],
            role="data_reviewer",
            session=context_source_session,
            record_ids=[item["id"] for item in context_evidence],
            checklist=[
                _check("snapshot_hash_closure", "pass", "Every context Evidence record resolves exact raw snapshot hashes and locators."),
                _check("source_rule_binding_closure", "pass", "Every context Source ID has an exact copied artwork source-rule binding."),
            ],
            authority="Finalized MUSEUM-03B context source review and verified artwork snapshot receipt ledger.",
        ),
        _signoff(
            signoff_id=RELATIONSHIP_SIGNOFF_IDS[0],
            role="relationship_reviewer",
            session=relationship_session,
            record_ids=[*[item["id"] for item in relationships], *[item["id"] for item in relationship_claims]],
            checklist=[
                _check("c_level_only", "pass", "All 36 formal records are undirected C-level curatorial comparisons."),
                _check("no_algorithmic_or_causal_generation", "pass", "No all-pairs, computational, influence, self, or inverse-duplicate relation is present."),
                _check(
                    "no_unproven_historical_levels",
                    "pass",
                    "No direct or contextual historical evidence sufficient for A/B was accepted; zero A/B is conservative, not quota filling.",
                ),
            ],
            authority="Finalized MUSEUM-03B relationship decision set.",
        ),
        _signoff(
            signoff_id=RELATIONSHIP_SIGNOFF_IDS[1],
            role="data_reviewer",
            session=relationship_source_session,
            record_ids=[item["id"] for item in relationship_evidence],
            checklist=[
                _check("two_object_evidence", "pass", "Each relationship binds the two exact reviewed official object examples named by research."),
                _check("claim_evidence_source_backlinks", "pass", "Claim, Evidence, Source, snapshot, and source-rule backlinks are closed."),
            ],
            authority="Finalized MUSEUM-03B relationship evidence review and verified artwork output.",
        ),
        {
            "schema_version": "1.0.0",
            "id": DISPOSITION_SIGNOFF_ID,
            "entity_type": "review_signoff",
            "record_ids": [item["id"] for item in dispositions],
            "review_role": "relationship_reviewer",
            "reviewer_id": relationship_session["reviewer_id"],
            "reviewer_kind": relationship_session["reviewer_kind"],
            "single_operator_multi_role": True,
            "reviewed_at": lead_closure["generated_at"],
            "checklist": [
                _check("inherited_lead_closure", "pass", "All 45 inherited lead IDs retain their tracked dispositions."),
                _check("new_candidate_origin_honesty", "pass", "All 24 new candidates use research_candidate_id and do not mint inherited lead IDs."),
            ],
            "decision": "accepted_reviewed",
            "decision_note": "Accepted 69 schema-valid research dispositions with honest inherited/new origin separation.",
            "authority_basis": "Finalized MUSEUM-03B relationship lead closure and relationship decision set.",
            "data_version": "1.0.0",
        },
    ]


def _claim_record(
    *,
    claim_id: str,
    subject_id: str,
    predicate: str,
    object_value: dict[str, Any],
    claim_text: dict[str, str],
    temporal_description: str,
    applicability_scope: str,
    evidence_id: str,
    candidate_at: str,
    reviewed_at: str,
    reviewer: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": claim_id,
        "entity_type": "claim",
        "subject_id": subject_id,
        "predicate": predicate,
        "object": object_value,
        "claim_text": claim_text,
        "temporal_scope": _unknown_span(temporal_description),
        "applicability_scope": applicability_scope,
        "evidence_ids": [evidence_id],
        "counter_evidence_ids": [],
        "status": "reviewed",
        "status_history": _status_history(
            candidate_at,
            reviewed_at,
            reviewer,
            "collector",
            "source reviewer",
            "discipline reviewer",
        ),
        "disputed": False,
        "dispute_note": None,
        "no_counter_evidence_reason": None,
        "dispute_display": "not_disputed",
        "review": {
            "reviewer": reviewer,
            "reviewed_at": reviewed_at[:10],
            "decision_note": "Accepted for internal reviewed use only; no verified, publishable, or published promotion.",
        },
        "publish_status": "not_public",
        "supersedes": None,
        "data_version": "1.0.0",
    }


def _evidence_record(
    *,
    evidence_id: str,
    claim_id: str,
    source_refs: Sequence[dict[str, Any]],
    source_ids: list[str],
    bindings: list[dict[str, Any]],
    summary: str,
    extracted_at: str,
) -> dict[str, Any]:
    raw_refs = []
    for ref in source_refs:
        for raw_locator in ref["raw_locators"]:
            raw_refs.append({
                "snapshot_id": ref["snapshot_id"],
                "body_sha256": ref["snapshot_sha256"],
                "source_object_id": ref["source_object_id"],
                "raw_locator": raw_locator,
            })
    raw_refs = _dedupe_records(raw_refs)
    object_ids = _dedupe([ref["source_object_id"] for ref in source_refs])
    return {
        "schema_version": "1.1.0",
        "id": evidence_id,
        "entity_type": "evidence",
        "claim_ids": [claim_id],
        "stance": "supports",
        "evidence_kind": "curatorial_assessment",
        "source_ids": source_ids,
        "source_license_bindings": bindings,
        "locator": {
            "record_id": " + ".join(object_ids),
            "section": "project-reviewed synthesis from the exact raw locators in raw_snapshot_refs",
        },
        "summary": summary,
        "short_excerpt": None,
        "raw_snapshot_refs": raw_refs,
        "original_language": "und",
        "extracted_at": extracted_at,
        "extraction_method": "manual",
        "reliability_note": (
            "This bounded reviewed synthesis preserves official-field precision and does not convert material, technique, subject, "
            "institution, place, visual, or computational similarity into historical influence."
        ),
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
    }


def _source_closure(
    source_refs: Sequence[dict[str, Any]],
    binding_index: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[str], list[dict[str, Any]]]:
    source_ids = _dedupe([SOURCE_RECORD_IDS[ref["source_key"]] for ref in source_refs])
    bindings: list[dict[str, Any]] = []
    for ref in source_refs:
        key = (ref["source_key"], ref["source_object_id"])
        object_bindings = binding_index.get(key)
        if not object_bindings:
            raise PipelineError("artwork_source_binding_missing", f"No artwork source binding for {key[0]}:{key[1]}")
        bindings.extend(object_bindings)
    bindings = _dedupe_records(bindings)
    if {binding["source_id"] for binding in bindings} != set(source_ids):
        raise PipelineError("source_binding_closure_mismatch", "Source IDs and exact source-rule bindings differ")
    return source_ids, bindings


def _validated_source_refs(
    refs: Sequence[dict[str, Any]],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ref in refs:
        source_key = ref.get("source_key")
        object_id = str(ref.get("source_object_id"))
        key = (source_key, object_id)
        if source_key not in SOURCE_RECORD_IDS or key not in receipt_index:
            raise PipelineError("research_source_snapshot_missing", f"Research source snapshot cannot resolve: {source_key}:{object_id}")
        receipt = receipt_index[key]
        snapshot_sha256 = ref.get("snapshot_sha256")
        if snapshot_sha256 != receipt.get("body_sha256"):
            raise PipelineError("research_source_snapshot_hash_mismatch", f"Research snapshot hash differs: {source_key}:{object_id}")
        raw_locators = ref.get("raw_locators")
        if not isinstance(raw_locators, list) or not raw_locators or any(not isinstance(value, str) or not value for value in raw_locators):
            raise PipelineError("research_raw_locator_missing", f"Research raw locators are missing: {source_key}:{object_id}")
        result.append({
            **ref,
            "source_key": source_key,
            "source_object_id": object_id,
            "snapshot_sha256": snapshot_sha256,
            "snapshot_id": receipt["snapshot_id"],
            "raw_locators": list(raw_locators),
        })
    return result


def _selection_context_refs(
    context_id: str,
    selection: dict[str, Any],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for entry in selection["entries"]:
        if not any(context_id in entry[field] for field in ("material_ids", "technique_ids", "subject_ids")):
            continue
        source_key = entry["source_id"]
        object_id = str(entry["source_object_id"])
        receipt = receipt_index[(source_key, object_id)]
        refs.append({
            "source_key": source_key,
            "source_object_id": object_id,
            "snapshot_sha256": receipt["body_sha256"],
            "raw_locators": (
                ["/medium", "/objectDate"]
                if source_key == "met_open_access"
                else ["/data/medium_display", "/data/date_display"]
            ),
            "evidence_note": "Official medium and display-date fields support this bounded artwork classification.",
        })
    if not refs:
        raise PipelineError("artwork_context_source_missing", f"No selected object supports {context_id}")
    return refs


def _institution_source_ref(
    source_key: str,
    entry: dict[str, Any],
    receipt_index: Mapping[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    object_id = str(entry["source_object_id"])
    receipt = receipt_index[(source_key, object_id)]
    return {
        "source_key": source_key,
        "source_object_id": object_id,
        "snapshot_sha256": receipt["body_sha256"],
        "raw_locators": ["/repository"] if source_key == "met_open_access" else ["/data/api_link", "/config/website_url"],
        "evidence_note": "Official collection source identity is used only for the typed holding-institution and operational city link.",
    }


def _status_history(
    candidate_at: str,
    reviewed_at: str,
    reviewer: str,
    candidate_role: str,
    sourced_role: str,
    reviewed_role: str,
) -> list[dict[str, Any]]:
    return [
        {
            "from": None,
            "to": "candidate",
            "changed_at": candidate_at,
            "changed_by": reviewer,
            "role": candidate_role,
            "reason": "Created from the exact finalized MUSEUM-03B research decision and selected records.",
        },
        {
            "from": "candidate",
            "to": "sourced",
            "changed_at": reviewed_at,
            "changed_by": reviewer,
            "role": sourced_role,
            "reason": "Claim, Evidence, Source, raw snapshot, and source-rule references were closed.",
        },
        {
            "from": "sourced",
            "to": "reviewed",
            "changed_at": reviewed_at,
            "changed_by": reviewer,
            "role": reviewed_role,
            "reason": "Accepted for internal reviewed use without verified, publishable, or published promotion.",
        },
    ]


def _signoff(
    *,
    signoff_id: str,
    role: str,
    session: dict[str, Any],
    record_ids: list[str],
    checklist: list[dict[str, str]],
    authority: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": signoff_id,
        "entity_type": "review_signoff",
        "record_ids": record_ids,
        "review_role": role,
        "reviewer_id": session["reviewer_id"],
        "reviewer_kind": session["reviewer_kind"],
        "single_operator_multi_role": True,
        "reviewed_at": session["reviewed_at"],
        "checklist": checklist,
        "decision": session["decision"],
        "decision_note": session["decision_note"],
        "authority_basis": authority,
        "data_version": "1.0.0",
    }


def _validate_generated_records(
    result: dict[str, Any],
    sources: Sequence[dict[str, Any]],
    artists: Sequence[dict[str, Any]],
) -> None:
    records = [
        *result["contexts"],
        *result["claims"],
        *result["evidence"],
        *result["relationships"],
        *result["dispositions"],
        *result["signoffs"],
    ]
    environment = load_schema_environment()
    for record in records:
        issues = validate_record(record, environment=environment)
        if issues:
            first = issues[0]
            raise PipelineError(
                "relationship_stage_schema_invalid",
                f"{record.get('id')} failed canonical validation at {first.location}: {first.message}",
            )

    indexed = {
        item["id"]: item
        for item in [*sources, *artists, *records]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    expected_record_ids = set(indexed)
    for claim in result["claims"]:
        if claim["subject_id"] not in indexed:
            raise PipelineError("generated_claim_subject_missing", f"Claim subject is absent: {claim['id']}")
        for evidence_id in claim["evidence_ids"]:
            evidence = indexed.get(evidence_id)
            if evidence is None or claim["id"] not in evidence.get("claim_ids", []):
                raise PipelineError("generated_claim_evidence_closure_mismatch", f"Claim/Evidence backlink differs: {claim['id']}")
    context_by_id = {item["id"]: item for item in result["contexts"]}
    disposition_by_id = {item["id"]: item for item in result["dispositions"]}
    for relationship in result["relationships"]:
        if relationship["source_entity_id"] not in indexed or relationship["target_entity_id"] not in indexed:
            raise PipelineError("generated_relationship_endpoint_missing", f"Relationship endpoint is absent: {relationship['id']}")
        if not set(relationship["context_entity_ids"]) <= set(context_by_id):
            raise PipelineError("generated_relationship_context_missing", f"Relationship context is absent: {relationship['id']}")
        if relationship["research_disposition_id"] not in disposition_by_id:
            raise PipelineError("generated_relationship_disposition_missing", f"Relationship disposition is absent: {relationship['id']}")
    for context in result["contexts"]:
        if context["entity_type"] == "museum_institution" and context["place_id"] not in context_by_id:
            raise PipelineError("generated_institution_place_missing", f"Institution place is absent: {context['id']}")
    for signoff in result["signoffs"]:
        missing = set(signoff["record_ids"]) - expected_record_ids
        if missing:
            raise PipelineError("generated_signoff_record_missing", f"Sign-off references absent records: {sorted(missing)}")
    if any(
        record.get("lifecycle_status") in {"publishable", "published"}
        or record.get("review_status") in {"publishable", "published"}
        or record.get("publish_status") in {"publishable", "published"}
        for record in records
    ):
        raise PipelineError("relationship_stage_public_state_forbidden", "Relationship stage created a public-state record")
    if any(item.get("is_algorithmic") is not False or item.get("computational_similarity") is not None for item in result["relationships"]):
        raise PipelineError("relationship_stage_algorithmic_forbidden", "Relationship stage created algorithmic semantics")


def _artwork_payloads(stage: Mapping[str, Any]) -> Mapping[str, Any]:
    payloads = stage.get("payloads") if isinstance(stage, Mapping) else None
    if isinstance(payloads, Mapping):
        return payloads
    if isinstance(stage, Mapping):
        return stage
    raise PipelineError("artwork_stage_invalid", "Artwork stage must be a mapping or build_artwork_stage result")


def _payload_array(payloads: Mapping[str, Any], names: Iterable[str], code: str) -> list[dict[str, Any]]:
    for name in names:
        value = payloads.get(name)
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    raise PipelineError(code, f"Artwork stage is missing any of: {', '.join(names)}")


def _artwork_source_object(artwork: dict[str, Any]) -> tuple[str, str]:
    official = artwork.get("official_object_record") or {}
    canonical_source_id = official.get("source_id")
    object_id = official.get("source_object_id")
    branch = artwork.get("branch_extensions") or {}
    if canonical_source_id is None:
        source_ids = artwork.get("source_ids", [])
        canonical_source_id = source_ids[0] if len(source_ids) == 1 else None
    if object_id is None:
        object_id = branch.get("source_object_id")
    reverse_sources = {value: key for key, value in SOURCE_RECORD_IDS.items()}
    source_key = reverse_sources.get(canonical_source_id)
    if source_key is None or object_id is None:
        raise PipelineError("artwork_stage_source_object_missing", f"Artwork source/object cannot resolve: {artwork.get('id')}")
    return source_key, str(object_id)


def _receipt_index(ledger: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entries = ledger.get("entries")
    if not isinstance(entries, list) or len(entries) != 44:
        raise PipelineError("artwork_snapshot_ledger_count_mismatch", "Expected exactly 44 artwork snapshot receipts")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in entries:
        source_key = receipt.get("source_id")
        for source_object_id in receipt.get("source_object_ids", []):
            key = (source_key, str(source_object_id))
            if source_key not in SOURCE_RECORD_IDS or key in result:
                raise PipelineError("artwork_snapshot_ledger_duplicate", f"Duplicate or unknown receipt: {source_key}:{source_object_id}")
            result[key] = receipt
    if len(result) != 44:
        raise PipelineError("artwork_snapshot_ledger_object_count_mismatch", "Snapshot ledger must resolve exactly 44 source objects")
    return result


def _load_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(code, f"Cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise PipelineError(code, f"Expected JSON object: {path}")
    return value


def _load_array(path: Path, code: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(code, f"Cannot read JSON array: {path}") from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise PipelineError(code, f"Expected JSON object array: {path}")
    return value


def _require_content_hash(document: dict[str, Any], label: str) -> None:
    expected = canonical_sha256({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected:
        raise PipelineError("research_content_hash_mismatch", f"{label} content hash does not match canonical bytes")


def _unique_index(records: Sequence[dict[str, Any]], entity_type: str, code: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if record.get("entity_type") != entity_type or not isinstance(record_id, str) or record_id in result:
            raise PipelineError(code, f"Invalid or duplicate {entity_type} record: {record_id}")
        result[record_id] = record
    return result


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        marker = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if marker not in seen:
            seen.add(marker)
            result.append(record)
    return result


def _unknown_span(description: str) -> dict[str, Any]:
    return {"start": None, "end": None, "precision": "unknown", "uncertain": True, "description": description}


def _check(check: str, result: str, note: str) -> dict[str, str]:
    return {"check": check, "result": result, "note": note}
