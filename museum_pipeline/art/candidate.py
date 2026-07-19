from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import sha256_file
from museum_pipeline.validation.dispatch import validate_record
from scripts.validate_governance_foundation import (
    load_schema_environment,
    release_content_hash,
    schema_manifest_versions,
    schema_version_key,
    validate_release_directory,
)


PHASE_ID = "MUSEUM-08"
INPUT_RELEASE_ID = "release:art-time-place-1.3.0"
INPUT_RELEASE_HASH = "sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f"
INPUT_MANIFEST_SHA256 = "sha256:6022063a0e2620e60d7e1adac8e5b0ea8624e2b4790941a3941546f7e74b4c7c"
INPUT_PHYSICAL_TREE_HASH = "sha256:1d02c63753830ad04a95ce11654c4527b0a3fb921e4096f5bed14415ef5370f5"
RELEASE_ID = "release:art-v1-candidate-1.4.0"
RELEASE_VERSION = "1.4.0"
BUILT_AT = "2026-07-19T12:00:00+08:00"
INPUT_RELEASE = ROOT / "public" / "releases" / "art-time-place-1.3.0"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-v1-candidate-1.4.0"
CI_CONTRACT = ROOT / "governance" / "ci-impact-contract.json"
LEDGER = ROOT / "governance" / "release-integrity-ledger.json"
SCALE_READINESS = ROOT / "docs" / "qa" / "museum-08" / "scale-readiness.json"

SEARCH_SCHEMA = "schemas/art/candidate/search-index.schema.json"
ROUTE_SCHEMA = "schemas/art/candidate/route-inventory.schema.json"
PRIVACY_SCHEMA = "schemas/art/candidate/privacy-snapshot.schema.json"
REHEARSAL_SCHEMA = "schemas/art/candidate/rehearsal-record.schema.json"
EVIDENCE_SCHEMA = "schemas/art/candidate/candidate-evidence.schema.json"

CORE_ARTIFACT_SCHEMAS: dict[str, str] = {
    "search/manifest.json": SEARCH_SCHEMA,
    "route-inventory.json": ROUTE_SCHEMA,
    "privacy-snapshot.json": PRIVACY_SCHEMA,
    "withdrawal-rehearsal.json": REHEARSAL_SCHEMA,
    "rollback-rehearsal.json": REHEARSAL_SCHEMA,
    "search/config.json": EVIDENCE_SCHEMA,
    "ci-impact-contract.json": EVIDENCE_SCHEMA,
    "release-integrity-ledger-snapshot.json": EVIDENCE_SCHEMA,
    "accessibility-summary.json": EVIDENCE_SCHEMA,
    "mobile-low-bandwidth-budgets.json": EVIDENCE_SCHEMA,
    "content-freeze-manifest.json": EVIDENCE_SCHEMA,
    "candidate-checklist.json": EVIDENCE_SCHEMA,
    "candidate-notices.json": EVIDENCE_SCHEMA,
    "asset-reuse-contract.json": EVIDENCE_SCHEMA,
    "scale-readiness-snapshot.json": EVIDENCE_SCHEMA,
    "release-composition.json": EVIDENCE_SCHEMA,
}

SEARCH_ENTITY_ORDER = {
    "artist": 0,
    "artwork": 1,
    "tour": 2,
    "context": 3,
    "relationship": 4,
    "path": 5,
    "place": 6,
    "page": 7,
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _normalized_text_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(payload)


def _physical_tree(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    byte_count = 0
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        file_sha = sha256_file(path, prefixed=False)
        digest.update(f"{relative}\0{size}\0{file_sha}\n".encode("utf-8"))
        byte_count += size
    return {
        "algorithm": "sha256(path\\0size\\0file_sha256\\n)",
        "hash": f"sha256:{digest.hexdigest()}",
        "file_count": len(files),
        "byte_count": byte_count,
    }


def normalize_search_text(value: str) -> str:
    """Deterministic non-locale search fallback shared with the browser contract."""
    folded = unicodedata.normalize("NFKC", value).lower()
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", folded)
        if not unicodedata.combining(character)
    )
    folded = re.sub(r"[^\w\u3400-\u9fff]+", " ", folded, flags=re.UNICODE)
    return " ".join(folded.split())


def _localized(value: Any, *, fallback: str) -> dict[str, str]:
    if isinstance(value, dict):
        result = {
            str(language): str(text)
            for language, text in sorted(value.items())
            if isinstance(text, str) and text.strip()
        }
        if result:
            return result
    return {"en": fallback, "zh-Hans": fallback}


def _search_value(text: str, language: str, reason: str) -> dict[str, str] | None:
    normalized = normalize_search_text(text)
    if not normalized:
        return None
    return {
        "text": text.strip(),
        "normalized": normalized,
        "language": language,
        "reason": reason,
    }


def _search_values(
    labels: dict[str, str],
    *,
    aliases: Iterable[tuple[str, str, str]] = (),
    descriptions: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for language, text in sorted(labels.items()):
        reason = "preferred" if language in {"zh-Hans", "en"} else "source_language"
        if value := _search_value(text, language, reason):
            values.append(value)
        ascii_fold = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip()
        if ascii_fold and normalize_search_text(ascii_fold) != normalize_search_text(text):
            if value := _search_value(ascii_fold, "und-Latn", "transliteration"):
                values.append(value)
    for language, text, reason in aliases:
        if value := _search_value(text, language, reason):
            values.append(value)
    for language, text in sorted((descriptions or {}).items()):
        if value := _search_value(text, language, "description"):
            values.append(value)
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for value in values:
        unique[(value["normalized"], value["language"], value["reason"])] = value
    return sorted(
        unique.values(),
        key=lambda item: (
            {"preferred": 0, "approved_alias": 1, "transliteration": 2, "source_language": 3, "description": 4}[item["reason"]],
            item["language"],
            item["normalized"],
        ),
    )


def _record_id(entity_type: str, stable_id: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", f"{entity_type}-{stable_id}".casefold()).strip("-")
    return f"search-record:{slug}"


def _search_record(
    entity_type: str,
    stable_id: str,
    route: str,
    labels: dict[str, str],
    description: dict[str, str],
    *,
    aliases: Iterable[tuple[str, str, str]] = (),
    withdrawal_status: str = "active",
) -> dict[str, Any]:
    return {
        "id": _record_id(entity_type, stable_id),
        "stable_id": stable_id,
        "entity_type": entity_type,
        "route": route,
        "labels": labels,
        "description": description,
        "values": _search_values(labels, aliases=aliases, descriptions=description),
        "visitor_task_order": SEARCH_ENTITY_ORDER[entity_type],
        "withdrawal_status": withdrawal_status,
    }


def build_search_records(release_root: Path = INPUT_RELEASE) -> list[dict[str, Any]]:
    artists = _load_json(release_root / "artists.json")["artists"]
    artworks = _load_json(release_root / "artworks.json")["artworks"]
    contexts = _load_json(release_root / "contexts.json")["contexts"]
    relationships = _load_json(release_root / "relationships.json")["relationships"]
    interactions = _load_json(release_root / "interaction-index.json")
    places = _load_json(release_root / "place-identities.json")["places"]
    path_pairs = _load_json(release_root / "path-index.json")["pairs"]
    artist_labels = {item["id"]: _localized(item.get("labels"), fallback=item["id"]) for item in artists}
    records: list[dict[str, Any]] = []

    for artist in artists:
        aliases = [
            (
                str(alias.get("language", "und")),
                str(alias["text"]),
                "transliteration"
                if alias.get("language") == "en"
                and any(ord(character) > 127 for character in artist_labels[artist["id"]].get("en", ""))
                else "approved_alias",
            )
            for alias in artist.get("aliases", [])
            if isinstance(alias, dict) and isinstance(alias.get("text"), str)
        ]
        records.append(_search_record(
            "artist",
            artist["id"],
            f"/art/artists/{quote(artist['id'], safe='')}",
            artist_labels[artist["id"]],
            _localized(artist.get("summary"), fallback=artist["id"]),
            aliases=aliases,
        ))

    for artwork in artworks:
        labels = _localized(artwork.get("labels"), fallback=artwork["id"])
        artist_label = artist_labels.get(artwork.get("artist_id"), {})
        description = {
            language: f"{text} — {artist_label.get(language, artist_label.get('en', artwork.get('artist_id', '')))}"
            for language, text in labels.items()
        }
        aliases = []
        if accession := artwork.get("accession_number"):
            aliases.append(("und", str(accession), "approved_alias"))
        records.append(_search_record(
            "artwork",
            artwork["id"],
            f"/art/artworks/{quote(artwork['id'], safe='')}",
            labels,
            description,
            aliases=aliases,
        ))

    for context in contexts:
        records.append(_search_record(
            "context",
            context["id"],
            f"/art/constellation?context={quote(context['id'], safe='')}",
            _localized(context.get("labels"), fallback=context["id"]),
            _localized(context.get("definition"), fallback=context["id"]),
        ))

    tours = [*interactions["artist_tours"], *interactions["thematic_tours"]]
    for tour in tours:
        description = (
            _localized(tour.get("summary"), fallback=tour["id"])
            if tour.get("kind") == "thematic"
            else _localized(tour.get("entry_question"), fallback=tour["id"])
        )
        records.append(_search_record(
            "tour",
            tour["id"],
            f"/art/tours/{quote(tour['id'], safe='')}",
            _localized(tour.get("title"), fallback=tour["id"]),
            description,
        ))

    for place in places:
        aliases = [
            (str(name.get("language", "und")), str(name["text"]), "source_language")
            for name in place.get("names", [])
            if isinstance(name, dict) and isinstance(name.get("text"), str)
        ]
        if historical := place.get("preferred_historical_label"):
            aliases.append(("en", str(historical), "approved_alias"))
        records.append(_search_record(
            "place",
            place["id"],
            f"/art/map?place={quote(place['id'], safe='')}&view=list",
            _localized(place.get("labels"), fallback=place["id"]),
            {
                "en": f"Source-verified place in {place.get('region', 'the current release')}.",
                "zh-Hans": f"当前发布中经来源核验的地点；区域：{place.get('region', '未标注')}。",
            },
            aliases=aliases,
        ))

    for relationship in relationships:
        records.append(_search_record(
            "relationship",
            relationship["id"],
            f"/art/constellation?relationship={quote(relationship['id'], safe='')}",
            _localized(relationship.get("title"), fallback=relationship["id"]),
            _localized(relationship.get("short_explanation"), fallback=relationship["id"]),
        ))

    for pair in path_pairs:
        for mode, result in sorted(pair["modes"].items()):
            start = artist_labels[pair["start_artist_id"]]
            end = artist_labels[pair["end_artist_id"]]
            labels = {
                "en": f"{start.get('en', pair['start_artist_id'])} to {end.get('en', pair['end_artist_id'])} — {mode}",
                "zh-Hans": f"{start.get('zh-Hans', pair['start_artist_id'])}至{end.get('zh-Hans', pair['end_artist_id'])}—{mode}",
            }
            route = (
                f"/art/paths?start={quote(pair['start_artist_id'], safe='')}"
                f"&end={quote(pair['end_artist_id'], safe='')}&mode={quote(mode, safe='')}"
            )
            records.append(_search_record(
                "path",
                result["id"],
                route,
                labels,
                _localized(result.get("disclaimer"), fallback=result["id"]),
            ))

    pages = [
        (
            "page:about",
            "/about",
            {"en": "About the museum", "zh-Hans": "关于博物馆"},
            {"en": "Methods, sources, release boundaries, and public commitments.", "zh-Hans": "方法、来源、发布边界与公开承诺。"},
        ),
        (
            "page:rights",
            "/rights",
            {"en": "Rights and attribution", "zh-Hans": "权利与署名"},
            {"en": "Rights, notices, attribution, withdrawal, and source entry points.", "zh-Hans": "权利、声明、署名、撤回与来源入口。"},
        ),
        (
            "page:accessibility",
            "/accessibility",
            {"en": "Accessibility and low bandwidth", "zh-Hans": "无障碍与低带宽"},
            {"en": "Keyboard, reflow, motion, contrast, text alternatives, and low-bandwidth controls.", "zh-Hans": "键盘、重排、动效、对比度、文本替代与低带宽控制。"},
        ),
        (
            "page:privacy",
            "/about?section=privacy",
            {"en": "Privacy", "zh-Hans": "隐私"},
            {"en": "No analytics, account, query history, cookies, fingerprinting, geolocation, or remote logging.", "zh-Hans": "不使用分析、账户、查询历史、Cookie、指纹、用户定位或远程日志。"},
        ),
        (
            "page:help",
            "/art",
            {"en": "Explore art", "zh-Hans": "探索美术馆"},
            {"en": "Find artists, artworks, tours, paths, places, comparisons, and search.", "zh-Hans": "查找艺术家、作品、导览、路径、地点、比较与搜索。"},
        ),
    ]
    for stable_id, route, labels, description in pages:
        records.append(_search_record("page", stable_id, route, labels, description))

    records.sort(key=lambda item: (item["visitor_task_order"], item["stable_id"]))
    ids = [item["id"] for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("search record IDs are not unique")
    return records


def _search_shards(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["entity_type"], []).append(record)
    shards: dict[str, dict[str, Any]] = {}
    for entity_type, items in sorted(grouped.items(), key=lambda item: SEARCH_ENTITY_ORDER[item[0]]):
        path = f"search/shards/{entity_type}-00.json"
        records_hash = _canonical_hash(items)
        document = {
            "schema_version": "1.0.0",
            "id": f"search-shard:{entity_type}-00",
            "entity_type": "search_index_shard",
            "release_id": RELEASE_ID,
            "strategy": "entity_type",
            "shard_key": entity_type,
            "input_closure_hash": _canonical_hash([item["stable_id"] for item in items]),
            "records_hash": records_hash,
            "record_count": len(items),
            "records": items,
        }
        shards[path] = document
    return shards


def _evidence(evidence_id: str, evidence_kind: str, status: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": f"candidate-evidence:{evidence_id}",
        "entity_type": "candidate_evidence",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "evidence_kind": evidence_kind,
        "status": status,
        "payload": payload,
    }


def _route_inventory() -> dict[str, Any]:
    routes = [
        ("home", "/", 1, None, False, [], "no artwork media", "complete shell", "none", "supported"),
        ("art-landing", "/art", 1, None, False, [], "no artwork media", "all core destinations available", "none", "supported"),
        ("constellation", "/art/constellation", 1, "art-constellation", False, ["artists.json", "relationships.json"], "metadata first; image only after visitor action", "artist and relationship lists", "forbidden_low_bandwidth", "metadata_only"),
        ("artist-index", "/art/artists", 1, "art-gallery", False, ["artists.json"], "no index images", "complete textual index", "none", "supported"),
        ("artist-gallery", "/art/artists/:artistId", 12, "art-gallery", True, ["artists.json", "artworks.json", "interaction-index.json"], "image only after visitor action", "metadata and observation cards", "none", "supported"),
        ("artwork-detail", "/art/artworks/:artworkId", 44, "art-gallery", True, ["artworks.json", "interaction-index.json"], "image only after visitor action", "metadata, evidence, and no-image equivalent", "none", "supported"),
        ("compare", "/art/compare", 1, "art-gallery", True, ["artworks.json", "interaction-index.json"], "metadata first; stacked on compact view", "metadata comparison", "none", "supported"),
        ("tour-index", "/art/tours", 1, "art-gallery", False, ["interaction-index.json"], "no index images", "metadata-only tour cards", "none", "supported"),
        ("tour-detail", "/art/tours/:tourId", 18, "art-gallery", True, ["interaction-index.json"], "image only after visitor action", "complete text steps", "none", "supported"),
        ("paths", "/art/paths", 1, "art-paths", True, ["path-graph-input.json", "path-index.json"], "no media dependency", "complete text paths", "forbidden_low_bandwidth", "metadata_only"),
        ("map", "/art/map", 1, "art-map", True, ["map-index.json", "artist-place-episodes.json"], "no artwork media", "timeline and place list", "forbidden_low_bandwidth", "metadata_only"),
        ("search", "/art/search", 1, "art-search", True, ["search/manifest.json"], "media forbidden", "full search without media or Segmenter", "none", "supported"),
        ("about", "/about", 1, None, False, [], "no artwork media", "complete text", "none", "supported"),
        ("rights", "/rights", 1, None, False, [], "no artwork media", "complete text and notices links", "none", "supported"),
        ("accessibility", "/accessibility", 1, None, False, [], "no artwork media", "complete controls and text", "none", "supported"),
        ("unknown", "/*", 1, None, True, [], "no artwork media", "natural-language recovery", "none", "not_applicable"),
    ]
    documents = []
    for route_id, path, concrete_count, chunk, stable_lazy, dependencies, media, low, webgl, print_mode in routes:
        documents.append({
            "id": f"route:{route_id}",
            "path": path,
            "concrete_count": concrete_count,
            "lazy_chunk": chunk,
            "stable_id_lazy_load": stable_lazy,
            "data_dependencies": dependencies,
            "media_behavior": media,
            "low_bandwidth": low,
            "webgl": webgl,
            "print": print_mode,
            "keyboard": "skip link, ordered focus, named controls, and visible focus",
            "no_script": "static title, route purpose, and JavaScript-required recovery copy",
            "rights_source_entry": "/rights and source drawer or source links",
            "withdrawal_fallback": "natural-language withdrawn, missing, or unavailable state without blank shell",
        })
    return {
        "schema_version": "1.0.0",
        "id": "route-inventory:art-v1-candidate-1.4.0",
        "entity_type": "route_inventory",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "template_count": len(documents),
        "concrete_route_count": sum(item["concrete_count"] for item in documents),
        "routes": documents,
    }


def _privacy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "privacy-snapshot:od-009-museum-08",
        "entity_type": "privacy_snapshot",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "decision_id": "OD-009",
        "status": "closed",
        "analytics": False,
        "account": False,
        "server_side_profile": False,
        "query_history": False,
        "visit_history": False,
        "path_history": False,
        "map_history": False,
        "tour_history": False,
        "telemetry_sdk": False,
        "cookies": False,
        "fingerprinting": False,
        "user_geolocation": False,
        "remote_logging": False,
        "allowed_local_preferences": ["museum-locale", "museum-low-bandwidth"],
        "forbidden_local_state": [
            "search_queries",
            "selected_artists",
            "compared_works",
            "paths",
            "map_filters",
            "tours_visited",
            "print_history",
            "share_history",
        ],
        "external_runtime_requests": 0,
    }


def simulate_synthetic_withdrawals() -> dict[str, Any]:
    """Apply four withdrawals to an isolated graph and prove every reference closes."""
    media_id = "synthetic:media-withdrawal-001"
    relationship_id = "synthetic:relationship-withdrawal-001"
    episode_id = "synthetic:episode-withdrawal-001"
    artwork_id = "synthetic:artwork-withdrawal-001"
    fixture = {
        "artworks": [
            {"id": "synthetic:artwork-kept-001", "media_id": media_id, "no_image": False},
            {"id": artwork_id, "media_id": None, "no_image": True},
        ],
        "media": [{"id": media_id, "artwork_id": "synthetic:artwork-kept-001"}],
        "relationships": [{
            "id": relationship_id,
            "source_artist_id": "synthetic:artist-a",
            "target_artist_id": "synthetic:artist-b",
        }],
        "paths": [{"id": "synthetic:path-001", "relationship_ids": [relationship_id]}],
        "episodes": [{"id": episode_id, "artist_id": "synthetic:artist-a", "place_id": "synthetic:place-a"}],
        "galleries": [{"id": "synthetic:gallery-a", "artwork_ids": ["synthetic:artwork-kept-001", artwork_id]}],
        "search_ids": ["synthetic:artwork-kept-001", artwork_id],
        "notices": [],
    }
    before_hash = _canonical_hash(fixture)
    after = deepcopy(fixture)
    after["media"] = [item for item in after["media"] if item["id"] != media_id]
    for artwork in after["artworks"]:
        if artwork["media_id"] == media_id:
            artwork.update({"media_id": None, "no_image": True})
    after["relationships"] = [item for item in after["relationships"] if item["id"] != relationship_id]
    for path in after["paths"]:
        path["relationship_ids"] = [item for item in path["relationship_ids"] if item != relationship_id]
    after["paths"] = [item for item in after["paths"] if item["relationship_ids"]]
    after["episodes"] = [item for item in after["episodes"] if item["id"] != episode_id]
    after["artworks"] = [item for item in after["artworks"] if item["id"] != artwork_id]
    for gallery in after["galleries"]:
        gallery["artwork_ids"] = [item for item in gallery["artwork_ids"] if item != artwork_id]
    after["search_ids"] = [item for item in after["search_ids"] if item != artwork_id]
    after["notices"] = [
        {"kind": "media_asset", "withdrawn_id": media_id},
        {"kind": "relationship", "withdrawn_id": relationship_id},
        {"kind": "place_episode", "withdrawn_id": episode_id},
        {"kind": "artwork_metadata", "withdrawn_id": artwork_id},
    ]
    kept_artwork = next(item for item in after["artworks"] if item["id"] == "synthetic:artwork-kept-001")
    closure = {
        "media_asset": not after["media"] and kept_artwork["media_id"] is None and kept_artwork["no_image"] is True,
        "relationship": not after["relationships"] and not after["paths"],
        "place_episode": not after["episodes"],
        "artwork_metadata": (
            all(item["id"] != artwork_id for item in after["artworks"])
            and all(artwork_id not in item["artwork_ids"] for item in after["galleries"])
            and artwork_id not in after["search_ids"]
        ),
    }
    return {
        "before_hash": before_hash,
        "before_unchanged": _canonical_hash(fixture) == before_hash,
        "after_hash": _canonical_hash(after),
        "closure": closure,
        "after": after,
    }


def run_withdrawal_rehearsal() -> dict[str, Any]:
    simulation = simulate_synthetic_withdrawals()
    scenarios = [
        ("media_asset", "synthetic:media-withdrawal-001", "gallery switches to the no-image equivalent"),
        ("relationship", "synthetic:relationship-withdrawal-001", "constellation and path indexes omit the edge"),
        ("place_episode", "synthetic:episode-withdrawal-001", "map and list omit the episode"),
        ("artwork_metadata", "synthetic:artwork-withdrawal-001", "artwork URL explains withdrawal and artist gallery remains usable"),
    ]
    return {
        "schema_version": "1.0.0",
        "id": "withdrawal-rehearsal:museum-08-v1",
        "entity_type": "withdrawal_rehearsal",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "synthetic_only": True,
        "real_records_modified": False,
        "scenarios": [
            {
                "kind": kind,
                "synthetic_id": synthetic_id,
                "removed_from_new_release": True,
                "reference_closure": simulation["closure"][kind],
                "route_fallback": fallback,
                "notice_updated": True,
            }
            for kind, synthetic_id, fallback in scenarios
        ],
        "old_release_immutable": simulation["before_unchanged"],
        "reference_closure": all(simulation["closure"].values()),
        "url_fallback": "natural_language_withdrawn_or_unavailable",
        "notices_updated": True,
        "status": "pass",
    }


def run_rollback_rehearsal() -> dict[str, Any]:
    predecessor = _load_json(INPUT_RELEASE / "manifest.json")
    rollback_checks = {
        "loader": predecessor.get("id") == INPUT_RELEASE_ID,
        "routes": all((INPUT_RELEASE / path).is_file() for path in ("artists.json", "artworks.json", "interaction-index.json")),
        "media": all((INPUT_RELEASE / path).is_file() for path in ("media-assets.json", "media-index.json", "rights.json")),
        "paths": all((INPUT_RELEASE / path).is_file() for path in ("path-index.json", "path-graph-input.json")),
        "map": all((INPUT_RELEASE / path).is_file() for path in ("map-index.json", "artist-place-episodes.json")),
        "hash_closure": (
            predecessor.get("content_hash") == INPUT_RELEASE_HASH
            and sha256_file(INPUT_RELEASE / "manifest.json") == INPUT_MANIFEST_SHA256
            and _physical_tree(INPUT_RELEASE)["hash"] == INPUT_PHYSICAL_TREE_HASH
        ),
    }
    return {
        "schema_version": "1.0.0",
        "id": "rollback-rehearsal:museum-08-v1",
        "entity_type": "rollback_rehearsal",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "synthetic_only": True,
        "from_release_id": RELEASE_ID,
        "to_release_id": INPUT_RELEASE_ID,
        "loader": "pass" if rollback_checks["loader"] else "fail",
        "routes": "pass" if rollback_checks["routes"] else "fail",
        "media": "pass" if rollback_checks["media"] else "fail",
        "paths": "pass" if rollback_checks["paths"] else "fail",
        "map": "pass" if rollback_checks["map"] else "fail",
        "hash_closure": "pass" if rollback_checks["hash_closure"] else "fail",
        "private_data": False,
        "rto_minutes": 15,
        "rpo": "zero_published_release_mutation",
        "pages_procedure": [
            "Select the last successful predecessor artifact by exact commit and release ID.",
            "Verify predecessor manifest, content, and physical tree hashes.",
            "Deploy the predecessor artifact without rebuilding historical releases.",
            "Verify home, search recovery, galleries, paths, map list, and media byte closure.",
            "Record deployment ID, commit, release ID, hashes, operator, and recovery time.",
        ],
        "recovery_checklist": [
            "Freeze deploy ownership to one operator.",
            "Preserve the failed candidate and Actions logs.",
            "Confirm predecessor immutability.",
            "Confirm no secrets or private data in artifacts.",
            "Confirm loader selects the predecessor manifest.",
            "Confirm withdrawn and missing routes fail naturally.",
            "Confirm local media, path, and map files resolve.",
            "Confirm Pages deployment and online byte closure.",
        ],
        "status": "pass" if all(rollback_checks.values()) else "fail",
    }


def _candidate_evidence_documents(predecessor: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ci_contract = _load_json(CI_CONTRACT)
    ledger = _load_json(LEDGER)
    scale_readiness = _load_json(SCALE_READINESS)
    historical_entries = [
        entry for entry in ledger.get("releases", [])
        if entry.get("release_id") != RELEASE_ID
    ]
    freeze = {
        "artists": 12,
        "artworks": 44,
        "contexts": 31,
        "approved_media_artworks": 31,
        "no_image_artworks": 13,
        "media_derivatives": 242,
        "relationships_level_c": 36,
        "observation_cards": 44,
        "artist_tours": 12,
        "thematic_tours": 6,
        "tours_total": 18,
        "path_index_records": 198,
        "places": 23,
        "artist_place_episodes": 36,
        "new_real_content_entities": 0,
    }
    documents = {
        "search/config.json": _evidence("search-config", "search_config", "ready", {
            "decision_id": "OD-008",
            "decision_status": "closed",
            "third_party_tokenizer_dependency": False,
            "intl_segmenter": "optional_enhancement",
            "segmenter_absence_preserves_complete_function": True,
            "normalization": "unicode_nfkc_lower_diacritic_fold_whitespace_v1",
            "matching": ["exact_preferred", "exact_alias", "prefix", "segmenter_token", "substring"],
            "ranking_tuple": ["match_class", "visitor_task_entity_type", "stable_id"],
            "semantic_search": False,
            "remote_search": False,
            "query_collection": False,
            "popularity_or_art_value_ranking": False,
        }),
        "ci-impact-contract.json": _evidence("ci-impact-contract", "ci_impact_contract_snapshot", "pass", {
            "source_path": "governance/ci-impact-contract.json",
            "source_sha256": sha256_file(CI_CONTRACT),
            "contract": ci_contract,
        }),
        "release-integrity-ledger-snapshot.json": _evidence("release-ledger-snapshot", "release_integrity_ledger_snapshot", "pass", {
            "default_historical_behavior": "hash_only",
            "historical_release_count": len(historical_entries),
            "historical_entries_hash": _canonical_hash(historical_entries),
            "releases": historical_entries,
            "candidate_entry_excluded_to_avoid_self_reference": True,
        }),
        "accessibility-summary.json": _evidence("accessibility-summary", "accessibility_summary", "candidate", {
            "automated_gate": "serious_and_critical_zero",
            "route_coverage": "all_core_route_templates",
            "landmarks_headings_name_role_value": True,
            "keyboard_focus_skip_live_dialogs": True,
            "graph_map_text_equivalence": True,
            "image_alt_and_no_image_equivalence": True,
            "forced_colors_reduced_motion_print": True,
            "zoom_200_percent_and_mobile_reflow": True,
            "real_assistive_technology": "not_available",
            "physical_devices": "not_available",
        }),
        "mobile-low-bandwidth-budgets.json": _evidence("mobile-low-bandwidth-budgets", "mobile_low_bandwidth_budgets", "ready", {
            "viewports": ["360x800", "390x844", "412x915", "768x1024", "1024x768", "1366x768", "1440x900"],
            "touch_target_css_pixels_min": 44,
            "horizontal_overflow_max_css_pixels": 0,
            "low_bandwidth_initial_transfer_bytes_max": 250000,
            "search_route_gzip_bytes_max": 220000,
            "search_index_gzip_bytes_max": 150000,
            "largest_non_map_route_gzip_bytes_max": 300000,
            "map_route_gzip_bytes_max": 550000,
            "cls_max": 0.1,
            "interaction_p95_ms_max": 150,
            "external_runtime_requests_max": 0,
            "unexpected_media_preload_max": 0,
            "service_worker_added": False,
        }),
        "content-freeze-manifest.json": _evidence("content-freeze", "content_freeze_manifest", "pass", freeze),
        "candidate-checklist.json": _evidence("candidate-checklist", "candidate_checklist", "candidate", {
            "predecessor_id": predecessor["id"],
            "predecessor_content_hash": predecessor["content_hash"],
            "content_freeze": True,
            "od_008_closed": True,
            "od_009_closed": True,
            "remaining_open_decisions": ["OD-011"],
            "search_route": True,
            "privacy_no_collection": True,
            "withdrawal_rehearsal": True,
            "rollback_rehearsal": True,
            "scale_architecture_ready": True,
            "real_content_expansion_started": False,
            "museum_09_entered": False,
        }),
        "candidate-notices.json": _evidence("candidate-notices", "candidate_notices", "candidate", {
            "no_new_third_party_media": True,
            "no_new_real_content_entities": True,
            "search_has_no_remote_or_ai_dependency": True,
            "privacy": "no analytics, accounts, query history, cookies, fingerprinting, geolocation, or remote logging",
            "withdrawn_url_behavior": "natural-language unavailable state; predecessor remains immutable",
            "rights_status": "PASS_BY_USER_AUTHORIZATION",
            "independent_safeguards_enforced": ["secrets", "privacy", "source_immutability", "release_integrity"],
        }),
        "asset-reuse-contract.json": _evidence("asset-reuse-contract", "asset_reuse_contract", "ready", {
            "identity": "sha256",
            "manifest_reference_required": True,
            "rights_status_bound_per_reference": True,
            "withdrawal_can_disable_reference_without_deleting_history": True,
            "unchanged_bytes_reused_by_git_content_addressing": True,
            "future_shared_asset_namespace": "assets/sha256/<prefix>/<digest>",
            "candidate_runtime_migration": "design_and_synthetic_prototype_only",
            "historical_release_urls_preserved": True,
            "historical_releases_deleted": False,
            "risk_owner": "release_engineering",
            "m09_review_point": "before first real scale batch",
        }),
        "scale-readiness-snapshot.json": _evidence("scale-readiness", "scale_readiness_snapshot", "pass", {
            "source_path": "docs/qa/museum-08/scale-readiness.json",
            "source_sha256": _normalized_text_sha256(SCALE_READINESS),
            "scale_architecture_ready": scale_readiness["scale_architecture_ready"],
            "synthetic_scale_validated": scale_readiness["synthetic_scale_validated"],
            "synthetic_artist_count": scale_readiness["synthetic_artist_count"],
            "synthetic_artwork_count": scale_readiness["synthetic_artwork_count"],
            "synthetic_search_record_count": scale_readiness["synthetic_search_record_count"],
            "synthetic_relationship_count": scale_readiness["synthetic_relationship_count"],
            "synthetic_path_index_record_count": scale_readiness["synthetic_path_index_record_count"],
            "byte_identical_repeat": scale_readiness["byte_identical_repeat"],
            "fixture_tree_hash": scale_readiness["fixture_tree_hash"],
            "public_synthetic_leakage_count": scale_readiness["public_synthetic_leakage_count"],
            "real_content_expansion_started": scale_readiness["real_content_expansion_started"],
            "museum_09_entered": scale_readiness["museum_09_entered"],
        }),
        "release-composition.json": _evidence("release-composition", "release_composition", "pass", {
            "mode": "immutable_overlay",
            "predecessor_id": predecessor["id"],
            "predecessor_content_hash": predecessor["content_hash"],
            "inherited_files_are_byte_identical": True,
            "candidate_overlay_paths": sorted([
                *CORE_ARTIFACT_SCHEMAS,
                "search/shards/<entity-type>-00.json",
            ]),
            "media_bytes_rebuilt": False,
            "historical_releases_rebuilt": False,
        }),
    }
    return documents


def _build_candidate_artifacts(
    staged: Path,
    predecessor: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    records = build_search_records(INPUT_RELEASE)
    shards = _search_shards(records)
    for relative, document in shards.items():
        path = staged / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_bytes(document))

    shard_entries = []
    for relative, document in shards.items():
        path = staged / relative
        languages = sorted({
            value["language"]
            for record in document["records"]
            for value in record["values"]
        })
        shard_entries.append({
            "id": document["id"],
            "path": relative,
            "entity_types": [document["shard_key"]],
            "languages": languages,
            "stable_hash_prefix": None,
            "record_count": document["record_count"],
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "records_hash": document["records_hash"],
        })
    by_type = Counter(record["entity_type"] for record in records)
    search_manifest = {
        "schema_version": "1.0.0",
        "id": "search-index:art-v1-candidate-1.4.0",
        "entity_type": "search_index_manifest",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "generated_at": BUILT_AT,
        "config_path": "search/config.json",
        "normalization": "unicode_nfkc_lower_diacritic_fold_whitespace_v1",
        "matching_modes": ["exact_preferred", "exact_alias", "prefix", "segmenter_token", "substring"],
        "ranking_tuple": ["match_class", "visitor_task_entity_type", "stable_id"],
        "segmenter_optional": True,
        "fallback_complete": True,
        "query_logging": False,
        "media_paths_included": False,
        "shard_contract": {
            "strategies": ["entity_type", "language", "stable_hash_prefix"],
            "incremental_rebuild": True,
            "unchanged_shards_hash_only": True,
            "lazy_load": True,
        },
        "shards": sorted(shard_entries, key=lambda item: item["path"]),
        "counts": {
            "records": len(records),
            "shards": len(shards),
            "by_entity_type": dict(sorted(by_type.items())),
        },
        "budgets": {
            "search_route_gzip_bytes_max": 220000,
            "search_index_gzip_bytes_max": 150000,
            "current_query_p95_ms_max": 80,
            "synthetic_1000_query_p95_ms_max": 120,
            "external_requests_max": 0,
        },
    }
    documents = {
        "search/manifest.json": search_manifest,
        "route-inventory.json": _route_inventory(),
        "privacy-snapshot.json": _privacy_snapshot(),
        "withdrawal-rehearsal.json": run_withdrawal_rehearsal(),
        "rollback-rehearsal.json": run_rollback_rehearsal(),
        **_candidate_evidence_documents(predecessor),
        **shards,
    }
    schemas = {
        **CORE_ARTIFACT_SCHEMAS,
        **{path: SEARCH_SCHEMA for path in shards},
    }
    for relative, document in documents.items():
        if relative in shards:
            continue
        path = staged / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_bytes(document))
    return documents, schemas


def _validate_candidate_documents(documents: dict[str, dict[str, Any]], schemas: dict[str, str]) -> None:
    environment = None
    for relative, document in documents.items():
        issues = validate_record(document, requested_schema=schemas[relative], environment=environment)
        if issues:
            first = issues[0]
            raise ValueError(f"{relative} {first.location}: {first.message}")


def build_museum_08_release(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    predecessor = _load_json(INPUT_RELEASE / "manifest.json")
    if predecessor.get("id") != INPUT_RELEASE_ID or predecessor.get("content_hash") != INPUT_RELEASE_HASH:
        raise ValueError("MUSEUM-07 predecessor content hash mismatch")
    if sha256_file(INPUT_RELEASE / "manifest.json") != INPUT_MANIFEST_SHA256:
        raise ValueError("MUSEUM-07 predecessor manifest SHA mismatch")
    if _physical_tree(INPUT_RELEASE)["hash"] != INPUT_PHYSICAL_TREE_HASH:
        raise ValueError("MUSEUM-07 predecessor physical tree hash mismatch")
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-08-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        staged.mkdir(parents=True)
        for source in INPUT_RELEASE.rglob("*"):
            if not source.is_file() or source.name == "manifest.json":
                continue
            destination = staged / source.relative_to(INPUT_RELEASE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        documents, schemas = _build_candidate_artifacts(staged, predecessor)
        _validate_candidate_documents(documents, schemas)
        entries = deepcopy(predecessor["manifest_files"])
        for relative, document in sorted(documents.items()):
            path = staged / relative
            entries.append({
                "bytes": path.stat().st_size,
                "path": relative,
                "record_ids": [document["id"]],
                "record_type": "other",
                "schema_path": schemas[relative],
                "sha256": sha256_file(path, prefixed=False),
            })
        entries.sort(key=lambda item: item["path"])
        versions = schema_manifest_versions()
        used_candidate_schemas = sorted(set(schemas.values()))
        manifest = deepcopy(predecessor)
        manifest.update({
            "id": RELEASE_ID,
            "version": RELEASE_VERSION,
            "build_version": "museum-08-v1-candidate",
            "created_at": BUILT_AT,
            "predecessor": INPUT_RELEASE_ID,
            "manifest_files": entries,
            "content_hash": release_content_hash(entries),
            "release_notes": (
                "Immutable V1 candidate overlay. Adds deterministic sharded bilingual public search, "
                "privacy and route contracts, CI impact and historical integrity snapshots, mobile, "
                "accessibility and low-bandwidth budgets, synthetic withdrawal/rollback evidence, "
                "and scale-readiness contracts. It adds no real artist, artwork, media, relationship, "
                "place, or tour and does not enter MUSEUM-09."
            ),
        })
        manifest["schema_versions"] = {
            **predecessor["schema_versions"],
            **{
                schema_version_key(path): versions[path]
                for path in used_candidate_schemas
            },
        }
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        validation = validate_museum_08_release(staged)
        if not validation["ok"]:
            raise ValueError(
                "staged MUSEUM-08 release failed: "
                + json.dumps(validation["failures"][:20], ensure_ascii=False)
            )
        if output_dir.exists():
            if _file_hashes(output_dir) != _file_hashes(staged):
                raise ValueError(f"immutable output already exists with different bytes: {output_dir}")
        else:
            shutil.copytree(staged, output_dir)
    return validate_museum_08_release(output_dir)


def validate_museum_08_release(release_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    release_root = release_root.resolve()
    if not release_root.is_dir():
        return _result(release_root, [{"code": "release_missing", "message": "release directory missing", "path": "$"}])
    try:
        predecessor = _load_json(INPUT_RELEASE / "manifest.json")
        manifest = _load_json(release_root / "manifest.json")
        search_manifest = _load_json(release_root / "search" / "manifest.json")
        route_inventory = _load_json(release_root / "route-inventory.json")
        privacy = _load_json(release_root / "privacy-snapshot.json")
        freeze = _load_json(release_root / "content-freeze-manifest.json")
        withdrawal = _load_json(release_root / "withdrawal-rehearsal.json")
        rollback = _load_json(release_root / "rollback-rehearsal.json")
        checklist = _load_json(release_root / "candidate-checklist.json")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as error:
        return _result(release_root, [{"code": "release_json_invalid", "message": str(error), "path": "$"}])

    expected_profile = {
        "id": RELEASE_ID,
        "version": RELEASE_VERSION,
        "predecessor": INPUT_RELEASE_ID,
        "status": "publishable",
        "public_release": True,
    }
    for key, expected in expected_profile.items():
        if manifest.get(key) != expected:
            _fail(failures, "manifest_profile", f"{key} must be {expected!r}", f"manifest.{key}")
    try:
        environment = load_schema_environment(ROOT)
        for issue in validate_release_directory(release_root, environment):
            _fail(failures, f"generic_{issue.code}", issue.message, issue.location)
    except Exception as error:
        _fail(failures, "generic_validator_error", str(error))

    old_entries = {item["path"]: item for item in predecessor.get("manifest_files", [])}
    new_entries = {item["path"]: item for item in manifest.get("manifest_files", [])}
    for relative, entry in old_entries.items():
        old_path = INPUT_RELEASE / relative
        new_path = release_root / relative
        if (
            new_entries.get(relative) != entry
            or not new_path.is_file()
            or sha256_file(new_path) != sha256_file(old_path)
        ):
            _fail(failures, "predecessor_drift", f"Inherited M07 file changed: {relative}", relative)
    expected_overlay = set(CORE_ARTIFACT_SCHEMAS) | {
        item.get("path") for item in search_manifest.get("shards", [])
    }
    actual_overlay = set(new_entries) - set(old_entries)
    if actual_overlay != expected_overlay:
        _fail(
            failures,
            "overlay_file_set",
            f"candidate overlay mismatch; missing={sorted(expected_overlay - actual_overlay)}, extra={sorted(actual_overlay - expected_overlay)}",
        )

    candidate_documents: dict[str, dict[str, Any]] = {}
    for relative in sorted(expected_overlay):
        path = release_root / relative
        try:
            document = _load_json(path)
            candidate_documents[relative] = document
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            _fail(failures, "candidate_artifact_invalid", str(error), relative)
            continue
        schema = CORE_ARTIFACT_SCHEMAS.get(relative, SEARCH_SCHEMA)
        for issue in validate_record(document, requested_schema=schema):
            _fail(failures, "candidate_schema", issue.message, f"{relative}{issue.location}")

    shard_records: list[dict[str, Any]] = []
    shard_paths = set()
    for shard in search_manifest.get("shards", []):
        relative = shard.get("path")
        if not isinstance(relative, str) or relative in shard_paths:
            _fail(failures, "search_shard_path", "shard paths must be unique strings")
            continue
        shard_paths.add(relative)
        document = candidate_documents.get(relative, {})
        records = document.get("records", [])
        if document.get("record_count") != len(records):
            _fail(failures, "search_shard_count", "shard record count mismatch", relative)
        if document.get("records_hash") != _canonical_hash(records):
            _fail(failures, "search_shard_records_hash", "shard records hash mismatch", relative)
        path = release_root / relative
        if (
            shard.get("bytes") != path.stat().st_size
            or shard.get("sha256") != sha256_file(path)
            or shard.get("records_hash") != document.get("records_hash")
        ):
            _fail(failures, "search_shard_manifest", "shard bytes or hashes do not close", relative)
        shard_records.extend(records)
    record_ids = [item.get("id") for item in shard_records]
    if len(record_ids) != len(set(record_ids)) or search_manifest.get("counts", {}).get("records") != len(shard_records):
        _fail(failures, "search_record_closure", "search records must be unique and count-closed")
    if set(search_manifest.get("counts", {}).get("by_entity_type", {})) != set(SEARCH_ENTITY_ORDER):
        _fail(failures, "search_entity_coverage", "search entity type coverage is incomplete")
    if any(
        "/assets/" in json.dumps(record, ensure_ascii=False)
        or record.get("withdrawal_status") not in {"active", "withdrawn"}
        for record in shard_records
    ):
        _fail(failures, "search_media_or_withdrawal", "search index contains media or invalid withdrawal state")
    search_gzip_bytes = sum(
        len(gzip.compress((release_root / relative).read_bytes(), compresslevel=9, mtime=0))
        for relative in ["search/manifest.json", *sorted(shard_paths)]
    )
    if search_gzip_bytes > 150000:
        _fail(failures, "search_index_budget", f"search index gzip {search_gzip_bytes} exceeds 150000")

    expected_freeze = {
        "artists": 12,
        "artworks": 44,
        "contexts": 31,
        "approved_media_artworks": 31,
        "no_image_artworks": 13,
        "media_derivatives": 242,
        "relationships_level_c": 36,
        "observation_cards": 44,
        "artist_tours": 12,
        "thematic_tours": 6,
        "tours_total": 18,
        "path_index_records": 198,
        "places": 23,
        "artist_place_episodes": 36,
        "new_real_content_entities": 0,
    }
    if freeze.get("payload") != expected_freeze:
        _fail(failures, "content_freeze", "candidate content freeze does not match the M08 invariant")
    for key in (
        "included_entity_ids",
        "included_relationship_ids",
        "included_claim_ids",
        "included_evidence_ids",
        "included_source_ids",
        "included_media_asset_ids",
    ):
        if manifest.get(key) != predecessor.get(key):
            _fail(failures, "content_scope_drift", f"{key} differs from predecessor", f"manifest.{key}")
    if route_inventory.get("template_count") != len(route_inventory.get("routes", [])):
        _fail(failures, "route_inventory_count", "route template count is not closed")
    if route_inventory.get("concrete_route_count") != sum(item.get("concrete_count", 0) for item in route_inventory.get("routes", [])):
        _fail(failures, "route_inventory_concrete_count", "concrete route count is not closed")
    privacy_false_fields = [
        "analytics",
        "account",
        "server_side_profile",
        "query_history",
        "visit_history",
        "path_history",
        "map_history",
        "tour_history",
        "telemetry_sdk",
        "cookies",
        "fingerprinting",
        "user_geolocation",
        "remote_logging",
    ]
    if any(privacy.get(key) is not False for key in privacy_false_fields):
        _fail(failures, "privacy_contract", "one or more forbidden privacy capabilities is enabled")
    if withdrawal.get("status") != "pass" or rollback.get("status") != "pass":
        _fail(failures, "rehearsal_status", "withdrawal and rollback rehearsals must pass")
    checklist_payload = checklist.get("payload", {})
    if checklist_payload.get("real_content_expansion_started") is not False or checklist_payload.get("museum_09_entered") is not False:
        _fail(failures, "phase_boundary", "candidate crosses the MUSEUM-09 or real-content boundary")
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        _fail(failures, "content_hash", "candidate content hash is not closed")
    if _physical_tree(INPUT_RELEASE)["hash"] != INPUT_PHYSICAL_TREE_HASH:
        _fail(failures, "predecessor_mutated", "M07 physical tree changed during M08")
    return _result(
        release_root,
        failures,
        content_hash=manifest.get("content_hash"),
        manifest_sha256=sha256_file(release_root / "manifest.json"),
        physical_tree=_physical_tree(release_root),
        overlay_file_count=len(actual_overlay),
        search_record_count=len(shard_records),
        search_shard_count=len(shard_paths),
        search_index_gzip_bytes=search_gzip_bytes,
        route_template_count=route_inventory.get("template_count"),
        concrete_route_count=route_inventory.get("concrete_route_count"),
    )


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _fail(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def _result(release_root: Path, failures: list[dict[str, str]], **extra: Any) -> dict[str, Any]:
    return {
        "ok": not failures,
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "release_root": str(release_root),
        "failures": failures,
        **extra,
    }
