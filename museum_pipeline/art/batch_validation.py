from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from museum_pipeline.adapters import get_adapter
from museum_pipeline.art.contract_validation import (
    formal_package_contract_projection,
    validate_art_batch_contract,
)
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import (
    canonical_schema_path,
    load_schema_environment,
    validate_record,
)
from scripts.validate_governance_foundation import reference_graph_issues


DEFAULT_PACKAGE = (
    ROOT
    / "data"
    / "reviewed"
    / "art"
    / "museum-03b"
    / "museum-03b-first-slate-v1"
    / "package-v1"
)

APPROVED_ARTIST_COUNT = 12
NOMINAL_ARTWORK_COUNT = 44
MINIMUM_RELATIONSHIP_COUNT = 30
EXPECTED_RELATIONSHIP_COUNT = 36
EXPECTED_INHERITED_LEAD_COUNT = 45
EXPECTED_BATCH_ID = "art-batch:museum-03b-first-slate-v1"
EXPECTED_SELECTION_BUNDLE_HASH = "sha256:ba7640dbfe554c938fc9bf65ac5fa1eb42514ced015e0b4e56598870428072c7"
EXPECTED_SELECTION_DECISION_ID = "selection-decision:17bcd813-6a96-55e5-aed4-788df44ad006"
EXPECTED_SELECTION_APPLICATION_ID = "selection-decision-application:8c2666ef-fdfe-5250-af97-1d3b1d8c4a43"
EXPECTED_SELECTION_SCENARIO_ID = "selection-scenario:8966bf75-2830-5a0f-afc5-5d6801e93ccc"
EXPECTED_RECOMMENDED_SLATE_HASH = "sha256:b595d6b558d110111597f6edfd7273e2446519fdfc4dab919c59384e04e3c645"
EXPECTED_SUBMITTED_DECISION_HASH = "sha256:20dd0bf806dc06cc110140ece1b29838cf38ef8134ffa3f08f5ea82d256ba727"
EXPECTED_INHERITED_LEAD_ID_SET_HASH = "sha256:39387eb8fb051ba11d9bcfd6b6f3b23074b40e9d3d05d317c27e7c065a5b530b"
EXPECTED_CURATED_CANDIDATE_ID_SET_HASH = "sha256:0e4b7f09396b5c098b1d456ff26502992640cf03c7cd074cf12a7dcf8ed149fd"
EXPECTED_INHERITED_DISPOSITION_PROJECTION_HASH = "sha256:b98c96d7fc3cdfa074acc4a8defa8668deb3836d3303c11016d191cf71aa22c7"
EXPECTED_CURATED_DISPOSITION_PROJECTION_HASH = "sha256:8d5b444fa45bc5deeec882fab1ba7e421b4dfaeaee26493e653797e82f589ed1"
EXPECTED_FORMAL_RELATIONSHIP_ID_SET_HASH = "sha256:32d8f61b925612c9952ef2296f8f30ee99b31e130ae269fd6d0cf415f3c5d277"
EXPECTED_ARTWORK_SELECTION_TUPLE_HASH = "sha256:8ed60b48d56aaaa8feefd0bd4a9c2d807827bc202db108e91df3b2a56a4bdb9f"
EXPECTED_ARTWORK_SELECTION_SET_HASH = "sha256:eeda50dd1bcc75cd6353eabdedb184450df385d88d86b1b8d5d0dab743ab859d"
EXPECTED_ARTWORK_SELECTION_ORDERED_HASH = "sha256:7c6cce18e00f3a6345f94275c0fdb784f0f6576404ed5fef0288ee84bf5ae625"
EXPECTED_BATCH_REVIEW_SET_CONTENT_HASH = "sha256:56bc78aab591f82c566e369e0c2a0104237d982ca23d4c2d66db14d1e1713761"
DEFAULT_BATCH_REVIEW_SIGNOFFS = ROOT / "research" / "art" / "museum-03b-batch-review-signoffs.json"
_COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")
_BATCH_SIGNOFF_IDS = {
    "review-signoff:museum-03b-batch-data",
    "review-signoff:museum-03b-batch-relationship",
    "review-signoff:museum-03b-batch-release",
}
EXPECTED_CANDIDATE_IDS = (
    "artist-candidate:aba4e7b5-5cce-5903-98a3-debd6a8a30fe",
    "artist-candidate:28386296-3385-5ef8-a959-9f1ef8ae7bc9",
    "artist-candidate:708f8528-dbac-53f5-8fc7-bb15e816c0a5",
    "artist-candidate:f92e77cc-b45b-5998-9707-879503c1dabf",
    "artist-candidate:09ae6255-0541-57ef-9dcd-df1570ff2d62",
    "artist-candidate:f1757502-ff5e-5769-857a-e7e53cec7c60",
    "artist-candidate:1942ecb6-ca0e-58c5-9fca-7785d500b8cf",
    "artist-candidate:0ca3f12a-9ae9-5644-916f-3d599f1967f8",
    "artist-candidate:da02db61-430f-5d73-a97f-64b0e7a5ce26",
    "artist-candidate:f25c47aa-47bd-5009-b3fe-508b6cc9b039",
    "artist-candidate:ad5f2cda-6489-55d4-aa81-37be10697f58",
    "artist-candidate:0bfcdd78-5be2-5903-9819-d3a3a1406698",
)
EXPECTED_ARTIST_IDS = (
    "artist:albrecht-durer",
    "artist:francisco-de-goya",
    "artist:vincent-van-gogh",
    "artist:mary-cassatt",
    "artist:kathe-kollwitz",
    "artist:julia-margaret-cameron",
    "artist:katsushika-hokusai",
    "artist:kitagawa-utamaro",
    "artist:shen-zhou",
    "artist:raja-ravi-varma",
    "artist:jose-guadalupe-posada",
    "artist:henry-ossawa-tanner",
)

MEDIA_SUFFIXES = {
    ".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".m4a", ".mov", ".mp3",
    ".mp4", ".ogg", ".otf", ".png", ".svg", ".tif", ".tiff", ".ttf", ".wav",
    ".webm", ".webp", ".woff", ".woff2", ".zip", ".glb", ".gltf",
}

CONTEXT_TYPES = {
    "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
    "exhibition_event", "material", "technique", "subject", "time_period", "person",
}


def validate_approved_batch(package_dir: Path = DEFAULT_PACKAGE) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    requested_dir = _absolute(package_dir)
    if requested_dir.is_symlink():
        _fail(failures, "package_root_symlink_forbidden", f"Reviewed package root is a symlink: {requested_dir}")
    try:
        package_dir = requested_dir.resolve()
    except OSError as error:
        _fail(failures, "package_root_invalid", f"Cannot resolve reviewed package root: {error}")
        return _result(requested_dir, failures, {})
    environment = load_schema_environment()
    manifest_path = package_dir / "package-manifest.json"
    if not package_dir.is_dir():
        _fail(failures, "package_missing", f"Reviewed package directory is absent: {package_dir}")
        return _result(package_dir, failures, {})
    manifest = _read_root_manifest(package_dir, manifest_path, failures)
    if not isinstance(manifest, dict):
        return _result(package_dir, failures, {})

    _schema_check(manifest, failures, "package-manifest.json", environment)
    records, by_file = _validate_physical_package(package_dir, manifest, failures, environment)
    if not records:
        return _result(package_dir, failures, {})

    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            _fail(failures, "record_id_missing", "A packaged record has no stable ID")
            continue
        if record_id in indexed:
            _fail(failures, "record_id_duplicate", f"Duplicate packaged record ID: {record_id}")
        indexed[record_id] = record
        _schema_check(record, failures, record_id, environment)

    _validate_reference_graph(records, failures)
    _validate_decision_closure(indexed, failures)
    _validate_shared_contract(indexed, manifest, failures)
    counts = _validate_batch_semantics(indexed, manifest, failures)
    _validate_declared_closure(by_file, indexed, failures)
    _validate_content_hashes(indexed, manifest, failures)
    return _result(package_dir, failures, counts)


def _read_root_manifest(
    package_dir: Path,
    manifest_path: Path,
    failures: list[dict[str, str]],
) -> dict[str, Any] | None:
    if manifest_path.is_symlink():
        _fail(failures, "package_manifest_symlink_forbidden", "Root package manifest must not be a symlink")
        return None
    try:
        resolved = manifest_path.resolve(strict=True)
    except OSError as error:
        _fail(failures, "package_manifest_invalid", f"Cannot resolve root package manifest: {error}")
        return None
    if not resolved.is_relative_to(package_dir.resolve()):
        _fail(failures, "package_manifest_path_escape", "Root package manifest escapes the reviewed package")
        return None
    if not resolved.is_file():
        _fail(failures, "package_manifest_invalid", "Root package manifest is not a regular file")
        return None
    try:
        payload = manifest_path.read_bytes()
    except OSError as error:
        _fail(failures, "package_manifest_invalid", f"Cannot read root package manifest: {error}")
        return None
    document = _parse_bytes(payload, failures, "package-manifest.json")
    if not isinstance(document, dict):
        _fail(failures, "package_manifest_invalid", "Root package manifest must be a JSON object")
        return None
    if canonical_json_bytes(document) != payload:
        _fail(failures, "package_manifest_not_canonical_json", "Root package manifest is not canonical JSON")
    return document


def _validate_physical_package(
    package_dir: Path,
    manifest: dict[str, Any],
    failures: list[dict[str, str]],
    environment: Any,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        _fail(failures, "package_file_manifest_invalid", "Package files must be an array")
        return [], {}
    declared = {item.get("path") for item in entries if isinstance(item, dict) and isinstance(item.get("path"), str)}
    if len(declared) != len(entries):
        _fail(failures, "package_file_path_duplicate", "Package manifest contains duplicate or invalid file paths")
    actual: set[str] = set()
    root_resolved = package_dir.resolve()
    for current, directory_names, file_names in os.walk(package_dir, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in directory_names:
            path = current_path / name
            relative = path.relative_to(package_dir).as_posix()
            if path.is_symlink():
                _fail(failures, "package_symlink_forbidden", f"Symlink directory is forbidden: {relative}")
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                _fail(failures, "package_path_invalid", f"Cannot resolve package directory: {relative}")
                continue
            if not resolved.is_relative_to(root_resolved):
                _fail(failures, "package_path_escape", f"Directory escapes package root: {relative}")
        for name in file_names:
            path = current_path / name
            relative = path.relative_to(package_dir).as_posix()
            if path.is_symlink():
                _fail(failures, "package_symlink_forbidden", f"Symlink file is forbidden: {relative}")
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                _fail(failures, "package_path_invalid", f"Cannot resolve package file: {relative}")
                continue
            if not resolved.is_relative_to(root_resolved):
                _fail(failures, "package_path_escape", f"File escapes package root: {relative}")
            if relative == "package-manifest.json":
                continue
            if name == "package-manifest.json":
                _fail(failures, "nested_package_manifest_name_forbidden", f"Nested package-manifest.json is forbidden: {relative}")
            if path.suffix.lower() in MEDIA_SUFFIXES:
                _fail(failures, "media_bytes_in_package", f"Media-like file is forbidden: {relative}")
            actual.add(relative)
    if actual != declared:
        _fail(
            failures,
            "package_file_set_mismatch",
            f"Declared/actual file set differs; missing={sorted(declared - actual)}, undeclared={sorted(actual - declared)}",
        )
    if manifest.get("declared_file_count") != len(entries):
        _fail(failures, "package_declared_count_mismatch", "declared_file_count differs from files length")

    schema_id_to_path = {schema.get("$id"): path for path, schema in environment.by_path.items()}
    records: list[dict[str, Any]] = []
    by_file: dict[str, list[dict[str, Any]]] = {}
    observed_bytes = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _fail(failures, "package_file_entry_invalid", f"File entry {index} is not an object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not _safe_relative_path(relative):
            _fail(failures, "package_path_unsafe", f"Unsafe package path: {relative!r}")
            continue
        path = package_dir / PurePosixPath(relative)
        if path.suffix.lower() in MEDIA_SUFFIXES:
            _fail(failures, "media_bytes_in_package", f"Media-like file is forbidden: {relative}")
        if path.is_symlink():
            _fail(failures, "package_symlink_forbidden", f"Symlink is forbidden: {relative}")
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            _fail(failures, "package_file_missing", f"Declared file is absent: {relative}")
            continue
        if not resolved.is_relative_to(root_resolved):
            _fail(failures, "package_path_escape", f"File escapes package root: {relative}")
            continue
        payload = path.read_bytes()
        observed_bytes += len(payload)
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if entry.get("bytes") != len(payload):
            _fail(failures, "package_file_size_mismatch", f"Byte count differs for {relative}")
        if entry.get("sha256") != digest:
            _fail(failures, "package_file_hash_mismatch", f"SHA-256 differs for {relative}")
        document = _parse_bytes(payload, failures, relative)
        if document is None:
            continue
        if canonical_json_bytes(document) != payload:
            _fail(failures, "package_file_not_canonical_json", f"File is not canonical JSON: {relative}")
        file_records = document if isinstance(document, list) else [document]
        if not file_records or any(not isinstance(item, dict) for item in file_records):
            _fail(failures, "package_records_invalid", f"File must contain one record or a non-empty record array: {relative}")
            continue
        observed_ids = [item.get("id") for item in file_records]
        if observed_ids != entry.get("record_ids"):
            _fail(failures, "package_file_record_ids_mismatch", f"record_ids differ for {relative}")
        schema_path = schema_id_to_path.get(entry.get("schema_id"))
        if schema_path is None:
            _fail(failures, "package_schema_id_unknown", f"Unknown schema_id for {relative}")
        else:
            manifest_versions = _schema_versions()
            if entry.get("schema_version") != manifest_versions.get(schema_path):
                _fail(failures, "package_schema_version_mismatch", f"Schema version differs for {relative}")
            for record in file_records:
                if canonical_schema_path(record) != schema_path:
                    _fail(failures, "package_schema_dispatch_mismatch", f"Canonical dispatch differs for {record.get('id')}")
        by_file[relative] = file_records
        records.extend(file_records)
    if manifest.get("total_bytes") != observed_bytes:
        _fail(failures, "package_total_bytes_mismatch", "total_bytes differs from physical files")
    return records, by_file


def _validate_reference_graph(records: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    wrapped = [{"data": record} for record in records]
    for issue in reference_graph_issues(wrapped):
        _fail(failures, f"reference_{issue.code}", issue.message, issue.location)
    indexed = {item.get("id"): item for item in records if isinstance(item.get("id"), str)}
    for record in records:
        for field in ("review_signoff_ids", "reviewer_signoff_ids"):
            for signoff_id in record.get(field, []):
                if indexed.get(signoff_id, {}).get("entity_type") != "review_signoff":
                    _fail(failures, "review_signoff_reference_missing", f"{record.get('id')} references absent sign-off {signoff_id}")
        if record.get("entity_type") == "review_signoff":
            for record_id in record.get("record_ids", []):
                if record_id not in indexed:
                    _fail(failures, "signoff_record_reference_missing", f"Sign-off references absent record {record_id}")


def _validate_decision_closure(indexed: dict[str, dict[str, Any]], failures: list[dict[str, str]]) -> None:
    decisions = _records_of(indexed, "selection_decision")
    applications = _records_of(indexed, "selection_decision_application")
    identity_bases = _records_of(indexed, "approved_identity_basis")
    if len(decisions) != 1 or len(applications) != 1 or len(identity_bases) != 1:
        _fail(
            failures,
            "decision_closure_missing",
            "Exactly one submitted decision, application, and approved identity basis are required",
        )
        return
    decision, application, identity_basis = decisions[0], applications[0], identity_bases[0]
    if decision.get("id") != EXPECTED_SELECTION_DECISION_ID or application.get("id") != EXPECTED_SELECTION_APPLICATION_ID:
        _fail(failures, "selection_record_id_mismatch", "Decision/application IDs differ from the applied user decision")
    if decision.get("selected_scenario_id") != EXPECTED_SELECTION_SCENARIO_ID:
        _fail(failures, "selection_scenario_mismatch", "Decision does not select the immutable Recommended Slate scenario")
    if decision.get("input_bundle_hash") != EXPECTED_SELECTION_BUNDLE_HASH or application.get("input_bundle_hash") != EXPECTED_SELECTION_BUNDLE_HASH:
        _fail(failures, "selection_bundle_hash_mismatch", "Decision/application do not bind the verified MUSEUM-03A bundle hash")
    if application.get("recommended_slate_hash") != EXPECTED_RECOMMENDED_SLATE_HASH:
        _fail(failures, "recommended_slate_hash_mismatch", "Application does not bind the exact Recommended Slate hash")
    if application.get("submitted_decision_hash") != EXPECTED_SUBMITTED_DECISION_HASH or canonical_sha256(decision) != EXPECTED_SUBMITTED_DECISION_HASH:
        _fail(failures, "submitted_decision_hash_mismatch", "Packaged decision bytes do not match the applied decision hash")
    if decision.get("status") != "submitted" or decision.get("decision_authority") != "Mays":
        _fail(failures, "selection_decision_invalid", "Decision must be submitted by Mays")
    if decision.get("replacements") != [] or application.get("replacement_count") != 0:
        _fail(failures, "auto_replacement_forbidden", "Decision/application must have zero replacements")
    if decision.get("media_strategy") != "mixed" or application.get("media_strategy") != "mixed":
        _fail(failures, "media_strategy_mismatch", "Mixed media strategy is required")
    if application.get("submitted_decision_id") != decision.get("id"):
        _fail(failures, "decision_application_reference_mismatch", "Application does not resolve the submitted decision")
    if application.get("selected_candidate_ids") != decision.get("selected_candidate_ids"):
        _fail(failures, "decision_selected_ids_mismatch", "Decision/application approved candidate IDs differ")
    if tuple(decision.get("selected_candidate_ids", [])) != EXPECTED_CANDIDATE_IDS:
        _fail(failures, "approved_candidate_set_mismatch", "Approved candidates differ from the exact user-approved 12-person slate")
    bindings = identity_basis.get("bindings", [])
    if tuple(item.get("approved_candidate_id") for item in bindings) != EXPECTED_CANDIDATE_IDS:
        _fail(failures, "identity_candidate_binding_mismatch", "Identity basis candidate order differs from the approved slate")
    if tuple(item.get("artist_id") for item in bindings) != EXPECTED_ARTIST_IDS:
        _fail(failures, "identity_artist_binding_mismatch", "Identity basis artist IDs differ from the approved slate")
    if identity_basis.get("input_bundle_hash") != EXPECTED_SELECTION_BUNDLE_HASH:
        _fail(failures, "identity_bundle_hash_mismatch", "Identity basis does not bind the verified MUSEUM-03A bundle")
    if application.get("resulting_batch_id") != EXPECTED_BATCH_ID:
        _fail(failures, "selection_batch_id_mismatch", "Decision application targets an unexpected batch")
    if identity_basis.get("decision_application_id") != EXPECTED_SELECTION_APPLICATION_ID:
        _fail(failures, "identity_application_mismatch", "Identity basis does not bind the applied selection decision")
    stale_check = application.get("stale_check") or {}
    if application.get("application_status") != "applied" or application.get("validation_result") != "pass" or stale_check.get("status") != "fresh":
        _fail(failures, "selection_application_not_fresh", "Selection application must be applied, passing, and fresh")


def _validate_shared_contract(
    indexed: dict[str, dict[str, Any]],
    package_manifest: dict[str, Any],
    failures: list[dict[str, str]],
) -> None:
    decisions = _records_of(indexed, "selection_decision")
    applications = _records_of(indexed, "selection_decision_application")
    if len(decisions) != 1 or len(applications) != 1:
        return
    projection = formal_package_contract_projection(
        decision=decisions[0],
        application=applications[0],
        artists=_records_of(indexed, "artist"),
        artworks=_records_of(indexed, "artwork"),
        contexts=[record for record in indexed.values() if record.get("entity_type") in CONTEXT_TYPES],
        relationships=_records_of(indexed, "relationship"),
        media_assessments=_records_of(indexed, "media_eligibility_assessment"),
        package_manifest=package_manifest,
    )
    for code in sorted(validate_art_batch_contract(projection)):
        _fail(failures, f"shared_contract_{code}", f"Formal package violates shared art-batch contract: {code}")


def _validate_batch_semantics(
    indexed: dict[str, dict[str, Any]],
    package_manifest: dict[str, Any],
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    artists = _records_of(indexed, "artist")
    artworks = _records_of(indexed, "artwork")
    contexts = [record for record in indexed.values() if record.get("entity_type") in CONTEXT_TYPES]
    relationships = _records_of(indexed, "relationship")
    claims = _records_of(indexed, "claim")
    evidence = _records_of(indexed, "evidence")
    sources = _records_of(indexed, "source")
    assessments = _records_of(indexed, "media_eligibility_assessment")
    dispositions = _records_of(indexed, "relationship_research_disposition")
    signoffs = _records_of(indexed, "review_signoff")
    artwork_selection_bases = _records_of(indexed, "artwork_selection_basis")
    graphs = _records_of(indexed, "graph_input")
    formal_manifests = _records_of(indexed, "formal_art_batch_manifest")

    artist_ids = {item.get("id") for item in artists}
    if len(artists) != APPROVED_ARTIST_COUNT:
        _fail(failures, "approved_artist_count_mismatch", f"Expected 12 artists, observed {len(artists)}")
    if any(item.get("deceased_status") != "confirmed_deceased" for item in artists):
        _fail(failures, "artist_death_gate_failed", "Every primary artist must be confirmed deceased")
    if any(item.get("lifecycle_status") not in {"reviewed"} for item in artists):
        _fail(failures, "artist_review_state_invalid", "MUSEUM-03B artists must remain reviewed and not public")

    per_artist = Counter(item.get("approved_artist_id") for item in artworks)
    if len(artworks) != NOMINAL_ARTWORK_COUNT:
        _fail(failures, "artwork_count_mismatch", f"Expected nominal 44 artworks, observed {len(artworks)}")
    for artist_id in artist_ids:
        if per_artist[artist_id] < 2:
            _fail(failures, "artist_artwork_minimum_failed", f"Artist {artist_id} has fewer than two artworks")
    for artwork in artworks:
        _validate_artwork(artwork, artist_ids, indexed, failures)
    if len(artwork_selection_bases) != 1:
        _fail(failures, "artwork_selection_basis_missing", "Exactly one formal artwork-selection basis is required")
    else:
        _validate_artwork_selection_basis(artwork_selection_bases[0], artworks, failures)

    context_ids = {item.get("id") for item in contexts}
    for context in contexts:
        if not context.get("claim_ids") or not context.get("source_ids") or not context.get("source_license_bindings"):
            _fail(failures, "context_unsourced", f"Context lacks Claim/Source/license closure: {context.get('id')}")
    degree: Counter[str] = Counter()
    inverse_keys: set[tuple[str, str, str]] = set()
    if len(relationships) != EXPECTED_RELATIONSHIP_COUNT:
        _fail(failures, "relationship_count_mismatch", f"Expected 36 formal relationships, observed {len(relationships)}")
    if len(relationships) < MINIMUM_RELATIONSHIP_COUNT:
        _fail(failures, "relationship_minimum_failed", "Fewer than 30 formal relationships")
    for relationship in relationships:
        source_id = relationship.get("source_entity_id")
        target_id = relationship.get("target_entity_id")
        if source_id in artist_ids:
            degree[str(source_id)] += 1
        if target_id in artist_ids:
            degree[str(target_id)] += 1
        key = (str(relationship.get("relationship_type")), *sorted((str(source_id), str(target_id))))
        if key in inverse_keys:
            _fail(failures, "relationship_duplicate_inverse", f"Duplicate inverse relationship: {relationship.get('id')}")
        inverse_keys.add(key)
        if relationship.get("evidence_level") == "C":
            if relationship.get("relationship_semantics") != "curatorial_comparison" or not relationship.get("context_entity_ids"):
                _fail(failures, "relationship_c_context_missing", f"C relationship lacks explicit curatorial context: {relationship.get('id')}")
        if relationship.get("is_algorithmic") is not False or relationship.get("computational_similarity") is not None:
            _fail(failures, "relationship_algorithmic_forbidden", f"Algorithmic relationship is forbidden: {relationship.get('id')}")
        if not set(relationship.get("context_entity_ids", [])) <= context_ids:
            _fail(failures, "relationship_context_missing", f"Relationship has absent context: {relationship.get('id')}")
        if relationship.get("evidence_level") == "C" and relationship.get("relationship_type") in {
            "explicitly_influenced", "explicitly_influenced_by", "student_of", "teacher_of",
            "worked_in_studio_of", "collaborated_with", "referenced_or_quoted",
        }:
            _fail(failures, "curatorial_causal_wording", f"C relationship asserts a direct historical predicate: {relationship.get('id')}")
    for artist_id in artist_ids:
        if degree[artist_id] < 2:
            _fail(failures, "isolated_primary_artist", f"Primary artist degree is below two: {artist_id}")

    _validate_relationship_dispositions(dispositions, relationships, failures)

    if len(assessments) != len(artworks):
        _fail(failures, "media_assessment_count_mismatch", "Every artwork needs one media assessment")
    media_counts = Counter(item.get("outcome") for item in assessments)
    for item in assessments:
        if item.get("bytes_downloaded") is not False or item.get("media_bytes_present") is not False:
            _fail(failures, "media_bytes_forbidden", f"Media bytes present for {item.get('id')}")
        if (item.get("technical_delivery") or {}).get("cache_bytes") is not False:
            _fail(failures, "media_cache_forbidden", f"Media caching enabled for {item.get('id')}")
    if media_counts != Counter({"self_hosted_open_media_eligible": 31, "metadata_only": 9, "external_iiif_candidate": 4}):
        _fail(failures, "media_outcome_distribution_mismatch", f"Unexpected media distribution: {dict(media_counts)}")

    roles = {item.get("review_role") for item in signoffs}
    required_roles = {
        "identity_reviewer", "art_history_reviewer", "artwork_attribution_reviewer", "relationship_reviewer",
        "rights_reviewer", "multilingual_reviewer", "data_reviewer", "release_reviewer",
    }
    if not required_roles <= roles:
        _fail(failures, "review_role_coverage_missing", f"Missing review roles: {sorted(required_roles - roles)}")
    _validate_tracked_batch_signoffs(
        signoffs,
        artists=artists,
        artworks=artworks,
        contexts=contexts,
        relationships=relationships,
        claims=claims,
        evidence=evidence,
        sources=sources,
        assessments=assessments,
        dispositions=dispositions,
        artwork_selection_basis=artwork_selection_bases[0] if len(artwork_selection_bases) == 1 else None,
        failures=failures,
    )

    if len(graphs) != 1:
        _fail(failures, "graph_input_missing", "Exactly one graph input is required")
    else:
        _validate_graph(graphs[0], artists, contexts, relationships, claims, evidence, sources, failures)
    if len(formal_manifests) != 1:
        _fail(failures, "formal_batch_manifest_missing", "Exactly one formal batch manifest is required")
    else:
        _validate_formal_manifest(formal_manifests[0], artists, artworks, contexts, relationships, claims, evidence, sources, assessments, signoffs, failures)

    _scan_for_published(indexed.values(), failures)
    if package_manifest.get("no_media_bytes") is not True or package_manifest.get("no_published_state") is not True:
        _fail(failures, "package_boundary_declaration_invalid", "Package must declare no media bytes and no published state")
    return {
        "artists": len(artists),
        "artworks": len(artworks),
        "contexts": len(contexts),
        "relationships": len(relationships),
        "relationship_levels": dict(Counter(item.get("evidence_level") for item in relationships)),
        "claims": len(claims),
        "evidence": len(evidence),
        "sources": len(sources),
        "rights_records": len(assessments),
        "review_records": len(signoffs),
        "relationship_dispositions": len(dispositions),
        "per_artist_artworks": dict(sorted(per_artist.items())),
        "per_artist_degree": dict(sorted(degree.items())),
        "media_outcomes": dict(sorted(media_counts.items())),
    }


def _validate_artwork(
    artwork: dict[str, Any],
    artist_ids: set[Any],
    indexed: dict[str, dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    artwork_id = artwork.get("id")
    if artwork.get("approved_artist_id") not in artist_ids:
        _fail(failures, "artwork_unapproved_artist", f"Artwork is bound to an unapproved artist: {artwork_id}")
    official = artwork.get("official_object_record") or {}
    required = {"source_id", "source_object_id", "official_object_url", "raw_snapshot_id", "raw_snapshot_hash", "accessed_at"}
    if not required <= set(official):
        _fail(failures, "artwork_official_object_missing", f"Official object closure is incomplete: {artwork_id}")
    claim_ids = set(artwork.get("claim_ids", []))
    scalar_claims = {
        artwork.get("approved_artist_association_claim_id"), artwork.get("creation_date_claim_id"),
        artwork.get("holding_institution_claim_id"), artwork.get("accession_number_claim_id"),
    }
    field_claims = {
        item.get("claim_id")
        for field in ("material_records", "technique_records", "subject_records")
        for item in artwork.get(field, [])
        if isinstance(item, dict)
    }
    if not (scalar_claims | field_claims) <= claim_ids:
        _fail(failures, "artwork_claim_listing_incomplete", f"Artwork field claims are not all listed: {artwork_id}")
    for claim_id in claim_ids:
        claim = indexed.get(claim_id, {})
        if claim.get("entity_type") != "claim" or claim.get("subject_id") != artwork_id:
            _fail(failures, "artwork_claim_semantics_mismatch", f"Artwork claim does not resolve its subject: {claim_id}")
    if indexed.get(artwork.get("media_eligibility_assessment_id"), {}).get("artwork_id") != artwork_id:
        _fail(failures, "artwork_media_assessment_missing", f"Artwork media assessment does not resolve: {artwork_id}")
    if artwork.get("media_asset_ids"):
        _fail(failures, "artwork_media_asset_forbidden", f"MUSEUM-03B artwork must not bind media bytes/assets: {artwork_id}")


def _validate_artwork_selection_basis(
    basis: dict[str, Any],
    artworks: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    if (
        basis.get("id") != "artwork-selection-basis:museum-03b-first-slate-v1"
        or basis.get("batch_id") != EXPECTED_BATCH_ID
        or basis.get("selection_application_id") != EXPECTED_SELECTION_APPLICATION_ID
    ):
        _fail(failures, "artwork_selection_identity_mismatch", "Artwork-selection basis does not bind the approved batch/application")
    if tuple(basis.get("approved_artist_ids", [])) != EXPECTED_ARTIST_IDS:
        _fail(failures, "artwork_selection_artist_set_mismatch", "Artwork-selection basis differs from the exact approved artist slate")
    if (
        basis.get("nominal_target") != NOMINAL_ARTWORK_COUNT
        or basis.get("acceptable_range") != {"minimum": 36, "maximum": 48}
        or basis.get("minimum_per_artist") != 2
    ):
        _fail(failures, "artwork_selection_policy_mismatch", "Artwork-selection policy fields differ from the approved batch")
    if basis.get("review_signoff_ids") != ["review-signoff:museum-03b-batch-data"]:
        _fail(failures, "artwork_selection_signoff_mismatch", "Artwork-selection basis must bind the tracked data review")

    selections = basis.get("selections", [])
    if not isinstance(selections, list) or len(selections) != NOMINAL_ARTWORK_COUNT:
        _fail(failures, "artwork_selection_count_mismatch", "Artwork-selection basis must contain exactly 44 selections")
        return
    artwork_index = {item.get("id"): item for item in artworks}
    observed_ids = [item.get("artwork_id") for item in selections if isinstance(item, dict)]
    if len(observed_ids) != len(set(observed_ids)) or set(observed_ids) != set(artwork_index):
        _fail(failures, "artwork_selection_artwork_closure_mismatch", "Selections must bind every packaged artwork exactly once")
    for selection in selections:
        if not isinstance(selection, dict):
            _fail(failures, "artwork_selection_invalid", "Artwork selection must be an object")
            continue
        artwork = artwork_index.get(selection.get("artwork_id"))
        if artwork is None:
            continue
        official = artwork.get("official_object_record") or {}
        expected = {
            "artwork_id": artwork.get("id"),
            "approved_artist_id": artwork.get("approved_artist_id"),
            "source_id": official.get("source_id"),
            "source_object_id": str(official.get("source_object_id")),
            "official_object_url": official.get("official_object_url"),
            "rights_preflight_id": artwork.get("rights_preflight_id"),
        }
        observed = {key: selection.get(key) for key in expected}
        if observed != expected:
            _fail(failures, "artwork_selection_projection_mismatch", f"Selection does not resolve packaged artwork semantics: {artwork.get('id')}")

    tuples = _artwork_selection_tuples(basis)
    if canonical_sha256(tuples) != EXPECTED_ARTWORK_SELECTION_TUPLE_HASH:
        _fail(failures, "artwork_selection_tuple_hash_mismatch", "Artwork-selection identity/source/rights tuples differ from the reviewed basis")
    sorted_selections = sorted(selections, key=lambda item: str(item.get("artwork_id")) if isinstance(item, dict) else "")
    if canonical_sha256(sorted_selections) != EXPECTED_ARTWORK_SELECTION_SET_HASH:
        _fail(failures, "artwork_selection_set_hash_mismatch", "Artwork-selection content differs from the exact reviewed set")
    if canonical_sha256(selections) != EXPECTED_ARTWORK_SELECTION_ORDERED_HASH:
        _fail(failures, "artwork_selection_ordered_hash_mismatch", "Artwork-selection order/content differs from the deterministic reviewed basis")


def _validate_relationship_dispositions(
    dispositions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    inherited = sorted(
        (item for item in dispositions if item.get("origin_kind") == "inherited_lead"),
        key=lambda item: str(item.get("lead_id")),
    )
    curated = sorted(
        (item for item in dispositions if item.get("origin_kind") == "new_curated_candidate"),
        key=lambda item: str(item.get("research_candidate_id")),
    )
    if len(inherited) != EXPECTED_INHERITED_LEAD_COUNT:
        _fail(failures, "relationship_lead_closure_mismatch", f"Expected 45 inherited dispositions, observed {len(inherited)}")
    if len(dispositions) != 69 or len(curated) != 24:
        _fail(failures, "relationship_research_candidate_count_mismatch", "Expected 69 dispositions including 24 new curated candidates")
    if len(inherited) + len(curated) != len(dispositions):
        _fail(failures, "relationship_disposition_origin_invalid", "Every disposition must be inherited or newly curated")

    inherited_ids = [item.get("lead_id") for item in inherited]
    curated_ids = [item.get("research_candidate_id") for item in curated]
    if canonical_sha256(inherited_ids) != EXPECTED_INHERITED_LEAD_ID_SET_HASH:
        _fail(failures, "relationship_inherited_id_set_mismatch", "Inherited lead IDs differ from the exact reviewed closure")
    if canonical_sha256(curated_ids) != EXPECTED_CURATED_CANDIDATE_ID_SET_HASH:
        _fail(failures, "relationship_curated_id_set_mismatch", "Curated candidate IDs differ from the exact reviewed closure")
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
    if canonical_sha256(inherited_projection) != EXPECTED_INHERITED_DISPOSITION_PROJECTION_HASH:
        _fail(failures, "relationship_inherited_disposition_mismatch", "Inherited disposition/status/formal mapping differs from the reviewed closure")
    if canonical_sha256(curated_projection) != EXPECTED_CURATED_DISPOSITION_PROJECTION_HASH:
        _fail(failures, "relationship_curated_disposition_mismatch", "Curated disposition/status/formal mapping differs from the reviewed closure")

    relationship_index = {item.get("id"): item for item in relationships}
    disposition_index = {item.get("id"): item for item in dispositions}
    promoted_by_relationship: dict[Any, list[dict[str, Any]]] = {}
    inherited_by_lead = {item.get("lead_id"): item for item in inherited}
    for disposition in dispositions:
        origin = disposition.get("origin_kind")
        if origin == "inherited_lead" and disposition.get("research_candidate_id") is not None:
            _fail(failures, "relationship_disposition_origin_field_mismatch", f"Inherited disposition has a curated candidate ID: {disposition.get('id')}")
        if origin == "new_curated_candidate" and (
            disposition.get("lead_id") is not None or disposition.get("superseded_by_lead_id") is not None
        ):
            _fail(failures, "relationship_disposition_origin_field_mismatch", f"Curated disposition has inherited-lead fields: {disposition.get('id')}")
        status = disposition.get("disposition")
        formal_id = disposition.get("formal_relationship_id")
        superseded_by = disposition.get("superseded_by_lead_id")
        if status == "promoted_to_formal_relationship":
            if not isinstance(formal_id, str):
                _fail(failures, "relationship_disposition_formal_missing", f"Promoted disposition lacks a formal relationship: {disposition.get('id')}")
            else:
                promoted_by_relationship.setdefault(formal_id, []).append(disposition)
                if relationship_index.get(formal_id, {}).get("research_disposition_id") != disposition.get("id"):
                    _fail(failures, "relationship_disposition_backlink_mismatch", f"Formal relationship backlink differs: {formal_id}")
        elif formal_id is not None:
            _fail(failures, "relationship_disposition_formal_unexpected", f"Non-promoted disposition binds a formal relationship: {disposition.get('id')}")
        if status == "superseded":
            target = inherited_by_lead.get(superseded_by)
            if target is None or target.get("disposition") != "promoted_to_formal_relationship":
                _fail(failures, "relationship_disposition_supersession_invalid", f"Superseded disposition does not resolve a promoted inherited lead: {disposition.get('id')}")
        elif superseded_by is not None:
            _fail(failures, "relationship_disposition_supersession_unexpected", f"Non-superseded disposition has a supersession target: {disposition.get('id')}")

    relationship_ids = sorted(relationship_index)
    if canonical_sha256(relationship_ids) != EXPECTED_FORMAL_RELATIONSHIP_ID_SET_HASH:
        _fail(failures, "relationship_formal_id_set_mismatch", "Formal relationship IDs differ from the exact reviewed closure")
    if set(promoted_by_relationship) != set(relationship_index) or any(len(items) != 1 for items in promoted_by_relationship.values()):
        _fail(failures, "relationship_disposition_formal_closure_mismatch", "Every formal relationship must resolve exactly one promoted disposition")
    for relationship in relationships:
        disposition = disposition_index.get(relationship.get("research_disposition_id"))
        if (
            disposition is None
            or disposition.get("disposition") != "promoted_to_formal_relationship"
            or disposition.get("formal_relationship_id") != relationship.get("id")
        ):
            _fail(failures, "relationship_backlink_disposition_mismatch", f"Relationship does not resolve its promoted disposition: {relationship.get('id')}")


def _validate_tracked_batch_signoffs(
    signoffs: list[dict[str, Any]],
    *,
    artists: list[dict[str, Any]],
    artworks: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    dispositions: list[dict[str, Any]],
    artwork_selection_basis: dict[str, Any] | None,
    failures: list[dict[str, str]],
) -> None:
    document = _read_json(DEFAULT_BATCH_REVIEW_SIGNOFFS, failures, "batch_review_set_invalid")
    if not isinstance(document, dict):
        return
    expected_content = canonical_sha256({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected_content or expected_content != EXPECTED_BATCH_REVIEW_SET_CONTENT_HASH:
        _fail(failures, "batch_review_set_hash_mismatch", "Tracked batch review set differs from the approved hash-bound record")
        return
    review_basis = document.get("review_basis")
    tracked_signoffs = document.get("signoffs")
    if not isinstance(review_basis, dict) or not isinstance(tracked_signoffs, list):
        _fail(failures, "batch_review_set_invalid", "Tracked batch review set lacks its review basis or sign-offs")
        return
    if document.get("review_basis_hash") != canonical_sha256(review_basis):
        _fail(failures, "batch_review_basis_hash_mismatch", "Tracked batch review-basis hash is invalid")
    if document.get("signoff_set_hash") != canonical_sha256(tracked_signoffs):
        _fail(failures, "batch_review_signoff_hash_mismatch", "Tracked batch sign-off hash is invalid")
    packaged = sorted((item for item in signoffs if item.get("id") in _BATCH_SIGNOFF_IDS), key=lambda item: item.get("id", ""))
    tracked = sorted(tracked_signoffs, key=lambda item: item.get("id", "") if isinstance(item, dict) else "")
    if packaged != tracked:
        _fail(failures, "batch_review_signoff_records_mismatch", "Packaged batch sign-offs differ from the pre-existing tracked review records")

    collections = {
        "artists": artists,
        "artworks": artworks,
        "contexts": contexts,
        "relationships": relationships,
        "claims": claims,
        "evidence": evidence,
        "sources": sources,
        "media_assessments": assessments,
        "relationship_dispositions": dispositions,
    }
    observed_id_hashes = {
        key: canonical_sha256(sorted(item.get("id") for item in records))
        for key, records in collections.items()
    }
    if review_basis.get("record_id_set_hashes") != observed_id_hashes:
        _fail(failures, "batch_review_record_set_mismatch", "Packaged record ID sets differ from the tracked review basis")
    if review_basis.get("relationship_closure_hashes") != _relationship_closure_hashes(dispositions, relationships):
        _fail(failures, "batch_review_relationship_closure_mismatch", "Packaged relationship closure differs from the tracked review basis")
    if artwork_selection_basis is not None:
        selection_hash = canonical_sha256(_artwork_selection_tuples(artwork_selection_basis))
        if review_basis.get("artwork_selection_tuple_hash") != selection_hash:
            _fail(failures, "batch_review_artwork_selection_mismatch", "Packaged artwork selections differ from the tracked review basis")


def _relationship_closure_hashes(
    dispositions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, str]:
    inherited = sorted(
        (item for item in dispositions if item.get("origin_kind") == "inherited_lead"),
        key=lambda item: str(item.get("lead_id")),
    )
    curated = sorted(
        (item for item in dispositions if item.get("origin_kind") == "new_curated_candidate"),
        key=lambda item: str(item.get("research_candidate_id")),
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
        "inherited_lead_id_set": canonical_sha256([item.get("lead_id") for item in inherited]),
        "curated_candidate_id_set": canonical_sha256([item.get("research_candidate_id") for item in curated]),
        "inherited_disposition_projection": canonical_sha256(inherited_projection),
        "curated_disposition_projection": canonical_sha256(curated_projection),
        "formal_relationship_id_set": canonical_sha256(sorted(item.get("id") for item in relationships)),
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
        (
            {key: selection.get(key) for key in fields}
            for selection in selection_basis.get("selections", [])
            if isinstance(selection, dict)
        ),
        key=lambda item: str(item["artwork_id"]),
    )


def _validate_graph(
    graph: dict[str, Any],
    artists: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    artists = sorted(artists, key=lambda item: str(item.get("id")))
    contexts = sorted(contexts, key=lambda item: str(item.get("id")))
    relationships = sorted(relationships, key=lambda item: str(item.get("id")))
    claim_index = {item.get("id"): item for item in claims}
    evidence_index = {item.get("id"): item for item in evidence}
    expected_artist_ids = [item.get("id") for item in artists]
    expected_primary = [
        {
            "artist_id": item.get("id"),
            "node_role": "primary_artist",
            "labels": item.get("labels"),
            "claim_ids": sorted(item.get("claim_ids", [])),
            "filter_values": [],
        }
        for item in artists
    ]
    expected_contexts = [
        {
            "context_id": item.get("id"),
            "entity_type": item.get("entity_type"),
            "node_role": "supporting_context",
            "labels": item.get("labels"),
            "claim_ids": sorted(item.get("claim_ids", [])),
            "filter_values": [{"key": "context_type", "value": item.get("entity_type")}],
        }
        for item in contexts
    ]
    expected_edges = [_graph_edge_projection(item, claim_index) for item in relationships]
    if graph.get("approved_artist_ids") != expected_artist_ids or graph.get("primary_nodes") != expected_primary:
        _fail(failures, "graph_primary_projection_mismatch", "Graph primary-node projection differs from the exact packaged artists")
    if graph.get("context_nodes") != expected_contexts:
        _fail(failures, "graph_context_projection_mismatch", "Graph context-node projection differs from the exact packaged contexts")
    if graph.get("edges") != expected_edges:
        _fail(failures, "graph_edge_projection_mismatch", "Graph edge projection differs from the exact packaged relationships")

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
    graph_source_ids &= {item.get("id") for item in sources}
    if graph.get("claim_ids") != sorted(graph_claim_ids):
        _fail(failures, "graph_claim_aggregate_mismatch", "Graph claim aggregate differs from the exact node/edge claim union")
    if graph.get("evidence_ids") != sorted(graph_evidence_ids):
        _fail(failures, "graph_evidence_aggregate_mismatch", "Graph evidence aggregate differs from the exact claim/relationship closure")
    if graph.get("source_ids") != sorted(graph_source_ids):
        _fail(failures, "graph_source_aggregate_mismatch", "Graph source aggregate differs from the exact evidence/entity closure")
    if graph.get("review_signoff_ids") != [
        "review-signoff:museum-03b-batch-data",
        "review-signoff:museum-03b-batch-relationship",
    ]:
        _fail(failures, "graph_signoff_closure_mismatch", "Graph does not bind the tracked data and relationship reviews")
    if graph.get("no_auto_replacement") is not True or graph.get("no_algorithmic_edges") is not True:
        _fail(failures, "graph_safety_declaration_invalid", "Graph safety declarations are not closed")
    if graph.get("no_media_dependency") is not True or graph.get("public_release") is not False:
        _fail(failures, "graph_release_boundary_invalid", "Graph must be static, no-media, and non-public")


def _graph_edge_projection(
    relationship: dict[str, Any],
    claim_index: dict[Any, dict[str, Any]],
) -> dict[str, Any]:
    claim_ids = sorted(relationship.get("claim_ids", []))
    evidence_ids = sorted(
        {
            evidence_id
            for claim_id in claim_ids
            for evidence_id in claim_index.get(claim_id, {}).get("evidence_ids", [])
        }
        | set(relationship.get("evidence_ids", []))
    )
    return {
        "relationship_id": relationship.get("id"),
        "source_artist_id": relationship.get("source_entity_id"),
        "target_entity_id": relationship.get("target_entity_id"),
        "relationship_type": relationship.get("relationship_type"),
        "directed": relationship.get("directed"),
        "evidence_level": relationship.get("evidence_level"),
        "explanation": relationship.get("educational_rationale") or relationship.get("curatorial_note"),
        "context_entity_ids": sorted(relationship.get("context_entity_ids", [])),
        "temporal_scope": relationship.get("temporal_scope"),
        "place_ids": sorted((relationship.get("place_scope") or {}).get("place_ids", [])),
        "historical_relationship_strength": relationship.get("historical_relationship_strength"),
        "evidence_confidence": relationship.get("evidence_confidence"),
        "computational_similarity": relationship.get("computational_similarity"),
        "curatorial_relevance": relationship.get("curatorial_relevance"),
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "source_ids": sorted(relationship.get("source_ids", [])),
        "filter_values": [
            {"key": "evidence_level", "value": relationship.get("evidence_level")},
            {"key": "relationship_type", "value": relationship.get("relationship_type")},
        ],
        "is_algorithmic": relationship.get("is_algorithmic"),
        "media_dependency": False,
    }


def _validate_formal_manifest(
    manifest: dict[str, Any],
    artists: list[dict[str, Any]],
    artworks: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    signoffs: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    collections = {
        "artist_ids": artists,
        "artwork_ids": artworks,
        "context_ids": contexts,
        "relationship_ids": relationships,
        "claim_ids": claims,
        "evidence_ids": evidence,
        "source_ids": sources,
        "rights_record_ids": assessments,
        "review_record_ids": signoffs,
    }
    for field, records in collections.items():
        if manifest.get(field) != [item.get("id") for item in records]:
            _fail(failures, "formal_manifest_id_closure_mismatch", f"Formal manifest {field} differs from packaged records")
    expected_normalized_ids = sorted(
        item.get("id")
        for records in (artists, artworks, contexts, relationships)
        for item in records
    )
    if manifest.get("normalized_ids") != expected_normalized_ids:
        _fail(failures, "formal_manifest_normalized_id_mismatch", "Formal manifest normalized IDs differ from packaged entities")
    adapter_versions = manifest.get("adapter_versions", [])
    observed_adapter_versions = {
        item.get("source_id"): item.get("version")
        for item in adapter_versions
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    expected_adapter_versions = {
        source.get("id"): get_adapter(str(source.get("id")).removeprefix("source:")).adapter_version
        for source in sources
    }
    if len(observed_adapter_versions) != len(adapter_versions) or observed_adapter_versions != expected_adapter_versions:
        _fail(failures, "formal_manifest_adapter_version_mismatch", "Formal manifest adapter versions differ from the runtime adapters")
    if manifest.get("reviewer_signoff_ids") != [
        "review-signoff:museum-03b-batch-data",
        "review-signoff:museum-03b-batch-release",
    ]:
        _fail(failures, "formal_manifest_signoff_mismatch", "Formal manifest does not bind the tracked data/release reviews")
    _validate_code_commit(manifest.get("code_commit"), failures)
    expected_counts = {
        "artists": len(artists), "artworks": len(artworks), "contexts": len(contexts),
        "relationships": len(relationships), "claims": len(claims), "evidence": len(evidence),
        "sources": len(sources), "rights_records": len(assessments), "review_records": len(signoffs),
        "exclusions": len(manifest.get("exclusions", [])), "blocked_records": len(manifest.get("blocked_records", [])),
        "raw_snapshots": len(manifest.get("raw_snapshots", [])), "normalized": len(manifest.get("normalized_ids", [])),
    }
    if manifest.get("counts") != expected_counts:
        _fail(failures, "formal_manifest_counts_mismatch", "Formal manifest counts differ from declared collections")
    if (manifest.get("no_media_declaration") or {}).get("media_bytes_downloaded") is not False:
        _fail(failures, "formal_manifest_media_boundary_invalid", "Formal manifest must declare no media download")
    no_public = manifest.get("no_public_release_declaration") or {}
    if no_public.get("formal_public_release_created") is not False or no_public.get("pages_art_content_added") is not False:
        _fail(failures, "formal_manifest_public_boundary_invalid", "Formal manifest must declare no public release/Pages art")


def _validate_code_commit(value: Any, failures: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        _fail(failures, "code_commit_invalid", "Formal manifest code_commit must be an exact lowercase 40-character Git commit")
        return
    try:
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{value}^{{commit}}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        _fail(failures, "code_commit_verification_unavailable", f"Cannot execute Git: {error}")
        return
    if exists.returncode != 0:
        _fail(failures, "code_commit_unknown", "Formal manifest code_commit does not resolve to a local Git commit")
        return
    # The code anchor proves which implementation created the immutable M03B
    # package. Later phases append schemas and dispatch entries, so comparing
    # that historical commit byte-for-byte with the current implementation
    # would incorrectly invalidate an unchanged sealed package. Current schema,
    # reference, hash and physical closure are independently checked above.
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", value, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestor.returncode != 0:
        _fail(
            failures,
            "code_commit_not_ancestor",
            "Formal manifest code_commit is not an ancestor of the current main history",
        )


def _validate_declared_closure(
    by_file: dict[str, list[dict[str, Any]]],
    indexed: dict[str, dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    package_manifests = _records_of(indexed, "reviewed_package_manifest")
    if package_manifests:
        _fail(failures, "nested_package_manifest_forbidden", "The self-describing package manifest must not be declared inside itself")
    required_types = {
        "selection_decision", "selection_decision_application", "approved_identity_basis", "artwork_selection_basis",
        "snapshot_receipt_ledger", "artist", "artwork", "material", "technique", "subject", "relationship",
        "claim", "evidence", "source", "media_eligibility_assessment", "relationship_research_disposition",
        "review_signoff", "graph_input", "formal_art_batch_manifest", "public_leakage_label_set",
    }
    present = {record.get("entity_type") for records in by_file.values() for record in records}
    if not required_types <= present:
        _fail(failures, "package_required_record_type_missing", f"Missing record types: {sorted(required_types - present)}")


def _validate_content_hashes(
    indexed: dict[str, dict[str, Any]],
    package_manifest: dict[str, Any],
    failures: list[dict[str, str]],
) -> None:
    for record in indexed.values():
        if "content_hash" not in record:
            continue
        expected = canonical_sha256({key: value for key, value in record.items() if key != "content_hash"})
        if record.get("content_hash") != expected:
            _fail(failures, "record_content_hash_mismatch", f"Content hash differs for {record.get('id')}")
    expected_package_hash = canonical_sha256(package_manifest.get("files", []))
    if package_manifest.get("content_hash") != expected_package_hash:
        _fail(failures, "package_content_hash_mismatch", "Package content hash differs from the canonical file ledger")


def _scan_for_published(records: Any, failures: list[dict[str, str]]) -> None:
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"status", "review_status", "lifecycle_status", "publish_status", "to", "from"} and child == "published":
                    _fail(failures, "published_state_forbidden", f"Published state found at {path}.{key}")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
    for index, record in enumerate(records):
        visit(record, f"records[{index}]")


def _schema_check(
    record: dict[str, Any],
    failures: list[dict[str, str]],
    location: str,
    environment: Any,
) -> None:
    for issue in validate_record(record, environment=environment):
        _fail(failures, f"schema_{issue.code}", issue.message, f"{location}{issue.location}")


def _schema_versions() -> dict[str, str]:
    document = json.loads((ROOT / "schemas" / "schema-manifest.json").read_text(encoding="utf-8"))
    return {item["path"]: item["version"] for item in document["schemas"]}


def _records_of(indexed: dict[str, dict[str, Any]], entity_type: str) -> list[dict[str, Any]]:
    return [record for record in indexed.values() if record.get("entity_type") == entity_type]


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def _read_json(path: Path, failures: list[dict[str, str]], code: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail(failures, code, f"Cannot read JSON {path}: {error}")
        return None


def _parse_bytes(payload: bytes, failures: list[dict[str, str]], location: str) -> Any | None:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail(failures, "package_json_invalid", f"Cannot parse {location}: {error}")
        return None


def _absolute(path: Path) -> Path:
    value = path if path.is_absolute() else ROOT / path
    return Path(os.path.abspath(value))


def _fail(
    failures: list[dict[str, str]],
    code: str,
    message: str,
    location: str = "$",
) -> None:
    failures.append({"code": code, "message": message, "location": location})


def _result(package_dir: Path, failures: list[dict[str, str]], counts: dict[str, Any]) -> dict[str, Any]:
    unique = sorted(
        {(item["code"], item["message"], item["location"]) for item in failures},
        key=lambda item: (item[0], item[2], item[1]),
    )
    normalized = [{"code": code, "message": message, "location": location} for code, message, location in unique]
    return {
        "ok": not normalized,
        "phase_id": "MUSEUM-03B",
        "package_dir": str(package_dir),
        "counts": counts,
        "failure_count": len(normalized),
        "failures": normalized,
    }
