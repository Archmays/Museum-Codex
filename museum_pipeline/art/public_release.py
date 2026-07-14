from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import tempfile
import unicodedata
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from jsonschema import Draft202012Validator, FormatChecker

from museum_pipeline.art.batch_validation import DEFAULT_PACKAGE, validate_approved_batch
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment
from scripts.validate_governance_foundation import validate_release_directory


RELEASE_ID = "release:art-constellation-0.1.0"
RELEASE_VERSION = "0.1.0"
RELEASE_SCHEMA_VERSION = "1.0.0"
PHASE_ID = "MUSEUM-04"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-constellation-0.1.0"
PUBLIC_RECORD_SCHEMA = "schemas/art/release/public-constellation-record.schema.json"
PUBLIC_ARTIFACT_SCHEMA = "schemas/art/release/art-constellation-artifact.schema.json"
EXPECTED_PACKAGE_HASH = "sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86"
EXPECTED_GRAPH_HASH = "sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3"
DATA_RULE_IDS = {
    "source:aic_api": "aic_api:data:75df7e022b4e",
    "source:getty_ulan": "getty_ulan:data:eb25ddb4d400",
    "source:met_open_access": "met_open_access:data:8924a3c83dc7",
    "source:wikidata": "wikidata:data:dab022172e7e",
}
EXPECTED_FILES = {
    "artists.json", "attributions.json", "claims.json", "contexts.json", "evidence.json",
    "facets.json", "graph-summary.json", "layout.json", "license-decisions.json",
    "performance-contract.json", "relationships.json", "release-signoff.json", "rights.json",
    "search-index.json", "source-rules-snapshot.json", "sources.json",
    "third-party-notices.json", "artworks.json",
}
CONTEXT_TYPES = {"material", "technique", "subject", "museum_institution", "place"}
RELATION_TYPES = {"shared_subject", "shared_material", "shared_technique"}
PUBLIC_AIC_SCOPE_FIELDS = (
    "artist_display",
    "date_display",
    "main_reference_number",
    "medium_display",
    "title",
)
MEDIA_FILE_SUFFIXES = {
    ".avif", ".gif", ".jpeg", ".jpg", ".m4a", ".mov", ".mp3", ".mp4",
    ".ogg", ".png", ".svg", ".tif", ".tiff", ".wav", ".webm", ".webp",
}
FORBIDDEN_PUBLIC_KEYS = {
    "approved_candidate_id", "candidate_id", "candidate_claims", "development_only", "external_ids",
    "field_provenance", "held_out", "image_id", "image_url", "media_asset_ids",
    "media_eligibility_assessment_id", "official_iiif_url", "portrait", "private_notes", "raw_locator",
    "raw_snapshot_hash", "raw_snapshot_id", "raw_snapshot_refs", "rejected", "rights_preflight_id",
    "rights_preflight_status", "source_object_id", "storage_path", "thumbnail", "thumbnail_url",
}
CAUSAL_ASSERTION = re.compile(
    r"(?:was|were|is|are)\s+(?:directly\s+)?influenced\s+by|\binfluenced\b|\bstudent\s+of\b|"
    r"\bteacher\s+of\b|\bmaster\s+of\b|\bcaused\b|\bled\s+to\b|受(?:到)?[^。；]{0,20}影响|师从|传承|直接导致|引领",
    re.IGNORECASE,
)


def build_museum_04_release(
    output_dir: Path = DEFAULT_OUTPUT,
    package_dir: Path = DEFAULT_PACKAGE,
) -> dict[str, Any]:
    package_dir = _resolve(package_dir)
    output_dir = _resolve(output_dir)
    package_validation = validate_approved_batch(package_dir)
    if not package_validation["ok"]:
        codes = ", ".join(item["code"] for item in package_validation["failures"][:10])
        raise ValueError(f"sealed MUSEUM-03B package is invalid: {codes}")
    source = _load_package(package_dir)
    _assert_baseline(source)
    documents, included = _build_documents(source)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-04-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        staged.mkdir()
        for name, document in sorted(documents.items()):
            (staged / name).write_bytes(canonical_json_bytes(document))
        manifest = _build_manifest(staged, included)
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        result = validate_museum_04_release(staged, package_dir=package_dir)
        if not result["ok"]:
            raise ValueError("staged MUSEUM-04 release failed validation: " + ", ".join(result["codes"][:12]))
        _replace_owned_directory(staged, output_dir)

    result = validate_museum_04_release(output_dir, package_dir=package_dir)
    if not result["ok"]:
        raise ValueError("written MUSEUM-04 release failed validation: " + ", ".join(result["codes"][:12]))
    return result


def validate_museum_04_release(
    release_root: Path = DEFAULT_OUTPUT,
    *,
    package_dir: Path = DEFAULT_PACKAGE,
    require_public: bool = False,
) -> dict[str, Any]:
    release_root = _resolve(release_root)
    package_dir = _resolve(package_dir)
    failures: list[dict[str, str]] = []
    baseline_source: dict[str, Any] | None = None

    package_validation = validate_approved_batch(package_dir)
    if not package_validation["ok"]:
        _fail(failures, "m03b_package_invalid", "The sealed MUSEUM-03B package no longer validates")
    else:
        try:
            baseline_source = _load_package(package_dir)
            _assert_baseline(baseline_source)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            _fail(failures, "m03b_baseline_mismatch", str(error))

    if not release_root.is_dir():
        _fail(failures, "release_missing", "MUSEUM-04 release directory is absent")
        return _validation_result(release_root, failures, {})
    actual_files = {path.relative_to(release_root).as_posix() for path in release_root.rglob("*") if path.is_file()}
    expected_files = {"manifest.json", *EXPECTED_FILES}
    if actual_files != expected_files:
        _fail(failures, "m04_file_set_mismatch", f"missing={sorted(expected_files-actual_files)}, extra={sorted(actual_files-expected_files)}")

    documents: dict[str, Any] = {}
    document_parse_failed = False
    for name in sorted(actual_files & expected_files):
        path = release_root / name
        try:
            payload = path.read_bytes()
            document = json.loads(payload.decode("utf-8"))
            documents[name] = document
            if canonical_json_bytes(document) != payload:
                _fail(failures, "m04_noncanonical_json", f"{name} is not canonical JSON", name)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            _fail(failures, "m04_json_invalid", str(error), name)
            document_parse_failed = True

    if "manifest.json" not in documents:
        return _validation_result(release_root, failures, {})
    non_object_documents = [name for name, document in documents.items() if not isinstance(document, dict)]
    if non_object_documents:
        for name in non_object_documents:
            _fail(failures, "m04_document_type", "Release JSON document must be an object", name)
        return _validation_result(release_root, failures, {})
    if document_parse_failed:
        return _validation_result(release_root, failures, {})
    generic_issues = validate_release_directory(release_root, load_schema_environment(ROOT))
    for issue in generic_issues:
        _fail(failures, f"generic_{issue.code}", issue.message, issue.location)
    _validate_artifact_schemas(documents, failures)
    _validate_manifest_profile(documents, failures, require_public=require_public)
    _validate_public_projection(documents, failures, baseline_source)
    _validate_governance_artifacts(documents, failures)
    _validate_no_media_or_private_data(documents, failures)

    graph = documents.get("graph-summary.json", {})
    counts = graph.get("counts", {}) if isinstance(graph, dict) else {}
    return _validation_result(release_root, failures, counts)


def _build_documents(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    artists_source = source["artists"]
    artworks_source = source["artworks"]
    contexts_source = source["contexts"]
    relationships_source = source["relationships"]
    claims_source = {item["id"]: item for item in source["claims"]}
    evidence_source = {item["id"]: item for item in source["evidence"]}
    sources_source = source["sources"]
    context_index = {item["id"]: item for item in contexts_source}

    relation_count = Counter()
    for relationship in relationships_source:
        relation_count[relationship["source_entity_id"]] += 1
        relation_count[relationship["target_entity_id"]] += 1

    artwork_by_object: dict[str, list[str]] = {}
    for artwork in artworks_source:
        object_id = str((artwork.get("official_object_record") or {}).get("source_object_id", ""))
        if object_id:
            artwork_by_object.setdefault(object_id, []).append(artwork["id"])

    selected_claim_ids: set[str] = set()
    artist_records: list[dict[str, Any]] = []
    for artist in sorted(artists_source, key=lambda item: item["id"]):
        safe_claim_ids = [
            claim_id for claim_id in artist.get("claim_ids", [])
            if claim_id in claims_source and not claims_source[claim_id].get("disputed")
            and claims_source[claim_id].get("publish_status") != "blocked"
            and any(token in claim_id for token in (
                "identity-profile", "-birth", "-death", "activity-scope", "historical-period",
                "artistic-tradition", "official-record",
            ))
        ]
        artist_artworks = [item for item in artworks_source if item.get("approved_artist_id") == artist["id"]]
        media_claim_ids = [
            claim_id
            for artwork in artist_artworks
            for claim_id in artwork.get("claim_ids", [])
            if claim_id in claims_source
            and claims_source[claim_id].get("predicate") in {"uses_material", "uses_technique"}
            and not claims_source[claim_id].get("disputed")
            and claims_source[claim_id].get("publish_status") != "blocked"
        ]
        summary_claim_ids = sorted(set(safe_claim_ids) | set(media_claim_ids))
        selected_claim_ids.update(summary_claim_ids)
        summary_source_ids = sorted({
            source_id
            for claim_id in summary_claim_ids
            for evidence_id in claims_source[claim_id].get("evidence_ids", [])
            for source_id in evidence_source.get(evidence_id, {}).get("source_ids", [])
        })
        material_labels = _context_labels({value for item in artist_artworks for value in item.get("material_ids", [])}, context_index)
        technique_labels = _context_labels({value for item in artist_artworks for value in item.get("technique_ids", [])}, context_index)
        extensions = artist.get("branch_extensions") or {}
        practice_en = ", ".join([*technique_labels["en"], *material_labels["en"]][:4]) or "reviewed object metadata"
        practice_zh = "、".join([*technique_labels["zh-Hans"], *material_labels["zh-Hans"]][:4]) or "经审核的作品元数据"
        life = artist["life_dates"]
        period_labels = [item["label"] for item in extensions.get("historical_periods", [])]
        tradition_labels = [item["label"] for item in extensions.get("artistic_traditions", [])]
        place_labels = [item["label"] for item in extensions.get("activity_places", [])]
        label_en = artist["labels"].get("en", next(iter(artist["labels"].values())))
        label_zh = artist["labels"].get("zh-Hans", label_en)
        period_text = ", ".join(period_labels) or "the reviewed historical period"
        place_text = ", ".join(place_labels) or "the reviewed activity context"
        summary = {
            "zh-Hans": f"{label_zh}（{life['birth']['display_value']}—{life['death']['display_value']}）的身份、活动地点与历史时期来自经审核的声明。本次星海以{practice_zh}相关元数据支持跨时空观察。所列地点、年代与媒材仅描述本展可核验的观察范围，并明确不把比较解释为影响、师承或价值排序。",
            "en": f"{label_en} ({life['birth']['display_value']}–{life['death']['display_value']}) is presented through reviewed identity, {place_text}, and {period_text} claims. The constellation uses {practice_en} metadata for comparison. Its places, dates, materials, and techniques define only this exhibition's verifiable scope and do not imply influence, instruction, or rank.",
        }
        record = {
            "schema_version": RELEASE_SCHEMA_VERSION,
            "id": artist["id"],
            "entity_type": "art_constellation_artist",
            "phase_id": PHASE_ID,
            "release_id": RELEASE_ID,
            "labels": deepcopy(artist["labels"]),
            "aliases": [
                {"text": item["text"], "language": item["language"]}
                for item in artist.get("aliases", [])
            ],
            "life_dates": deepcopy(life),
            "activity_places": [
                {key: item.get(key) for key in ("label", "historical_scope", "precision")}
                for item in extensions.get("activity_places", [])
            ],
            "historical_periods": period_labels,
            "artistic_traditions": tradition_labels,
            "media_practice": {"zh-Hans": practice_zh, "en": practice_en},
            "summary": summary,
            "verified_claim_ids": summary_claim_ids,
            "source_ids": sorted(artist.get("source_ids", [])),
            "source_license_bindings": _data_bindings(artist.get("source_license_bindings", [])),
            "summary_provenance": {
                "authority_basis": "deterministic_claim_bounded_assembly_from_museum_03b_accepted_reviewed_records",
                "claim_ids": summary_claim_ids,
                "source_ids": summary_source_ids,
                "reviewed_at": "2026-07-14",
                "reviewer_id": "codex-primary-agent",
                "reviewer_kind": "ai_assisted_operator",
                "human_reviewed": False,
                "copied_museum_label": False,
            },
            "relation_count": relation_count[artist["id"]],
            "review": _review_provenance(),
            "review_status": "reviewed",
            "lifecycle_status": "reviewed",
            "data_version": RELEASE_VERSION,
        }
        artist_records.append(record)

    context_records: list[dict[str, Any]] = []
    for context in sorted(contexts_source, key=lambda item: item["id"]):
        relation_total = sum(context["id"] in item.get("context_entity_ids", []) for item in relationships_source)
        label_en = context["labels"].get("en", context["id"])
        label_zh = context["labels"].get("zh-Hans", label_en)
        record = {
            "schema_version": RELEASE_SCHEMA_VERSION,
            "id": context["id"],
            "entity_type": "art_constellation_context",
            "context_type": context["entity_type"],
            "phase_id": PHASE_ID,
            "release_id": RELEASE_ID,
            "labels": deepcopy(context["labels"]),
            "definition": {
                "zh-Hans": f"用于标记所选作品元数据中的{label_zh}语境；它只支持策展比较。",
                "en": f"A reviewed {label_en} context in the selected object metadata, used only for curatorial comparison.",
            },
            "source_ids": sorted(context.get("source_ids", [])),
            "source_license_bindings": _data_bindings(context.get("source_license_bindings", [])),
            "relation_count": relation_total,
            "review_status": "publishable",
            "lifecycle_status": "publishable",
            "data_version": RELEASE_VERSION,
        }
        context_records.append(record)

    relationship_records: list[dict[str, Any]] = []
    for relationship in sorted(relationships_source, key=lambda item: item["id"]):
        claim_ids = sorted(relationship.get("claim_ids", []))
        selected_claim_ids.update(claim_ids)
        evidence_ids = sorted({
            evidence_id for claim_id in claim_ids
            for evidence_id in claims_source.get(claim_id, {}).get("evidence_ids", [])
        })
        supporting_artworks = sorted({
            artwork_id for evidence_id in evidence_ids
            for raw in evidence_source.get(evidence_id, {}).get("raw_snapshot_refs", [])
            for artwork_id in artwork_by_object.get(str(raw.get("source_object_id", "")), [])
        })
        source_label = next(item for item in artist_records if item["id"] == relationship["source_entity_id"])["labels"]
        target_label = next(item for item in artist_records if item["id"] == relationship["target_entity_id"])["labels"]
        relation_label = _relation_label(relationship["relationship_type"])
        explanation = _relationship_short_explanation(
            relationship,
            source_label,
            target_label,
            context_index,
        )
        record = {
            "schema_version": RELEASE_SCHEMA_VERSION,
            "id": relationship["id"],
            "entity_type": "art_constellation_relationship",
            "phase_id": PHASE_ID,
            "release_id": RELEASE_ID,
            "source_artist_id": relationship["source_entity_id"],
            "target_artist_id": relationship["target_entity_id"],
            "type": relationship["relationship_type"],
            "level": "C",
            "level_label": {"zh-Hans": "C｜策展比较", "en": "C | Curatorial comparison"},
            "title": {
                "zh-Hans": f"{source_label.get('zh-Hans', source_label.get('en'))}与{target_label.get('zh-Hans', target_label.get('en'))}：{relation_label['zh-Hans']}",
                "en": f"{source_label.get('en')} and {target_label.get('en')}: {relation_label['en']}",
            },
            "short_explanation": deepcopy(explanation),
            "what_it_means": {
                "zh-Hans": "两位艺术家的所选作品记录共享经审核的题材、材料或技法语境，因此可并置观察。",
                "en": "Selected object records share a reviewed subject, material, or technique context and can be observed together.",
            },
            "what_it_does_not_mean": {
                "zh-Hans": "这条连线不表示相识、影响、师承、传播、亲密程度或艺术价值。",
                "en": "The connection does not assert acquaintance, influence, instruction, transmission, intimacy, or artistic value.",
            },
            "context_ids": sorted(relationship.get("context_entity_ids", [])),
            "supporting_artwork_ids": supporting_artworks,
            "claim_ids": claim_ids,
            "evidence_ids": evidence_ids,
            "source_ids": sorted(relationship.get("source_ids", [])),
            "source_license_bindings": _data_bindings(relationship.get("source_license_bindings", [])),
            "evidence_confidence": relationship["evidence_confidence"],
            "curatorial_relevance": relationship["curatorial_relevance"],
            "historical_relationship_strength": None,
            "computational_similarity": None,
            "directed": False,
            "is_algorithmic": False,
            "limitations": {
                "zh-Hans": "比较范围仅限本 release 所列作品元数据与来源；不外推历史因果。",
                "en": "The comparison is limited to the listed release metadata and sources; no historical causality is inferred.",
            },
            "review": _review_provenance(),
            "review_status": "publishable",
            "lifecycle_status": "publishable",
            "data_version": RELEASE_VERSION,
        }
        relationship_records.append(record)

    artwork_records = [
        _project_artwork(item, context_index)
        for item in sorted(artworks_source, key=lambda value: value["id"])
    ]

    claim_records: list[dict[str, Any]] = []
    evidence_ids: set[str] = set()
    for claim_id in sorted(selected_claim_ids):
        claim = claims_source[claim_id]
        if claim.get("disputed") or claim.get("publish_status") == "blocked":
            continue
        evidence_ids.update(claim.get("evidence_ids", []))
        claim_records.append({
            "schema_version": RELEASE_SCHEMA_VERSION,
            "id": claim_id,
            "entity_type": "art_constellation_claim",
            "phase_id": PHASE_ID,
            "release_id": RELEASE_ID,
            "subject_id": claim["subject_id"],
            "predicate": claim["predicate"],
            "object": deepcopy(claim["object"]),
            "claim_text": _public_claim_text(claim["predicate"]),
            "applicability_scope": "MUSEUM-04 public metadata-only constellation release.",
            "evidence_ids": sorted(claim.get("evidence_ids", [])),
            "counter_evidence_ids": [],
            "status": "publishable",
            "publish_status": "publishable",
            "disputed": False,
            "review": _review_provenance(),
            "data_version": RELEASE_VERSION,
        })

    evidence_records: list[dict[str, Any]] = []
    for evidence_id in sorted(evidence_ids):
        evidence = evidence_source[evidence_id]
        visible_claim_ids = sorted(set(evidence.get("claim_ids", [])) & {item["id"] for item in claim_records})
        if not visible_claim_ids:
            continue
        public_evidence_text = _public_evidence_text(evidence["evidence_kind"])
        evidence_records.append({
            "schema_version": RELEASE_SCHEMA_VERSION,
            "id": evidence_id,
            "entity_type": "art_constellation_evidence",
            "phase_id": PHASE_ID,
            "release_id": RELEASE_ID,
            "claim_ids": visible_claim_ids,
            "stance": evidence["stance"],
            "evidence_kind": evidence["evidence_kind"],
            "source_ids": sorted(evidence.get("source_ids", [])),
            "source_license_bindings": _data_bindings(evidence.get("source_license_bindings", [])),
            "locator": _public_evidence_locator(evidence["locator"], evidence_id),
            "summary": public_evidence_text["summary"],
            "reliability_note": public_evidence_text["reliability_note"],
            "review": _review_provenance(),
            "lifecycle_status": "publishable",
            "data_version": RELEASE_VERSION,
        })

    source_records = [_publishable_source(item) for item in sorted(sources_source, key=lambda value: value["id"])]
    source_dtos = [_source_dto(item) for item in source_records]

    all_records = [
        *artist_records, *context_records, *artwork_records, *relationship_records,
        *claim_records, *evidence_records, *source_records,
    ]
    record_envelope = [
        {
            "target_schema": "schemas/common/source.schema.json" if item["entity_type"] == "source" else PUBLIC_RECORD_SCHEMA,
            "data": item,
        }
        for item in sorted(all_records, key=lambda value: value["id"])
    ]

    layout_nodes = []
    for index, artist in enumerate(artist_records):
        angle = (2 * math.pi * index / len(artist_records)) - (math.pi / 2)
        layout_nodes.append({
            "artist_id": artist["id"],
            "x": round(500 + 380 * math.cos(angle), 6),
            "y": round(500 + 380 * math.sin(angle), 6),
            "order": index,
        })
    layout = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "algorithm": "deterministic_circle_v1",
        "seed": "museum-04-art-constellation-0.1.0",
        "coordinate_space": {"width": 1000, "height": 1000},
        "nodes": layout_nodes,
    }
    layout["content_hash"] = canonical_sha256(layout)

    relationship_type_counts = Counter(item["type"] for item in relationship_records)
    counts = {
        "artists": len(artist_records),
        "contexts": len(context_records),
        "relationships": len(relationship_records),
        "artworks": len(artwork_records),
        "claims": len(claim_records),
        "evidence": len(evidence_records),
        "sources": len(source_records),
        "media": 0,
        "media_bytes": 0,
        "levels": {"A": 0, "B": 0, "C": len(relationship_records)},
        "relationship_types": {key: relationship_type_counts[key] for key in sorted(RELATION_TYPES)},
    }
    graph_summary = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "release_version": RELEASE_VERSION,
        "profile": "metadata_only",
        "title": {"zh-Hans": "艺术星海：观察与比较", "en": "Constellation of Art: Observation and Comparison"},
        "counts": counts,
        "semantics": {
            "level_label": {"zh-Hans": "C｜策展比较", "en": "C | Curatorial comparison"},
            "what_it_means": {"zh-Hans": "经审核的共同题材、材料或技法比较。", "en": "Reviewed comparison through a shared subject, material, or technique."},
            "what_it_does_not_mean": {"zh-Hans": "不证明相识、影响、师承、传播或价值排序。", "en": "It does not prove acquaintance, influence, instruction, transmission, or rank."},
            "algorithmic": False,
            "causal": False,
            "directed": False,
        },
        "initial_state": {"view": "graph", "edges_visible": False, "focused_artist_id": None},
        "artifact_paths": {
            "artists": "artists.json", "contexts": "contexts.json", "relationships": "relationships.json",
            "artworks": "artworks.json", "evidence": "evidence.json", "sources": "sources.json",
            "search_index": "search-index.json", "layout": "layout.json", "facets": "facets.json",
            "rights": "rights.json",
        },
    }

    search_entries = []
    for artist in artist_records:
        values = [(value, locale, "preferred") for locale, value in artist["labels"].items()]
        values.extend((item["text"], item["language"], "alias") for item in artist["aliases"])
        normalized_keys = [
            {"value": value, "locale": locale, "reason": reason, "normalized_key": _normalize_search(value)}
            for value, locale, reason in values
        ]
        normalized_keys.sort(key=lambda item: (item["normalized_key"], item["locale"], item["value"]))
        search_entries.append({
            "id": artist["id"],
            "type": "artist",
            "labels": deepcopy(artist["labels"]),
            "aliases": deepcopy(artist["aliases"]),
            "normalized_keys": normalized_keys,
        })
    search_entries.sort(key=lambda item: item["id"])

    facet_levels = [
        {"value": level, "count": counts["levels"][level], "label": {"zh-Hans": f"{level} 级", "en": f"Level {level}"}}
        for level in ("A", "B", "C")
    ]
    facet_types = [
        {"value": key, "count": counts["relationship_types"][key], "label": _relation_label(key)}
        for key in sorted(RELATION_TYPES)
    ]
    periods = Counter(value for artist in artist_records for value in artist["historical_periods"])
    regions = Counter(item["label"] for artist in artist_records for item in artist["activity_places"])
    traditions = Counter(value for artist in artist_records for value in artist["artistic_traditions"])

    documents: dict[str, Any] = {
        "graph-summary.json": graph_summary,
        "artists.json": _artifact("artists", artist_records),
        "contexts.json": _artifact("contexts", context_records),
        "relationships.json": _artifact("relationships", relationship_records),
        "artworks.json": _artifact("artworks", artwork_records),
        "evidence.json": _artifact("evidence", evidence_records),
        "sources.json": _artifact("sources", source_dtos),
        "claims.json": {"schema_version": RELEASE_SCHEMA_VERSION, "release_id": RELEASE_ID, "claims": claim_records, "records": record_envelope},
        "search-index.json": {"schema_version": RELEASE_SCHEMA_VERSION, "release_id": RELEASE_ID, "normalization": "NFKD-casefold-strip-marks-v1", "entries": search_entries},
        "layout.json": layout,
        "facets.json": {
            "schema_version": RELEASE_SCHEMA_VERSION,
            "release_id": RELEASE_ID,
            "facets": {
                "levels": facet_levels,
                "relationship_types": facet_types,
                "periods": [{"value": key, "count": periods[key], "label": {"zh-Hans": key, "en": key}} for key in sorted(periods)],
                "regions": [{"value": key, "count": regions[key], "label": {"zh-Hans": key, "en": key}} for key in sorted(regions)],
                "traditions": [{"value": key, "count": traditions[key], "label": {"zh-Hans": key, "en": key}} for key in sorted(traditions)],
            },
        },
        "rights.json": _rights_document(),
        "license-decisions.json": _license_decisions_snapshot(),
        "source-rules-snapshot.json": _source_rules_snapshot(source_records),
        "third-party-notices.json": _third_party_notices(source_records),
        "attributions.json": {"assets": []},
        "release-signoff.json": _release_signoff(counts, _summary_digest(artist_records)),
        "performance-contract.json": _performance_contract(),
    }
    included = {
        "entities": [item["id"] for item in [*artist_records, *context_records, *artwork_records]],
        "relationships": [item["id"] for item in relationship_records],
        "claims": [item["id"] for item in claim_records],
        "evidence": [item["id"] for item in evidence_records],
        "sources": [item["id"] for item in source_records],
        "media": [],
    }
    return documents, included


def _project_artwork(artwork: dict[str, Any], context_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    official = artwork.get("official_object_record") or {}
    source_id = official.get("source_id") or artwork.get("source_ids", [None])[0]
    rule_id = DATA_RULE_IDS[source_id]
    source_bindings = [item for item in _data_bindings(artwork.get("source_license_bindings", [])) if item["source_id"] == source_id]
    status = "disputed" if artwork.get("lifecycle_status") == "disputed" else "reviewed"
    labels = deepcopy(artwork["labels"])
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "id": artwork["id"],
        "entity_type": "art_constellation_artwork",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "labels": labels,
        "artist_id": artwork["approved_artist_id"],
        "creation": deepcopy(artwork["creation_span"]),
        "institution": {"id": artwork["holding_institution_id"], "label": _label_for(artwork["holding_institution_id"], context_index)},
        "accession_number": artwork["accession_number"],
        "materials": [_context_ref(value, context_index) for value in artwork.get("material_ids", [])],
        "techniques": [_context_ref(value, context_index) for value in artwork.get("technique_ids", [])],
        "subjects": [_context_ref(value, context_index) for value in artwork.get("subject_ids", [])],
        "official_object_url": official["official_object_url"],
        "metadata_license": {"source_id": source_id, "rule_id": rule_id},
        "source_ids": sorted(artwork.get("source_ids", [])),
        "source_license_bindings": source_bindings,
        "attribution_status": status,
        "limitations": {
            "zh-Hans": "仅发布支持关系解释的作品元数据；不含作品图像或 IIIF 资源。",
            "en": "Only metadata supporting relationship explanation is released; no artwork image or IIIF resource is included.",
        },
        "review_status": "publishable",
        "lifecycle_status": "publishable",
        "data_version": RELEASE_VERSION,
    }


def _publishable_source(source: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(source)
    with (ROOT / "research" / "source-registry" / "source-comparison-matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        registry_row = next(
            row for row in csv.DictReader(handle)
            if row["source_id"] == record["registry_source_id"]
        )
    registry_snapshot_hash = _load_json(
        ROOT / "research" / "source-registry" / "minimum-source-set.json"
    )["source_matrix_snapshot_hash"]
    record["title"] = registry_row["name"]
    record["publisher"] = registry_row["name"]
    record["official_url"] = registry_row["official_url"]
    record["registry_identity"] = {
        "canonical_name": registry_row["name"],
        "canonical_official_host": (urlparse(registry_row["official_url"]).hostname or "").lower(),
        "snapshot_hash": registry_snapshot_hash,
    }
    record["lifecycle_status"] = "publishable"
    record["data_version"] = RELEASE_VERSION
    selected_rule_id = DATA_RULE_IDS[record["id"]]
    selected_rule = next(
        deepcopy(item)
        for item in record["license_rules"]
        if item["rule_id"] == selected_rule_id
    )
    record["license_rules"] = [selected_rule]
    record["license_rules_snapshot_hash"] = canonical_sha256(record["license_rules"])
    record["selected_license_rule_ids"] = [selected_rule_id]
    record["public_static_redistribution"] = "allowed"
    record["risk_note"] = (
        "This public projection binds only the listed canonical data rule; "
        "no other source rule or content class is included."
    )
    if not record.get("terms_snapshot_hash"):
        record["terms_snapshot_hash"] = sha256_file(ROOT / "research" / "source-registry" / "source-license-rules.json")
    return record


def _source_dto(source: dict[str, Any]) -> dict[str, Any]:
    rule = next(item for item in source["license_rules"] if item["rule_id"] == DATA_RULE_IDS[source["id"]])
    attribution = [rule["attribution_template"]] if rule.get("attribution_template") else []
    return {
        "id": source["id"],
        "title": source["title"],
        "publisher": source["publisher"],
        "official_url": source["official_url"],
        "accessed_at": source["accessed_at"],
        "tier": source["tier"],
        "license": {"rule_ids": [rule["rule_id"]], "identifiers": [rule["identifier"]], "attribution_texts": attribution},
        "attribution": attribution[0] if attribution else source["publisher"],
        "locator": {
            "label": {"zh-Hans": "官方来源页面", "en": "Official source page"},
            "url": source["official_url"],
        },
        "release_id": RELEASE_ID,
    }


def _build_manifest(staged: Path, included: dict[str, list[str]]) -> dict[str, Any]:
    manifest_files: list[dict[str, Any]] = []
    records = json.loads((staged / "claims.json").read_text(encoding="utf-8"))["records"]
    record_ids = sorted(item["data"]["id"] for item in records)
    for path in sorted(staged.iterdir(), key=lambda item: item.name):
        payload = path.read_bytes()
        name = path.name
        record_type = "other"
        schema_path: str | None = PUBLIC_ARTIFACT_SCHEMA
        ids: list[str] = []
        if name == "claims.json":
            record_type, schema_path, ids = "data", None, record_ids
        elif name == "source-rules-snapshot.json":
            record_type, schema_path, ids = "source_registry", "schemas/common/source-rules-snapshot.schema.json", included["sources"]
        elif name == "license-decisions.json":
            record_type, schema_path, ids = "license_decisions", "schemas/common/license-decision-registry.schema.json", ["license-decision:od-001", "license-decision:od-002"]
        elif name == "third-party-notices.json":
            record_type, schema_path, ids = "third_party_notices", "schemas/common/third-party-notices.schema.json", included["sources"]
        elif name == "attributions.json":
            record_type, schema_path, ids = "attributions", "schemas/common/attribution-manifest.schema.json", []
        elif name == "search-index.json":
            record_type = "search_index"
        manifest_files.append({
            "path": name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "record_type": record_type,
            "schema_path": schema_path,
            "record_ids": ids,
        })
    schema_index = {
        item["path"]: item["version"]
        for manifest_path in sorted((ROOT / "schemas").rglob("schema-manifest.json"))
        for item in _load_json(manifest_path)["schemas"]
    }
    used_schemas = {
        "schemas/common/dataset-release.schema.json", "schemas/common/source.schema.json",
        "schemas/common/source-rules-snapshot.schema.json", "schemas/common/license-decision-registry.schema.json",
        "schemas/common/third-party-notices.schema.json", "schemas/common/attribution-manifest.schema.json",
        PUBLIC_RECORD_SCHEMA, PUBLIC_ARTIFACT_SCHEMA,
    }
    manifest: dict[str, Any] = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "id": RELEASE_ID,
        "entity_type": "dataset_release",
        "version": RELEASE_VERSION,
        "schema_versions": {_schema_key(path): schema_index[path] for path in sorted(used_schemas)},
        "build_version": "museum-04-projection-v1",
        "created_at": "2026-07-14T00:00:00+08:00",
        "source_snapshot_at": "2026-07-13T15:32:00+08:00",
        "content_hash": _release_content_hash(manifest_files),
        "status": "reviewed",
        "predecessor": None,
        "public_release": False,
        "public_until": None,
        "included_entity_ids": sorted(included["entities"]),
        "included_relationship_ids": sorted(included["relationships"]),
        "included_claim_ids": sorted(included["claims"]),
        "included_evidence_ids": sorted(included["evidence"]),
        "included_source_ids": sorted(included["sources"]),
        "included_media_asset_ids": [],
        "withdrawals": [],
        "deprecations": [],
        "manifest_files": manifest_files,
        "license_decisions": {
            "code_license_decision_id": "license-decision:od-001",
            "code_license_status": "decided",
            "original_content_license_decision_id": "license-decision:od-002",
            "original_content_license_status": "decided",
            "third_party_scope_statement": "Only the four bound metadata/data rules listed in notices apply; no media rights are included.",
            "registry_path": "license-decisions.json",
            "registry_sha256": next(item["sha256"] for item in manifest_files if item["path"] == "license-decisions.json"),
        },
        "source_registry_manifest": _artifact_ref(manifest_files, "source-rules-snapshot.json"),
        "third_party_notices_manifest": _artifact_ref(manifest_files, "third-party-notices.json"),
        "attribution_manifest": {**_artifact_ref(manifest_files, "attributions.json"), "asset_ids": []},
        "release_notes": "Metadata-only constellation release candidate: 12 artists, 31 contexts, 36 C-level curatorial comparisons, zero media and zero algorithmic edges; formal public release is pending identified human editorial review of all 12 bilingual artist summaries.",
    }
    return manifest


def _validate_artifact_schemas(documents: dict[str, Any], failures: list[dict[str, str]]) -> None:
    environment = load_schema_environment(ROOT)
    record_validator = Draft202012Validator(environment.by_path[PUBLIC_RECORD_SCHEMA], registry=environment.registry, format_checker=FormatChecker())
    artifact_validator = Draft202012Validator(environment.by_path[PUBLIC_ARTIFACT_SCHEMA], registry=environment.registry, format_checker=FormatChecker())
    claims = documents.get("claims.json", {})
    for index, envelope in enumerate(claims.get("records", []) if isinstance(claims, dict) else []):
        if not isinstance(envelope, dict) or set(envelope) != {"target_schema", "data"} or not isinstance(envelope.get("data"), dict):
            _fail(failures, "m04_record_envelope_invalid", "Record envelope must contain only target_schema and data", f"claims.json.records[{index}]")
            continue
        if envelope["data"].get("entity_type") == "source":
            continue
        if envelope.get("target_schema") != PUBLIC_RECORD_SCHEMA:
            _fail(failures, "m04_record_schema_dispatch", "Public projection record requested a non-canonical schema", f"claims.json.records[{index}]")
        for error in record_validator.iter_errors(envelope["data"]):
            _fail(failures, "m04_record_schema", error.message, f"claims.json.records[{index}]")
    for name in sorted(EXPECTED_FILES - {"source-rules-snapshot.json", "license-decisions.json", "third-party-notices.json", "attributions.json"}):
        document = documents.get(name)
        if document is None:
            continue
        for error in artifact_validator.iter_errors(document):
            _fail(failures, "m04_artifact_schema", error.message, name)


def _validate_manifest_profile(
    documents: dict[str, Any],
    failures: list[dict[str, str]],
    *,
    require_public: bool,
) -> None:
    manifest = documents["manifest.json"]
    candidate_profile = manifest.get("status") == "reviewed" and manifest.get("public_release") is False
    public_profile = manifest.get("status") in {"publishable", "published"} and manifest.get("public_release") is True
    if manifest.get("id") != RELEASE_ID or manifest.get("version") != RELEASE_VERSION or not (candidate_profile or public_profile):
        _fail(failures, "m04_release_identity", "Release identity, version, public flag or lifecycle is invalid")
    if require_public and not public_profile:
        _fail(
            failures,
            "m04_human_editorial_review_required",
            "Formal public release is blocked until all 12 bilingual artist summaries receive identified human editorial approval",
        )
    if manifest.get("included_media_asset_ids") != []:
        _fail(failures, "m04_media_ids_nonzero", "Metadata-only release must include zero media IDs")
    if manifest.get("predecessor") is not None or not isinstance(manifest.get("withdrawals"), list):
        _fail(failures, "m04_withdrawal_contract", "Initial release needs predecessor=null and structured withdrawals")
    if {item.get("path") for item in manifest.get("manifest_files", [])} != EXPECTED_FILES:
        _fail(failures, "m04_manifest_artifact_set", "Manifest artifact set differs from the MUSEUM-04 contract")


def _validate_public_projection(
    documents: dict[str, Any],
    failures: list[dict[str, str]],
    baseline_source: dict[str, Any] | None,
) -> None:
    graph = documents.get("graph-summary.json", {})
    counts = graph.get("counts", {})
    expected = {"artists": 12, "contexts": 31, "relationships": 36, "artworks": 44, "sources": 4, "media": 0, "media_bytes": 0}
    for key, value in expected.items():
        if counts.get(key) != value:
            _fail(failures, "m04_count_mismatch", f"{key} expected {value}, got {counts.get(key)}")
    if counts.get("levels") != {"A": 0, "B": 0, "C": 36}:
        _fail(failures, "m04_level_counts", "A/B/C must equal 0/0/36")
    if counts.get("relationship_types") != {"shared_material": 11, "shared_subject": 17, "shared_technique": 8}:
        _fail(failures, "m04_relationship_type_counts", "Relationship type counts differ from sealed graph")
    if graph.get("profile") != "metadata_only" or graph.get("initial_state", {}).get("edges_visible") is not False:
        _fail(failures, "m04_graph_profile", "Graph must be metadata-only with no initial edges")
    semantics = graph.get("semantics", {})
    if any(semantics.get(key) is not False for key in ("algorithmic", "causal", "directed")):
        _fail(failures, "m04_graph_semantics", "Graph semantics must be non-algorithmic, non-causal and undirected")

    collections = {
        "artists": documents.get("artists.json", {}).get("artists", []),
        "contexts": documents.get("contexts.json", {}).get("contexts", []),
        "relationships": documents.get("relationships.json", {}).get("relationships", []),
        "artworks": documents.get("artworks.json", {}).get("artworks", []),
        "evidence": documents.get("evidence.json", {}).get("evidence", []),
        "sources": documents.get("sources.json", {}).get("sources", []),
        "claims": documents.get("claims.json", {}).get("claims", []),
    }
    public_profile = documents.get("manifest.json", {}).get("public_release") is True
    envelope_records = {
        item["data"]["id"]: item["data"]
        for item in documents.get("claims.json", {}).get("records", [])
        if isinstance(item, dict) and isinstance(item.get("data"), dict) and isinstance(item["data"].get("id"), str)
    }
    projected_records = {
        item["id"]: item
        for name in ("artists", "contexts", "relationships", "artworks", "claims", "evidence")
        for item in collections[name]
    }
    if any(envelope_records.get(record_id) != record for record_id, record in projected_records.items()):
        _fail(failures, "m04_record_projection_mismatch", "Public artifacts and physical record envelopes differ")
    for name, values in collections.items():
        if counts.get(name) != len(values):
            _fail(failures, "m04_self_report_mismatch", f"{name} count differs from artifact length")
        ids = [item.get("id") for item in values if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            _fail(failures, "m04_duplicate_id", f"Duplicate IDs in {name}")

    artist_ids = {item["id"] for item in collections["artists"]}
    artists_by_id = {item["id"]: item for item in collections["artists"]}
    context_ids = {item["id"] for item in collections["contexts"]}
    contexts_by_id = {item["id"]: item for item in collections["contexts"]}
    artwork_ids = {item["id"] for item in collections["artworks"]}
    artworks_by_id = {item["id"]: item for item in collections["artworks"]}
    if baseline_source is not None:
        expected_object_urls = {
            item["id"]: (item.get("official_object_record") or {}).get("official_object_url")
            for item in baseline_source["artworks"]
        }
        if any(
            artwork.get("official_object_url") != expected_object_urls.get(artwork.get("id"))
            for artwork in collections["artworks"]
        ):
            _fail(
                failures,
                "m04_artwork_url_projection",
                "Artwork official object URLs must exactly match the sealed MUSEUM-03B records",
            )
    claim_ids = {item["id"] for item in collections["claims"]}
    evidence_ids = {item["id"] for item in collections["evidence"]}
    source_ids = {item["id"] for item in collections["sources"]}
    for artist in collections["artists"]:
        summary = artist.get("summary", {})
        chinese = str(summary.get("zh-Hans", ""))
        english = str(summary.get("en", ""))
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", chinese))
        if not 80 <= cjk_count <= 160:
            _fail(failures, "m04_artist_summary_length", f"Artist summary must contain 80-160 CJK characters, got {cjk_count}: {artist.get('id')}")
        if len(english) < 160 or "constellation" not in english.lower():
            _fail(failures, "m04_artist_summary_english", f"Artist English summary lacks corresponding exhibition meaning: {artist.get('id')}")
        provenance = artist.get("summary_provenance", {})
        common_provenance_invalid = (
            provenance.get("authority_basis") != "deterministic_claim_bounded_assembly_from_museum_03b_accepted_reviewed_records"
            or provenance.get("copied_museum_label") is not False
            or provenance.get("claim_ids") != artist.get("verified_claim_ids")
            or not set(provenance.get("claim_ids", [])) <= claim_ids
            or not set(provenance.get("source_ids", [])) <= source_ids
        )
        public_provenance_invalid = (
            artist.get("review_status") != "publishable"
            or artist.get("lifecycle_status") != "publishable"
            or provenance.get("reviewer_kind") != "human_editorial_reviewer"
            or provenance.get("reviewer_id") in {None, "", "codex-primary-agent"}
            or provenance.get("human_reviewed") is not True
        )
        candidate_provenance_invalid = (
            artist.get("review_status") != "reviewed"
            or artist.get("lifecycle_status") != "reviewed"
            or provenance.get("reviewer_id") != "codex-primary-agent"
            or provenance.get("reviewer_kind") != "ai_assisted_operator"
            or provenance.get("human_reviewed") is not False
        )
        if common_provenance_invalid or (public_provenance_invalid if public_profile else candidate_provenance_invalid):
            _fail(failures, "m04_artist_summary_provenance", f"Summary provenance is incomplete or overclaims human review: {artist.get('id')}")
    for collection_name in ("contexts", "relationships", "artworks"):
        for record in collections[collection_name]:
            if record.get("lifecycle_status") != "publishable" or record.get("review_status") != "publishable":
                _fail(
                    failures,
                    "m04_non_artist_publish_state",
                    f"Non-artist projection record is not publishable: {record.get('id')}",
                )
    for claim in collections["claims"]:
        if claim.get("status") != "publishable" or claim.get("publish_status") != "publishable":
            _fail(failures, "m04_non_artist_publish_state", f"Claim is not publishable: {claim.get('id')}")
    for evidence in collections["evidence"]:
        if evidence.get("lifecycle_status") != "publishable":
            _fail(failures, "m04_non_artist_publish_state", f"Evidence is not publishable: {evidence.get('id')}")
    source_dtos = collections["sources"]
    if any(
        source.get("locator", {}).get("url") != source.get("official_url")
        or set(source.get("locator", {}).get("label", {})) != {"zh-Hans", "en"}
        or envelope_records.get(source.get("id"), {}).get("publisher") != source.get("publisher")
        or envelope_records.get(source.get("id"), {}).get("official_url") != source.get("official_url")
        for source in source_dtos
    ):
        _fail(failures, "m04_source_locator", "Every source locator must be bilingual and resolve to its official HTTPS URL")

    search_entries = documents.get("search-index.json", {}).get("entries", [])
    search_by_id = {item.get("id"): item for item in search_entries if isinstance(item, dict)}
    if len(search_entries) != 12 or set(search_by_id) != artist_ids:
        _fail(failures, "m04_search_artist_set", "Search index must contain exactly one aggregate row per artist")
    for artist in collections["artists"]:
        entry = search_by_id.get(artist["id"], {})
        expected_keys = [
            {"value": value, "locale": locale, "reason": "preferred", "normalized_key": _normalize_search(value)}
            for locale, value in artist["labels"].items()
        ]
        expected_keys.extend(
            {"value": alias["text"], "locale": alias["language"], "reason": "alias", "normalized_key": _normalize_search(alias["text"])}
            for alias in artist["aliases"]
        )
        expected_keys.sort(key=lambda item: (item["normalized_key"], item["locale"], item["value"]))
        if (
            entry.get("type") != "artist"
            or entry.get("labels") != artist["labels"]
            or entry.get("aliases") != artist["aliases"]
            or entry.get("normalized_keys") != expected_keys
        ):
            _fail(failures, "m04_search_projection", f"Search projection drifted for {artist['id']}")

    facets = documents.get("facets.json", {}).get("facets", {})
    expected_facet_counts = {
        "periods": Counter(value for artist in collections["artists"] for value in artist["historical_periods"]),
        "regions": Counter(place["label"] for artist in collections["artists"] for place in artist["activity_places"]),
        "traditions": Counter(value for artist in collections["artists"] for value in artist["artistic_traditions"]),
    }
    for facet_name, expected_counts in expected_facet_counts.items():
        observed = {item.get("value"): item.get("count") for item in facets.get(facet_name, [])}
        if observed != dict(sorted(expected_counts.items())):
            _fail(failures, "m04_facet_projection", f"Facet counts drifted for {facet_name}")
    degree = Counter()
    chinese_relationship_explanations: list[str] = []
    for relationship in collections["relationships"]:
        if relationship.get("level") != "C" or relationship.get("type") not in RELATION_TYPES or relationship.get("directed") is not False or relationship.get("is_algorithmic") is not False:
            _fail(failures, "m04_relationship_semantics", f"Invalid public relationship semantics for {relationship.get('id')}")
        if relationship.get("historical_relationship_strength") is not None or relationship.get("computational_similarity") is not None:
            _fail(failures, "m04_relationship_score_crosswire", f"Historical/computational fields must stay null for {relationship.get('id')}")
        endpoints = {relationship.get("source_artist_id"), relationship.get("target_artist_id")}
        if not endpoints <= artist_ids or len(endpoints) != 2:
            _fail(failures, "m04_relationship_endpoint", f"Unknown or self endpoint in {relationship.get('id')}")
        degree.update(endpoints)
        if not set(relationship.get("context_ids", [])) <= context_ids:
            _fail(failures, "m04_relationship_context", f"Unknown context in {relationship.get('id')}")
        if any(not relationship.get(field) for field in ("context_ids", "claim_ids", "evidence_ids", "source_ids")):
            _fail(failures, "m04_relationship_reference_required", f"Relationship references cannot be empty: {relationship.get('id')}")
        if not set(relationship.get("supporting_artwork_ids", [])) <= artwork_ids or len(relationship.get("supporting_artwork_ids", [])) < 2:
            _fail(failures, "m04_relationship_artwork_closure", f"Relationship lacks two public supporting artworks: {relationship.get('id')}")
        supporting_artist_ids = {
            artworks_by_id[artwork_id].get("artist_id")
            for artwork_id in relationship.get("supporting_artwork_ids", [])
            if artwork_id in artworks_by_id
        }
        if not endpoints <= supporting_artist_ids:
            _fail(failures, "m04_relationship_endpoint_artworks", f"Supporting artworks do not cover both relationship endpoints: {relationship.get('id')}")
        if not set(relationship.get("claim_ids", [])) <= claim_ids or not set(relationship.get("evidence_ids", [])) <= evidence_ids or not set(relationship.get("source_ids", [])) <= source_ids:
            _fail(failures, "m04_relationship_reference_closure", f"Claim/Evidence/Source closure fails for {relationship.get('id')}")
        chinese_explanation = str(relationship.get("short_explanation", {}).get("zh-Hans", ""))
        chinese_relationship_explanations.append(chinese_explanation)
        source_artist = artists_by_id.get(relationship.get("source_artist_id"), {})
        target_artist = artists_by_id.get(relationship.get("target_artist_id"), {})
        relation_type = relationship.get("type")
        required_specific_terms = [
            source_artist.get("labels", {}).get("zh-Hans", ""),
            target_artist.get("labels", {}).get("zh-Hans", ""),
            _relation_label(relation_type)["zh-Hans"] if relation_type in RELATION_TYPES else "",
            *(
                contexts_by_id.get(context_id, {}).get("labels", {}).get("zh-Hans", "")
                for context_id in relationship.get("context_ids", [])
            ),
        ]
        if (
            any(not term or term not in chinese_explanation for term in required_specific_terms)
            or "不表示" not in chinese_explanation
            or "因果关系" not in chinese_explanation
        ):
            _fail(
                failures,
                "m04_relationship_explanation_not_specific",
                f"Chinese explanation must name both endpoints, relation/context, and its non-causal boundary: {relationship.get('id')}",
            )
        for field in ("title", "short_explanation", "what_it_means"):
            value = relationship.get(field, {})
            if CAUSAL_ASSERTION.search(" ".join(str(item) for item in value.values())):
                _fail(failures, "m04_causal_wording", f"Positive causal wording in {relationship.get('id')}.{field}")
    if len(chinese_relationship_explanations) != len(set(chinese_relationship_explanations)):
        _fail(failures, "m04_relationship_explanation_duplicate", "Every Chinese relationship explanation must be relation-specific")
    if set(degree) != artist_ids:
        _fail(failures, "m04_isolated_artist", f"Isolated artists: {sorted(artist_ids-set(degree))}")

    evidence_index = {item["id"]: item for item in collections["evidence"]}
    for evidence in collections["evidence"]:
        for field in ("summary", "reliability_note"):
            text = evidence.get(field, {})
            if not isinstance(text, dict) or any(len(str(value)) > 600 for value in text.values()):
                _fail(failures, "m04_evidence_summary_length", f"Evidence {field} is not concise: {evidence.get('id')}")
    for claim in collections["claims"]:
        if claim.get("status") != "publishable" or claim.get("publish_status") != "publishable" or claim.get("disputed") is not False:
            _fail(failures, "m04_claim_not_publishable", f"Claim is not safe for public release: {claim.get('id')}")
        if not claim.get("evidence_ids"):
            _fail(failures, "m04_claim_evidence_required", f"Claim has no Evidence: {claim.get('id')}")
        if not set(claim.get("evidence_ids", [])) <= evidence_ids:
            _fail(failures, "m04_claim_evidence_closure", f"Missing Evidence for {claim.get('id')}")
        for evidence_id in claim.get("evidence_ids", []):
            evidence = evidence_index.get(evidence_id)
            if evidence is not None and claim["id"] not in evidence.get("claim_ids", []):
                _fail(failures, "m04_evidence_backlink", f"Evidence backlink missing for {claim.get('id')}")

    layout = documents.get("layout.json", {})
    if layout.get("algorithm") != "deterministic_circle_v1" or layout.get("seed") != "museum-04-art-constellation-0.1.0":
        _fail(failures, "m04_layout_contract", "Layout algorithm or seed changed")
    if {item.get("artist_id") for item in layout.get("nodes", [])} != artist_ids or len(layout.get("nodes", [])) != 12:
        _fail(failures, "m04_layout_closure", "Layout must contain exactly the 12 artists")
    expected_hash = canonical_sha256({key: value for key, value in layout.items() if key != "content_hash"})
    if layout.get("content_hash") != expected_hash:
        _fail(failures, "m04_layout_hash", "Layout content_hash is invalid")


def _validate_governance_artifacts(documents: dict[str, Any], failures: list[dict[str, str]]) -> None:
    decisions = documents.get("license-decisions.json", {}).get("decisions", [])
    if {item.get("decision_id") for item in decisions} != {"license-decision:od-001", "license-decision:od-002"}:
        _fail(failures, "m04_license_decision_set", "Release must snapshot exactly OD-001 and OD-002")
    for decision in decisions:
        license_value = decision.get("license") or {}
        if decision.get("status") != "decided" or license_value.get("identifier") != "ALL-RIGHTS-RESERVED" or decision.get("approver") != "Mays":
            _fail(failures, "m04_license_decision_open", f"License decision is not closed: {decision.get('decision_id')}")
    notices = documents.get("third-party-notices.json", {}).get("notices", [])
    if len(notices) != 4 or {rule for item in notices for rule in item.get("license_rule_ids", [])} != set(DATA_RULE_IDS.values()):
        _fail(failures, "m04_notice_rule_set", "Notices must cover exactly the four used data rules")
    source_rule_snapshots = documents.get("source-rules-snapshot.json", {}).get("sources", [])
    snapshots_by_source = {
        item.get("source_id"): item
        for item in source_rule_snapshots
        if isinstance(item, dict)
    }
    if set(snapshots_by_source) != set(DATA_RULE_IDS):
        _fail(failures, "m04_source_rule_set", "Source rules snapshot must cover exactly the four used sources")
    for source_id, selected_rule_id in DATA_RULE_IDS.items():
        snapshot = snapshots_by_source.get(source_id, {})
        rules = snapshot.get("license_rules", []) if isinstance(snapshot, dict) else []
        if (
            len(rules) != 1
            or not isinstance(rules[0], dict)
            or rules[0].get("rule_id") != selected_rule_id
            or rules[0].get("content_class") != "data"
            or snapshot.get("license_rules_snapshot_hash") != canonical_sha256(rules)
        ):
            _fail(
                failures,
                "m04_source_rule_scope",
                f"Source {source_id} must snapshot only its exact selected canonical data rule",
            )
    source_dtos = {
        item.get("id"): item
        for item in documents.get("sources.json", {}).get("sources", [])
        if isinstance(item, dict)
    }
    notices_by_source = {
        item.get("record_id"): item
        for item in notices
        if isinstance(item, dict)
    }
    for source_id, selected_rule_id in DATA_RULE_IDS.items():
        source = source_dtos.get(source_id, {})
        snapshot = snapshots_by_source.get(source_id, {})
        rules = snapshot.get("license_rules", []) if isinstance(snapshot, dict) else []
        rule = rules[0] if len(rules) == 1 and isinstance(rules[0], dict) else {}
        attribution_texts = [rule["attribution_template"]] if rule.get("attribution_template") else []
        notice = notices_by_source.get(source_id, {})
        if (
            source.get("license") != {
                "rule_ids": [selected_rule_id],
                "identifiers": [rule.get("identifier")],
                "attribution_texts": attribution_texts,
            }
            or source.get("attribution") != (attribution_texts[0] if attribution_texts else source.get("publisher"))
            or notice.get("license_rule_ids") != [selected_rule_id]
            or notice.get("license_identifiers") != [rule.get("identifier")]
            or notice.get("attribution_texts") != attribution_texts
        ):
            _fail(failures, "m04_source_license_projection", f"Source DTO, snapshot and notice disagree for {source_id}")
    if documents.get("attributions.json") != {"assets": []}:
        _fail(failures, "m04_attribution_nonzero", "Zero-media attribution manifest must have assets=[]")
    rights = documents.get("rights.json", {})
    if rights != _rights_document():
        _fail(failures, "m04_rights_contract", "Rights snapshot differs from the approved MUSEUM-04 visitor and zero-media contract")
    media = rights.get("media", {})
    if media != {
        "count": 0,
        "bytes": 0,
        "downloaded": False,
        "statement": {
            "zh-Hans": "本次发布不含作品图像、缩略图或 IIIF 资源。",
            "en": "This release contains no artwork media, thumbnails, or IIIF resources.",
        },
    }:
        _fail(failures, "m04_no_media_declaration", "Rights no-media declaration is missing or inconsistent")
    request = rights.get("rights_request", {})
    if request.get("url") != "https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml" or request.get("sensitive_evidence_public_issue") is not False:
        _fail(failures, "m04_rights_request", "Rights request URL or sensitive-evidence boundary is invalid")
    signoff = documents.get("release-signoff.json", {})
    graph_counts = documents.get("graph-summary.json", {}).get("counts", {})
    artists = documents.get("artists.json", {}).get("artists", [])
    summary_digest = _summary_digest(artists)
    public_profile = documents.get("manifest.json", {}).get("public_release") is True
    if not public_profile:
        if signoff != _release_signoff(graph_counts, summary_digest):
            _fail(failures, "m04_release_signoff_contract", "Candidate sign-off fields, checks, limitations or counts drifted")
    else:
        reviewer_id = signoff.get("reviewer_id")
        reviewed_at = signoff.get("reviewed_at")
        human_date = reviewed_at[:10] if isinstance(reviewed_at, str) else None
        formal_signoff_invalid = (
            signoff.get("decision") != "accepted_for_public_release"
            or signoff.get("editorial_review_status") != "approved"
            or signoff.get("reviewer_kind") != "human_editorial_reviewer"
            or reviewer_id in {None, "", "codex-primary-agent"}
            or signoff.get("human_reviewer_claimed") is not True
            or signoff.get("summary_digest") != summary_digest
            or signoff.get("counts") != graph_counts
            or any(
                artist.get("summary_provenance", {}).get("reviewer_id") != reviewer_id
                or artist.get("summary_provenance", {}).get("reviewer_kind") != "human_editorial_reviewer"
                or artist.get("summary_provenance", {}).get("human_reviewed") is not True
                or artist.get("summary_provenance", {}).get("reviewed_at") != human_date
                for artist in artists
            )
        )
        if formal_signoff_invalid:
            _fail(failures, "m04_release_signoff_contract", "Formal release lacks matching identified human editorial approval for all 12 summaries")
    if signoff.get("m03b_package_hash") != EXPECTED_PACKAGE_HASH or signoff.get("m03b_graph_hash") != EXPECTED_GRAPH_HASH:
        _fail(failures, "m04_release_signoff_baseline", "Release sign-off does not bind the sealed baseline hashes")
    performance = documents.get("performance-contract.json", {})
    if performance != _performance_contract():
        _fail(failures, "m04_performance_contract", "Performance contract differs from the approved MUSEUM-04 budgets and scale boundaries")
    graph_budget = performance.get("budgets", {}).get("graph_summary_gzip_bytes_max")
    route_budget = performance.get("budgets", {}).get("route_assets_gzip_bytes_max")
    graph_gzip_bytes = len(gzip.compress(canonical_json_bytes(documents.get("graph-summary.json", {})), mtime=0))
    if graph_budget != 100 * 1024 or graph_gzip_bytes > graph_budget:
        _fail(failures, "m04_graph_summary_budget", f"graph-summary gzip bytes {graph_gzip_bytes} exceed or drift from the 100 KiB contract")
    if route_budget != 450 * 1024:
        _fail(failures, "m04_route_assets_budget", "route asset budget must be exactly 450 KiB")


def _validate_no_media_or_private_data(documents: dict[str, Any], failures: list[dict[str, str]]) -> None:
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_PUBLIC_KEYS:
                    _fail(failures, "m04_forbidden_public_field", f"Forbidden field {key}", f"{path}.{key}")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in ("file://", "c:\\", "d:\\", "/data/raw/", "/data/intermediate/")):
                _fail(failures, "m04_private_path", "Local/private path leaked", path)
            if any(token in lowered for token in ("raw fields:", "raw locator", "raw_snapshot", "local path", "internal note")):
                _fail(failures, "m04_internal_locator", "Raw/private locator terminology leaked", path)
            if re.search(r"\bQ[1-9][0-9]{2,}\b", value) or re.search(
                r"(?:vocab\.getty\.edu/ulan/|\bulan[:\s]+)[0-9]{6,}",
                value,
                re.IGNORECASE,
            ):
                _fail(failures, "m04_external_id", "External authority identifier leaked", path)
            if lowered.startswith(("http://", "https://")):
                parsed = urlparse(value)
                url_path = parsed.path.lower()
                query = parsed.query.lower()
                if (
                    any(url_path.endswith(suffix) for suffix in MEDIA_FILE_SUFFIXES)
                    or "iiif" in (parsed.hostname or "").lower()
                    or "/iiif" in url_path
                    or any(token in query for token in ("image_id", "image_url", "media_url", "thumbnail", "iiif"))
                ):
                    _fail(failures, "m04_media_url", "Media or IIIF URL leaked into metadata-only release", path)
    for name, document in documents.items():
        visit(document, name)


def _assert_baseline(source: dict[str, Any]) -> None:
    manifest = source["package_manifest"]
    graph = source["graph"]
    if manifest.get("content_hash") != EXPECTED_PACKAGE_HASH:
        raise ValueError("M03B package hash mismatch")
    if graph.get("content_hash") != EXPECTED_GRAPH_HASH:
        raise ValueError("M03B graph hash mismatch")
    if (len(source["artists"]), len(source["artworks"]), len(source["contexts"]), len(source["relationships"])) != (12, 44, 31, 36):
        raise ValueError("M03B record counts mismatch")
    if Counter(item.get("evidence_level") for item in source["relationships"]) != {"C": 36}:
        raise ValueError("M03B relationship levels mismatch")
    if Counter(item.get("relationship_type") for item in source["relationships"]) != {"shared_subject": 17, "shared_material": 11, "shared_technique": 8}:
        raise ValueError("M03B relationship type counts mismatch")
    if any(item.get("is_algorithmic") or item.get("computational_similarity") is not None or item.get("historical_relationship_strength") is not None for item in source["relationships"]):
        raise ValueError("M03B graph semantics mismatch")


def _load_package(package_dir: Path) -> dict[str, Any]:
    return {
        "package_manifest": _load_json(package_dir / "package-manifest.json"),
        "graph": _load_json(package_dir / "graph-input.json"),
        **{
            key: _load_json(package_dir / file_name)
            for key, file_name in (
                ("artists", "artists.json"), ("artworks", "artworks.json"), ("contexts", "contexts.json"),
                ("relationships", "relationships.json"), ("claims", "claims.json"),
                ("evidence", "evidence.json"), ("sources", "sources.json"),
            )
        },
    }


def _license_decisions_snapshot() -> dict[str, Any]:
    global_registry = _load_json(ROOT / "governance" / "license-decisions.json")
    selected = [item for item in global_registry["decisions"] if item["decision_id"] in {"license-decision:od-001", "license-decision:od-002"}]
    if len(selected) != 2:
        raise ValueError("OD-001/OD-002 are not both present in the global registry")
    return {"schema_version": global_registry["schema_version"], "decisions": selected}


def _source_rules_snapshot(sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "snapshot_id": "source-rules:museum-04-art-constellation-0.1.0",
        "generated_at": "2026-07-14T00:00:00+08:00",
        "sources": [
            {
                "source_id": source["id"],
                "registry_source_id": source["registry_source_id"],
                "registry_identity": source["registry_identity"],
                "license_rules_snapshot_hash": source["license_rules_snapshot_hash"],
                "license_rules": source["license_rules"],
            }
            for source in sources
        ],
    }


def _third_party_notices(sources: list[dict[str, Any]]) -> dict[str, Any]:
    notices = []
    for source in sources:
        rule = next(item for item in source["license_rules"] if item["rule_id"] == DATA_RULE_IDS[source["id"]])
        attributions = [rule["attribution_template"]] if rule.get("attribution_template") else []
        notices.append({
            "record_id": source["id"],
            "notice": f"本元数据发布仅在精确绑定字段范围内使用 {source['publisher']} 数据，规则标识为 {rule['identifier']}。 / {source['publisher']} data used under {rule['identifier']} for the exact bound fields in this metadata-only release.",
            "source_url": source["official_url"],
            "license_rule_ids": [rule["rule_id"]],
            "license_identifiers": [rule["identifier"]],
            "attribution_texts": attributions,
            "rights_holder": source["publisher"],
        })
    return {
        "scope_statement": "本发布仅使用四条来源数据规则，不包含任何媒体规则或媒体权利。 / Exactly four source data rules are used. No media rule or media right is included.",
        "notices": notices,
    }


def _rights_document() -> dict[str, Any]:
    statement = {
        "zh-Hans": "保留所有权利；公开可见不代表授予复制、修改、再分发或商业使用许可。",
        "en": "All rights reserved; public visibility does not grant permission to copy, modify, redistribute, or use commercially.",
    }
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "code_rights": {"identifier": "ALL-RIGHTS-RESERVED", "status": "decided", "statement": statement},
        "original_content_rights": {"identifier": "ALL-RIGHTS-RESERVED", "status": "decided", "statement": statement},
        "third_party_metadata": {
            "statement": {
                "zh-Hans": "第三方元数据仍受精确来源规则与署名通知约束。",
                "en": "Third-party metadata remains governed by the exact source rules and attribution notices.",
            },
            "notices_path": "third-party-notices.json",
            "source_rules_path": "source-rules-snapshot.json",
        },
        "media": {
            "count": 0,
            "bytes": 0,
            "downloaded": False,
            "statement": {
                "zh-Hans": "本次发布不含作品图像、缩略图或 IIIF 资源。",
                "en": "This release contains no artwork media, thumbnails, or IIIF resources.",
            },
        },
        "rights_request": {
            "url": "https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml",
            "label": {"zh-Hans": "权利或署名请求", "en": "Rights or attribution request"},
            "sensitive_evidence_public_issue": False,
        },
        "attributions_path": "attributions.json",
        "public_scope": {"zh-Hans": "仅含本 release 列出的策展文字与第三方元数据。", "en": "Only the curatorial text and third-party metadata listed in this release are public."},
    }


def _summary_digest(artists: list[dict[str, Any]]) -> str:
    return canonical_sha256({
        "release_id": RELEASE_ID,
        "summaries": [
            {"artist_id": artist["id"], "summary": artist["summary"]}
            for artist in sorted(artists, key=lambda item: item["id"])
        ],
    })


def _release_signoff(counts: dict[str, Any], summary_digest: str) -> dict[str, Any]:
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "id": "release-signoff:art-constellation-0.1.0",
        "release_id": RELEASE_ID,
        "phase_id": PHASE_ID,
        "decision": "candidate_pending_human_editorial_review",
        "reviewer_id": "codex-primary-agent",
        "reviewer_kind": "ai_assisted_operator",
        "human_reviewer_claimed": False,
        "editorial_review_status": "pending",
        "summary_digest": summary_digest,
        "reviewed_at": "2026-07-14T00:00:00+08:00",
        "m03b_package_hash": EXPECTED_PACKAGE_HASH,
        "m03b_graph_hash": EXPECTED_GRAPH_HASH,
        "counts": counts,
        "checks": [
            "baseline_hashes", "exact_counts", "c_level_only", "non_causal", "non_algorithmic",
            "zero_media", "field_allowlist", "claim_evidence_source_closure", "source_rules",
            "license_decisions", "notices", "attributions", "physical_hashes", "withdrawal_capability",
        ],
        "limitations": "AI-assisted structural validation is recorded accurately; formal public release remains blocked until all 12 bilingual artist summaries receive identified human editorial approval.",
    }


def _performance_contract() -> dict[str, Any]:
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "profile": "museum-04-current-graph",
        "budgets": {
            "graph_summary_gzip_bytes_max": 100 * 1024,
            "route_assets_gzip_bytes_max": 450 * 1024,
            "mobile_visible_vertices_max": 150,
            "mobile_visible_edges_max": 600,
            "desktop_visible_vertices_max": 300,
            "desktop_visible_edges_max": 1200,
        },
        "scale_boundaries": {
            "one_k": {
                "vertices": 1000,
                "edges": 5000,
                "full_initial_render": False,
                "rendering_mode": "capped_progressive",
                "initial_visible_vertices": 150,
                "initial_visible_edges": 600,
            },
            "ten_k": {"vertices": 10000, "edges": 60000, "full_initial_render": False},
            "fifty_k": {"vertices": 50000, "edges": 300000, "mobile_full_render": "refused"},
        },
        "continuous_force_layout": False,
        "external_runtime_api": False,
        "media_requests": False,
    }


def _artifact(key: str, values: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": RELEASE_SCHEMA_VERSION, "release_id": RELEASE_ID, key: values}


def _data_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for item in bindings:
        if DATA_RULE_IDS.get(item.get("source_id")) != item.get("rule_id"):
            continue
        binding = deepcopy(item)
        if binding["source_id"] == "source:aic_api":
            binding["scope_fields"] = list(PUBLIC_AIC_SCOPE_FIELDS)
            binding["scope_locator"] = _public_aic_locator(binding["scope_locator"])
        projected.append(binding)
    return sorted(projected, key=lambda item: (item["source_id"], item["rule_id"]))


def _review_provenance() -> dict[str, Any]:
    return {"reviewed_at": "2026-07-14", "reviewer_id": "codex-primary-agent", "reviewer_kind": "ai_assisted_operator"}


def _public_evidence_locator(locator: dict[str, Any], evidence_id: str) -> dict[str, str]:
    section = str(locator["section"])
    if section.startswith("https://api.artic.edu/"):
        section = _public_aic_locator(section)
    if section.startswith("raw fields:"):
        section = "official record fields:" + section.removeprefix("raw fields:")
    if "raw locators" in section or "raw_snapshot_refs" in section:
        section = "reviewed synthesis from the listed official record fields"
    if not section.startswith(("http://", "https://")):
        if section.startswith("/"):
            section = "official record field: " + section.strip("/").replace("/", " ").replace("_", " ")
        section = re.sub(
            r"/(?:data/)?([a-z][a-z0-9_]*)",
            lambda match: match.group(1).replace("_", " "),
            section,
            flags=re.IGNORECASE,
        )
    return {"record_id": evidence_id, "section": section}


def _public_aic_locator(locator: str) -> str:
    base = locator.split("?", 1)[0].split("#", 1)[0]
    return f"{base}?{urlencode({'fields': ','.join(PUBLIC_AIC_SCOPE_FIELDS)})}"


def _public_evidence_text(evidence_kind: str) -> dict[str, dict[str, str]]:
    summaries = {
        "collection_record": {
            "zh-Hans": "官方馆藏记录字段支持所列经审核声明。",
            "en": "Official collection record fields support the listed reviewed claims.",
        },
        "dataset_record": {
            "zh-Hans": "官方数据记录字段支持所列经审核声明。",
            "en": "Official dataset record fields support the listed reviewed claims.",
        },
        "curatorial_assessment": {
            "zh-Hans": "受限的审核整理把所列官方记录字段与经审核声明相连。",
            "en": "A bounded reviewed synthesis links the listed official record fields to reviewed claims.",
        },
    }
    summary = summaries.get(evidence_kind, summaries["curatorial_assessment"])
    return {
        "summary": summary,
        "reliability_note": {
            "zh-Hans": "可靠性仅限所列来源字段与声明，不延伸为历史因果、影响或价值判断。",
            "en": "Reliability is limited to the listed source fields and claims; it does not extend to historical causality, influence, or value judgments.",
        },
    }


def _public_claim_text(predicate: str) -> dict[str, str]:
    labels = {
        "birth_year": ("出生年份", "birth year"),
        "death_year": ("去世年份", "death year"),
        "identity_profile": ("身份确认", "identity"),
        "activity_scope": ("活动地点", "activity place"),
        "historical_period": ("历史时期", "historical period"),
        "artistic_tradition": ("艺术传统", "artistic tradition"),
        "official_object_record": ("官方作品记录", "official object record"),
        "uses_material": ("作品材料", "artwork material"),
        "uses_technique": ("作品技法", "artwork technique"),
        "shared_material": ("共同材料比较", "shared-material comparison"),
        "shared_subject": ("共同题材比较", "shared-subject comparison"),
        "shared_technique": ("共同技法比较", "shared-technique comparison"),
    }
    zh_label, en_label = labels.get(predicate, ("策展事实", "curatorial fact"))
    return {
        "zh-Hans": f"所列证据支持该公开记录的经审核{zh_label}声明。",
        "en": f"The listed evidence supports this public record's reviewed {en_label} claim.",
    }


def _relation_label(value: str) -> dict[str, str]:
    return {
        "shared_subject": {"zh-Hans": "共同题材", "en": "Shared subject"},
        "shared_material": {"zh-Hans": "共同材料", "en": "Shared material"},
        "shared_technique": {"zh-Hans": "共同技法", "en": "Shared technique"},
    }[value]


def _relationship_short_explanation(
    relationship: dict[str, Any],
    source_label: dict[str, str],
    target_label: dict[str, str],
    context_index: dict[str, dict[str, Any]],
) -> dict[str, str]:
    relation_label = _relation_label(relationship["relationship_type"])
    context_labels = _context_labels(set(relationship.get("context_entity_ids", [])), context_index)
    source_zh = source_label.get("zh-Hans", source_label.get("en", relationship["source_entity_id"]))
    target_zh = target_label.get("zh-Hans", target_label.get("en", relationship["target_entity_id"]))
    context_zh = "、".join(context_labels["zh-Hans"])
    source_explanation = relationship.get("educational_rationale") or relationship.get("curatorial_note") or {}
    english = str(source_explanation.get("en", "")).strip()
    if not english:
        english = (
            f"Compare selected works by {source_label.get('en', source_zh)} and "
            f"{target_label.get('en', target_zh)} through the reviewed {relation_label['en'].lower()} context "
            "without implying acquaintance, influence, instruction, transmission, or causality."
        )
    return {
        "zh-Hans": (
            f"并置{source_zh}与{target_zh}的所选作品，比较经审核的{relation_label['zh-Hans']}“{context_zh}”。"
            "这仅是元数据范围内的策展比较，不表示两人相识、影响、师承、传播或任何因果关系。"
        ),
        "en": english,
    }


def _context_labels(ids: set[str], index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    return {
        locale: [index[value]["labels"].get(locale, index[value]["labels"].get("en", value)) for value in sorted(ids) if value in index]
        for locale in ("zh-Hans", "en")
    }


def _context_ref(value: str, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"id": value, "labels": deepcopy(index[value]["labels"])}


def _label_for(value: str, index: dict[str, dict[str, Any]]) -> dict[str, str]:
    return deepcopy(index[value]["labels"]) if value in index else {"zh-Hans": value, "en": value}


def _normalize_search(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in normalized if not unicodedata.combining(character)).strip()


def _artifact_ref(files: list[dict[str, Any]], name: str) -> dict[str, str]:
    item = next(value for value in files if value["path"] == name)
    return {"path": name, "sha256": item["sha256"]}


def _release_content_hash(files: list[dict[str, Any]]) -> str:
    lines = [f"{item['path']}\0{item['sha256']}\0{item['bytes']}\n" for item in sorted(files, key=lambda value: value["path"])]
    return "sha256:" + hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _schema_key(path: str) -> str:
    return path.removeprefix("schemas/").removesuffix(".schema.json")


def _replace_owned_directory(staged: Path, output: Path) -> None:
    if output.exists():
        if not output.is_dir() or output.is_symlink():
            raise ValueError(f"Refusing to replace non-directory release path: {output}")
        staged_files = {
            path.relative_to(staged).as_posix(): path.read_bytes()
            for path in staged.rglob("*") if path.is_file()
        }
        output_files = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*") if path.is_file()
        }
        if staged_files == output_files:
            return
        raise ValueError(
            f"Refusing to overwrite immutable release {output}; use a new release ID and version"
        )
    staged.replace(output)


def _validation_result(root: Path, failures: list[dict[str, str]], counts: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": not failures,
        "release_root": root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else str(root),
        "release_id": RELEASE_ID,
        "counts": counts,
        "codes": sorted({item["code"] for item in failures}),
        "failures": failures,
    }


def _fail(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()
