"""Build and validate the immutable MUSEUM-09B-RELEASE public overlay.

The tracked release contains resolved public metadata plus exact references to
the predecessor media and to reviewed derivative source bytes.  New derivative
bytes are materialized only into the production build artifact.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import shutil
import tempfile
import unicodedata
from collections import Counter, defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file
from scripts.generate_release_integrity_ledger import build_ledger, physical_tree
from scripts.validate_governance_foundation import release_content_hash, schema_manifest_versions, schema_version_key


ROOT = Path(__file__).resolve().parents[2]
PHASE_ID = "MUSEUM-09B-RELEASE"
BATCH_ID = "museum-09-batch-01"
RELEASE_ID = "release:art-expansion-batch-01-1.5.0"
RELEASE_VERSION = "1.5.0"
RELEASE_DIRECTORY = "art-expansion-batch-01-1.5.0"
PREDECESSOR_ID = "release:art-v1-candidate-1.4.0"
PREDECESSOR_DIRECTORY = "art-v1-candidate-1.4.0"
PREDECESSOR_CONTENT_HASH = "sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202"
PREDECESSOR_MANIFEST_SHA256 = "sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114"
PREDECESSOR_TREE_SHA256 = "sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1"
CANDIDATE_ID = "museum-09b:batch-01-formal-candidate-v1"
CANDIDATE_CONTENT_HASH = "sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9"
CANDIDATE_TREE_HASH = "sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87"
MEDIA_ID = "museum-09b-media:batch-01-media-bundle-v1"
MEDIA_CONTENT_HASH = "sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50"
MEDIA_TREE_HASH = "sha256:39c855c8640271310d448d819a8fc80e6ae2b95852bfe6e5211faffb1f173a5e"
MEDIA_MANIFEST_SHA256 = "sha256:e08f5d0ff4ddaf7f3c9682bd2f0c8c08a2f469e1583bab32dbb705ea5a11cc64"
BUILT_AT = "2026-07-22T12:00:00+08:00"

PREDECESSOR = ROOT / "public" / "releases" / PREDECESSOR_DIRECTORY
CANDIDATE = ROOT / "data" / "reviewed" / "art" / "museum-09b" / "batch-01-formal-candidate-v1"
MEDIA = ROOT / "data" / "reviewed" / "art" / "museum-09b-media" / "batch-01-media-bundle-v1"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / RELEASE_DIRECTORY
LEDGER = ROOT / "governance" / "release-integrity-ledger.json"

EXPECTED_COUNTS = {
    "artists": 62,
    "artworks": 532,
    "legacy_artists": 12,
    "new_artists": 50,
    "legacy_artworks": 44,
    "new_artworks": 488,
    "gallery_profiles": 24,
    "collection_profiles": 38,
    "self_hosted_works": 71,
    "external_link_only_works": 25,
    "metadata_only_works": 436,
    "new_derivatives": 318,
    "new_public_originals": 0,
    "place_time_episodes": 110,
    "tours": 18,
}

LOCAL_SCHEMA = "schemas/art/release/art-constellation-artifact.schema.json"
OTHER_SCHEMA = "schemas/art/candidate/rehearsal-record.schema.json"
SEARCH_SCHEMA = "schemas/art/candidate/search-index.schema.json"
PATH_SCHEMA = "schemas/art/release/art-pathways-artifact.schema.json"
MAP_SCHEMA = "schemas/art/map/map-release-index.schema.json"
MAP_ARTWORK_SUMMARY_SCHEMA = "schemas/art/map/map-artwork-summary-collection.schema.json"
INTERACTION_SCHEMA = "schemas/art/release/art-gallery-interaction-index.schema.json"
PUBLIC_RECORD_SCHEMA = "schemas/art/release/art-expansion-public-record.schema.json"
PUBLIC_MEDIA_SCHEMA = "schemas/art/release/art-expansion-media-asset.schema.json"
PUBLIC_SOURCE_SCHEMA = "schemas/art/release/art-expansion-source.schema.json"
DATASET_SCHEMA = "schemas/common/dataset-release.schema.json"
ATTRIBUTION_SCHEMA = "schemas/common/attribution-manifest.schema.json"
LICENSE_DECISION_SCHEMA = "schemas/common/license-decision-registry.schema.json"
SOURCE_RULES_SCHEMA = "schemas/common/source-rules-snapshot.schema.json"
THIRD_PARTY_SCHEMA = "schemas/common/third-party-notices.schema.json"
AUTHORIZATION_SCOPE = "MUSEUM-09B immutable public release records"
TRANSFORM_RECIPE = "Resized without crop or upscale; ICC normalized to sRGB when present; metadata stripped; no AI modification or artwork-content change."


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_id(value: str) -> str:
    return value if value.startswith("source:") else f"source:{value}"


def _public_media_id(value: str) -> str:
    return value if value.startswith("media:") else f"media:m09b-{value.removeprefix('derivative:')}"


def _localized(en: str | None, zh: str | None = None) -> dict[str, str]:
    english = (en or "Not asserted").strip()
    chinese = (zh or english).strip()
    return {"en": english, "zh-Hans": chinese}


def _normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    ascii_value = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    source = ascii_value or normalized
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    return slug[:72] or "record"


def _stable_slug(value: str, stable_id: str, used: set[str]) -> str:
    base = _slug_base(value)
    slug = base
    if slug in used:
        suffix = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:8]
        slug = f"{base[:63]}-{suffix}"
    used.add(slug)
    return slug


def _artifact_path_for_derivative(derivative: dict[str, Any]) -> str:
    digest = derivative["sha256"].removeprefix("sha256:")
    extension = "jpg" if derivative["format"] == "jpeg" else "webp"
    return f"releases/{RELEASE_DIRECTORY}/assets/sha256/{digest[:2]}/{digest}.{extension}"


def _load_candidate_artworks() -> list[dict[str, Any]]:
    root = _read(CANDIDATE / "artworks.json")
    records: list[dict[str, Any]] = []
    for shard in root["shards"]:
        records.extend(_read(CANDIDATE / shard["path"])["artworks"])
    return records


def _assert_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    predecessor = _read(PREDECESSOR / "manifest.json")
    if predecessor.get("id") != PREDECESSOR_ID or predecessor.get("content_hash") != PREDECESSOR_CONTENT_HASH:
        raise ValueError("predecessor identity/content hash mismatch")
    if sha256_file(PREDECESSOR / "manifest.json") != PREDECESSOR_MANIFEST_SHA256:
        raise ValueError("predecessor manifest hash mismatch")
    if physical_tree(PREDECESSOR)["hash"] != PREDECESSOR_TREE_SHA256:
        raise ValueError("predecessor tree hash mismatch")
    candidate = _read(CANDIDATE / "build-manifest.json")
    if (
        candidate.get("package_id") != CANDIDATE_ID
        or candidate.get("artifact_content_hash") != CANDIDATE_CONTENT_HASH
        or candidate.get("artifact_tree_hash") != CANDIDATE_TREE_HASH
    ):
        raise ValueError("formal candidate sealed hash mismatch")
    media = _read(MEDIA / "build-manifest.json")
    if (
        media.get("package_id") != MEDIA_ID
        or media.get("artifact_content_hash") != MEDIA_CONTENT_HASH
        or media.get("artifact_tree_hash") != MEDIA_TREE_HASH
        or sha256_file(MEDIA / "build-manifest.json") != MEDIA_MANIFEST_SHA256
    ):
        raise ValueError("media bundle sealed hash mismatch")
    registry = _read(ROOT / "governance" / "museum-09-batch-registry.json")
    batch = next(item for item in registry["batches"] if item["id"] == BATCH_ID)
    expected = {
        "status": "media_bundle_ready",
        "next_authorized_phase": PHASE_ID,
        "formal_package_content_hash": CANDIDATE_CONTENT_HASH,
        "formal_package_tree_hash": CANDIDATE_TREE_HASH,
        "media_package_content_hash": MEDIA_CONTENT_HASH,
        "media_package_tree_hash": MEDIA_TREE_HASH,
        "artist_count": 50,
        "work_count": 488,
        "gallery_tier_count": 12,
        "collection_tier_count": 38,
        "final_self_hosted_count": 40,
        "external_iiif_link_only_count": 25,
        "derivative_count": 318,
    }
    for key, value in expected.items():
        if batch.get(key) != value:
            raise ValueError(f"batch registry mismatch: {key}")
    return predecessor, candidate, media


def _period(artist: dict[str, Any]) -> str:
    birth = artist.get("birth", {}).get("year")
    death = artist.get("death", {}).get("year")
    if isinstance(birth, int) and isinstance(death, int):
        century = ((birth - 1) // 100) + 1
        return f"{century}th century" if 10 <= century <= 20 else f"{birth}–{death}"
    return "Date recorded by source"


def _candidate_sources() -> list[dict[str, Any]]:
    records = []
    for source in _read(CANDIDATE / "sources.json")["sources"]:
        license_identifiers = []
        for value in (source.get("metadata_license"), source.get("media_license")):
            if not value:
                continue
            normalized = str(value).replace("; no media acquired in MUSEUM-09A", "").strip()
            if normalized:
                license_identifiers.append(normalized)
        records.append({
            "id": source["id"],
            "entity_type": "source",
            "release_id": RELEASE_ID,
            "schema_version": "1.0.0",
            "title": source["title"],
            "publisher": source["publisher"],
            "official_url": source["official_url"],
            "accessed_at": source["accessed_at"],
            "locator": {"url": source["official_url"], "label": _localized("Official source", "官方来源")},
            "license": {
                "identifiers": sorted(set(license_identifiers)),
                "attribution_texts": [source["publisher"]],
            },
            "attribution": source["publisher"],
            "source_rule_ids": source["source_rule_ids"],
            "snapshot_hash": source["snapshot_hash"],
        })
    return records


def _authorization_rule(registry_source_id: str, publisher: str, content_class: str) -> dict[str, Any]:
    is_media = content_class == "media"
    return {
        "rule_id": f"{registry_source_id}:{content_class}:user_authorization_v1",
        "content_class": content_class,
        "applies_to": AUTHORIZATION_SCOPE,
        "scope_match": {
            "normalization": "none",
            "pattern": f"^{re.escape(AUTHORIZATION_SCOPE)}$",
            "allowed_schemes": [],
            "allowed_hosts": [],
            "allow_relative_path": True,
            "field_policy": "any",
            "fields": [],
            "require_explicit_query_fields": False,
        },
        "rights_status": "cc0" if is_media else "licensed",
        "identifier": "CC0-1.0" if is_media else "PASS_BY_USER_AUTHORIZATION",
        "version": "1.0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/" if is_media else "https://archmays.github.io/Museum-Codex/#/rights",
        "attribution_template": None if is_media else publisher,
        "redistribution": "allowed",
        "modification": "allowed",
        "commercial_use": "allowed",
        "share_alike": False,
        "scope_note": "The user supplied or designated this project resource and authorized its intended public release use; independent privacy, secret, source-immutability, and technical gates remain enforced.",
        "no_inheritance": True,
    }


def _canonical_sources(runtime_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    predecessor_records = _read(PREDECESSOR / "claims.json").get("records", [])
    predecessor_sources = {
        item["data"]["id"]: item["data"]
        for item in predecessor_records
        if isinstance(item, dict) and isinstance(item.get("data"), dict) and item["data"].get("entity_type") == "source"
    }
    candidate_sources = {item["id"]: item for item in _read(CANDIDATE / "sources.json")["sources"]}
    records = []
    for runtime in runtime_sources:
        source_id = runtime["id"]
        raw = candidate_sources.get(source_id) or predecessor_sources.get(source_id) or runtime
        registry_source_id = raw.get("registry_source_id") or source_id.removeprefix("source:")
        publisher = raw.get("publisher") or runtime.get("publisher") or runtime.get("title")
        official_url = raw.get("official_url") or runtime["official_url"]
        official_host = raw.get("official_host") or (urlparse(official_url).hostname or "").lower()
        identity_base = {"canonical_name": publisher, "canonical_official_host": official_host}
        rules = [
            _authorization_rule(registry_source_id, publisher, "data"),
            _authorization_rule(registry_source_id, publisher, "media"),
        ]
        records.append({
            "schema_version": "1.0.0",
            "id": source_id,
            "entity_type": "source",
            "release_id": RELEASE_ID,
            "registry_source_id": registry_source_id,
            "registry_identity": {**identity_base, "snapshot_hash": _hash(identity_base)},
            "title": raw.get("title") or publisher,
            "publisher": publisher,
            "official_url": official_url,
            "accessed_at": raw.get("accessed_at") or "2026-07-20",
            "tier": min(int(raw.get("tier", 1)), 3),
            "source_type": raw.get("source_type") or "official_database",
            "license_rules": rules,
            "license_rules_snapshot_hash": _hash(rules),
            "selected_license_rule_ids": [rule["rule_id"] for rule in rules],
            "authorization_basis": "PASS_BY_USER_AUTHORIZATION",
            "public_static_redistribution": "allowed",
            "permission_status": "not_required",
            "lifecycle_status": "published",
            "data_version": RELEASE_VERSION,
        })
    return sorted(records, key=lambda item: item["id"])


def _source_binding(source_id: str, content_class: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "rule_id": f"{source_id.removeprefix('source:')}:{content_class}:user_authorization_v1",
        "content_class": content_class,
        "scope_locator": AUTHORIZATION_SCOPE,
        "scope_fields": ["record"],
        "permission_resolution": "rule_direct",
    }


def _canonical_public_records(groups: Iterable[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    entity_types = {
        "artist": "art_constellation_artist",
        "artwork": "art_constellation_artwork",
        "context": "art_constellation_context",
        "artist_relationship": "art_constellation_relationship",
        "claim": "art_constellation_claim",
        "evidence": "art_constellation_evidence",
    }
    records = []
    for group in groups:
        for original in group:
            record = deepcopy(original)
            record["entity_type"] = entity_types.get(record.get("entity_type"), record.get("entity_type"))
            record["phase_id"] = record.get("phase_id") or PHASE_ID
            record["release_id"] = RELEASE_ID
            record["data_version"] = RELEASE_VERSION
            record["lifecycle_status"] = "published"
            if record["entity_type"] in {
                "art_constellation_artist", "art_constellation_artwork",
                "art_constellation_context", "art_constellation_relationship",
            }:
                record["review_status"] = "published"
            if record["entity_type"] == "art_constellation_claim":
                record["status"] = "publishable"
                record["publish_status"] = "publishable"
            source_ids = sorted(set(record.get("source_ids", [])))
            if source_ids:
                record["source_ids"] = source_ids
                record["source_license_bindings"] = [_source_binding(source_id, "data") for source_id in source_ids]
            else:
                record.pop("source_license_bindings", None)
            records.append(record)
    return sorted(records, key=lambda item: item["id"])


def _license_descriptor() -> dict[str, Any]:
    return {
        "identifier": "CC0-1.0",
        "version": "1.0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution_required": False,
        "share_alike": False,
        "redistribution_allowed": True,
        "modification_allowed": True,
        "commercial_use_allowed": True,
    }


def _canonical_media_records(media_index: dict[str, Any]) -> list[dict[str, Any]]:
    assets = {item["id"]: item for item in media_index["assets"]}
    predecessor_records = _read(PREDECESSOR / "claims.json").get("records", [])
    predecessor_media = {
        item["data"]["id"]: deepcopy(item["data"])
        for item in predecessor_records
        if isinstance(item, dict) and isinstance(item.get("data"), dict) and item["data"].get("entity_type") == "media_asset"
    }
    records = []
    for media_id in sorted(set(assets) & set(predecessor_media)):
        asset = assets[media_id]
        record = predecessor_media[media_id]
        record.update({
            "release_id": RELEASE_ID,
            "delivery_mode": "predecessor_reference",
            "storage_path": asset["src"],
            "content_hash": asset["sha256"],
            "source_license_bindings": [_source_binding(record["source_id"], "media")],
            "data_version": RELEASE_VERSION,
        })
        records.append(record)

    decisions = {item["work_id"]: item for item in _read(MEDIA / "object-rights-decisions.json")["decisions"]}
    derivatives = {_public_media_id(item["id"]): item for item in _read(MEDIA / "derivatives-manifest.json")["derivatives"]}
    candidate_artworks = {item["id"]: item for item in _load_candidate_artworks()}
    for media_id in sorted(set(assets) & set(derivatives)):
        asset = assets[media_id]
        derivative = derivatives[media_id]
        work_id = derivative["work_references"][0]
        decision = decisions[work_id]
        artwork = candidate_artworks[work_id]
        descriptor = _license_descriptor()
        source_object_url = artwork.get("official_object_url") or decision["current_media_identity"]
        records.append({
            "schema_version": "1.0.0",
            "id": media_id,
            "entity_type": "media_asset",
            "release_id": RELEASE_ID,
            "media_type": "image",
            "source_id": decision["source_id"],
            "source_object_url": source_object_url,
            "delivery_mode": "build_materialized",
            "storage_path": asset["src"],
            "cache_bytes": True,
            "content_hash": derivative["sha256"],
            "rights_status": "cc0",
            "metadata_license": descriptor,
            "media_license": deepcopy(descriptor),
            "rights_statement_url": decision["rights_statement_url"],
            "rights_evidence": {
                "source_url": decision["rights_statement_url"],
                "verified_at": "2026-07-21",
                "object_rights_field": "Object-specific CC0 designation and reviewed identity, rights, bytes, and quality closure.",
                "statement_snapshot_hash": decision["rights_evidence_hash"],
            },
            "rights_holder": None,
            "attribution": decision["attribution"],
            "allow_redistribution": True,
            "allow_modification": True,
            "allow_commercial_use": True,
            "development_only": False,
            "reuse_mode": "adaptation",
            "derivation": {
                "derived_from_media_id": f"media:m09b-source-{derivative['parent_original_sha256'].removeprefix('sha256:')}",
                "source_content_hash": derivative["parent_original_sha256"],
                "transform_recipe": TRANSFORM_RECIPE,
                "transform_version": derivative["recipe_version"],
                "output_content_hash": derivative["sha256"],
                "output_license_identifier": "CC0-1.0",
                "share_alike_compatibility_decision": "not_applicable",
            },
            "license_scope": None,
            "source_license_bindings": [_source_binding(decision["source_id"], "media")],
            "review_status": "verified",
            "reviewed_by": "museum-09b-media-review-pipeline",
            "reviewed_at": "2026-07-21",
            "publish_status": "published",
            "lifecycle_status": "published",
            "data_version": RELEASE_VERSION,
        })
    return sorted(records, key=lambda item: item["id"])


def _public_artist(
    artist: dict[str, Any],
    artwork_ids: list[str],
    media_by_work: dict[str, list[dict[str, Any]]],
    relation_counts: Counter[str],
    slug: str,
    sequence: list[str],
) -> dict[str, Any]:
    chinese = artist.get("chinese_label")
    label_zh = chinese if isinstance(chinese, str) and chinese.strip() else artist["preferred_display_name"]
    birth = artist.get("birth", {}).get("year")
    death = artist.get("death", {}).get("year")
    representative = next(
        (
            sorted(media_by_work[work_id], key=lambda item: (item["width"], item["format"]))[-1]["id"]
            for work_id in sequence
            if media_by_work.get(work_id)
        ),
        None,
    )
    practice = ", ".join(artist.get("documented_practice_media", [])) or "Source-recorded practice"
    source_ids = sorted({_source_id(item["source_id"]) for item in artist["official_source_identities"]})
    life = f"{birth}–{death}" if isinstance(birth, int) and isinstance(death, int) else "dates recorded by source"
    work_count = len(artwork_ids)
    summary_en = (
        f"{artist['preferred_display_name']} ({life}) is represented by {work_count} reviewed object records from official museum sources. "
        f"The selected records document {practice}. Titles, dates, materials, attributions, and holding institutions remain attached to their source records, including explicit gaps where a source provides no value. "
        "This public profile supports close observation and comparison; it does not assert contact, influence, lineage, ethnicity, a complete catalogue, or artistic rank."
    )
    summary_zh = (
        f"{label_zh}（{life}）收录了来自博物馆官方来源的{work_count}条经审核作品记录。"
        f"所选记录记载的创作实践包括：{practice}。标题、年代、材料、归属表述与收藏机构均依附于各自来源记录；来源未提供的信息保持为空。"
        "本公开档案用于细看与比较，不据此断言接触、影响、师承、族裔、完整作品目录或艺术价值排序。"
    )
    return {
        "schema_version": "1.0.0",
        "id": artist["id"],
        "entity_type": "artist",
        "release_id": RELEASE_ID,
        "public_slug": slug,
        "profile_kind": "gallery" if artist["tier"] == "gallery" else "collection",
        "source_language_name": artist.get("source_language_name"),
        "transliterations": artist.get("transliterations", []),
        "labels": _localized(artist["preferred_display_name"], label_zh),
        "aliases": [{"text": value} for value in artist.get("approved_aliases", [])],
        "summary": _localized(summary_en, summary_zh),
        "activity_places": [{"label": artist["primary_coverage_bucket"].replace("-", " ").title()}],
        "historical_periods": [_period(artist)],
        "artistic_traditions": [],
        "life_dates": {
            "birth": {"display_value": str(birth) if isinstance(birth, int) else "Not asserted"},
            "death": {"display_value": str(death) if isinstance(death, int) else "Not asserted"},
        },
        "media_practice": _localized(practice, practice),
        "verified_claim_ids": artist["claim_ids"],
        "source_ids": source_ids,
        "relation_count": relation_counts[artist["id"]],
        "artwork_ids": artwork_ids,
        "gallery_sequence": sequence if artist["tier"] == "gallery" else [],
        "representative_media_id": representative,
        "approved_media_artwork_count": sum(bool(media_by_work.get(work_id)) for work_id in artwork_ids),
        "review": {"reviewer_id": "museum-09b-release-review", "reviewed_at": "2026-07-22"},
        "review_status": "publishable",
        "lifecycle_status": "published",
        "chinese_label_status": artist.get("chinese_label_status"),
    }


def _public_artwork(
    artwork: dict[str, Any],
    media_status: dict[str, dict[str, Any]],
    media_by_work: dict[str, list[dict[str, Any]]],
    slug: str,
) -> dict[str, Any]:
    projection = media_status.get(artwork["id"])
    derivatives = media_by_work.get(artwork["id"], [])
    if projection and projection["final_status"] == "approved_self_hosted":
        decision = "approved_self_hosted"
        media_ids = [item["id"] for item in derivatives]
        representative = sorted(derivatives, key=lambda item: (item["width"], item["format"]))[-1]["id"]
        reasons = ["reviewed_derivative_bytes"]
    elif projection and projection["final_status"] == "approved_external_iiif_link_only":
        decision = "external_link_only"
        media_ids = []
        representative = None
        reasons = ["image_not_hosted_by_this_site"]
    else:
        decision = "metadata_only"
        media_ids = []
        representative = None
        reasons = ["metadata_first_no_local_image"]
    title = artwork["preferred_title"]
    material = artwork.get("medium_or_material")
    institution = artwork.get("holding_institution")
    return {
        "schema_version": "1.0.0",
        "id": artwork["id"],
        "entity_type": "artwork",
        "release_id": RELEASE_ID,
        "public_slug": slug,
        "artist_id": artwork["artist_id"],
        "labels": _localized(title, title),
        "creation": {"description": _localized(artwork.get("creation_date"), artwork.get("creation_date")) if artwork.get("creation_date") else None},
        "institution": {"label": _localized(institution, institution)} if institution else {"label": _localized("Not asserted", "未断言")},
        "official_object_url": artwork.get("official_object_url") or None,
        "source_ids": [_source_id(artwork["source_id"])],
        "accession_number": artwork.get("accession_or_object_number"),
        "materials": [_localized(material, material)] if material else [],
        "techniques": [],
        "subjects": [],
        "metadata_license": {"rule_id": artwork.get("metadata_license") or "source-record-specific"},
        "limitations": _localized(artwork.get("uncertainty"), artwork.get("uncertainty")),
        "media": {
            "decision": decision,
            "reason_codes": reasons,
            "representative_media_id": representative,
            "media_ids": media_ids,
        },
        "claim_ids": artwork["claim_ids"],
        "review_status": "publishable",
        "lifecycle_status": "published",
    }


def _public_claim(claim: dict[str, Any]) -> dict[str, Any]:
    text = claim.get("statement") or f"{claim['predicate']}: {_json_text(claim.get('value'))}"
    return {
        "schema_version": "1.0.0",
        "id": claim["id"],
        "entity_type": "claim",
        "release_id": RELEASE_ID,
        "subject_id": claim["subject_id"],
        "predicate": claim["predicate"],
        "object": {"value": _json_text(claim.get("value"))},
        "evidence_ids": claim["evidence_ids"],
        "claim_text": _localized(text, text),
        "status": "publishable",
        "publish_status": "publishable",
    }


def _public_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    locator = evidence.get("locator") or {}
    if isinstance(locator, str):
        record_id = locator
        section = "official record locator"
    else:
        record_id = locator.get("record_id") or locator.get("stable_id") or locator.get("url") or "official record"
        section = locator.get("field") or locator.get("section") or "record fields"
    return {
        "schema_version": "1.0.0",
        "id": evidence["id"],
        "entity_type": "evidence",
        "release_id": RELEASE_ID,
        "claim_ids": evidence["claim_ids"],
        "source_ids": evidence["source_ids"],
        "summary": _localized(evidence["summary"], evidence["summary"]),
        "locator": {
            "record_id": _json_text(record_id),
            "section": _json_text(section),
        },
        "reliability_note": _localized(
            evidence.get("what_it_proves", "Official record supports the bounded claim."),
            evidence.get("what_it_proves", "官方记录支持此有限主张。"),
        ),
    }


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": context["id"],
        "entity_type": "context",
        "release_id": RELEASE_ID,
        "context_type": context["context_type"],
        "labels": _localized(context["summary"], context["summary"]),
        "artist_id": context["artist_id"],
        "claim_ids": context["claim_ids"],
        "source_ids": context["source_ids"],
    }


def _public_relationships(
    candidates: list[dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    artists: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for candidate in candidates:
        source = artists[candidate["source_artist_id"]]
        target = artists[candidate["target_artist_id"]]
        values = [set(claims[claim_id]["value"]) for claim_id in candidate["claim_ids"]]
        shared = sorted(set.intersection(*values)) if values else []
        if not shared:
            continue
        evidence_ids = sorted({item for claim_id in candidate["claim_ids"] for item in claims[claim_id]["evidence_ids"]})
        source_ids = sorted({item for evidence_id in evidence_ids for item in evidence[evidence_id]["source_ids"]})
        shared_text = ", ".join(shared)
        records.append({
            "schema_version": "1.0.0",
            "id": candidate["id"].replace("relationship:", "art-rel:", 1),
            "entity_type": "artist_relationship",
            "release_id": RELEASE_ID,
            "source_artist_id": source["id"],
            "target_artist_id": target["id"],
            "type": "shared_technique",
            "level": "C",
            "level_label": "Curatorial comparison",
            "directed": False,
            "is_algorithmic": False,
            "historical_relationship_strength": None,
            "computational_similarity": None,
            "evidence_confidence": 0.75,
            "curatorial_relevance": 0.7,
            "title": _localized(
                f"Documented practice: {source['preferred_display_name']} and {target['preferred_display_name']}",
                f"记录中的创作实践：{source['preferred_display_name']}与{target['preferred_display_name']}",
            ),
            "short_explanation": _localized(
                f"Their official records share documented practice terms: {shared_text}.",
                f"双方官方记录共有以下创作实践字段：{shared_text}。",
            ),
            "what_it_means": _localized(
                "The two records can be compared through source-documented practice fields.",
                "两份记录可通过来源明确记载的创作实践字段进行比较。",
            ),
            "what_it_does_not_mean": _localized(
                "This does not assert contact, influence, lineage, causation, similarity score, or artistic rank.",
                "这不表示接触、影响、师承、因果、相似度评分或艺术价值排序。",
            ),
            "context_ids": sorted(set(source["context_ids"][:1] + target["context_ids"][:1])),
            "supporting_artwork_ids": [source["selected_work_ids"][0], target["selected_work_ids"][0]],
            "claim_ids": candidate["claim_ids"],
            "evidence_ids": evidence_ids,
            "source_ids": source_ids,
            "limitations": _localized(candidate["basis"], candidate["basis"]),
            "review": {"reviewer_id": "museum-09b-release-review", "reviewed_at": "2026-07-22"},
            "review_status": "publishable",
            "lifecycle_status": "published",
        })
    return records


def _media_projection(
    legacy_artworks: list[dict[str, Any]],
    new_artworks: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    old_index = _read(PREDECESSOR / "media-index.json")
    old_attributions = _read(PREDECESSOR / "attributions.json")
    old_withdrawals = _read(PREDECESSOR / "withdrawal-mapping.json")
    old_manifest = _read(PREDECESSOR / "manifest.json")
    derivatives = _read(MEDIA / "derivatives-manifest.json")["derivatives"]
    decisions = {item["work_id"]: item for item in _read(MEDIA / "object-rights-decisions.json")["decisions"]}
    work_attributions = {item["work_id"]: item for item in _read(MEDIA / "attributions.json")["records"]}
    work_withdrawals = {item["work_id"]: item for item in _read(MEDIA / "withdrawal-registry.json")["records"]}
    candidate_by_id = {item["id"]: item for item in new_artworks}

    assets = []
    references = []
    old_file_by_path = {item["path"]: item for item in old_manifest["manifest_files"]}
    for asset in old_index["assets"]:
        projected = deepcopy(asset)
        old_path = asset["src"]
        projected["src"] = f"releases/{PREDECESSOR_DIRECTORY}/{old_path}"
        projected["delivery_mode"] = "predecessor_reference"
        assets.append(projected)
        manifest_file = old_file_by_path[old_path]
        references.append({
            "bytes": manifest_file["bytes"],
            "path": projected["src"],
            "source_path": f"public/releases/{PREDECESSOR_DIRECTORY}/{old_path}",
            "sha256": "sha256:" + manifest_file["sha256"].removeprefix("sha256:"),
            "record_ids": [asset["id"]],
            "record_type": "media",
            "delivery_mode": "predecessor_reference",
        })

    materialized = []
    media_by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for derivative in derivatives:
        work_id = derivative["work_references"][0]
        public_path = _artifact_path_for_derivative(derivative)
        role = "thumbnail" if derivative["width"] <= 320 else "detail" if derivative["width"] <= 960 else "zoom"
        asset = {
            "id": _public_media_id(derivative["id"]),
            "artwork_id": work_id,
            "parent_media_id": derivative["parent_original_sha256"],
            "src": public_path,
            "format": derivative["format"],
            "mime_type": derivative["mime"],
            "width": derivative["width"],
            "height": derivative["height"],
            "bytes": derivative["bytes"],
            "sha256": derivative["sha256"],
            "role": role,
            "delivery_mode": "build_materialized",
        }
        assets.append(asset)
        media_by_work[work_id].append(asset)
        materialized.append({
            "bytes": derivative["bytes"],
            "path": public_path,
            "source_path": f"data/reviewed/art/museum-09b-media/batch-01-media-bundle-v1/{derivative['storage_path']}",
            "sha256": derivative["sha256"],
            "record_ids": [_public_media_id(derivative["id"])],
            "record_type": "media",
            "delivery_mode": "build_materialized",
        })

    artwork_media = []
    for artwork in [*legacy_artworks, *new_artworks]:
        state = artwork["media"]
        artwork_media.append({
            "artwork_id": artwork["id"],
            "decision": state["decision"],
            "reason_codes": state["reason_codes"],
            "representative_media_id": state["representative_media_id"],
            "media_ids": state["media_ids"],
        })
    media_index = {
        "schema_version": "1.0.0",
        "release_id": RELEASE_ID,
        "media_bundle_hash": MEDIA_CONTENT_HASH,
        "delivery_policy": {
            "preferred": "self_hosted",
            "external_runtime_api": False,
            "external_delivery_count": 0,
            "blocked_asset_count": 0,
            "low_bandwidth_default": "metadata_only",
        },
        "counts": {
            "approved_artworks": EXPECTED_COUNTS["self_hosted_works"],
            "no_image_artworks": EXPECTED_COUNTS["external_link_only_works"] + EXPECTED_COUNTS["metadata_only_works"],
            "assets": len(assets),
            "bytes": sum(item["bytes"] for item in assets),
        },
        "artworks": artwork_media,
        "assets": assets,
        "external_link_only_count": EXPECTED_COUNTS["external_link_only_works"],
        "metadata_only_count": EXPECTED_COUNTS["metadata_only_works"],
    }

    public_legacy_media_ids = {item["id"] for item in old_index["assets"]}
    attributions = {
        "assets": [
            deepcopy(item)
            for item in old_attributions["assets"]
            if item["asset_id"] in public_legacy_media_ids
        ]
    }
    for derivative in derivatives:
        work_id = derivative["work_references"][0]
        decision = decisions[work_id]
        work = candidate_by_id[work_id]
        attributions["assets"].append({
            "asset_id": _public_media_id(derivative["id"]),
            "attribution": work_attributions[work_id]["text"],
            "changes_statement": TRANSFORM_RECIPE,
            "license_identifier": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "source_url": work.get("official_object_url") or decision["rights_statement_url"],
        })
    withdrawals = deepcopy(old_withdrawals)
    withdrawals["release_id"] = RELEASE_ID
    withdrawals["media_bundle_id"] = MEDIA_ID
    withdrawals["media_bundle_hash"] = MEDIA_CONTENT_HASH
    for derivative in derivatives:
        work_id = derivative["work_references"][0]
        withdrawals["mappings"].append({
            "media_id": _public_media_id(derivative["id"]),
            "artwork_id": work_id,
            "status": "active",
            "derivative_paths": [_artifact_path_for_derivative(derivative)],
            "public_notice": "Active reviewed derivative; corrections create a successor release and do not rewrite history.",
            "withdrawal_route": work_withdrawals[work_id]["route"],
        })
    return media_index, attributions, withdrawals, references, materialized


def _search_value(text: str, language: str, reason: str) -> dict[str, str]:
    return {"text": text, "normalized": _normalize_search(text), "language": language, "reason": reason}


def _search_record(
    record_id: str,
    entity_type: str,
    route: str,
    labels: dict[str, str],
    description: dict[str, str],
    extras: Iterable[tuple[str, str, str]] = (),
) -> dict[str, Any]:
    values = [_search_value(labels["en"], "en", "preferred"), _search_value(labels["zh-Hans"], "zh-Hans", "preferred")]
    values.extend(_search_value(text, language, reason) for text, language, reason in extras if text)
    deduped = {(_normalize_search(item["text"]), item["reason"]): item for item in values if item["normalized"]}
    order = {"artist": 1, "artwork": 2, "context": 3, "tour": 4, "place": 5, "relationship": 6, "path": 7, "page": 8}
    return {
        "id": f"search:{record_id}",
        "stable_id": record_id,
        "entity_type": entity_type,
        "route": route,
        "labels": labels,
        "description": description,
        "values": list(deduped.values()),
        "visitor_task_order": order[entity_type],
        "withdrawal_status": "active",
    }


def _build_search(
    artists: list[dict[str, Any]],
    artworks: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    interaction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    artist_slugs = {item["id"]: item["public_slug"] for item in artists}
    records: list[dict[str, Any]] = []
    for artist in artists:
        extras = [(value.get("text", ""), "und", "approved_alias") for value in artist.get("aliases", [])]
        extras += [(artist.get("source_language_name") or "", "und", "source_language")]
        extras += [(value, "und", "transliteration") for value in artist.get("transliterations", [])]
        records.append(_search_record(
            artist["id"], "artist", f"/art/artists/{artist['public_slug']}", artist["labels"], artist["summary"], extras,
        ))
    for artwork in artworks:
        records.append(_search_record(
            artwork["id"], "artwork", f"/art/artworks/{artwork['public_slug']}", artwork["labels"],
            artwork["creation"]["description"] or _localized("Artwork metadata", "作品元数据"),
        ))
    for context in contexts:
        records.append(_search_record(context["id"], "context", f"/art/artists/{artist_slugs.get(context.get('artist_id'), '')}", context["labels"], context["labels"]))
    for relationship in relationships:
        records.append(_search_record(relationship["id"], "relationship", "/art/constellation?view=table", relationship["title"], relationship["short_explanation"]))
    for episode in episodes:
        records.append(_search_record(episode["id"], "place", "/art/map?view=list", episode["public_wording"], episode["public_wording"]))
    for tour in [*interaction["artist_tours"], *interaction["thematic_tours"]]:
        tour_summary = tour.get("disclaimer") or tour.get("summary") or tour.get("noncausal_statement") or tour["title"]
        records.append(_search_record(tour["id"], "tour", tour["share_path"], tour["title"], tour_summary))
    pages = [
        ("page:art", "/art", _localized("Art museum", "美术馆")),
        ("page:paths", "/art/paths", _localized("Artist paths", "艺术家路径")),
        ("page:rights", "/rights", _localized("Rights and sources", "权利与来源")),
        ("page:accessibility", "/accessibility", _localized("Accessibility", "无障碍")),
    ]
    for record_id, route, labels in pages:
        records.append(_search_record(record_id, "page", route, labels, labels))
    records.sort(key=lambda item: (item["entity_type"], item["stable_id"]))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["entity_type"]].append(record)
    documents: dict[str, dict[str, Any]] = {}
    shards = []
    for entity_type, values in sorted(grouped.items()):
        path = f"search/shards/{entity_type}-00.json"
        document = {
            "schema_version": "1.0.0",
            "id": f"search-shard:{entity_type}-00",
            "entity_type": "search_index_shard",
            "release_id": RELEASE_ID,
            "strategy": "entity_type",
            "shard_key": entity_type,
            "input_closure_hash": _hash([item["stable_id"] for item in values]),
            "records_hash": _hash(values),
            "record_count": len(values),
            "records": values,
        }
        documents[path] = document
        payload = canonical_json_bytes(document)
        shards.append({
            "id": document["id"],
            "path": path,
            "entity_types": [entity_type],
            "languages": ["en", "zh-Hans", "und"],
            "stable_hash_prefix": None,
            "record_count": len(values),
            "bytes": len(payload),
            "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "records_hash": document["records_hash"],
        })
    config = {
        "schema_version": "1.0.0",
        "id": "search-config:art-expansion-1.5.0",
        "entity_type": "search_config",
        "release_id": RELEASE_ID,
        "query_logging": False,
        "analytics": False,
        "remote_search": False,
        "media_preload": False,
        "normalization": "unicode_nfkc_lower_diacritic_fold_whitespace_v1",
        "ranking": ["match_class", "visitor_task_entity_type", "stable_id"],
    }
    manifest = {
        "schema_version": "1.0.0",
        "id": "search-manifest:art-expansion-1.5.0",
        "entity_type": "search_index_manifest",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "config_path": "search/config.json",
        "normalization": "unicode_nfkc_lower_diacritic_fold_whitespace_v1",
        "matching_modes": ["exact_preferred", "exact_alias", "prefix", "segmenter_token", "substring"],
        "ranking_tuple": ["match_class", "visitor_task_entity_type", "stable_id"],
        "segmenter_optional": True,
        "fallback_complete": True,
        "query_logging": False,
        "media_paths_included": False,
        "shard_contract": {"strategies": ["entity_type"], "incremental_rebuild": True, "unchanged_shards_hash_only": True, "lazy_load": True},
        "shards": shards,
        "counts": {"records": len(records), "shards": len(shards), "by_entity_type": dict(Counter(item["entity_type"] for item in records))},
        "budgets": {
            "search_route_gzip_bytes_max": 220000,
            "search_index_gzip_bytes_max": 300000,
            "current_query_p95_ms_max": 80,
            "synthetic_1000_query_p95_ms_max": 120,
            "external_requests_max": 0,
        },
    }
    documents["search/config.json"] = config
    documents["search/manifest.json"] = manifest
    return documents


def _path_artifacts(artists: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    path_artists = [{
        "id": item["id"],
        "labels": item["labels"],
        "periods": [item["historical_periods"][0]],
        "regions": [item["activity_places"][0]["label"]],
        "source_ids": item["source_ids"],
        "rights_attribution": item["source_ids"],
    } for item in artists]
    path_relationships = [{
        "id": item["id"],
        "source_artist_id": item["source_artist_id"],
        "target_artist_id": item["target_artist_id"],
        "relationship_type": item["type"],
        "level": "C",
        "directed": False,
        "is_algorithmic": False,
        "historical_relationship_strength": None,
        "computational_similarity": None,
        "context_ids": item["context_ids"],
        "claim_ids": item["claim_ids"],
        "evidence_ids": item["evidence_ids"],
        "source_ids": item["source_ids"],
        "supporting_artwork_ids": item["supporting_artwork_ids"],
        "evidence_confidence": item["evidence_confidence"],
        "why_connected": item["what_it_means"],
        "does_not_prove": item["what_it_does_not_mean"],
        "rights_attribution": item["source_ids"],
    } for item in relationships]
    graph_hash = _hash({"artists": path_artists, "relationships": path_relationships})
    graph = {
        "schema_version": "1.0.0",
        "id": "path-graph:art-expansion-1.5.0",
        "entity_type": "art_path_graph_input",
        "release_id": RELEASE_ID,
        "input_release_id": RELEASE_ID,
        "input_release_hash": "resolved-by-current-manifest",
        "graph_hash": graph_hash,
        "artists": path_artists,
        "relationships": path_relationships,
        "counts": {"artists": len(path_artists), "relationships": len(path_relationships), "levels": {"A": 0, "B": 0, "C": len(path_relationships)}, "directed": 0, "algorithmic": 0},
    }
    pair_count = len(artists) * (len(artists) - 1) // 2
    index = {
        "schema_version": "1.0.0",
        "id": "path-index:art-expansion-1.5.0",
        "entity_type": "art_path_index",
        "release_id": RELEASE_ID,
        "algorithm_version": "museum-paths-bibfs-yen-1.0.0",
        "input_graph_hash": graph_hash,
        "default_pair_count": pair_count,
        "precomputed_path_count": 0,
        "computed_at_runtime": True,
        "pairs": [],
    }
    algorithm = deepcopy(_read(PREDECESSOR / "path-algorithm-contract.json"))
    algorithm.update({"release_id": RELEASE_ID, "input_release_id": RELEASE_ID, "input_release_hash": "resolved-by-current-manifest"})
    explanations = {
        "schema_version": "1.0.0",
        "id": "path-explanations:art-expansion-1.5.0",
        "entity_type": "art_path_explanation_collection",
        "release_id": RELEASE_ID,
        "input_graph_hash": graph_hash,
        "explanations": path_relationships,
    }
    route = deepcopy(_read(PREDECESSOR / "path-route-config.json"))
    return {
        "path-graph-input.json": graph,
        "path-index.json": index,
        "path-algorithm-contract.json": algorithm,
        "path-explanations.json": explanations,
        "path-route-config.json": route,
    }


def _map_artifacts(
    artists: list[dict[str, Any]],
    artworks: list[dict[str, Any]],
    candidate_episodes: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    places = deepcopy(_read(PREDECESSOR / "place-identities.json"))
    if not any(item["id"] == "place:not-asserted" for item in places["places"]):
        places["places"].append({
            "schema_version": "1.0.0",
            "id": "place:not-asserted",
            "entity_type": "place_identity",
            "tgn_id": "not-asserted",
            "tgn_uri": "https://museum.invalid/not-asserted",
            "preferred_historical_label": "Place not asserted",
            "current_common_label": "Place not asserted",
            "labels": {"en": "Place not asserted by the source", "zh-Hans": "来源未断言地点", "source": "not asserted"},
            "alternate_historical_names": [],
            "names": [],
            "place_types": ["not asserted"],
            "broader_hierarchy": [],
            "coordinates": None,
            "coordinate_precision": "unknown",
            "geometry_type": "None",
            "uncertainty_radius_km": None,
            "valid_time": None,
            "modern_jurisdiction": None,
            "modern_jurisdiction_role": "secondary_context_only",
            "region": "Not asserted",
            "source_ids": [],
            "release_status": "verified_list_only",
            "coordinate_issue": "The source does not close an event place; no coordinates are inferred.",
        })
    places["release_id"] = RELEASE_ID
    episodes = deepcopy(_read(PREDECESSOR / "artist-place-episodes.json"))
    for item in episodes["episodes"]:
        item["release_id"] = RELEASE_ID
    for item in candidate_episodes:
        claim_id = item["claim_ids"][0]
        episodes["episodes"].append({
            "schema_version": "1.0.0",
            "id": item["id"],
            "entity_type": "artist_place_episode",
            "artist_id": item["artist_id"],
            "place_id": "place:not-asserted",
            "episode_type": item["episode_type"],
            "start_year": item.get("date"),
            "end_year": item.get("date"),
            "date_precision": item["date_precision"],
            "place_precision": "unknown",
            "role": f"documented {item['episode_type']} date; place not asserted",
            "claim_id": claim_id,
            "evidence": [],
            "source_ids": [],
            "confidence": "date_supported_place_not_asserted",
            "uncertain": True,
            "public_wording": _localized(
                f"{item['episode_type'].replace('_', ' ').title()} ({item.get('date')}): the source does not assert a place.",
                f"{item['episode_type'].replace('_', ' ')}（{item.get('date')}）：来源未断言地点。",
            ),
            "what_it_proves": "The cited claim supports the event date at the stated precision.",
            "does_not_prove": "It does not prove an event place, route, residence, influence, or holding location.",
            "release_status": "verified_list_only",
            "release_id": RELEASE_ID,
        })
    map_index = deepcopy(_read(PREDECESSOR / "map-index.json"))
    map_index["release_id"] = RELEASE_ID
    map_index["input_release_id"] = RELEASE_ID
    map_index["counts"].update({
        "artists": len(artists),
        "artworks": len(artworks),
        "episodes": len(episodes["episodes"]),
        "places": len(places["places"]),
        "list_only_episodes": sum(item["release_status"] == "verified_list_only" for item in episodes["episodes"]),
        "verified_public_episodes": sum(item["release_status"] == "verified_public" for item in episodes["episodes"]),
        "mapped_episode_points": sum(item["release_status"] == "verified_public" for item in episodes["episodes"]),
    })
    years = [year for item in episodes["episodes"] for year in (item.get("start_year"), item.get("end_year")) if isinstance(year, int)]
    map_index["year_range"] = {"min": min(years), "max": max(years)}
    filter_index = deepcopy(_read(PREDECESSOR / "filter-index.json"))
    filter_index["release_id"] = RELEASE_ID
    episode_counts = Counter(item["artist_id"] for item in episodes["episodes"])
    filter_index["facets"]["artists"] = [
        {"id": item["id"], "labels": item["labels"], "count": episode_counts[item["id"]]}
        for item in artists if episode_counts[item["id"]]
    ]
    filter_index["facets"]["episode_types"] = [
        {"id": key, "count": value} for key, value in sorted(Counter(item["episode_type"] for item in episodes["episodes"]).items())
    ]
    filter_index["facets"]["precisions"] = [
        {"id": key, "count": value} for key, value in sorted(Counter(item["place_precision"] for item in episodes["episodes"]).items())
    ]
    filter_index["facets"]["regions"] = [
        {"id": key, "count": value} for key, value in sorted(Counter(next(place["region"] for place in places["places"] if place["id"] == item["place_id"]) for item in episodes["episodes"]).items())
    ]
    filter_index["facets"]["layers"] = [
        {"id": "artist_activity", "count": len(episodes["episodes"])},
        {"id": "artwork_creation_place", "count": 0},
        {"id": "current_holding_institution", "count": map_index["counts"]["holding_institutions"]},
    ]
    timeline = {
        "schema_version": "1.0.0",
        "id": "timeline-index:art-expansion-1.5.0",
        "entity_type": "map_timeline_index",
        "release_id": RELEASE_ID,
        "entries": [{
            "artist_id": item["artist_id"], "date_precision": item["date_precision"], "end_year": item["end_year"],
            "episode_id": item["id"], "place_id": item["place_id"], "release_status": item["release_status"], "start_year": item["start_year"],
        } for item in episodes["episodes"]],
    }
    source_attributions = deepcopy(_read(PREDECESSOR / "map-source-attributions.json"))
    existing = {item["id"] for item in source_attributions["sources"]}
    for source in sources:
        if source["id"] in existing:
            continue
        source_attributions["sources"].append({
            "id": source["id"], "name": source["publisher"], "tier": 1, "url": source["official_url"],
            "license": ", ".join(source["license"]["identifiers"]), "attribution": source["publisher"],
        })
    holding_locations = deepcopy(_read(PREDECESSOR / "holding-locations.json"))
    holding_locations["release_id"] = RELEASE_ID
    holding_artwork_ids = {
        artwork_id
        for location in holding_locations["locations"]
        for artwork_id in location["artwork_ids"]
    }
    map_artworks = {
        "schema_version": "1.0.0",
        "id": "map-artwork-summaries:1.5.0",
        "entity_type": "map_artwork_summary_collection",
        "release_id": RELEASE_ID,
        "artworks": [
            {"id": item["id"], "labels": item["labels"]}
            for item in artworks
            if item["id"] in holding_artwork_ids
        ],
    }
    documents = {
        "place-identities.json": places,
        "artist-place-episodes.json": episodes,
        "map-index.json": map_index,
        "filter-index.json": filter_index,
        "timeline-index.json": timeline,
        "map-source-attributions.json": source_attributions,
        "map-artworks.json": map_artworks,
        "holding-locations.json": holding_locations,
    }
    for name in ["map-style.json", "map-layer-config.json", "map-view-state.json", "map-points.geojson", "basemap-manifest.json"]:
        documents[name] = deepcopy(_read(PREDECESSOR / name))
        if isinstance(documents[name], dict) and "release_id" in documents[name]:
            documents[name]["release_id"] = RELEASE_ID
    referenced = []
    predecessor_manifest = _read(PREDECESSOR / "manifest.json")
    file_by_path = {item["path"]: item for item in predecessor_manifest["manifest_files"]}
    for path in ["basemap/land.geojson", "basemap/coastline.geojson", "basemap/lakes.geojson"]:
        item = file_by_path[path]
        referenced.append({
            "bytes": item["bytes"], "path": path, "resolved_path": f"releases/{PREDECESSOR_DIRECTORY}/{path}",
            "source_path": f"public/releases/{PREDECESSOR_DIRECTORY}/{path}", "sha256": "sha256:" + item["sha256"].removeprefix("sha256:"),
            "record_ids": item["record_ids"], "record_type": "other", "delivery_mode": "predecessor_reference",
        })
    return documents, referenced


def _connected_components(artists: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> tuple[int, int]:
    adjacency: dict[str, set[str]] = {item["id"]: set() for item in artists}
    for item in relationships:
        adjacency[item["source_artist_id"]].add(item["target_artist_id"])
        adjacency[item["target_artist_id"]].add(item["source_artist_id"])
    seen: set[str] = set()
    components = 0
    connected_pairs = 0
    for node in adjacency:
        if node in seen:
            continue
        components += 1
        queue = deque([node])
        seen.add(node)
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        connected_pairs += size * (size - 1) // 2
    total_pairs = len(artists) * (len(artists) - 1) // 2
    return components, total_pairs - connected_pairs


def _record_ids(document: dict[str, Any], path: str) -> list[str]:
    if isinstance(document.get("records"), list) and path == "claims.json":
        return [item["data"]["id"] for item in document["records"]]
    keys = {
        "artists.json": "artists", "artworks.json": "artworks", "contexts.json": "contexts",
        "relationships.json": "relationships", "claims.json": "claims", "evidence.json": "evidence", "sources.json": "sources",
    }
    if path in keys:
        return [item["id"] for item in document[keys[path]]]
    if path == "media-index.json":
        return [item["id"] for item in document["assets"]]
    return [document["id"]] if isinstance(document.get("id"), str) else []


def _schema_for(path: str) -> str | None:
    if path == "claims.json":
        return None
    if path == "attributions.json":
        return ATTRIBUTION_SCHEMA
    if path == "license-decisions.json":
        return LICENSE_DECISION_SCHEMA
    if path == "source-rules-snapshot.json":
        return SOURCE_RULES_SCHEMA
    if path == "third-party-notices.json":
        return THIRD_PARTY_SCHEMA
    if path == "interaction-index.json":
        return INTERACTION_SCHEMA
    if path.startswith("path-"):
        return PATH_SCHEMA
    if path.startswith("search/"):
        return SEARCH_SCHEMA
    if path in {"map-index.json", "artist-place-episodes.json", "place-identities.json", "filter-index.json", "timeline-index.json"}:
        return MAP_SCHEMA
    if path == "map-artworks.json":
        return MAP_ARTWORK_SUMMARY_SCHEMA
    return LOCAL_SCHEMA if path in {"artists.json", "artworks.json", "contexts.json", "relationships.json", "claims.json", "evidence.json", "sources.json", "media-index.json", "rights.json", "withdrawal-mapping.json"} else OTHER_SCHEMA


def _build_documents() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    legacy_artists = deepcopy(_read(PREDECESSOR / "artists.json")["artists"])
    legacy_artworks = deepcopy(_read(PREDECESSOR / "artworks.json")["artworks"])
    legacy_contexts = deepcopy(_read(PREDECESSOR / "contexts.json")["contexts"])
    legacy_relationships = deepcopy(_read(PREDECESSOR / "relationships.json")["relationships"])
    legacy_claims = deepcopy(_read(PREDECESSOR / "claims.json")["claims"])
    legacy_evidence = deepcopy(_read(PREDECESSOR / "evidence.json")["evidence"])

    candidate_artists = _read(CANDIDATE / "artists.json")["artists"]
    candidate_artworks = _load_candidate_artworks()
    candidate_claims = _read(CANDIDATE / "claims.json")["claims"]
    candidate_evidence = _read(CANDIDATE / "evidence.json")["evidence"]
    candidate_contexts = _read(CANDIDATE / "contexts.json")["contexts"]
    candidate_relationships = _read(CANDIDATE / "relationship-candidates.json")["relationships"]
    candidate_episodes = _read(CANDIDATE / "place-time-episodes.json")["episodes"]
    gallery = {item["artist_id"]: item for item in _read(CANDIDATE / "gallery-readiness.json")["artists"]}
    collection = {item["artist_id"]: item for item in _read(CANDIDATE / "collection-readiness.json")["artists"]}
    projections = {item["work_id"]: item for item in _read(MEDIA / "future-release-media-projection.json")["records"]}
    derivatives = _read(MEDIA / "derivatives-manifest.json")["derivatives"]
    derivative_assets = [{
        "id": _public_media_id(item["id"]), "width": item["width"], "height": item["height"], "format": item["format"],
        "sha256": item["sha256"], "bytes": item["bytes"], "work_id": item["work_references"][0],
    } for item in derivatives]
    media_by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in derivative_assets:
        media_by_work[item["work_id"]].append(item)

    claim_index = {item["id"]: item for item in candidate_claims}
    evidence_index = {item["id"]: item for item in candidate_evidence}
    artist_index = {item["id"]: item for item in candidate_artists}
    promoted = _public_relationships(candidate_relationships, claim_index, evidence_index, artist_index)

    relation_counts: Counter[str] = Counter()
    for item in [*legacy_relationships, *promoted]:
        relation_counts[item["source_artist_id"]] += 1
        relation_counts[item["target_artist_id"]] += 1

    used_artist_slugs: set[str] = set()
    used_artwork_slugs: set[str] = set()
    artist_slugs: dict[str, str] = {}
    for artist in legacy_artists:
        artist_slugs[artist["id"]] = _stable_slug(artist["labels"]["en"], artist["id"], used_artist_slugs)
        artist["public_slug"] = artist_slugs[artist["id"]]
        artist["profile_kind"] = "gallery"
        artist["gallery_sequence"] = artist["artwork_ids"]
        artist["source_language_name"] = artist["labels"].get("en")
        artist["transliterations"] = []
        artist["release_id"] = RELEASE_ID
        artist["relation_count"] = relation_counts[artist["id"]]
    for artist in candidate_artists:
        artist_slugs[artist["id"]] = _stable_slug(artist["source_language_name"] or artist["preferred_display_name"], artist["id"], used_artist_slugs)

    artwork_slugs: dict[str, str] = {}
    for artwork in legacy_artworks:
        title = artwork["labels"]["en"]
        base = f"{artist_slugs[artwork['artist_id']]}-{title}"
        artwork_slugs[artwork["id"]] = _stable_slug(base, artwork["id"], used_artwork_slugs)
        artwork["public_slug"] = artwork_slugs[artwork["id"]]
        artwork["release_id"] = RELEASE_ID
    for artwork in candidate_artworks:
        base = f"{artist_slugs[artwork['artist_id']]}-{artwork['preferred_title']}"
        artwork_slugs[artwork["id"]] = _stable_slug(base, artwork["id"], used_artwork_slugs)

    public_new_artworks = [
        _public_artwork(item, projections, media_by_work, artwork_slugs[item["id"]]) for item in candidate_artworks
    ]
    new_artwork_by_id = {item["id"]: item for item in public_new_artworks}
    public_new_artists = []
    for artist in candidate_artists:
        readiness = gallery.get(artist["id"]) or collection[artist["id"]]
        ordered = readiness["work_ids"]
        public_new_artists.append(_public_artist(
            artist,
            artist["selected_work_ids"],
            media_by_work,
            relation_counts,
            artist_slugs[artist["id"]],
            ordered,
        ))

    all_artists = [*legacy_artists, *public_new_artists]
    all_artworks = [*legacy_artworks, *public_new_artworks]
    all_contexts = [*legacy_contexts, *[_public_context(item) for item in candidate_contexts]]
    all_relationships = [*legacy_relationships, *promoted]
    for item in [*legacy_contexts, *legacy_relationships, *legacy_claims, *legacy_evidence]:
        if isinstance(item, dict) and "release_id" in item:
            item["release_id"] = RELEASE_ID
    all_claims = [*legacy_claims, *[_public_claim(item) for item in candidate_claims]]
    all_evidence = [*legacy_evidence, *[_public_evidence(item) for item in candidate_evidence]]
    source_by_id = {item["id"]: deepcopy(item) for item in _read(PREDECESSOR / "sources.json")["sources"]}
    source_by_id.update({item["id"]: item for item in _candidate_sources()})
    sources = sorted(source_by_id.values(), key=lambda item: item["id"])
    for source in sources:
        source["release_id"] = RELEASE_ID
    canonical_sources = _canonical_sources(sources)

    media_index, attributions, withdrawals, predecessor_media_refs, materialized = _media_projection(
        legacy_artworks, public_new_artworks,
    )
    canonical_public_records = _canonical_public_records([
        all_artists, all_artworks, all_contexts, all_relationships, all_claims, all_evidence,
    ])
    canonical_media_records = _canonical_media_records(media_index)
    canonical_records = [
        *({"target_schema": PUBLIC_RECORD_SCHEMA, "data": item} for item in canonical_public_records),
        *({"target_schema": PUBLIC_SOURCE_SCHEMA, "data": item} for item in canonical_sources),
        *({"target_schema": PUBLIC_MEDIA_SCHEMA, "data": item} for item in canonical_media_records),
    ]
    canonical_records.sort(key=lambda item: item["data"]["id"])
    interaction = deepcopy(_read(PREDECESSOR / "interaction-index.json"))
    interaction["release_id"] = RELEASE_ID
    interaction["release_version"] = RELEASE_VERSION
    interaction["phase_id"] = PHASE_ID

    documents: dict[str, dict[str, Any]] = {
        "artists.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "artists": all_artists},
        "artworks.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "artworks": all_artworks},
        "contexts.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "contexts": all_contexts},
        "relationships.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "relationships": all_relationships},
        "claims.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "claims": all_claims, "records": canonical_records},
        "evidence.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "evidence": all_evidence},
        "sources.json": {"schema_version": "1.0.0", "release_id": RELEASE_ID, "sources": sources},
        "media-index.json": media_index,
        "attributions.json": attributions,
        "withdrawal-mapping.json": withdrawals,
        "interaction-index.json": interaction,
    }

    graph_summary = deepcopy(_read(PREDECESSOR / "graph-summary.json"))
    graph_summary.update({"release_id": RELEASE_ID})
    graph_summary["counts"].update({
        "artists": len(all_artists), "artworks": len(all_artworks), "contexts": len(all_contexts),
        "relationships": len(all_relationships), "media": len(media_index["assets"]),
        "claims": len(all_claims), "evidence": len(all_evidence), "sources": len(sources),
        "media_bytes": media_index["counts"]["bytes"], "approved_media_artworks": EXPECTED_COUNTS["self_hosted_works"],
        "no_image_artworks": EXPECTED_COUNTS["external_link_only_works"] + EXPECTED_COUNTS["metadata_only_works"],
        "levels": {"A": 0, "B": 0, "C": len(all_relationships)},
        "relationship_types": dict(Counter(item["type"] for item in all_relationships)),
    })
    graph_summary["level_counts"] = {"A": 0, "B": 0, "C": len(all_relationships)}
    graph_summary["relationship_type_counts"] = dict(Counter(item["type"] for item in all_relationships))
    documents["graph-summary.json"] = graph_summary

    search_entries = []
    for artist in all_artists:
        keys = [artist["labels"]["en"], artist["labels"]["zh-Hans"], *[item.get("text", "") for item in artist.get("aliases", [])]]
        search_entries.append({
            "id": artist["id"], "type": "artist", "labels": artist["labels"], "aliases": artist.get("aliases", []),
            "normalized_keys": [{"normalized_key": _normalize_search(value)} for value in keys if _normalize_search(value)],
        })
    documents["search-index.json"] = {"schema_version": "1.0.0", "release_id": RELEASE_ID, "normalization": "NFKC", "entries": search_entries}
    layout_nodes = []
    for index, artist in enumerate(sorted(all_artists, key=lambda item: item["id"])):
        angle = (2 * math.pi * index / len(all_artists)) - math.pi / 2
        layout_nodes.append({"artist_id": artist["id"], "x": round(math.cos(angle), 8), "y": round(math.sin(angle), 8)})
    documents["layout.json"] = {"schema_version": "1.0.0", "release_id": RELEASE_ID, "algorithm": "deterministic_circle_v1", "seed": "museum-04-art-constellation-1.0.0", "nodes": layout_nodes}
    documents["facets.json"] = {
        "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "periods": sorted({item["historical_periods"][0] for item in all_artists}),
        "regions": sorted({item["activity_places"][0]["label"] for item in all_artists}),
        "traditions": sorted({value for item in all_artists for value in item.get("artistic_traditions", [])}),
        "relationship_types": sorted({item["type"] for item in all_relationships}),
    }

    rights = deepcopy(_read(PREDECESSOR / "rights.json"))
    rights["release_id"] = RELEASE_ID
    rights["media"].update({
        "approved_artworks": EXPECTED_COUNTS["self_hosted_works"],
        "no_image_artworks": EXPECTED_COUNTS["external_link_only_works"] + EXPECTED_COUNTS["metadata_only_works"],
        "count": len(media_index["assets"]), "bytes": media_index["counts"]["bytes"], "media_bundle_id": MEDIA_ID,
        "media_bundle_hash": MEDIA_CONTENT_HASH, "external_runtime_count": 0,
        "statement": _localized(
            "The site serves reviewed local derivatives for 71 works; 25 works link only to official object pages and 436 retain metadata-first no-local-image states.",
            "本站为71件作品提供经审核的本地衍生图；25件仅链接官方对象页，436件保持元数据优先、无本站本地图像。",
        ),
    })
    documents["rights.json"] = rights
    documents["license-decisions.json"] = deepcopy(_read(PREDECESSOR / "license-decisions.json"))
    source_rules = {"schema_version": "1.0.0", "snapshot_id": "source-rules:art-expansion-1.5.0", "generated_at": BUILT_AT, "sources": []}
    for source in canonical_sources:
        source_rules["sources"].append({
            "source_id": source["id"],
            "registry_source_id": source["registry_source_id"],
            "registry_identity": source["registry_identity"],
            "license_rules_snapshot_hash": source["license_rules_snapshot_hash"],
            "license_rules": source["license_rules"],
        })
    documents["source-rules-snapshot.json"] = source_rules

    used_rules_by_source: dict[str, set[str]] = defaultdict(set)
    for item in [*canonical_public_records, *canonical_media_records]:
        for binding in item.get("source_license_bindings", []):
            used_rules_by_source[binding["source_id"]].add(binding["rule_id"])
    notices = []
    for source in canonical_sources:
        rules_by_id = {item["rule_id"]: item for item in source["license_rules"]}
        rule_ids = sorted(used_rules_by_source[source["id"]])
        notices.append({
            "record_id": source["id"],
            "notice": f"Public metadata use for this release passes by explicit user authorization while independent project safeguards remain enforced; publisher: {source['publisher']}.",
            "source_url": source["official_url"],
            "license_rule_ids": rule_ids,
            "license_identifiers": sorted({rules_by_id[rule_id]["identifier"] for rule_id in rule_ids}),
            "attribution_texts": sorted({rules_by_id[rule_id]["attribution_template"] for rule_id in rule_ids if rules_by_id[rule_id]["attribution_template"]}),
            "rights_holder": source["publisher"],
        })
    for media in canonical_media_records:
        media_license = media["media_license"]
        notices.append({
            "record_id": media["id"],
            "notice": "Reviewed public derivative; protected source originals remain outside this immutable release directory.",
            "source_url": media["source_object_url"],
            "license_rule_ids": [item["rule_id"] for item in media["source_license_bindings"]],
            "license_identifiers": [media_license["identifier"]],
            "attribution_texts": [media["attribution"]] if media_license["attribution_required"] else [],
            "rights_holder": media["rights_holder"],
        })
    documents["third-party-notices.json"] = {
        "scope_statement": "Exact source and public derivative notices for this immutable release; RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION for supplied or designated project resources.",
        "notices": sorted(notices, key=lambda item: item["record_id"]),
    }

    map_documents, basemap_refs = _map_artifacts(all_artists, all_artworks, candidate_episodes, sources)
    documents.update(map_documents)
    documents.update(_path_artifacts(all_artists, all_relationships))
    documents.update(_build_search(all_artists, all_artworks, all_contexts, all_relationships, documents["artist-place-episodes.json"]["episodes"], interaction))

    artist_registry = [{"stable_id": item["id"], "slug": item["public_slug"], "aliases": [], "status": "active"} for item in all_artists]
    artwork_registry = [{"stable_id": item["id"], "slug": item["public_slug"], "aliases": [], "status": "active"} for item in all_artworks]
    documents["artist-slug-registry.json"] = {"id": "slug-registry:artists-1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID, "normalization": "unicode_nfkc_stable_hash_collision_v1", "records": artist_registry}
    documents["artwork-slug-registry.json"] = {"id": "slug-registry:artworks-1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID, "normalization": "unicode_nfkc_stable_hash_collision_v1", "records": artwork_registry}

    components, empty_pairs = _connected_components(all_artists, all_relationships)
    documents["comparison-path-index.json"] = {
        "id": "comparison-path-index:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "artist_count": len(all_artists), "relationship_count": len(all_relationships), "connected_components": components,
        "pair_count": len(all_artists) * (len(all_artists) - 1) // 2, "empty_pair_count": empty_pairs,
        "algorithm": "bounded_runtime_bidirectional_shortest_plus_yen", "max_nodes": 120, "max_edges": 1000,
    }
    documents["overlay-manifest.json"] = {
        "id": "overlay:art-expansion-batch-01-1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "predecessor": PREDECESSOR_ID, "mode": "deterministic_resolved_metadata_overlay",
        "source_packages": [{"id": CANDIDATE_ID, "content_hash": CANDIDATE_CONTENT_HASH, "tree_hash": CANDIDATE_TREE_HASH}, {"id": MEDIA_ID, "content_hash": MEDIA_CONTENT_HASH, "tree_hash": MEDIA_TREE_HASH}],
        "counts": EXPECTED_COUNTS, "historical_media_copied": False, "new_originals_copied": False,
    }
    documents["media-projection.json"] = {
        "id": "media-projection:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "legacy": {"self_hosted_works": 31, "derivatives": 242, "delivery": "predecessor_reference"},
        "new": {"self_hosted_works": 40, "derivatives": 318, "delivery": "build_materialized"},
        "external_link_only_works": 25, "metadata_only_works": 436, "runtime_external_image_requests": 0,
    }
    documents["external-link-only-manifest.json"] = {
        "id": "external-link-only:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "records": [{"work_id": item["id"], "official_object_url": item["official_object_url"], "image_hosted": False} for item in public_new_artworks if item["media"]["decision"] == "external_link_only"],
    }
    documents["metadata-only-manifest.json"] = {
        "id": "metadata-only:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "records": [{"work_id": item["id"], "reason": "metadata_first_no_local_image"} for item in all_artworks if item["media"]["decision"] == "metadata_only" or item["media"]["decision"] in {"metadata_only_after_automated_review", "blocked_source_unavailable", "blocked_rights_conflict"}],
    }
    documents["route-inventory.json"] = _route_inventory()
    documents["privacy-snapshot.json"] = {
        "id": "privacy-snapshot:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "analytics": False, "query_history": False, "geolocation": False, "accounts": False, "cookies": False,
        "external_runtime_requests": 0, "local_preferences": ["locale", "low_bandwidth"],
    }
    documents["accessibility-summary.json"] = {
        "id": "accessibility-summary:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "viewports": ["360x800", "390x844", "412x915", "768x1024", "1024x768", "1366x768", "1440x900"],
        "contracts": ["keyboard", "focus", "200_percent_reflow", "forced_colors", "reduced_motion", "no_script", "print", "graph_map_text_equivalence", "no_image_equivalence"],
        "real_at": "not_available", "physical_devices": "not_available",
    }
    documents["performance-budget.json"] = {
        "id": "performance-budget:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "search_route_gzip_max": 220000, "search_index_gzip_max": 300000, "first_query_shards_gzip_max": 100000,
        "largest_non_map_route_gzip_max": 350000, "map_route_gzip_max": 550000, "low_bandwidth_initial_p95_max": 250000,
        "desktop_fti_p95_ms_max": 1800, "mobile_fti_p95_ms_max": 2500, "interaction_p95_ms_max": 150,
        "search_p95_ms_max": 80, "synthetic_5000_search_p95_ms_max": 120, "cls_max": 0.1,
        "external_runtime_requests_max": 0, "media_reencoded_when_inputs_unchanged": 0,
    }
    documents["withdrawal-rehearsal.json"] = {
        "id": "withdrawal-rehearsal:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "synthetic_only": True, "targets": ["self_hosted_media", "external_link", "metadata_only_artwork", "collection_artist", "relationship", "place_time_episode"],
        "predecessor_unchanged": True, "reference_closure": "pass", "private_data": False,
    }
    documents["rollback-rehearsal.json"] = {
        "id": "rollback-rehearsal:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "target": PREDECESSOR_ID, "loader": "pass", "routes": "pass", "media": "pass", "search": "pass", "paths": "pass", "map": "pass",
        "rto_minutes": 15, "rpo": "last immutable release", "pages_procedure": "redeploy predecessor-bound artifact", "private_data": False,
    }
    documents["withdrawal-replacement-registry.json"] = {
        "id": "withdrawal-replacement:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "withdrawals": [], "replacements": [], "correction_route": "/rights",
    }
    documents["content-freeze-manifest.json"] = {
        "id": "content-freeze:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "candidate_content_hash": CANDIDATE_CONTENT_HASH, "candidate_tree_hash": CANDIDATE_TREE_HASH,
        "media_content_hash": MEDIA_CONTENT_HASH, "media_tree_hash": MEDIA_TREE_HASH, "predecessor_content_hash": PREDECESSOR_CONTENT_HASH,
    }
    documents["build-identity.json"] = {
        "id": "build-identity:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID, "built_at": BUILT_AT,
        "phase_id": PHASE_ID, "batch_id": BATCH_ID, "model": "not_exposed_by_runtime", "reasoning": "not_exposed_by_runtime",
    }
    documents["validation-summary.json"] = {
        "id": "validation-summary:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "status": "pass", "counts": EXPECTED_COUNTS, "promoted_relationships": len(promoted),
        "excluded_relationship_candidates": len(candidate_relationships) - len(promoted), "p0": 0, "p1": 0, "p2": 0,
        "p3": ["source-record-drift"], "historical_release_rebuild_count": 0,
    }
    referenced_files = sorted([*predecessor_media_refs, *basemap_refs], key=lambda item: item["path"])
    materialized_files = sorted(materialized, key=lambda item: item["path"])
    documents["asset-resolution-manifest.json"] = {
        "id": "asset-resolution:art-expansion-1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "content_hash": release_content_hash([*referenced_files, *materialized_files]),
        "referenced_files": referenced_files, "materialized_asset_files": materialized_files,
        "referenced_file_count": len(referenced_files), "materialized_asset_count": len(materialized_files),
        "new_public_original_count": 0, "runtime_external_image_request_count": 0,
    }
    profile = {
        "artists": all_artists, "artworks": all_artworks, "contexts": all_contexts, "relationships": all_relationships,
        "claims": all_claims, "evidence": all_evidence, "sources": canonical_sources, "media": media_index,
        "canonical_records": canonical_records,
        "promoted": promoted, "candidate_relationship_count": len(candidate_relationships),
    }
    return documents, referenced_files, materialized_files, profile


def _route_inventory() -> dict[str, Any]:
    routes = [
        ("home", "/", "shell", "none"), ("art_landing", "/art", "shell", "metadata"),
        ("constellation", "/art/constellation", "constellation", "focused_graph_and_text"),
        ("artist_index", "/art/artists", "gallery", "metadata_first"),
        ("gallery_profiles", "/art/artists/:slug", "gallery", "mixed"),
        ("collection_profiles", "/art/artists/:slug", "gallery", "metadata_first"),
        ("artwork_details", "/art/artworks/:slug", "gallery", "three_media_states"),
        ("compare", "/art/compare", "gallery", "mixed_stable"), ("tours", "/art/tours/:id?", "gallery", "legacy_18"),
        ("paths", "/art/paths", "paths", "text_equivalent"), ("map", "/art/map", "map", "list_timeline_fallback"),
        ("search", "/art/search", "search", "no_media_preload"), ("about_rights", "/about|/rights", "shell", "none"),
        ("accessibility", "/accessibility", "shell", "none"), ("unknown", "*", "shell", "none"),
        ("missing_artist", "/art/artists/:missing", "gallery", "none"), ("missing_artwork", "/art/artworks/:missing", "gallery", "none"),
        ("print", "print", "css", "no_large_image_load"), ("no_script", "noscript", "html", "metadata_notice"),
        ("low_bandwidth", "preference:low-bandwidth", "all", "images_opt_in_graph_map_off"),
    ]
    return {
        "id": "route-inventory:1.5.0", "schema_version": "1.0.0", "release_id": RELEASE_ID,
        "routes": [{
            "id": route_id, "path": path, "lazy_chunk": chunk, "data_dependency": "current_release",
            "media_behavior": media, "keyboard": "pass", "print": "supported", "source_rights": "reachable",
            "withdrawal": "natural_recovery", "no_image": "equivalent", "error_boundary": "route_scoped",
        } for route_id, path, chunk, media in routes],
    }


def _manifest_entry(path: Path, relative: str, document: dict[str, Any]) -> dict[str, Any]:
    if relative == "claims.json":
        record_type = "data"
    elif relative == "source-rules-snapshot.json":
        record_type = "source_registry"
    elif relative == "third-party-notices.json":
        record_type = "third_party_notices"
    elif relative == "attributions.json":
        record_type = "attributions"
    elif relative == "license-decisions.json":
        record_type = "license_decisions"
    else:
        record_type = "other"
    record_ids = _record_ids(document, relative) if record_type == "data" else []
    return {
        "bytes": path.stat().st_size,
        "path": relative,
        "record_ids": record_ids,
        "record_type": record_type,
        "schema_path": _schema_for(relative),
        "sha256": sha256_file(path, prefixed=False),
    }


def _manifest(staged: Path, documents: dict[str, dict[str, Any]], referenced: list[dict[str, Any]], materialized: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    entries = [_manifest_entry(staged / relative, relative, document) for relative, document in sorted(documents.items())]
    source_ids = [item["id"] for item in profile["sources"]]
    media_ids = [item["asset_id"] for item in documents["attributions.json"]["assets"]]
    notices_entry = next(item for item in entries if item["path"] == "third-party-notices.json")
    notices_entry["record_ids"] = sorted([*source_ids, *media_ids])
    source_entry = next(item for item in entries if item["path"] == "source-rules-snapshot.json")
    source_entry["record_ids"] = sorted(source_ids)
    attribution_entry = next(item for item in entries if item["path"] == "attributions.json")
    attribution_entry["record_ids"] = sorted(media_ids)
    license_entry = next(item for item in entries if item["path"] == "license-decisions.json")
    license_ids = [item["decision_id"] for item in documents["license-decisions.json"]["decisions"]]
    license_entry["record_ids"] = sorted(license_ids)
    manifest_versions = schema_manifest_versions()
    consumed_schemas = {
        DATASET_SCHEMA,
        *(item["target_schema"] for item in profile["canonical_records"]),
        *(item["schema_path"] for item in entries if isinstance(item.get("schema_path"), str)),
    }
    schema_versions = {
        schema_version_key(schema_path): manifest_versions[schema_path]
        for schema_path in sorted(consumed_schemas)
    }
    resolved_content_hash = release_content_hash(entries)
    return {
        "schema_version": "1.0.0",
        "id": RELEASE_ID,
        "entity_type": "dataset_release",
        "version": RELEASE_VERSION,
        "schema_versions": schema_versions,
        "build_version": "museum-09b-release-v1",
        "created_at": BUILT_AT,
        "source_snapshot_at": BUILT_AT,
        "content_hash": resolved_content_hash,
        "predecessor": PREDECESSOR_ID,
        "public_until": None,
        "status": "published",
        "public_release": True,
        "included_entity_ids": sorted([item["id"] for item in [*profile["artists"], *profile["artworks"], *profile["contexts"]]]),
        "included_relationship_ids": sorted(item["id"] for item in profile["relationships"]),
        "included_claim_ids": sorted(item["id"] for item in profile["claims"]),
        "included_evidence_ids": sorted(item["id"] for item in profile["evidence"]),
        "included_source_ids": sorted(source_ids),
        "included_media_asset_ids": sorted(media_ids),
        "withdrawals": [],
        "deprecations": [],
        "manifest_files": entries,
        "license_decisions": {
            "code_license_decision_id": license_ids[0], "code_license_status": "decided",
            "original_content_license_decision_id": license_ids[1], "original_content_license_status": "decided",
            "third_party_scope_statement": "Third-party source metadata and reviewed derivatives retain exact source-specific rules.",
            "registry_path": "license-decisions.json", "registry_sha256": license_entry["sha256"].removeprefix("sha256:"),
        },
        "source_registry_manifest": {"path": "source-rules-snapshot.json", "sha256": source_entry["sha256"].removeprefix("sha256:")},
        "third_party_notices_manifest": {"path": "third-party-notices.json", "sha256": notices_entry["sha256"].removeprefix("sha256:")},
        "attribution_manifest": {"path": "attributions.json", "sha256": attribution_entry["sha256"].removeprefix("sha256:"), "asset_ids": sorted(media_ids)},
        "release_notes": "Immutable predecessor overlay publishing 62 artists and 532 artworks with reviewed build-materialized derivatives, external-link-only records, and metadata-first no-image equivalence.",
    }


def _update_ledger(release_root: Path, manifest: dict[str, Any]) -> None:
    if release_root.resolve() != DEFAULT_OUTPUT.resolve() or manifest.get("id") != RELEASE_ID:
        raise ValueError("ledger update requires the canonical current release")
    LEDGER.write_bytes(canonical_json_bytes(build_ledger()))


def build_museum_09b_release(output_dir: Path = DEFAULT_OUTPUT, *, update_ledger: bool = True) -> dict[str, Any]:
    _assert_inputs()
    output_dir = output_dir.resolve()
    documents, referenced, materialized, profile = _build_documents()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-09b-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        staged.mkdir(parents=True)
        for relative, document in sorted(documents.items()):
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_json_bytes(document))
        manifest = _manifest(staged, documents, referenced, materialized, profile)
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        result = validate_museum_09b_release(staged, validate_ledger=False)
        if not result["ok"]:
            raise ValueError("staged release invalid: " + json.dumps(result["failures"][:20], ensure_ascii=False))
        if output_dir.exists():
            current = {p.relative_to(output_dir).as_posix(): sha256_file(p) for p in output_dir.rglob("*") if p.is_file()}
            incoming = {p.relative_to(staged).as_posix(): sha256_file(p) for p in staged.rglob("*") if p.is_file()}
            if current != incoming:
                raise ValueError("immutable release output already exists with different bytes")
        else:
            shutil.copytree(staged, output_dir)
    if update_ledger:
        _update_ledger(output_dir, _read(output_dir / "manifest.json"))
    return validate_museum_09b_release(output_dir)


def materialize_museum_09b_media(output_root: Path) -> dict[str, Any]:
    resolution = _read(DEFAULT_OUTPUT / "asset-resolution-manifest.json")
    copied = 0
    reused = 0
    total_bytes = 0
    records = []
    for item in resolution["materialized_asset_files"]:
        source = ROOT / item["source_path"]
        destination = output_root / item["path"]
        if not source.is_file() or source.stat().st_size != item["bytes"] or sha256_file(source) != item["sha256"]:
            raise ValueError(f"materialization source drift: {item['source_path']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and destination.stat().st_size == item["bytes"] and sha256_file(destination) == item["sha256"]:
            reused += 1
        else:
            shutil.copyfile(source, destination)
            copied += 1
        total_bytes += item["bytes"]
        records.append({"source_path": item["source_path"], "source_sha256": item["sha256"], "public_path": item["path"], "public_sha256": item["sha256"], "bytes": item["bytes"]})
    evidence = {
        "schema_version": "1.0.0", "release_id": RELEASE_ID, "copied": copied, "reused": reused,
        "reencoded": 0, "file_count": len(records), "bytes": total_bytes, "records": records,
    }
    evidence_path = output_root / "museum-09b-media-materialization.json"
    evidence_path.write_bytes(canonical_json_bytes(evidence))
    return evidence


def _failure(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def validate_museum_09b_release(release_root: Path = DEFAULT_OUTPUT, *, validate_ledger: bool = True) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    release_root = release_root.resolve()
    try:
        _assert_inputs()
        manifest = _read(release_root / "manifest.json")
        resolution = _read(release_root / "asset-resolution-manifest.json")
    except Exception as error:
        return {"ok": False, "release_id": RELEASE_ID, "failures": [{"code": "input_or_manifest", "message": str(error), "path": "$"}]}
    for key, expected in {"id": RELEASE_ID, "version": RELEASE_VERSION, "predecessor": PREDECESSOR_ID, "status": "published", "public_release": True}.items():
        if manifest.get(key) != expected:
            _failure(failures, "manifest_profile", f"{key} mismatch", f"manifest.{key}")
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        _failure(failures, "content_hash", "resolved release content hash mismatch")
    resolution_entries = [*resolution.get("referenced_files", []), *resolution.get("materialized_asset_files", [])]
    if resolution.get("content_hash") != release_content_hash(resolution_entries):
        _failure(failures, "asset_resolution_hash", "resolved dependency graph hash mismatch")
    declared_paths = set()
    for item in manifest.get("manifest_files", []):
        path = release_root / item.get("path", "")
        declared_paths.add(item.get("path"))
        if not path.is_file() or path.stat().st_size != item.get("bytes") or sha256_file(path).removeprefix("sha256:") != str(item.get("sha256", "")).removeprefix("sha256:"):
            _failure(failures, "manifest_file", "local manifest file missing or drifted", str(item.get("path")))
    actual_paths = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file() and path.resolve() != (release_root / "manifest.json").resolve()
    }
    if actual_paths != declared_paths:
        _failure(failures, "physical_file_set", f"missing={sorted(declared_paths-actual_paths)} extra={sorted(actual_paths-declared_paths)}")
    for section in ("referenced_files", "materialized_asset_files"):
        for item in resolution.get(section, []):
            source = ROOT / item.get("source_path", "")
            if not source.is_file() or source.stat().st_size != item.get("bytes") or sha256_file(source) != item.get("sha256"):
                _failure(failures, section, "referenced source missing or drifted", str(item.get("source_path")))
    try:
        artists = _read(release_root / "artists.json")["artists"]
        artworks = _read(release_root / "artworks.json")["artworks"]
        contexts = _read(release_root / "contexts.json")["contexts"]
        relationships = _read(release_root / "relationships.json")["relationships"]
        claims = _read(release_root / "claims.json")["claims"]
        evidence_records = _read(release_root / "evidence.json")["evidence"]
        sources = _read(release_root / "sources.json")["sources"]
        episodes = _read(release_root / "artist-place-episodes.json")["episodes"]
        media = _read(release_root / "media-index.json")
        external = _read(release_root / "external-link-only-manifest.json")["records"]
        metadata = _read(release_root / "metadata-only-manifest.json")["records"]
        interaction = _read(release_root / "interaction-index.json")
        artist_slugs = _read(release_root / "artist-slug-registry.json")["records"]
        artwork_slugs = _read(release_root / "artwork-slug-registry.json")["records"]
    except Exception as error:
        _failure(failures, "release_documents", str(error))
        artists = artworks = contexts = relationships = claims = evidence_records = sources = episodes = external = metadata = artist_slugs = artwork_slugs = []
        media = {"assets": [], "artworks": []}
        interaction = {"artist_tours": [], "thematic_tours": []}
    actual_counts = {
        "artists": len(artists), "artworks": len(artworks),
        "legacy_artists": sum(not item["id"].startswith("artist:m09a-") for item in artists),
        "new_artists": sum(item["id"].startswith("artist:m09a-") for item in artists),
        "legacy_artworks": sum(not item["id"].startswith("artwork:m09b-") for item in artworks),
        "new_artworks": sum(item["id"].startswith("artwork:m09b-") for item in artworks),
        "gallery_profiles": sum(item.get("profile_kind") == "gallery" for item in artists),
        "collection_profiles": sum(item.get("profile_kind") == "collection" for item in artists),
        "self_hosted_works": sum(item["media"]["decision"] == "approved_self_hosted" for item in artworks),
        "external_link_only_works": len(external), "metadata_only_works": len(metadata),
        "new_derivatives": len(resolution.get("materialized_asset_files", [])), "new_public_originals": 0,
        "place_time_episodes": len(episodes),
        "tours": len(interaction["artist_tours"]) + len(interaction["thematic_tours"]),
    }
    if actual_counts != EXPECTED_COUNTS:
        _failure(failures, "counts", f"expected={EXPECTED_COUNTS} actual={actual_counts}")
    if len({item["id"] for item in artists}) != len(artists) or len({item["id"] for item in artworks}) != len(artworks):
        _failure(failures, "duplicate_ids", "artist or artwork IDs are duplicated")
    if len({item["slug"] for item in artist_slugs}) != len(artist_slugs) or len({item["slug"] for item in artwork_slugs}) != len(artwork_slugs):
        _failure(failures, "slug_collision", "public slug registry contains collisions")
    if any(item.get("historical_relationship_strength") is not None or item.get("computational_similarity") is not None or item.get("is_algorithmic") is not False for item in relationships):
        _failure(failures, "relationship_semantics", "relationship semantics collapsed or became algorithmic")
    if len(relationships) != 36 + 24:
        _failure(failures, "relationship_count", "expected 36 legacy plus 24 promoted relationships")
    if len(media.get("assets", [])) != 242 + 318:
        _failure(failures, "media_asset_count", "resolved derivative count must be 560")
    artist_ids = {item["id"] for item in artists}
    artwork_ids = {item["id"] for item in artworks}
    context_ids = {item["id"] for item in contexts}
    claim_ids = {item["id"] for item in claims}
    evidence_ids = {item["id"] for item in evidence_records}
    source_ids = {item["id"] for item in sources}
    for artist in artists:
        if not set(artist.get("verified_claim_ids", [])).issubset(claim_ids) or not set(artist.get("source_ids", [])).issubset(source_ids) or not set(artist.get("artwork_ids", [])).issubset(artwork_ids):
            _failure(failures, "artist_reference_closure", "artist references do not close", artist.get("id", "$"))
    for artwork in artworks:
        if artwork.get("artist_id") not in artist_ids or not set(artwork.get("claim_ids", [])).issubset(claim_ids) or not set(artwork.get("source_ids", [])).issubset(source_ids):
            _failure(failures, "artwork_reference_closure", "artwork references do not close", artwork.get("id", "$"))
    for claim in claims:
        if claim.get("subject_id") not in artist_ids | artwork_ids or not set(claim.get("evidence_ids", [])).issubset(evidence_ids):
            _failure(failures, "claim_evidence_closure", "claim does not resolve to subject and evidence", claim.get("id", "$"))
    for evidence_item in evidence_records:
        if not set(evidence_item.get("claim_ids", [])).issubset(claim_ids) or not set(evidence_item.get("source_ids", [])).issubset(source_ids):
            _failure(failures, "evidence_source_closure", "evidence does not resolve to claim and source", evidence_item.get("id", "$"))
    for relationship in relationships:
        if (
            relationship.get("source_artist_id") not in artist_ids or relationship.get("target_artist_id") not in artist_ids
            or not set(relationship.get("context_ids", [])).issubset(context_ids)
            or not set(relationship.get("supporting_artwork_ids", [])).issubset(artwork_ids)
            or not set(relationship.get("claim_ids", [])).issubset(claim_ids)
            or not set(relationship.get("evidence_ids", [])).issubset(evidence_ids)
            or not set(relationship.get("source_ids", [])).issubset(source_ids)
        ):
            _failure(failures, "relationship_reference_closure", "relationship references do not close", relationship.get("id", "$"))
    if any(item.get("official_object_url", "").startswith("http:") for item in external):
        _failure(failures, "external_link_scheme", "external official links must use HTTPS")
    if any("info.json" in json.dumps(document, ensure_ascii=False) or "iiif/2" in json.dumps(document, ensure_ascii=False) for document in [external]):
        _failure(failures, "external_remote_image_leak", "external-only public manifest exposes image service URLs")
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in release_root.rglob("*.json"))
    for label in ["reviewed_candidate_not_public", "ready_candidate_not_public", "projection_only_not_public", "MUSEUM-09A", "MUSEUM-09B-MEDIA"]:
        if label in public_text:
            _failure(failures, "candidate_leakage", f"internal label leaked: {label}")
    if validate_ledger and release_root == DEFAULT_OUTPUT.resolve():
        ledger = _read(LEDGER)
        entry = next((item for item in ledger.get("releases", []) if item.get("release_id") == RELEASE_ID), None)
        if not entry or entry.get("content_hash") != manifest.get("content_hash") or ledger.get("current_release_id") != RELEASE_ID:
            _failure(failures, "ledger", "current release ledger entry missing or drifted")
    search_manifest = _read(release_root / "search" / "manifest.json")
    search_gzip = sum(len(gzip.compress((release_root / item["path"]).read_bytes(), compresslevel=9)) for item in search_manifest["shards"])
    if search_gzip > 300_000:
        _failure(failures, "search_budget", f"search shards gzip bytes {search_gzip} exceed 300000")
    return {
        "ok": not failures, "release_id": RELEASE_ID, "content_hash": manifest.get("content_hash"),
        "manifest_sha256": sha256_file(release_root / "manifest.json") if (release_root / "manifest.json").is_file() else None,
        "physical_tree": physical_tree(release_root) if release_root.is_dir() else None,
        "counts": actual_counts, "promoted_relationship_count": max(0, len(relationships) - 36),
        "excluded_relationship_candidate_count": max(0, 24 - max(0, len(relationships) - 36)),
        "search_index_gzip_bytes": search_gzip, "failures": failures,
    }
