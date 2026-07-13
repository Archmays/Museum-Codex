from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlencode

from museum_pipeline.config import ROOT, source_configuration, source_license_rules
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_bytes, sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record


BATCH_ID = "art-batch:museum-03b-first-slate-v1"
DEFAULT_SELECTION_BASIS = ROOT / "research" / "art" / "museum-03b-artwork-selection-basis.json"
DEFAULT_SNAPSHOT_RECEIPTS = ROOT / "research" / "art" / "museum-03b-artwork-snapshot-receipts.json"
DEFAULT_OUTPUT = ROOT / "data" / "reviewed" / "art" / "museum-03b" / "museum-03b-first-slate-v1"
CURATION_RAW_RELATIVE = Path("data/raw/curation_museum03a/20260713-survey-final")

SOURCE_RECORD_IDS = {
    "met_open_access": "source:met_open_access",
    "aic_api": "source:aic_api",
}
INSTITUTION_IDS = {
    "met_open_access": "museum_institution:metropolitan-museum-of-art",
    "aic_api": "museum_institution:art-institute-of-chicago",
}
INSTITUTION_LABELS = {
    "met_open_access": "The Metropolitan Museum of Art",
    "aic_api": "Art Institute of Chicago",
}


def _selection() -> tuple[tuple[str, str, str], ...]:
    groups = (
        ("artist:albrecht-durer", "met_open_access", "436244 436243 459211 334816"),
        ("artist:francisco-de-goya", "met_open_access", "436545 436544 436546 436543"),
        ("artist:vincent-van-gogh", "met_open_access", "436533 436532 436528 437984"),
        ("artist:mary-cassatt", "aic_api", "111442 13506 26650 28826"),
        ("artist:kathe-kollwitz", "aic_api", "60513 158971"),
        ("artist:julia-margaret-cameron", "met_open_access", "267426 282043 283099 268690"),
        ("artist:katsushika-hokusai", "met_open_access", "39799 54305 54303 56128"),
        ("artist:kitagawa-utamaro", "met_open_access", "56716 54876 45323 37110"),
        ("artist:shen-zhou", "met_open_access", "53601 53602 53603 51858"),
        ("artist:raja-ravi-varma", "met_open_access", "851484 851486"),
        ("artist:jose-guadalupe-posada", "met_open_access", "717597 729644 358856 735905"),
        ("artist:henry-ossawa-tanner", "met_open_access", "16947 17016 12774 372068"),
    )
    return tuple((artist_id, source_id, object_id) for artist_id, source_id, ids in groups for object_id in ids.split())


EXPECTED_SELECTION = _selection()
EXPECTED_MEDIA_DISTRIBUTION = {
    "self_hosted_open_media_eligible": 31,
    "external_iiif_candidate": 4,
    "metadata_only": 9,
}
EXPECTED_UNKNOWN_DATE_OBJECTS = {"54876", "53601", "53602", "53603", "51858", "17016"}
EXPECTED_EXCLUDED_CANDIDATE_COUNT = 4
EXPECTED_EXCLUDED_CANDIDATE_SET_HASH = "sha256:95e3e485a7174ec373c992e4a80fc6662e4ab1e721588950ccd65bb4c89b053e"
OUTPUT_FILES = (
    "artwork-selection-basis.json",
    "artworks.json",
    "artwork-claims.json",
    "artwork-evidence.json",
    "media-eligibility-assessments.json",
    "artwork-review-signoffs.json",
)
MOJIBAKE_MARKERS = ("瀹", "鏀", "棌", "牳", "锛", "銆", "�")
EXPECTED_RIGHTS_PREFLIGHT_PROVENANCE = {
    "source_path": "data/review/curation/museum-03a/bundle-20260713-v5/artwork-rights-preflight.json",
    "source_sha256": "sha256:27b756e2bdfd291b2e81ba1b5488361c586a848bf8209951c4289f349259bf59",
    "source_record_count": 91,
    "selected_record_count": 44,
    "selection_key_fields": ["source_id", "official_object_id"],
    "copied_fields": [
        "id", "preflight_status", "attribution_required", "delivery_mode", "media_license",
        "media_license_basis", "modification_allowed", "rights_evidence", "rights_page_url", "risk",
        "technical_availability",
    ],
}


def _contains_mojibake(value: str) -> bool:
    return "?" in value or any(marker in value for marker in MOJIBAKE_MARKERS)


def build_artwork_stage(
    *,
    selection_basis_path: Path = DEFAULT_SELECTION_BASIS,
    snapshot_receipts_path: Path = DEFAULT_SNAPSHOT_RECEIPTS,
    output_dir: Path = DEFAULT_OUTPUT,
    repository_root: Path = ROOT,
) -> dict[str, Any]:
    """Build the exact reviewed Wave 3 metadata batch without acquiring media."""
    basis = _load_object(selection_basis_path, "artwork_selection_basis_invalid")
    ledger = _load_object(snapshot_receipts_path, "artwork_snapshot_ledger_invalid")
    _validate_basis(basis)
    receipt_index, source_records = _validate_receipts(basis, ledger, repository_root.resolve())

    artworks: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    signoffs: list[dict[str, Any]] = []
    for decision in basis["entries"]:
        key = (decision["source_id"], decision["source_object_id"])
        built = _build_one(decision, receipt_index[key], source_records[key], basis)
        artworks.append(built["artwork"])
        claims.extend(built["claims"])
        evidence.extend(built["evidence"])
        assessments.append(built["media_assessment"])
        signoffs.extend(built["signoffs"])

    payloads = {
        "artwork-selection-basis.json": {},
        "artworks.json": artworks,
        "artwork-claims.json": claims,
        "artwork-evidence.json": evidence,
        "media-eligibility-assessments.json": assessments,
        "artwork-review-signoffs.json": signoffs,
    }
    payloads["artwork-selection-basis.json"] = _formal_selection_basis(basis, artworks, signoffs)
    _validate_outputs(payloads, basis, ledger)
    serialized = {name: _pretty_json(value) for name, value in payloads.items()}
    written, reused = _write_fail_closed(output_dir.resolve(), serialized)
    media_counts = dict(sorted(Counter(item["outcome"] for item in assessments).items()))
    return {
        "status": "pass",
        "batch_id": BATCH_ID,
        "output_dir": str(output_dir.resolve()),
        "files": {name: str(output_dir.resolve() / name) for name in OUTPUT_FILES},
        "written_files": written,
        "reused_files": reused,
        "artwork_count": len(artworks),
        "claim_count": len(claims),
        "evidence_count": len(evidence),
        "media_assessment_count": len(assessments),
        "review_signoff_count": len(signoffs),
        "media_eligibility_counts": media_counts,
        "media_bytes_acquired": 0,
        "public_records_created": 0,
        "payloads": payloads,
    }


def _validate_basis(basis: dict[str, Any]) -> None:
    expected_hash = canonical_sha256({key: value for key, value in basis.items() if key != "content_hash"})
    if basis.get("content_hash") != expected_hash:
        raise PipelineError("artwork_selection_basis_hash_mismatch", "Artwork selection basis content hash does not match")
    fixed = {
        "id": "artwork-selection-basis:museum-03b-first-slate-v1",
        "entity_type": "artwork_selection_basis",
        "batch_id": BATCH_ID,
        "selection_decision_application_id": "selection-decision-application:8c2666ef-fdfe-5250-af97-1d3b1d8c4a43",
        "identity_basis_id": "approved-identity-basis:museum-03b-first-slate-v1",
    }
    if any(basis.get(key) != value for key, value in fixed.items()):
        raise PipelineError("artwork_selection_basis_identity_mismatch", "Artwork selection basis identity or decision closure differs")
    entries = basis.get("entries")
    if not isinstance(entries, list):
        raise PipelineError("artwork_selection_basis_entries_invalid", "Artwork selection basis entries must be an array")
    observed = tuple((item.get("approved_artist_id"), item.get("source_id"), str(item.get("source_object_id"))) for item in entries)
    if observed != EXPECTED_SELECTION:
        raise PipelineError("artwork_selection_basis_exact_set_mismatch", "Artwork selection basis is not the exact ordered nominal 44")
    if (
        basis.get("excluded_candidate_count") != EXPECTED_EXCLUDED_CANDIDATE_COUNT
        or basis.get("excluded_candidate_set_hash") != EXPECTED_EXCLUDED_CANDIDATE_SET_HASH
    ):
        raise PipelineError(
            "artwork_selection_basis_exclusion_mismatch",
            "The private held-out candidate set no longer matches its reviewed aggregate closure",
        )
    if basis.get("expected_media_distribution") != EXPECTED_MEDIA_DISTRIBUTION:
        raise PipelineError("artwork_selection_basis_media_distribution_mismatch", "Reviewed media distribution differs from 31/4/9")
    if basis.get("rights_preflight_provenance") != EXPECTED_RIGHTS_PREFLIGHT_PROVENANCE:
        raise PipelineError("artwork_rights_preflight_provenance_mismatch", "Artwork rights preflight provenance is not the exact private MUSEUM-03A v5 source")
    counts = Counter(artist_id for artist_id, _, _ in observed)
    expected_counts = Counter(artist_id for artist_id, _, _ in EXPECTED_SELECTION)
    if counts != expected_counts or min(counts.values()) < 2:
        raise PipelineError("artwork_selection_basis_quota_mismatch", "Per-artist artwork quotas are not the reviewed exact quotas")
    sessions = basis.get("review_sessions", {})
    expected_roles = {"artwork_attribution_reviewer", "data_reviewer", "multilingual_reviewer", "rights_reviewer"}
    if set(sessions) != expected_roles:
        raise PipelineError("artwork_review_session_roles_mismatch", "Artwork basis requires four distinct review roles")
    timestamps = set()
    checklists = set()
    for role, session in sessions.items():
        if session.get("decision") != "accepted_reviewed" or any(row.get("result") != "pass" for row in session.get("checklist", [])):
            raise PipelineError("artwork_review_session_not_accepted", f"Review session is not accepted: {role}")
        timestamps.add(session.get("reviewed_at"))
        checklists.add(canonical_sha256(session.get("checklist")))
    if len(timestamps) != 4 or len(checklists) != 4:
        raise PipelineError("artwork_review_sessions_not_distinct", "Review roles require distinct timestamps and checklists")

    for order, item in enumerate(entries, 1):
        fields = item.get("expected_source_fields")
        if item.get("order") != order or not isinstance(fields, dict) or item.get("expected_source_fields_hash") != canonical_sha256(fields):
            raise PipelineError("artwork_selection_entry_hash_mismatch", f"Artwork basis entry is not stable at order {order}")
        for key in ("title", "medium", "accession_number", "object_url", "creator_display", "department", "credit_line"):
            if not isinstance(fields.get(key), str) or not fields[key].strip():
                raise PipelineError("artwork_required_source_field_missing", f"Missing {key} for {item['source_id']}:{item['source_object_id']}")
        translation = item.get("title_translation", {})
        text = translation.get("text")
        provenance = translation.get("provenance", {})
        if (
            translation.get("language") != "zh-Hans"
            or not isinstance(text, str)
            or not text.strip()
            or _contains_mojibake(text)
            or provenance.get("method") != "project_authored_translation"
            or provenance.get("decision") != "accepted_reviewed"
            or provenance.get("source_title_sha256") != sha256_bytes(fields["title"].encode("utf-8"))
        ):
            raise PipelineError("artwork_title_translation_invalid", f"Invalid reviewed zh-Hans title for {item['source_object_id']}")
        if (
            not isinstance(item.get("rights_preflight_id"), str)
            or not item["rights_preflight_id"].startswith("artwork-preflight:")
            or item.get("rights_preflight_status") not in {"rights_path_clear_candidate", "external_iiif_candidate", "metadata_only_candidate"}
            or not isinstance(item.get("preflight_media_rights"), dict)
        ):
            raise PipelineError("artwork_rights_preflight_basis_invalid", f"Invalid rights-preflight closure for {item['source_object_id']}")
        for key, prefix in (("material_ids", "material:"), ("technique_ids", "technique:"), ("subject_ids", "subject:")):
            values = item.get(key)
            minimum = 0 if key == "subject_ids" else 1
            if not isinstance(values, list) or len(values) < minimum or len(values) != len(set(values)) or any(not value.startswith(prefix) for value in values):
                raise PipelineError("artwork_classification_ids_invalid", f"Invalid {key} for {item['source_object_id']}")
        span = item.get("creation_span", {})
        if fields["date_display"] == "":
            if span != {"start": None, "end": None, "precision": "unknown", "uncertain": True, "description": "Official collection record does not state a display date; numeric life-span endpoints are excluded."}:
                raise PipelineError("artwork_life_year_fallback_detected", f"Blank display date was not preserved for {item['source_object_id']}")
        if item["source_object_id"] in {"53601", "53602", "53603", "51858"} and item["creator_attribution"].get("attribution_type") != "attributed_to":
            raise PipelineError("artwork_attribution_prefix_lost", f"Shen Zhou attribution prefix lost for {item['source_object_id']}")
        if item["source_object_id"] in {"851484", "851486"} and item["creator_attribution"] != {
            "attribution_type": "attributed_to",
            "disputed": True,
            "review_note": item["creator_attribution"].get("review_note"),
        }:
            raise PipelineError("artwork_posthumous_attribution_not_disputed", f"Ravi Varma attribution not disputed for {item['source_object_id']}")
        if item["source_object_id"] == "13506" and "Leroy" not in str(item.get("collaboration_note")):
            raise PipelineError("artwork_collaboration_note_missing", "Cassatt 13506 must preserve the Leroy printer credit")


def _validate_receipts(
    basis: dict[str, Any],
    ledger: dict[str, Any],
    repository_root: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    issues = validate_record(ledger)
    if issues:
        issue = issues[0]
        raise PipelineError("artwork_snapshot_ledger_schema_invalid", f"Artwork snapshot ledger schema invalid: {issue.code} at {issue.location}: {issue.message}")
    expected_hash = canonical_sha256({key: value for key, value in ledger.items() if key != "content_hash"})
    if ledger.get("content_hash") != expected_hash or ledger.get("batch_id") != BATCH_ID:
        raise PipelineError("artwork_snapshot_ledger_hash_mismatch", "Artwork snapshot ledger content hash or batch differs")
    entries = ledger.get("entries", [])
    if len(entries) != 44:
        raise PipelineError("artwork_snapshot_ledger_count_mismatch", "Artwork snapshot ledger must contain exactly 44 entries")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    records: dict[tuple[str, str], dict[str, Any]] = {}
    raw_root = (repository_root / CURATION_RAW_RELATIVE).resolve()
    for receipt in entries:
        object_ids = receipt.get("source_object_ids", [])
        if len(object_ids) != 1:
            raise PipelineError("artwork_snapshot_object_ids_invalid", "Artwork receipt must bind one exact object")
        key = (str(receipt.get("source_id")), str(object_ids[0]))
        if key in index:
            raise PipelineError("artwork_snapshot_duplicate", f"Duplicate artwork snapshot receipt: {key[0]}:{key[1]}")
        body_path = _safe_raw_path(repository_root, raw_root, receipt.get("raw_body_path"))
        metadata_path = _safe_raw_path(repository_root, raw_root, receipt.get("raw_receipt_path"))
        if sha256_file(body_path) != receipt.get("body_sha256") or body_path.stat().st_size != receipt.get("body_bytes"):
            raise PipelineError("artwork_snapshot_body_mismatch", f"Artwork raw body differs: {key[0]}:{key[1]}")
        metadata = _load_object(metadata_path, "artwork_snapshot_receipt_invalid")
        if (
            metadata.get("sha256") != receipt.get("body_sha256")
            or metadata.get("bytes") != receipt.get("body_bytes")
            or metadata.get("content_type") != receipt.get("content_type")
            or metadata.get("source_id") != key[0]
            or metadata.get("status") != 200
            or metadata.get("media_downloaded") is not False
            or metadata.get("cookies_sent") is not False
            or metadata.get("credentials_sent") is not False
        ):
            raise PipelineError("artwork_snapshot_receipt_mismatch", f"Artwork raw receipt differs: {key[0]}:{key[1]}")
        record = _load_object(body_path, "artwork_snapshot_body_invalid")
        record_id = str(record.get("objectID")) if key[0] == "met_open_access" else str(record.get("data", {}).get("id"))
        if record_id != key[1]:
            raise PipelineError("artwork_snapshot_object_mismatch", f"Artwork body object ID differs: {key[0]}:{key[1]}")
        index[key] = receipt
        records[key] = record
    expected_keys = [(item["source_id"], item["source_object_id"]) for item in basis["entries"]]
    if list(index) != expected_keys:
        raise PipelineError("artwork_snapshot_exact_set_mismatch", "Artwork receipt order or exact object set differs")
    return index, records


def _safe_raw_path(repository_root: Path, raw_root: Path, raw_value: Any) -> Path:
    if not isinstance(raw_value, str) or not raw_value or "\\" in raw_value:
        raise PipelineError("artwork_snapshot_path_invalid", "Artwork raw path must be a non-empty POSIX relative path")
    relative = PurePosixPath(raw_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise PipelineError("artwork_snapshot_path_escape", f"Artwork raw path escapes: {raw_value}")
    path = (repository_root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(raw_root)
    except ValueError as error:
        raise PipelineError("artwork_snapshot_path_escape", f"Artwork raw path is outside fixed raw root: {raw_value}") from error
    if not path.is_file() or path.is_symlink():
        raise PipelineError("artwork_snapshot_path_missing", f"Artwork raw file is absent or a symlink: {raw_value}")
    return path


def _build_one(decision: dict[str, Any], receipt: dict[str, Any], raw_record: dict[str, Any], basis: dict[str, Any]) -> dict[str, Any]:
    source_key = decision["source_id"]
    object_id = decision["source_object_id"]
    fields = _source_fields(source_key, raw_record)
    if fields != decision["expected_source_fields"] or canonical_sha256(fields) != decision["expected_source_fields_hash"]:
        raise PipelineError("artwork_source_fields_drift", f"Official object fields drifted: {source_key}:{object_id}")
    short_source = "met" if source_key == "met_open_access" else "aic"
    slug = f"{short_source}-{object_id}"
    artwork_id = f"artwork:{slug}"
    object_evidence_id = f"evidence:{slug}-official-object"
    attribution_evidence_id = f"evidence:{slug}-attribution"
    classification_evidence_id = f"evidence:{slug}-classification"
    counter_evidence_id = f"evidence:{slug}-posthumous-date-conflict"

    claim_specs: list[dict[str, Any]] = [
        _claim_spec("official_object", "official_object_record", {"value": fields["object_url"], "datatype": "uri", "precision": "not_applicable"}, object_evidence_id, f"The official collection object is {fields['title']}.", f"官方馆藏对象题名为《{decision['title_translation']['text']}》。"),
        _claim_spec("attribution", "creator_attribution", {"entity_id": decision["approved_artist_id"]}, attribution_evidence_id, f"The reviewed creator attribution is {decision['creator_attribution']['attribution_type']} to {decision['approved_artist_label']}.", f"审核后的创作者归属为 {decision['approved_artist_label']}（{decision['creator_attribution']['attribution_type']}）。", [counter_evidence_id] if decision["creator_attribution"]["disputed"] else []),
        _claim_spec("date", "creation_date_display", {"value": fields["date_display"] or "not stated", "datatype": "string", "precision": _claim_precision(decision["creation_span"])}, object_evidence_id, f"The official display date is {fields['date_display'] or 'not stated'}; precision is {decision['creation_span']['precision']}.", f"官方显示年代为“{fields['date_display'] or '未注明'}”；精度为 {decision['creation_span']['precision']}。"),
        _claim_spec("institution", "holding_institution", {"entity_id": INSTITUTION_IDS[source_key]}, object_evidence_id, f"The holding institution is {INSTITUTION_LABELS[source_key]}.", f"收藏机构为 {INSTITUTION_LABELS[source_key]}。"),
        _claim_spec("accession", "accession_number", {"value": fields["accession_number"], "datatype": "string", "precision": "exact"}, object_evidence_id, f"The accession number is {fields['accession_number']}.", f"登录号为 {fields['accession_number']}。"),
    ]
    for context_id in decision["material_ids"]:
        claim_specs.append(_claim_spec(f"material-{context_id.split(':', 1)[1]}", "uses_material", {"entity_id": context_id}, classification_evidence_id, f"The reviewed medium normalization includes {context_id}.", f"审核后的材料规范项包括 {context_id}。"))
    for context_id in decision["technique_ids"]:
        claim_specs.append(_claim_spec(f"technique-{context_id.split(':', 1)[1]}", "uses_technique", {"entity_id": context_id}, classification_evidence_id, f"The reviewed technique normalization includes {context_id}.", f"审核后的技法规范项包括 {context_id}。"))
    for context_id in decision["subject_ids"]:
        claim_specs.append(_claim_spec(f"subject-{context_id.split(':', 1)[1]}", "depicts_subject", {"entity_id": context_id}, classification_evidence_id, f"The official title supports the reviewed subject tag {context_id}.", f"官方题名支持审核后的主题标签 {context_id}。"))

    claims: list[dict[str, Any]] = []
    claim_ids: dict[str, str] = {}
    for spec in claim_specs:
        claim_id = f"claim:{slug}-{spec['suffix']}"
        claim_ids[spec["suffix"]] = claim_id
        claims.append(_claim_record(claim_id, artwork_id, spec, decision, basis))
    object_claim_ids = [claim_ids[key] for key in ("official_object", "date", "institution", "accession")]
    attribution_claim_id = claim_ids["attribution"]
    classification_claim_ids = [claim_ids[spec["suffix"]] for spec in claim_specs[5:]]
    snapshot_ref = _snapshot_ref(receipt, source_key, object_id)
    evidence = [
        _evidence_record(
            object_evidence_id,
            object_claim_ids,
            source_key,
            object_id,
            snapshot_ref,
            _field_locators(source_key, "object"),
            "Exact official collection fields support the source title/object identity, display-date precision, institution role, accession number and raw medium.",
            "collection_record",
            "api_field",
            basis["reviewed_at"],
        ),
        _evidence_record(
            attribution_evidence_id,
            [attribution_claim_id],
            source_key,
            object_id,
            snapshot_ref,
            _field_locators(source_key, "attribution"),
            f"The official creator field is {fields['creator_display']!r} and preserves the source attribution qualifier or collaboration wording.",
            "collection_record",
            "api_field",
            basis["reviewed_at"],
        ),
        _evidence_record(
            classification_evidence_id,
            classification_claim_ids,
            source_key,
            object_id,
            snapshot_ref,
            _field_locators(source_key, "classification"),
            "A bounded manual review normalizes only terms supported by the exact official medium and title fields; it does not assert influence.",
            "curatorial_assessment",
            "manual",
            basis["reviewed_at"],
        ),
    ]
    if decision["creator_attribution"]["disputed"]:
        evidence.append(_evidence_record(
            counter_evidence_id,
            [attribution_claim_id],
            source_key,
            object_id,
            snapshot_ref,
            _field_locators(source_key, "posthumous"),
            "The same official record dates the chromolithograph ca. 1910, after the reviewed 1906 death claim; this contradicts confirmed personal execution but does not erase the named attribution.",
            "curatorial_assessment",
            "manual",
            basis["reviewed_at"],
            stance="contradicts",
        ))

    signoff_ids = {role: f"review-signoff:{slug}-{role.replace('_reviewer', '').replace('_', '-')}" for role in basis["review_sessions"]}
    media_assessment = _media_assessment(decision, receipt, fields, artwork_id, slug, basis, signoff_ids["rights_reviewer"])
    signoffs = [
        _signoff(signoff_ids["artwork_attribution_reviewer"], "artwork_attribution_reviewer", [artwork_id, attribution_claim_id], decision, basis),
        _signoff(signoff_ids["data_reviewer"], "data_reviewer", [artwork_id, *[record["id"] for record in claims]], decision, basis),
        _signoff(signoff_ids["multilingual_reviewer"], "multilingual_reviewer", [artwork_id, claim_ids["official_object"]], decision, basis),
        _signoff(signoff_ids["rights_reviewer"], "rights_reviewer", [artwork_id, media_assessment["id"]], decision, basis),
    ]
    lifecycle = "disputed" if decision["creator_attribution"]["disputed"] else "reviewed"
    material_claims = [claim_ids[f"material-{value.split(':', 1)[1]}"] for value in decision["material_ids"]]
    technique_claims = [claim_ids[f"technique-{value.split(':', 1)[1]}"] for value in decision["technique_ids"]]
    subject_claims = [claim_ids[f"subject-{value.split(':', 1)[1]}"] for value in decision["subject_ids"]]
    artwork = {
        "schema_version": "1.1.0",
        "id": artwork_id,
        "entity_type": "artwork",
        "branch_id": "art",
        "phase_id": "MUSEUM-03B",
        "labels": {"en": fields["title"], "zh-Hans": decision["title_translation"]["text"]},
        "external_ids": {"met_object" if source_key == "met_open_access" else "aic_object": object_id},
        "approved_artist_id": decision["approved_artist_id"],
        "approved_artist_association_claim_id": attribution_claim_id,
        "official_object_record": {
            "source_id": SOURCE_RECORD_IDS[source_key],
            "source_object_id": object_id,
            "official_object_url": fields["object_url"],
            "raw_snapshot_id": snapshot_ref["snapshot_id"],
            "raw_snapshot_hash": snapshot_ref["body_sha256"],
            "accessed_at": basis["reviewed_at"],
        },
        "title_records": [
            {
                "text": fields["title"],
                "language": "en",
                "script": "Latn",
                "title_type": "preferred",
                "provenance_type": "official_source",
                "source_id": SOURCE_RECORD_IDS[source_key],
                "source_locator": _field_locators(source_key, "title")[0],
                "source_claim_id": claim_ids["official_object"],
                "translated_from_claim_id": None,
                "translation_review_signoff_id": None,
            },
            {
                "text": decision["title_translation"]["text"],
                "language": "zh-Hans",
                "script": "Hans",
                "title_type": "translated_display",
                "provenance_type": "project_curatorial_translation",
                "source_id": SOURCE_RECORD_IDS[source_key],
                "source_locator": f"project translation of source-title hash {decision['title_translation']['provenance']['source_title_sha256']}",
                "source_claim_id": claim_ids["official_object"],
                "translated_from_claim_id": claim_ids["official_object"],
                "translation_review_signoff_id": signoff_ids["multilingual_reviewer"],
            },
        ],
        "claim_ids": [record["id"] for record in claims],
        "source_ids": [SOURCE_RECORD_IDS[source_key]],
        "source_license_bindings": [_data_binding(source_key, object_id)],
        "lifecycle_status": lifecycle,
        "data_version": "1.0.0",
        "created_at": basis["reviewed_at"],
        "updated_at": basis["reviewed_at"],
        "creator_attributions": [{
            "attribution_type": decision["creator_attribution"]["attribution_type"],
            "creator_entity_id": decision["approved_artist_id"],
            "display_label": decision["approved_artist_label"],
            "claim_id": attribution_claim_id,
            "public_note": decision["creator_attribution"]["review_note"],
        }],
        "creation_span": decision["creation_span"],
        "creation_date_claim_id": claim_ids["date"],
        "holding_institution_id": INSTITUTION_IDS[source_key],
        "holding_institution_claim_id": claim_ids["institution"],
        "accession_number": fields["accession_number"],
        "accession_number_claim_id": claim_ids["accession"],
        "material_ids": decision["material_ids"],
        "material_records": [
            {"material_id": material_id, "claim_id": claim_id}
            for material_id, claim_id in zip(decision["material_ids"], material_claims, strict=True)
        ],
        "technique_ids": decision["technique_ids"],
        "technique_records": [
            {"technique_id": technique_id, "claim_id": claim_id}
            for technique_id, claim_id in zip(decision["technique_ids"], technique_claims, strict=True)
        ],
        "subject_ids": decision["subject_ids"],
        "subject_records": [
            {"subject_id": subject_id, "claim_id": claim_id}
            for subject_id, claim_id in zip(decision["subject_ids"], subject_claims, strict=True)
        ],
        "rights_preflight_id": decision["rights_preflight_id"],
        "rights_preflight_status": decision["rights_preflight_status"],
        "media_asset_ids": [],
        "media_eligibility_assessment_id": media_assessment["id"],
        "uncertainty_note": decision["uncertainty_note"],
        "review_status": lifecycle,
        "reviewed_by": basis["reviewer_id"],
        "reviewed_at": basis["reviewed_at"],
        "review_signoff_ids": list(signoff_ids.values()),
        "status_history": [
            {"from": None, "to": "candidate", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "artwork collector", "reason": "Created from the exact selected official object and immutable snapshot receipt."},
            {"from": "candidate", "to": "sourced", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "data reviewer", "reason": "Required field Claims resolve to exact Evidence and registered Source bindings."},
            {"from": "sourced", "to": lifecycle, "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "artwork attribution reviewer", "reason": "Attribution, precision, translation and rights preflight were reviewed without public or verified promotion."},
        ],
    }
    return {"artwork": artwork, "claims": claims, "evidence": evidence, "media_assessment": media_assessment, "signoffs": signoffs}


def _source_fields(source_key: str, record: dict[str, Any]) -> dict[str, Any]:
    if source_key == "met_open_access":
        return {
            "accession_number": record.get("accessionNumber"),
            "copyright_notice": None,
            "credit_line": record.get("creditLine"),
            "creator_display": record.get("artistDisplayName"),
            "creator_prefix": record.get("artistPrefix"),
            "date_display": record.get("objectDate"),
            "department": record.get("department"),
            "is_public_domain": record.get("isPublicDomain"),
            "media_ref": record.get("primaryImage") or None,
            "medium": record.get("medium"),
            "object_url": record.get("objectURL"),
            "title": record.get("title"),
        }
    data = record.get("data", {})
    return {
        "accession_number": data.get("main_reference_number"),
        "copyright_notice": data.get("copyright_notice"),
        "credit_line": data.get("credit_line"),
        "creator_display": data.get("artist_display"),
        "creator_prefix": None,
        "date_display": data.get("date_display"),
        "department": data.get("department_title"),
        "is_public_domain": data.get("is_public_domain"),
        "media_ref": data.get("image_id") or None,
        "medium": data.get("medium_display"),
        "object_url": data.get("api_link"),
        "title": data.get("title"),
    }


def _claim_spec(suffix: str, predicate: str, object_value: dict[str, Any], evidence_id: str, text_en: str, text_zh: str, counter: list[str] | None = None) -> dict[str, Any]:
    return {"suffix": suffix, "predicate": predicate, "object": object_value, "evidence_id": evidence_id, "text_en": text_en, "text_zh": text_zh, "counter": counter or []}


def _claim_record(claim_id: str, artwork_id: str, spec: dict[str, Any], decision: dict[str, Any], basis: dict[str, Any]) -> dict[str, Any]:
    disputed = bool(spec["counter"])
    status = "disputed" if disputed else "reviewed"
    temporal = decision["creation_span"] if spec["predicate"] == "creation_date_display" else {"start": None, "end": None, "precision": "unknown", "uncertain": False, "description": "Not a temporal assertion"}
    return {
        "schema_version": "1.0.0",
        "id": claim_id,
        "entity_type": "claim",
        "subject_id": artwork_id,
        "predicate": spec["predicate"],
        "object": spec["object"],
        "claim_text": {"en": spec["text_en"], "zh-Hans": spec["text_zh"]},
        "temporal_scope": temporal,
        "applicability_scope": "MUSEUM-03B internal reviewed artwork metadata; not a public release",
        "evidence_ids": [spec["evidence_id"]],
        "counter_evidence_ids": spec["counter"],
        "status": status,
        "status_history": [
            {"from": None, "to": "candidate", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "collector", "reason": "Created from the exact official object selection."},
            {"from": "candidate", "to": "sourced", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "data reviewer", "reason": "Bound to exact raw snapshot evidence and source-license scope."},
            {"from": "sourced", "to": status, "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "discipline reviewer", "reason": "Reviewed at source precision; competing posthumous evidence retained where applicable."},
        ],
        "disputed": disputed,
        "dispute_note": decision["creator_attribution"]["review_note"] if disputed else None,
        "no_counter_evidence_reason": None,
        "dispute_display": "not_public" if disputed else "not_disputed",
        "review": {"reviewer": basis["reviewer_id"], "reviewed_at": basis["reviewed_at"][:10], "decision_note": "Accepted for internal reviewed use only; no automatic verification or public promotion."},
        "publish_status": "blocked" if disputed else "not_public",
        "supersedes": None,
        "data_version": "1.0.0",
    }


def _claim_precision(span: dict[str, Any]) -> str:
    if span["precision"] == "year" and not span["uncertain"]:
        return "exact"
    if span["precision"] in {"range", "decade", "century"}:
        return "range"
    return "uncertain"


def _evidence_record(
    evidence_id: str,
    claim_ids: list[str],
    source_key: str,
    object_id: str,
    snapshot_ref: dict[str, str],
    raw_locators: list[str],
    summary: str,
    evidence_kind: str,
    extraction_method: str,
    extracted_at: str,
    *,
    stance: str = "supports",
) -> dict[str, Any]:
    return {
        "schema_version": "1.1.0",
        "id": evidence_id,
        "entity_type": "evidence",
        "claim_ids": claim_ids,
        "stance": stance,
        "evidence_kind": evidence_kind,
        "source_ids": [SOURCE_RECORD_IDS[source_key]],
        "source_license_bindings": [_data_binding(source_key, object_id)],
        "locator": {"record_id": object_id, "section": f"raw fields: {' + '.join(raw_locators)}"},
        "summary": summary,
        "short_excerpt": None,
        "raw_snapshot_refs": [{**snapshot_ref, "raw_locator": locator} for locator in raw_locators],
        "original_language": "und",
        "extracted_at": extracted_at,
        "extraction_method": extraction_method,
        "reliability_note": "The assertion remains limited to exact official fields and reviewed normalization; no visual similarity or computational result is converted into authorship or influence.",
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
    }


def _snapshot_ref(receipt: dict[str, Any], source_key: str, object_id: str) -> dict[str, str]:
    return {
        "snapshot_id": receipt["snapshot_id"],
        "body_sha256": receipt["body_sha256"],
        "source_object_id": object_id,
    }


def _field_locators(source_key: str, purpose: str) -> list[str]:
    prefix = "" if source_key == "met_open_access" else "/data"
    names = {
        "title": ["title"],
        "object": ["title", "objectDate", "repository", "accessionNumber", "medium", "objectURL"] if source_key == "met_open_access" else ["title", "date_display", "department_title", "main_reference_number", "medium_display", "api_link"],
        "attribution": ["artistDisplayName", "artistPrefix"] if source_key == "met_open_access" else ["artist_display"],
        "classification": ["medium", "title"] if source_key == "met_open_access" else ["medium_display", "title"],
        "posthumous": ["artistDisplayName", "objectDate"],
    }[purpose]
    return [f"{prefix}/{name}" for name in names]


def _data_binding(source_key: str, object_id: str) -> dict[str, Any]:
    rule = next(rule for rule in source_license_rules(source_key) if rule["content_class"] == "data" and (source_key != "aic_api" or rule["scope_match"]["field_policy"] == "exclude"))
    if source_key == "aic_api":
        fields = list(source_configuration(source_key)["query_profiles"]["default"])
        locator = f"https://api.artic.edu/api/v1/artworks/{object_id}?{urlencode({'fields': ','.join(fields)})}"
    else:
        fields = ["record"]
        locator = "Open Access collection API/CSV fields"
    return {"source_id": SOURCE_RECORD_IDS[source_key], "rule_id": rule["rule_id"], "content_class": "data", "scope_locator": locator, "scope_fields": fields, "permission_resolution": "rule_direct"}


def _media_binding(source_key: str) -> dict[str, Any]:
    rule = next(rule for rule in source_license_rules(source_key) if rule["content_class"] == "media")
    fields = ["isPublicDomain", "primaryImage"] if source_key == "met_open_access" else ["is_public_domain", "image_id"]
    return {
        "source_id": SOURCE_RECORD_IDS[source_key],
        "rule_id": rule["rule_id"],
        "content_class": "media",
        "scope_locator": rule["applies_to"],
        "scope_fields": fields,
        "permission_resolution": "object_level",
    }


def _license_descriptor(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "identifier": rule["identifier"],
        "version": rule["version"],
        "url": rule["url"],
        "attribution_required": bool(rule["attribution_template"]),
        "share_alike": bool(rule["share_alike"]),
        "redistribution_allowed": rule["redistribution"] in {"allowed", "conditional"},
        "modification_allowed": rule["modification"] in {"allowed", "conditional"},
        "commercial_use_allowed": rule["commercial_use"] in {"allowed", "conditional"},
    }


def _resolved_object_media_license(preflight: dict[str, Any]) -> dict[str, Any]:
    if preflight.get("media_license") != "cc0" or preflight.get("media_license_basis") != "object_level":
        raise PipelineError("artwork_media_license_resolution_invalid", "Open media requires an object-level CC0 preflight resolution")
    return {
        "identifier": "CC0-1.0",
        "version": "1.0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution_required": bool(preflight.get("attribution_required")),
        "share_alike": False,
        "redistribution_allowed": True,
        "modification_allowed": True,
        "commercial_use_allowed": True,
    }


def _media_assessment(
    decision: dict[str, Any],
    receipt: dict[str, Any],
    fields: dict[str, Any],
    artwork_id: str,
    slug: str,
    basis: dict[str, Any],
    rights_signoff_id: str,
) -> dict[str, Any]:
    source_key = decision["source_id"]
    outcome = decision["media_eligibility_class"]
    open_eligible = outcome != "metadata_only"
    metadata_rule = next(
        rule
        for rule in source_license_rules(source_key)
        if rule["content_class"] == "data" and (source_key != "aic_api" or rule["scope_match"]["field_policy"] == "exclude")
    )
    preflight = decision["preflight_media_rights"]
    resolved_media_license = _resolved_object_media_license(preflight) if open_eligible else None
    rights_evidence = [
        {
            "evidence_type": item["evidence_type"],
            "source_url": item["url"],
            "locator": (
                f"object-level {'/isPublicDomain' if source_key == 'met_open_access' else '/data/is_public_domain'} field bound by {decision['rights_preflight_id']}"
                if item["evidence_type"] == "object_rights_statement"
                else f"institution policy bound to the same object-level decision {decision['rights_preflight_id']}"
            ),
            "snapshot_hash": item["snapshot_hash"],
        }
        for item in preflight["rights_evidence"]
    ]
    if outcome == "external_iiif_candidate":
        delivery_mode = "external_iiif_candidate"
        official_iiif_url = f"https://www.artic.edu/iiif/2/{fields['media_ref']}"
    elif outcome == "self_hosted_open_media_eligible":
        delivery_mode = "self_hosted_future_candidate"
        official_iiif_url = None
    else:
        delivery_mode = "metadata_only"
        official_iiif_url = None
    return {
        "schema_version": "1.0.0",
        "id": f"media-assessment:{slug}",
        "entity_type": "media_eligibility_assessment",
        "phase_id": "MUSEUM-03B",
        "batch_id": BATCH_ID,
        "artwork_id": artwork_id,
        "source_id": SOURCE_RECORD_IDS[source_key],
        "source_license_bindings": [_media_binding(source_key)],
        "source_object_url": fields["object_url"],
        "rights_statement_url": preflight["rights_page_url"],
        "metadata_license": _license_descriptor(metadata_rule),
        "media_license": resolved_media_license,
        "media_rights_status": "cc0" if open_eligible else "unknown",
        "media_rights_basis": "object_level_evidence" if open_eligible else "no_evidence",
        "rights_holder": INSTITUTION_LABELS[source_key] if open_eligible else (fields["copyright_notice"] or None),
        "attribution": fields["credit_line"],
        "permissions": {
            "redistribution": "allowed" if open_eligible else "unknown",
            "modification": "allowed" if open_eligible else "unknown",
            "commercial_use": "allowed" if open_eligible else "unknown",
            "share_alike": "not_required" if open_eligible else "unknown",
        },
        "license_scope": None,
        "permission_status": "not_applicable" if open_eligible else "pending",
        "withdrawal_or_revocation": {
            "status": "active",
            "effective_at": None,
            "note": "No withdrawal or revocation was observed in the exact reviewed preflight evidence.",
        },
        "technical_delivery": {
            "delivery_mode": delivery_mode,
            "official_iiif_url": official_iiif_url,
            "cache_bytes": False,
        },
        "rights_evidence": rights_evidence,
        "evidence_hash": receipt["body_sha256"],
        "risk": "low" if open_eligible else "high",
        "block_reasons": [] if open_eligible else ["unknown_rights"],
        "outcome": outcome,
        "future_public_media_eligible": open_eligible,
        "self_hosted_open_media_eligible": outcome == "self_hosted_open_media_eligible",
        "development_only": False,
        "metadata_inherited_as_media_rights": False,
        "bytes_downloaded": False,
        "media_bytes_present": False,
        "verified_at": basis["reviewed_at"],
        "reverify_by": "2027-07-13",
        "review_signoff_ids": [rights_signoff_id],
        "status_history": [
            {"from": None, "to": "candidate", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "rights reviewer", "reason": "Created from the exact object-level MUSEUM-03A rights preflight and immutable snapshot receipt."},
            {"from": "candidate", "to": "reviewed", "changed_at": basis["reviewed_at"], "changed_by": basis["reviewer_id"], "role": "rights reviewer", "reason": "Reviewed without downloading, caching, publishing or inferring rights from image availability."},
        ],
        "data_version": "1.0.0",
    }


def _signoff(signoff_id: str, role: str, record_ids: list[str], decision: dict[str, Any], basis: dict[str, Any]) -> dict[str, Any]:
    session = basis["review_sessions"][role]
    return {
        "schema_version": "1.0.0",
        "id": signoff_id,
        "entity_type": "review_signoff",
        "record_ids": record_ids,
        "review_role": role,
        "reviewer_id": basis["reviewer_id"],
        "reviewer_kind": basis["reviewer_kind"],
        "single_operator_multi_role": True,
        "reviewed_at": session["reviewed_at"],
        "checklist": session["checklist"],
        "decision": session["decision"],
        "decision_note": f"{decision['source_id']}:{decision['source_object_id']}: {session['decision_note']}",
        "authority_basis": basis["authority_basis"],
        "data_version": "1.0.0",
    }


def _formal_selection_basis(
    basis: dict[str, Any],
    artworks: list[dict[str, Any]],
    signoffs: list[dict[str, Any]],
) -> dict[str, Any]:
    selections = []
    for decision, artwork in zip(basis["entries"], artworks, strict=True):
        considerations = ["medium_or_material"]
        if decision["subject_ids"]:
            considerations.append("subject")
        considerations.extend(["comparative_question", "official_object_record", "rights_readiness"])
        selections.append({
            "artwork_id": artwork["id"],
            "approved_artist_id": decision["approved_artist_id"],
            "source_id": SOURCE_RECORD_IDS[decision["source_id"]],
            "source_object_id": decision["source_object_id"],
            "official_object_url": decision["expected_source_fields"]["object_url"],
            "selection_considerations": considerations,
            "selection_rationale": decision["selection_note"],
            "rights_preflight_id": decision["rights_preflight_id"],
        })
    result = {
        "schema_version": "1.0.0",
        "id": "artwork-selection-basis:museum-03b-first-slate-v1",
        "entity_type": "artwork_selection_basis",
        "phase_id": "MUSEUM-03B",
        "batch_id": BATCH_ID,
        "selection_application_id": basis["selection_decision_application_id"],
        "approved_artist_ids": list(dict.fromkeys(item["approved_artist_id"] for item in basis["entries"])),
        "nominal_target": 44,
        "acceptable_range": {"minimum": 36, "maximum": 48},
        "minimum_per_artist": 2,
        "selections": selections,
        "review_signoff_ids": [record["id"] for record in signoffs],
        "generated_at": basis["reviewed_at"],
        "data_version": "1.0.0",
    }
    result["content_hash"] = canonical_sha256(result)
    return result


def _validate_outputs(payloads: dict[str, Any], basis: dict[str, Any], ledger: dict[str, Any]) -> None:
    formal_basis = payloads["artwork-selection-basis.json"]
    artworks = payloads["artworks.json"]
    claims = payloads["artwork-claims.json"]
    evidence = payloads["artwork-evidence.json"]
    assessments = payloads["media-eligibility-assessments.json"]
    signoffs = payloads["artwork-review-signoffs.json"]
    if (len(artworks), len(claims), len(evidence), len(assessments), len(signoffs)) != (44, 413, 134, 44, 176):
        raise PipelineError("artwork_output_count_mismatch", "Artwork output counts must be 44/413/134/44/176")
    schema_environment = load_schema_environment()
    for record in [formal_basis, *artworks, *claims, *evidence, *assessments, *signoffs]:
        issues = validate_record(record, environment=schema_environment)
        if issues:
            issue = issues[0]
            raise PipelineError("artwork_output_schema_invalid", f"Output schema invalid for {record.get('id')}: {issue.code} at {issue.location}: {issue.message}")
    if formal_basis["content_hash"] != canonical_sha256({key: value for key, value in formal_basis.items() if key != "content_hash"}):
        raise PipelineError("artwork_formal_selection_basis_hash_mismatch", "Formal artwork selection basis hash differs")
    claim_by_id = _unique_index(claims, "artwork_claim_duplicate")
    evidence_by_id = _unique_index(evidence, "artwork_evidence_duplicate")
    assessment_by_id = _unique_index(assessments, "artwork_media_assessment_duplicate")
    signoff_by_id = _unique_index(signoffs, "artwork_signoff_duplicate")
    snapshot_by_id = {entry["snapshot_id"]: entry for entry in ledger["entries"]}
    if formal_basis["review_signoff_ids"] != [record["id"] for record in signoffs]:
        raise PipelineError("artwork_selection_signoff_closure_mismatch", "Formal artwork selection basis signoff closure differs")
    if [item["artwork_id"] for item in formal_basis["selections"]] != [item["id"] for item in artworks]:
        raise PipelineError("artwork_selection_artwork_closure_mismatch", "Formal artwork selection basis artwork order or closure differs")
    for claim in claims:
        if _contains_mojibake(claim["claim_text"]["zh-Hans"]):
            raise PipelineError("artwork_claim_zh_text_invalid", f"Chinese claim text contains placeholder or mojibake: {claim['id']}")
        for evidence_id in [*claim["evidence_ids"], *claim["counter_evidence_ids"]]:
            linked = evidence_by_id.get(evidence_id)
            if linked is None or claim["id"] not in linked["claim_ids"]:
                raise PipelineError("artwork_claim_evidence_backlink_missing", f"Claim/evidence backlink missing: {claim['id']}")
    for record in evidence:
        for claim_id in record["claim_ids"]:
            if claim_id not in claim_by_id:
                raise PipelineError("artwork_evidence_claim_missing", f"Evidence references missing claim: {claim_id}")
        for ref in record["raw_snapshot_refs"]:
            receipt = snapshot_by_id.get(ref["snapshot_id"])
            if receipt is None or receipt["body_sha256"] != ref["body_sha256"] or ref["source_object_id"] not in receipt["source_object_ids"]:
                raise PipelineError("artwork_evidence_snapshot_mismatch", f"Evidence snapshot closure differs: {record['id']}")
    unknown_dates = set()
    per_artist = Counter()
    for artwork, assessment, decision, receipt in zip(artworks, assessments, basis["entries"], ledger["entries"], strict=True):
        per_artist[decision["approved_artist_id"]] += 1
        if artwork["claim_ids"] != [record["id"] for record in claims if record["subject_id"] == artwork["id"]]:
            raise PipelineError("artwork_claim_order_or_closure_mismatch", f"Artwork claim closure differs: {artwork['id']}")
        if artwork["creation_span"]["precision"] == "unknown":
            unknown_dates.add(decision["source_object_id"])
        if any(signoff_id not in signoff_by_id for signoff_id in artwork["review_signoff_ids"]):
            raise PipelineError("artwork_signoff_closure_missing", f"Artwork signoff closure differs: {artwork['id']}")
        if _contains_mojibake(artwork["labels"]["zh-Hans"]):
            raise PipelineError("artwork_label_zh_text_invalid", f"Chinese artwork label contains placeholder or mojibake: {artwork['id']}")
        translated_titles = [item for item in artwork["title_records"] if item["language"] == "zh-Hans"]
        if len(translated_titles) != 1 or _contains_mojibake(translated_titles[0]["text"]):
            raise PipelineError("artwork_title_zh_text_invalid", f"Chinese artwork title contains placeholder or mojibake: {artwork['id']}")
        if translated_titles[0]["translation_review_signoff_id"] not in signoff_by_id:
            raise PipelineError("artwork_title_translation_signoff_missing", f"Chinese artwork title signoff is missing: {artwork['id']}")
        if artwork["media_eligibility_assessment_id"] != assessment["id"] or assessment["artwork_id"] != artwork["id"]:
            raise PipelineError("artwork_media_assessment_closure_mismatch", f"Artwork/media assessment closure differs: {artwork['id']}")
        if assessment["outcome"] != decision["media_eligibility_class"] or assessment["evidence_hash"] != receipt["body_sha256"]:
            raise PipelineError("artwork_media_assessment_basis_mismatch", f"Artwork media assessment differs from its reviewed basis: {artwork['id']}")
        if assessment["source_license_bindings"] != [_media_binding(decision["source_id"])]:
            raise PipelineError("artwork_media_source_binding_mismatch", f"Media assessment does not bind the canonical source media rule: {artwork['id']}")
        if assessment["future_public_media_eligible"] and (
            assessment["media_rights_status"] != "cc0"
            or (assessment["media_license"] or {}).get("identifier") != "CC0-1.0"
            or assessment["permissions"]["redistribution"] != "allowed"
            or assessment["permission_status"] != "not_applicable"
            or assessment["withdrawal_or_revocation"]["status"] != "active"
            or assessment["risk"] not in {"low", "medium"}
        ):
            raise PipelineError("artwork_open_media_contract_mismatch", f"Open media contract is contradictory: {artwork['id']}")
        expected_rights_evidence = [
            (item["evidence_type"], item["url"], item["snapshot_hash"])
            for item in decision["preflight_media_rights"]["rights_evidence"]
        ]
        observed_rights_evidence = [
            (item["evidence_type"], item["source_url"], item["snapshot_hash"])
            for item in assessment["rights_evidence"]
        ]
        if observed_rights_evidence != expected_rights_evidence:
            raise PipelineError("artwork_media_rights_evidence_mismatch", f"Media rights evidence differs from the exact MUSEUM-03A preflight: {artwork['id']}")
        object_evidence = [item for item in decision["preflight_media_rights"]["rights_evidence"] if item["evidence_type"] == "object_rights_statement"]
        if len(object_evidence) != 1 or object_evidence[0]["snapshot_hash"] != receipt["body_sha256"]:
            raise PipelineError("artwork_media_object_evidence_snapshot_mismatch", f"Object rights evidence is not the selected raw snapshot: {artwork['id']}")
    if per_artist != Counter(artist_id for artist_id, _, _ in EXPECTED_SELECTION) or unknown_dates != EXPECTED_UNKNOWN_DATE_OBJECTS:
        raise PipelineError("artwork_quota_or_date_precision_mismatch", "Artwork quotas or explicit unknown-date set differs")
    if Counter(item["outcome"] for item in assessments) != Counter(EXPECTED_MEDIA_DISTRIBUTION):
        raise PipelineError("artwork_media_distribution_mismatch", "Artwork media eligibility distribution differs")
    for assessment in assessments:
        if assessment["media_bytes_present"] or assessment["bytes_downloaded"] or assessment["technical_delivery"]["cache_bytes"]:
            raise PipelineError("artwork_media_or_public_boundary_crossed", f"Media/public boundary crossed: {assessment['id']}")
        if assessment["id"] not in assessment_by_id:
            raise PipelineError("artwork_media_assessment_missing", f"Media assessment missing: {assessment['id']}")
        if any(signoff_id not in signoff_by_id for signoff_id in assessment["review_signoff_ids"]):
            raise PipelineError("artwork_media_signoff_closure_missing", f"Media assessment signoff closure differs: {assessment['id']}")
    all_records = [record for value in payloads.values() for record in (value if isinstance(value, list) else [value])]
    if any(record.get("lifecycle_status") == "published" or record.get("publish_status") == "published" for record in all_records):
        raise PipelineError("artwork_published_state_forbidden", "Wave 3 outputs cannot be published")
    if any(marker in text for record in all_records for text in _strings(record) for marker in (*MOJIBAKE_MARKERS, "\ufffd")):
        raise PipelineError("artwork_output_mojibake_detected", "Wave 3 output contains a known mojibake or replacement marker")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _unique_index(records: list[dict[str, Any]], code: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if record["id"] in result:
            raise PipelineError(code, f"Duplicate record ID: {record['id']}")
        result[record["id"]] = record
    return result


def _write_fail_closed(output_dir: Path, serialized: dict[str, str]) -> tuple[list[str], list[str]]:
    written: list[str] = []
    reused: list[str] = []
    for name, content in serialized.items():
        target = output_dir / name
        if target.exists():
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                raise PipelineError("artwork_output_conflict", f"Refusing to overwrite different artwork output: {target}")
            reused.append(name)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in serialized.items():
        target = output_dir / name
        if not target.exists():
            _atomic_write_text(target, content)
            written.append(name)
    return written, reused


def _load_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(code, f"Cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise PipelineError(code, f"Expected JSON object: {path}")
    return value


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write_text(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
