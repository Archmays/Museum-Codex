from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from museum_pipeline.adapters import get_adapter
from museum_pipeline.art.batch_validation import DEFAULT_PACKAGE, validate_approved_batch
from museum_pipeline.art.leakage import build_public_leakage_label_set
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import (
    ROOT,
    license_rules_snapshot_hash,
    source_registry_snapshot_hash,
)
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.validation.dispatch import canonical_schema_path, load_schema_environment, validate_record


BATCH_ID = "art-batch:museum-03b-first-slate-v1"
GRAPH_ID = "graph-input:museum-03b-first-slate-v1"
FORMAL_MANIFEST_ID = "art-batch-manifest:museum-03b-first-slate-v1"
PACKAGE_MANIFEST_ID = "reviewed-package-manifest:museum-03b-first-slate-v1"

DEFAULT_DECISION = ROOT / "governance" / "decisions" / "museum-03b-selection-decision.json"
DEFAULT_APPLICATION = ROOT / "governance" / "decisions" / "museum-03b-selection-application.json"
DEFAULT_IDENTITY_SEED = ROOT / "research" / "art" / "museum-03b-identity-decisions.json"
DEFAULT_IDENTITY_BASIS = ROOT / "research" / "art" / "museum-03b-approved-identity-basis.json"
DEFAULT_ARTWORK_BASIS = ROOT / "research" / "art" / "museum-03b-artwork-selection-basis.json"
DEFAULT_ARTWORK_SNAPSHOTS = ROOT / "research" / "art" / "museum-03b-artwork-snapshot-receipts.json"
DEFAULT_RELATIONSHIP_DECISIONS = ROOT / "research" / "art" / "museum-03b-relationship-decisions.json"
DEFAULT_RELATIONSHIP_LEAD_CLOSURE = ROOT / "research" / "art" / "museum-03b-relationship-lead-closure.json"
DEFAULT_BATCH_REVIEW_SIGNOFFS = ROOT / "research" / "art" / "museum-03b-batch-review-signoffs.json"

EXPECTED_BATCH_REVIEW_SET_CONTENT_HASH = "sha256:56bc78aab591f82c566e369e0c2a0104237d982ca23d4c2d66db14d1e1713761"

_COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")
_CONTEXT_TYPES = {
    "art_movement",
    "art_group",
    "museum_institution",
    "organization",
    "place",
    "exhibition",
    "exhibition_event",
    "material",
    "technique",
    "subject",
    "time_period",
    "person",
}
_ADAPTER_IDS = {
    "source:aic_api": "aic_artwork_fields_adapter",
    "source:getty_ulan": "getty_ulan_record_adapter",
    "source:met_open_access": "met_collection_object_adapter",
    "source:wikidata": "wikidata_entity_adapter",
}
_BATCH_SIGNOFF_IDS = (
    "review-signoff:museum-03b-batch-data",
    "review-signoff:museum-03b-batch-relationship",
    "review-signoff:museum-03b-batch-release",
)
_IMPLEMENTATION_INPUT_PATHS = (
    "museum_pipeline/art/batch.py",
    "museum_pipeline/art/batch_validation.py",
    "museum_pipeline/art/identity.py",
    "museum_pipeline/art/artworks.py",
    "museum_pipeline/art/relationships.py",
    "museum_pipeline/art/leakage.py",
    "museum_pipeline/art/contract_validation.py",
    "museum_pipeline/validation/dispatch.py",
    "schemas/schema-manifest.json",
    "research/art/museum-03b-batch-review-signoffs.json",
)


def build_approved_batch(
    *,
    code_commit: str,
    output_dir: Path = DEFAULT_PACKAGE,
    components: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build and atomically seal the reviewed MUSEUM-03B package.

    Production calls the deterministic identity, artwork, and relationship
    builders. Tests may inject the same component contract without touching
    raw snapshots. The output is never promoted to a public or published path.
    """

    if not _COMMIT_RE.fullmatch(code_commit):
        raise PipelineError("code_commit_invalid", "code_commit must be an exact lowercase 40-character Git commit")
    _verify_code_commit(code_commit)
    output_dir = _resolve(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir.parent / f".{output_dir.name}.lock"

    with _exclusive_lock(lock_path):
        with tempfile.TemporaryDirectory(prefix=".museum-03b-batch-", dir=output_dir.parent) as temporary:
            workspace = Path(temporary)
            raw_components = (
                _production_components(workspace / "component-stages")
                if components is None
                else deepcopy(components)
            )
            normalized = _normalize_components(raw_components)
            _preflight_exact_batch(normalized)
            review_set, batch_signoffs = _load_batch_review_signoffs(normalized)
            normalized["signoffs"] = _deduplicate_records(
                [*normalized["signoffs"], *batch_signoffs],
                collection="signoffs",
            )
            timestamp = generated_at or _deterministic_generated_at(normalized)
            formal_artwork_basis = build_artwork_selection_basis(
                research_basis=normalized["artwork_research_basis"],
                artworks=normalized["artworks"],
                approved_artist_ids=[item["artist_id"] for item in normalized["identity_basis"]["bindings"]],
                selection_application_id=normalized["application"]["id"],
                review_signoff_ids=["review-signoff:museum-03b-batch-data"],
                generated_at=timestamp,
            )
            _validate_batch_review_basis(review_set, normalized, formal_artwork_basis)
            graph = build_graph_input(
                artists=normalized["artists"],
                contexts=normalized["contexts"],
                relationships=normalized["relationships"],
                claims=normalized["claims"],
                evidence=normalized["evidence"],
                sources=normalized["sources"],
                review_signoff_ids=[
                    "review-signoff:museum-03b-batch-data",
                    "review-signoff:museum-03b-batch-relationship",
                ],
                generated_at=timestamp,
                batch_id=BATCH_ID,
            )
            formal_manifest = build_formal_batch_manifest(
                components=normalized,
                code_commit=code_commit,
                reviewer_signoff_ids=[
                    "review-signoff:museum-03b-batch-data",
                    "review-signoff:museum-03b-batch-release",
                ],
                generated_at=timestamp,
            )
            identity_seed = raw_components.get("identity_seed")
            if not isinstance(identity_seed, dict):
                identity_seed = {
                    "batch_id": BATCH_ID,
                    "artists": [
                        {
                            "labels": artist.get("labels", {}),
                            "aliases": artist.get("aliases", []),
                        }
                        for artist in normalized["artists"]
                    ],
                }
            formal_records = [
                normalized["decision"],
                normalized["application"],
                normalized["identity_basis"],
                formal_artwork_basis,
                *normalized["snapshot_receipt_ledgers"],
                *normalized["artists"],
                *normalized["artworks"],
                *normalized["contexts"],
                *normalized["relationships"],
                *normalized["claims"],
                *normalized["evidence"],
                *normalized["sources"],
                *normalized["media_assessments"],
                *normalized["relationship_dispositions"],
                *normalized["signoffs"],
                graph,
                formal_manifest,
            ]
            normalized["leakage_label_set"] = build_public_leakage_label_set(
                identity_seed=identity_seed,
                identity_basis=normalized["identity_basis"],
                application=normalized["application"],
                formal_records=formal_records,
            )

            documents = _package_documents(normalized, formal_artwork_basis, graph, formal_manifest)
            staged_package = workspace / "package-v1"
            staged_package.mkdir()
            file_entries = _write_documents(staged_package, documents)
            package_manifest = _reviewed_package_manifest(
                file_entries=file_entries,
                reviewer_signoff_ids=["review-signoff:museum-03b-batch-release"],
                generated_at=timestamp,
            )
            (staged_package / "package-manifest.json").write_bytes(canonical_json_bytes(package_manifest))

            staged_validation = validate_approved_batch(staged_package)
            if not staged_validation["ok"]:
                codes = ", ".join(item["code"] for item in staged_validation["failures"][:12])
                raise PipelineError("approved_batch_validation_failed", f"Staged reviewed batch failed validation: {codes}")

            reused = _publish_directory(staged_package, output_dir)
            final_validation = validate_approved_batch(output_dir)
            if not final_validation["ok"]:
                codes = ", ".join(item["code"] for item in final_validation["failures"][:12])
                raise PipelineError("approved_batch_validation_failed", f"Published reviewed directory failed validation: {codes}")
            return {
                "ok": True,
                "phase_id": "MUSEUM-03B",
                "batch_id": BATCH_ID,
                "output_dir": _display_path(output_dir),
                "code_commit": code_commit,
                "written": not reused,
                "reused": reused,
                "declared_file_count": len(file_entries),
                "package_content_hash": package_manifest["content_hash"],
                "counts": final_validation["counts"],
                "summary": "sealed internal reviewed package built with no media bytes and no public release",
            }


def build_graph_input(
    *,
    artists: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    review_signoff_ids: list[str],
    generated_at: str,
    batch_id: str = BATCH_ID,
) -> dict[str, Any]:
    """Create the static artist/context/relationship graph input."""

    artists = sorted(artists, key=_record_id)
    contexts = sorted(contexts, key=_record_id)
    relationships = sorted(relationships, key=_record_id)
    claim_index = {item["id"]: item for item in claims}
    evidence_index = {item["id"]: item for item in evidence}

    graph_claim_ids = {
        claim_id
        for item in [*artists, *contexts, *relationships]
        for claim_id in item.get("claim_ids", [])
    }
    graph_evidence_ids = {
        evidence_id
        for claim_id in graph_claim_ids
        for evidence_id in claim_index.get(claim_id, {}).get("evidence_ids", [])
    }
    graph_evidence_ids.update(
        evidence_id
        for relationship in relationships
        for evidence_id in relationship.get("evidence_ids", [])
    )
    graph_source_ids = {
        source_id
        for item in [*artists, *contexts, *relationships]
        for source_id in item.get("source_ids", [])
    }
    graph_source_ids.update(
        source_id
        for evidence_id in graph_evidence_ids
        for source_id in evidence_index.get(evidence_id, {}).get("source_ids", [])
    )
    known_source_ids = {item["id"] for item in sources}
    graph_source_ids &= known_source_ids

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": GRAPH_ID,
        "entity_type": "graph_input",
        "phase_id": "MUSEUM-03B",
        "batch_id": batch_id,
        "approved_artist_ids": [item["id"] for item in artists],
        "primary_nodes": [
            {
                "artist_id": item["id"],
                "node_role": "primary_artist",
                "labels": item["labels"],
                "claim_ids": sorted(item.get("claim_ids", [])),
                "filter_values": [],
            }
            for item in artists
        ],
        "context_nodes": [
            {
                "context_id": item["id"],
                "entity_type": item["entity_type"],
                "node_role": "supporting_context",
                "labels": item["labels"],
                "claim_ids": sorted(item.get("claim_ids", [])),
                "filter_values": [{"key": "context_type", "value": item["entity_type"]}],
            }
            for item in contexts
        ],
        "edges": [_graph_edge(item, claim_index) for item in relationships],
        "claim_ids": sorted(graph_claim_ids),
        "evidence_ids": sorted(graph_evidence_ids),
        "source_ids": sorted(graph_source_ids),
        "review_signoff_ids": sorted(review_signoff_ids),
        "no_auto_replacement": True,
        "no_algorithmic_edges": True,
        "no_media_dependency": True,
        "public_release": False,
        "review_status": "reviewed",
        "generated_at": generated_at,
        "data_version": "1.0.0",
    }
    payload["content_hash"] = canonical_sha256(payload)
    return payload


def build_artwork_selection_basis(
    *,
    research_basis: dict[str, Any],
    artworks: list[dict[str, Any]],
    approved_artist_ids: list[str],
    selection_application_id: str,
    review_signoff_ids: list[str],
    generated_at: str,
) -> dict[str, Any]:
    """Project the rich research ledger into the canonical formal contract."""

    artwork_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for artwork in artworks:
        official = artwork.get("official_object_record") or {}
        source_id = official.get("source_id") or (artwork.get("source_ids") or [None])[0]
        source_object_id = official.get("source_object_id")
        if source_object_id is None:
            source_object_id = (artwork.get("branch_extensions") or {}).get("source_object_id")
        key = (str(artwork.get("approved_artist_id") or (artwork.get("branch_extensions") or {}).get("approved_artist_id")), str(source_id), str(source_object_id))
        if key in artwork_index:
            raise PipelineError("artwork_selection_projection_duplicate", f"Duplicate formal artwork key: {key}")
        artwork_index[key] = artwork

    selections: list[dict[str, Any]] = []
    for entry in research_basis.get("entries", []):
        source_id = "source:" + str(entry["source_id"])
        key = (str(entry["approved_artist_id"]), source_id, str(entry["source_object_id"]))
        artwork = artwork_index.get(key)
        if artwork is None:
            raise PipelineError("artwork_selection_projection_missing", f"No formal artwork resolves research selection {key}")
        official = artwork.get("official_object_record") or {}
        official_url = official.get("official_object_url") or (artwork.get("branch_extensions") or {}).get("source_object_url")
        considerations = ["official_object_record"]
        if entry.get("creation_span", {}).get("precision") != "unknown":
            considerations.append("career_stage")
        if entry.get("material_ids") or entry.get("technique_ids"):
            considerations.append("medium_or_material")
        if entry.get("subject_ids"):
            considerations.append("subject")
        considerations.extend(["comparative_question", "rights_readiness"])
        selections.append(
            {
                "artwork_id": artwork["id"],
                "approved_artist_id": entry["approved_artist_id"],
                "source_id": source_id,
                "source_object_id": str(entry["source_object_id"]),
                "official_object_url": official_url,
                "selection_considerations": considerations,
                "selection_rationale": entry["selection_note"],
                "rights_preflight_id": entry["rights_preflight_id"],
            }
        )
    if len(selections) != 44 or len(artwork_index) != 44:
        raise PipelineError("artwork_selection_projection_count", "Formal artwork-selection projection must close exactly 44 artworks")
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": "artwork-selection-basis:museum-03b-first-slate-v1",
        "entity_type": "artwork_selection_basis",
        "phase_id": "MUSEUM-03B",
        "batch_id": BATCH_ID,
        "selection_application_id": selection_application_id,
        "approved_artist_ids": approved_artist_ids,
        "nominal_target": 44,
        "acceptable_range": {"minimum": 36, "maximum": 48},
        "minimum_per_artist": 2,
        "selections": selections,
        "review_signoff_ids": sorted(review_signoff_ids),
        "generated_at": generated_at,
        "data_version": "1.0.0",
    }
    payload["content_hash"] = canonical_sha256(payload)
    return payload


def build_formal_batch_manifest(
    *,
    components: dict[str, Any],
    code_commit: str,
    reviewer_signoff_ids: list[str],
    generated_at: str,
) -> dict[str, Any]:
    """Create the logical manifest that closes the reviewed batch records."""

    arrays = {
        key: sorted(components[key], key=_record_id)
        for key in (
            "artists",
            "artworks",
            "contexts",
            "relationships",
            "claims",
            "evidence",
            "sources",
            "media_assessments",
            "signoffs",
        )
    }
    snapshots = _snapshot_declarations(components["snapshot_receipt_ledgers"])
    normalized_ids = sorted(
        item["id"]
        for key in ("artists", "artworks", "contexts", "relationships")
        for item in arrays[key]
    )
    exclusions = _formal_exclusions(components["artwork_research_basis"])
    adapter_versions = [
        {
            "source_id": source["id"],
            "adapter_id": _ADAPTER_IDS.get(source["id"], _safe_adapter_id(source["id"])),
            "version": get_adapter(source["id"].removeprefix("source:")).adapter_version,
        }
        for source in arrays["sources"]
    ]
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": FORMAL_MANIFEST_ID,
        "entity_type": "formal_art_batch_manifest",
        "phase_id": "MUSEUM-03B",
        "batch_id": BATCH_ID,
        "selection_decision_id": components["decision"]["id"],
        "selection_application_id": components["application"]["id"],
        "input_bundle_hash": components["application"]["input_bundle_hash"],
        "code_commit": code_commit,
        "adapter_versions": adapter_versions,
        "source_registry_hash": source_registry_snapshot_hash(),
        "license_rules_hash": license_rules_snapshot_hash(),
        "schema_manifest_hash": sha256_file(ROOT / "schemas" / "schema-manifest.json"),
        "raw_snapshots": snapshots,
        "normalized_ids": normalized_ids,
        "artist_ids": [item["id"] for item in arrays["artists"]],
        "artwork_ids": [item["id"] for item in arrays["artworks"]],
        "context_ids": [item["id"] for item in arrays["contexts"]],
        "relationship_ids": [item["id"] for item in arrays["relationships"]],
        "claim_ids": [item["id"] for item in arrays["claims"]],
        "evidence_ids": [item["id"] for item in arrays["evidence"]],
        "source_ids": [item["id"] for item in arrays["sources"]],
        "rights_record_ids": [item["id"] for item in arrays["media_assessments"]],
        "review_record_ids": [item["id"] for item in arrays["signoffs"]],
        "exclusions": exclusions,
        "blocked_records": [],
        "counts": {
            "raw_snapshots": len(snapshots),
            "normalized": len(normalized_ids),
            "artists": len(arrays["artists"]),
            "artworks": len(arrays["artworks"]),
            "contexts": len(arrays["contexts"]),
            "relationships": len(arrays["relationships"]),
            "claims": len(arrays["claims"]),
            "evidence": len(arrays["evidence"]),
            "sources": len(arrays["sources"]),
            "rights_records": len(arrays["media_assessments"]),
            "review_records": len(arrays["signoffs"]),
            "exclusions": len(exclusions),
            "blocked_records": 0,
        },
        "generated_at": generated_at,
        "reviewer_signoff_ids": sorted(reviewer_signoff_ids),
        "predecessor": None,
        "no_media_declaration": {
            "media_bytes_downloaded": False,
            "media_bytes_in_package": False,
        },
        "no_public_release_declaration": {
            "formal_public_release_created": False,
            "pages_art_content_added": False,
        },
        "data_version": "1.0.0",
    }
    payload["content_hash"] = canonical_sha256(payload)
    return payload


def _production_components(stage_root: Path) -> dict[str, Any]:
    """Run the three local, offline component builders and collect their records."""

    from museum_pipeline.art.artworks import build_artwork_stage
    from museum_pipeline.art.identity import build_identity_stage
    from museum_pipeline.art.relationships import build_relationship_stage

    identity_dir = stage_root / "identity"
    artwork_dir = stage_root / "artwork"
    stage_root.mkdir(parents=True, exist_ok=True)
    build_identity_stage(output_dir=identity_dir)
    artwork_result = build_artwork_stage(output_dir=artwork_dir)
    relationship_result = build_relationship_stage(
        artwork_stage=artwork_result,
        identity_dir=identity_dir,
    )

    collected = _merge_components(
        _collect_component_directory(identity_dir),
        _collect_component_directory(artwork_dir),
        _result_components(relationship_result),
    )
    collected.setdefault("snapshot_receipt_ledgers", []).append(_load_json(DEFAULT_ARTWORK_SNAPSHOTS))
    identity_seed = _load_json(DEFAULT_IDENTITY_SEED)
    identity_basis = _load_json(DEFAULT_IDENTITY_BASIS)
    application = _load_json(DEFAULT_APPLICATION)
    collected.update(
        {
            "decision": _load_json(DEFAULT_DECISION),
            "application": application,
            "identity_basis": identity_basis,
            "artwork_selection_basis": _load_json(DEFAULT_ARTWORK_BASIS),
            "identity_seed": identity_seed,
        }
    )
    return collected


def _normalize_components(components: dict[str, Any]) -> dict[str, Any]:
    singletons = {
        "decision": ("decision", "selection_decision"),
        "application": ("application", "selection_application", "selection_decision_application"),
        "identity_basis": ("identity_basis", "approved_identity_basis"),
        "artwork_research_basis": ("artwork_selection_basis", "artwork_basis", "artwork_research_basis"),
    }
    arrays = {
        "artists": ("artists",),
        "artworks": ("artworks",),
        "contexts": ("contexts",),
        "relationships": ("relationships",),
        "claims": ("claims",),
        "evidence": ("evidence",),
        "sources": ("sources",),
        "media_assessments": ("media_assessments", "assessments", "rights_records"),
        "relationship_dispositions": ("relationship_dispositions", "dispositions"),
        "signoffs": ("signoffs", "review_signoffs"),
        "snapshot_receipt_ledgers": ("snapshot_receipt_ledgers", "snapshot_receipts"),
    }
    normalized: dict[str, Any] = {}
    for target, aliases in singletons.items():
        value = _first_present(components, aliases)
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if not isinstance(value, dict):
            raise PipelineError("batch_component_missing", f"Missing singleton batch component: {target}")
        normalized[target] = value
    for target, aliases in arrays.items():
        value = _first_present(components, aliases)
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PipelineError("batch_component_missing", f"Missing record-array batch component: {target}")
        normalized[target] = _deduplicate_records(value, collection=target)
    normalized["contexts"] = [item for item in normalized["contexts"] if item.get("entity_type") in _CONTEXT_TYPES]
    return normalized


def _preflight_exact_batch(components: dict[str, Any]) -> None:
    artists = components["artists"]
    artist_ids = {item.get("id") for item in artists}
    approved_ids = {item.get("artist_id") for item in components["identity_basis"].get("bindings", [])}
    if len(artists) != 12 or len(artist_ids) != 12 or artist_ids != approved_ids:
        raise PipelineError("approved_artist_closure_mismatch", "Batch artists must exactly equal the approved 12-person identity basis")
    application = components["application"]
    decision = components["decision"]
    if application.get("resulting_batch_id") != BATCH_ID or decision.get("media_strategy") != "mixed":
        raise PipelineError("selection_boundary_mismatch", "Batch must use the applied Mixed MUSEUM-03B decision")
    if application.get("replacement_count") != 0 or decision.get("replacements") != []:
        raise PipelineError("auto_replacement_forbidden", "The approved MUSEUM-03B batch permits zero replacements")
    if len(components["artworks"]) != 44:
        raise PipelineError("artwork_count_mismatch", "The nominal reviewed batch must contain exactly 44 artworks")
    if len(components["relationships"]) != 36:
        raise PipelineError("relationship_count_mismatch", "The formal graph must contain exactly 36 relationships")
    dispositions = components["relationship_dispositions"]
    inherited = sum(item.get("origin_kind") == "inherited_lead" for item in dispositions)
    curated = sum(item.get("origin_kind") == "new_curated_candidate" for item in dispositions)
    if len(dispositions) != 69 or inherited != 45 or curated != 24:
        raise PipelineError("relationship_disposition_count_mismatch", "Research closure requires 45 inherited and 24 new dispositions")


def _package_documents(
    components: dict[str, Any],
    artwork_selection_basis: dict[str, Any],
    graph: dict[str, Any],
    formal_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artists.json": sorted(components["artists"], key=_record_id),
        "artwork-selection-basis.json": artwork_selection_basis,
        "artworks.json": sorted(components["artworks"], key=_record_id),
        "claims.json": sorted(components["claims"], key=_record_id),
        "contexts.json": sorted(components["contexts"], key=_record_id),
        "evidence.json": sorted(components["evidence"], key=_record_id),
        "formal-batch-manifest.json": formal_manifest,
        "graph-input.json": graph,
        "identity-basis.json": components["identity_basis"],
        "media-assessments.json": sorted(components["media_assessments"], key=_record_id),
        "public-leakage-label-set.json": components["leakage_label_set"],
        "relationship-dispositions.json": sorted(components["relationship_dispositions"], key=_record_id),
        "relationships.json": sorted(components["relationships"], key=_record_id),
        "review-signoffs.json": sorted(components["signoffs"], key=_record_id),
        "selection-application.json": components["application"],
        "selection-decision.json": components["decision"],
        "snapshot-receipt-ledgers.json": sorted(components["snapshot_receipt_ledgers"], key=_record_id),
        "sources.json": sorted(components["sources"], key=_record_id),
    }


def _write_documents(package_dir: Path, documents: dict[str, Any]) -> list[dict[str, Any]]:
    environment = load_schema_environment(ROOT)
    manifest_index = _schema_manifest_index()
    entries: list[dict[str, Any]] = []
    for name in sorted(documents):
        document = documents[name]
        records = document if isinstance(document, list) else [document]
        if not records or any(not isinstance(item, dict) for item in records):
            raise PipelineError("package_document_invalid", f"Package document must contain records: {name}")
        schema_paths = {canonical_schema_path(item) for item in records}
        if None in schema_paths or len(schema_paths) != 1:
            raise PipelineError("package_schema_group_invalid", f"Package file mixes canonical schemas: {name}")
        schema_path = next(iter(schema_paths))
        assert schema_path is not None
        schema = environment.by_path.get(schema_path)
        schema_manifest = manifest_index.get(schema_path)
        if schema is None or schema_manifest is None:
            raise PipelineError("package_schema_unregistered", f"Canonical schema is not registered: {schema_path}")
        payload = canonical_json_bytes(document)
        (package_dir / name).write_bytes(payload)
        entries.append(
            {
                "path": name,
                "bytes": len(payload),
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "canonical_json": True,
                "schema_id": schema["$id"],
                "schema_version": schema_manifest["version"],
                "record_ids": [item["id"] for item in records],
            }
        )
    return entries


def _reviewed_package_manifest(
    *,
    file_entries: list[dict[str, Any]],
    reviewer_signoff_ids: list[str],
    generated_at: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0.0",
        "id": PACKAGE_MANIFEST_ID,
        "entity_type": "reviewed_package_manifest",
        "phase_id": "MUSEUM-03B",
        "batch_id": BATCH_ID,
        "formal_batch_manifest_id": FORMAL_MANIFEST_ID,
        "package_root": "package-v1",
        "files": file_entries,
        "declared_file_count": len(file_entries),
        "total_bytes": sum(item["bytes"] for item in file_entries),
        "canonical_json": True,
        "no_undeclared_files": True,
        "safe_relative_paths": True,
        "no_symlink_escape": True,
        "stable_ids_closed": True,
        "schema_versions_closed": True,
        "reference_closure": True,
        "source_license_binding_closure": True,
        "decision_closure": True,
        "no_media_bytes": True,
        "no_published_state": True,
        "review_signoff_ids": sorted(reviewer_signoff_ids),
        "generated_at": generated_at,
        "data_version": "1.0.0",
    }
    payload["content_hash"] = canonical_sha256(file_entries)
    return payload


def _graph_edge(relationship: dict[str, Any], claim_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claim_ids = sorted(relationship.get("claim_ids", []))
    evidence_ids = sorted(
        {
            evidence_id
            for claim_id in claim_ids
            for evidence_id in claim_index.get(claim_id, {}).get("evidence_ids", [])
        }
        | set(relationship.get("evidence_ids", []))
    )
    explanation = relationship.get("educational_rationale") or relationship.get("curatorial_note")
    if not isinstance(explanation, dict):
        raise PipelineError("relationship_explanation_missing", f"Relationship lacks a localized explanation: {relationship.get('id')}")
    return {
        "relationship_id": relationship["id"],
        "source_artist_id": relationship["source_entity_id"],
        "target_entity_id": relationship["target_entity_id"],
        "relationship_type": relationship["relationship_type"],
        "directed": relationship["directed"],
        "evidence_level": relationship["evidence_level"],
        "explanation": explanation,
        "context_entity_ids": sorted(relationship.get("context_entity_ids", [])),
        "temporal_scope": relationship["temporal_scope"],
        "place_ids": sorted((relationship.get("place_scope") or {}).get("place_ids", [])),
        "historical_relationship_strength": relationship["historical_relationship_strength"],
        "evidence_confidence": relationship["evidence_confidence"],
        "computational_similarity": relationship["computational_similarity"],
        "curatorial_relevance": relationship["curatorial_relevance"],
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "source_ids": sorted(relationship.get("source_ids", [])),
        "filter_values": [
            {"key": "evidence_level", "value": relationship["evidence_level"]},
            {"key": "relationship_type", "value": relationship["relationship_type"]},
        ],
        "is_algorithmic": relationship["is_algorithmic"],
        "media_dependency": False,
    }


def _load_batch_review_signoffs(
    components: dict[str, Any],
    path: Path = DEFAULT_BATCH_REVIEW_SIGNOFFS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = _load_json(path)
    if document.get("content_hash") != EXPECTED_BATCH_REVIEW_SET_CONTENT_HASH:
        raise PipelineError("batch_review_set_unapproved", "Tracked batch review-set hash differs from the approved record")
    expected_content_hash = canonical_sha256({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected_content_hash:
        raise PipelineError("batch_review_set_hash_mismatch", "Tracked batch review-set content hash is invalid")
    if (
        document.get("id") != "batch-review-signoff-set:museum-03b-first-slate-v1"
        or document.get("entity_type") != "batch_review_signoff_set"
        or document.get("phase_id") != "MUSEUM-03B"
        or document.get("batch_id") != BATCH_ID
    ):
        raise PipelineError("batch_review_set_identity_mismatch", "Tracked batch review-set identity is invalid")
    review_basis = document.get("review_basis")
    signoffs = document.get("signoffs")
    if not isinstance(review_basis, dict) or not isinstance(signoffs, list) or any(not isinstance(item, dict) for item in signoffs):
        raise PipelineError("batch_review_set_invalid", "Tracked batch review-set must contain a review basis and sign-off records")
    if document.get("review_basis_hash") != canonical_sha256(review_basis):
        raise PipelineError("batch_review_basis_hash_mismatch", "Tracked batch review-basis hash is invalid")
    if document.get("signoff_set_hash") != canonical_sha256(signoffs):
        raise PipelineError("batch_review_signoff_hash_mismatch", "Tracked batch sign-off set hash is invalid")

    signoff_index = {item.get("id"): item for item in signoffs}
    if tuple(signoff_index) != _BATCH_SIGNOFF_IDS or len(signoff_index) != len(signoffs):
        raise PipelineError("batch_review_signoff_set_mismatch", "Tracked batch sign-off IDs differ from the approved set")
    expected_records = [
        "artwork-selection-basis:museum-03b-first-slate-v1",
        GRAPH_ID,
        FORMAL_MANIFEST_ID,
    ]
    expected_by_id = {
        _BATCH_SIGNOFF_IDS[0]: ("data_reviewer", expected_records),
        _BATCH_SIGNOFF_IDS[1]: ("relationship_reviewer", [GRAPH_ID, *sorted(item["id"] for item in components["relationships"])]),
        _BATCH_SIGNOFF_IDS[2]: ("release_reviewer", expected_records),
    }
    environment = load_schema_environment(ROOT)
    for signoff_id, (role, record_ids) in expected_by_id.items():
        signoff = signoff_index[signoff_id]
        issues = validate_record(signoff, environment=environment)
        if issues:
            issue = issues[0]
            raise PipelineError("batch_review_signoff_schema_invalid", f"{signoff_id}: {issue.code} at {issue.location}: {issue.message}")
        if (
            signoff.get("review_role") != role
            or signoff.get("record_ids") != record_ids
            or signoff.get("decision") != "accepted_reviewed"
            or document["review_basis_hash"] not in str(signoff.get("authority_basis"))
        ):
            raise PipelineError("batch_review_signoff_closure_mismatch", f"Tracked sign-off closure differs for {signoff_id}")
    return document, deepcopy(signoffs)


def _validate_batch_review_basis(
    review_set: dict[str, Any],
    components: dict[str, Any],
    artwork_selection_basis: dict[str, Any],
) -> None:
    relationship_decisions = _load_json(DEFAULT_RELATIONSHIP_DECISIONS)
    relationship_lead_closure = _load_json(DEFAULT_RELATIONSHIP_LEAD_CLOSURE)
    expected = {
        "input_record_hashes": {
            "selection_decision": canonical_sha256(components["decision"]),
            "selection_application": canonical_sha256(components["application"]),
            "approved_identity_basis": canonical_sha256(components["identity_basis"]),
            "artwork_research_basis": canonical_sha256(components["artwork_research_basis"]),
            "relationship_decisions": _validated_declared_content_hash(relationship_decisions, "relationship decisions"),
            "relationship_lead_closure": _validated_declared_content_hash(relationship_lead_closure, "relationship lead closure"),
        },
        "record_id_set_hashes": {
            key: canonical_sha256(sorted(item["id"] for item in components[key]))
            for key in (
                "artists",
                "artworks",
                "contexts",
                "relationships",
                "claims",
                "evidence",
                "sources",
                "media_assessments",
                "relationship_dispositions",
            )
        },
        "relationship_closure_hashes": _relationship_closure_hashes(components["relationship_dispositions"], components["relationships"]),
        "artwork_selection_tuple_hash": canonical_sha256(_artwork_selection_tuples(artwork_selection_basis)),
    }
    if review_set.get("review_basis") != expected:
        raise PipelineError("batch_review_basis_drift", "Current deterministic batch differs from the tracked hash-bound review basis")


def _validated_declared_content_hash(document: dict[str, Any], label: str) -> str:
    expected = canonical_sha256({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected:
        raise PipelineError("batch_review_input_hash_invalid", f"Declared content hash is invalid for {label}")
    return expected


def _relationship_closure_hashes(
    dispositions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, str]:
    inherited = sorted(
        (item for item in dispositions if item.get("origin_kind") == "inherited_lead"),
        key=lambda item: item["lead_id"],
    )
    curated = sorted(
        (item for item in dispositions if item.get("origin_kind") == "new_curated_candidate"),
        key=lambda item: item["research_candidate_id"],
    )
    inherited_projection = [
        {
            key: item.get(key)
            for key in ("lead_id", "disposition", "formal_relationship_id", "superseded_by_lead_id")
        }
        for item in inherited
    ]
    curated_projection = [
        {key: item.get(key) for key in ("research_candidate_id", "disposition", "formal_relationship_id")}
        for item in curated
    ]
    return {
        "inherited_lead_id_set": canonical_sha256([item["lead_id"] for item in inherited]),
        "curated_candidate_id_set": canonical_sha256([item["research_candidate_id"] for item in curated]),
        "inherited_disposition_projection": canonical_sha256(inherited_projection),
        "curated_disposition_projection": canonical_sha256(curated_projection),
        "formal_relationship_id_set": canonical_sha256(sorted(item["id"] for item in relationships)),
    }


def _artwork_selection_tuples(selection_basis: dict[str, Any]) -> list[dict[str, Any]]:
    fields = (
        "artwork_id",
        "approved_artist_id",
        "source_id",
        "source_object_id",
        "official_object_url",
        "rights_preflight_id",
    )
    return sorted(
        ({key: selection.get(key) for key in fields} for selection in selection_basis.get("selections", [])),
        key=lambda item: str(item["artwork_id"]),
    )


def _verify_code_commit(code_commit: str) -> None:
    try:
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{code_commit}^{{commit}}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise PipelineError("code_commit_verification_unavailable", f"Cannot execute Git: {error}") from error
    if exists.returncode != 0:
        raise PipelineError("code_commit_unknown", "code_commit does not resolve to a local Git commit")

    mismatches: list[str] = []
    for relative in _IMPLEMENTATION_INPUT_PATHS:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            mismatches.append(relative)
            continue
        committed = subprocess.run(
            ["git", "show", f"{code_commit}:{relative}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if committed.returncode != 0 or committed.stdout != path.read_bytes():
            mismatches.append(relative)
    if mismatches:
        raise PipelineError(
            "code_commit_implementation_mismatch",
            f"code_commit does not contain the current deterministic implementation inputs: {', '.join(mismatches)}",
        )


def _snapshot_declarations(ledgers: list[dict[str, Any]]) -> list[dict[str, str]]:
    indexed: dict[str, str] = {}
    for ledger in ledgers:
        for entry in ledger.get("entries", []):
            snapshot_id = entry.get("snapshot_id")
            digest = entry.get("body_sha256")
            if not isinstance(snapshot_id, str) or not isinstance(digest, str):
                raise PipelineError("snapshot_declaration_invalid", "Snapshot ledgers must contain stable IDs and body hashes")
            if snapshot_id in indexed and indexed[snapshot_id] != digest:
                raise PipelineError("snapshot_declaration_conflict", f"Snapshot ID has conflicting hashes: {snapshot_id}")
            indexed[snapshot_id] = digest
    return [{"snapshot_id": key, "body_sha256": indexed[key]} for key in sorted(indexed)]


def _formal_exclusions(artwork_basis: dict[str, Any]) -> list[dict[str, str]]:
    count = artwork_basis.get("excluded_candidate_count")
    set_hash = artwork_basis.get("excluded_candidate_set_hash")
    if count in {None, 0}:
        return []
    if not isinstance(count, int) or count < 0 or not isinstance(set_hash, str):
        raise PipelineError("artwork_exclusion_aggregate_invalid", "Artwork exclusions must use a count and canonical set hash")
    return [
        {
            "record_id": "artwork-exclusion-set:museum-03b-held-out-alternates",
            "reason": f"{count} held-out alternatives were omitted from the reviewed slate; private identifiers are represented only by canonical set hash {set_hash}.",
        }
    ]


def _collect_component_directory(directory: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(directory.rglob("*.json")):
        document = _load_json(path)
        records = document if isinstance(document, list) else [document]
        for record in records:
            if not isinstance(record, dict):
                continue
            _append_record_component(result, record)
    return result


def _result_components(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    payload = result.get("outputs") if isinstance(result.get("outputs"), dict) else result
    recognized = {
        "artists", "artworks", "contexts", "relationships", "claims", "evidence", "sources",
        "media_assessments", "assessments", "rights_records", "relationship_dispositions",
        "dispositions", "signoffs", "review_signoffs", "snapshot_receipt_ledgers", "snapshot_receipts",
    }
    return {key: value for key, value in payload.items() if key in recognized}


def _append_record_component(result: dict[str, Any], record: dict[str, Any]) -> None:
    entity_type = record.get("entity_type")
    mapping = {
        "artist": "artists",
        "artwork": "artworks",
        "relationship": "relationships",
        "claim": "claims",
        "evidence": "evidence",
        "source": "sources",
        "media_eligibility_assessment": "media_assessments",
        "relationship_research_disposition": "relationship_dispositions",
        "review_signoff": "signoffs",
        "snapshot_receipt_ledger": "snapshot_receipt_ledgers",
    }
    key = "contexts" if entity_type in _CONTEXT_TYPES else mapping.get(str(entity_type))
    if key:
        result.setdefault(key, []).append(record)


def _merge_components(*component_sets: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for components in component_sets:
        for key, value in components.items():
            values = value if isinstance(value, list) else [value]
            merged.setdefault(key, []).extend(values)
    return merged


def _deduplicate_records(records: list[dict[str, Any]], *, collection: str) -> list[dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            raise PipelineError("batch_record_id_missing", f"Record in {collection} has no stable ID")
        if record_id in indexed and indexed[record_id] != record:
            raise PipelineError("batch_record_conflict", f"Conflicting duplicate record in {collection}: {record_id}")
        indexed[record_id] = record
    return [indexed[key] for key in sorted(indexed)]


def _deterministic_generated_at(components: dict[str, Any]) -> str:
    candidates: list[tuple[datetime, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"generated_at", "reviewed_at", "verified_at", "application_timestamp"} and isinstance(child, str) and "T" in child:
                    try:
                        candidates.append((datetime.fromisoformat(child.replace("Z", "+00:00")), child))
                    except ValueError:
                        pass
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(components)
    if not candidates:
        raise PipelineError("batch_timestamp_missing", "A deterministic reviewed timestamp is required")
    return max(candidates, key=lambda item: item[0])[1]


def _publish_directory(staged: Path, output: Path) -> bool:
    if output.exists():
        if not output.is_dir() or not _directories_equal(staged, output):
            raise PipelineError("reviewed_batch_conflict", f"Refusing to overwrite different reviewed package: {output}")
        return True
    os.replace(staged, output)
    return False


def _directories_equal(left: Path, right: Path) -> bool:
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*") if path.is_file()}
    if left_files.keys() != right_files.keys():
        return False
    return all(left_files[name].read_bytes() == right_files[name].read_bytes() for name in left_files)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise PipelineError("reviewed_batch_locked", f"Another reviewed batch build owns the lock: {path}") from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid()}, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        path.unlink(missing_ok=True)


def _schema_manifest_index() -> dict[str, dict[str, Any]]:
    document = _load_json(ROOT / "schemas" / "schema-manifest.json")
    return {item["path"]: item for item in document["schemas"]}


def _safe_adapter_id(source_id: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "_", source_id.removeprefix("source:").lower()).strip("_.-")
    return (value or "source") + "_adapter"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PipelineError("batch_input_invalid", f"Cannot read required batch input {path}: {error}") from error


def _first_present(components: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        if key in components:
            return components[key]
    return None


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("id", ""))


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _display_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
