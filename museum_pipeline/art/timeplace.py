from __future__ import annotations

import gzip
import json
import shutil
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import release_content_hash, validate_release_directory


PHASE_ID = "MUSEUM-07"
INPUT_RELEASE_ID = "release:art-pathways-1.2.0"
INPUT_RELEASE_HASH = "sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3"
INPUT_MANIFEST_SHA256 = "sha256:9eb27757c4888784bc79727ba7ce95179e313472a75b99a4b2098d3e4a6fb2dc"
RELEASE_ID = "release:art-time-place-1.3.0"
RELEASE_VERSION = "1.3.0"
BUILT_AT = "2026-07-16T16:00:00+08:00"
INPUT_RELEASE = ROOT / "public" / "releases" / "art-pathways-1.2.0"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-time-place-1.3.0"
RESEARCH_INPUT = ROOT / "research" / "art" / "museum-07-place-research.json"
BASEMAP_INPUT = ROOT / "data" / "reviewed" / "art" / "museum-07" / "basemap"

SCHEMA_BY_FILE = {
    "place-names.json": "schemas/art/map/place-name.schema.json",
    "place-identities.json": "schemas/art/map/place-identity.schema.json",
    "geospatial-claims.json": "schemas/art/map/geospatial-claim.schema.json",
    "artist-place-episodes.json": "schemas/art/map/artist-place-episode.schema.json",
    "artwork-place-claims.json": "schemas/art/map/artwork-place-claim.schema.json",
    "holding-locations.json": "schemas/art/map/holding-location.schema.json",
    "map-layer-config.json": "schemas/art/map/map-layer-config.schema.json",
    "map-style.json": "schemas/art/map/map-style-contract.schema.json",
    "map-index.json": "schemas/art/map/map-release-index.schema.json",
    "timeline-index.json": "schemas/art/map/map-release-index.schema.json",
    "filter-index.json": "schemas/art/map/map-release-index.schema.json",
    "map-view-state.json": "schemas/art/map/map-view-state.schema.json",
    "basemap-manifest.json": "schemas/art/map/map-basemap-manifest.schema.json",
    "map-source-attributions.json": "schemas/art/map/map-source-attribution.schema.json",
    "place-research-dispositions.json": "schemas/art/map/place-research-disposition.schema.json",
    "od-006-snapshot.json": "schemas/art/map/map-decision-snapshot.schema.json",
}
GEOJSON_FILES = {
    "basemap/land.geojson": "geojson:museum-07-natural-earth-land",
    "basemap/coastline.geojson": "geojson:museum-07-natural-earth-coastline",
    "basemap/lakes.geojson": "geojson:museum-07-natural-earth-lakes",
    "map-points.geojson": "geojson:museum-07-map-points",
}
EXPECTED_OVERLAY = set(SCHEMA_BY_FILE) | set(GEOJSON_FILES)
REFRESHED_INHERITED_FILES = {"claims.json", "source-rules-snapshot.json"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _base(entity_id: str, entity_type: str) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "id": entity_id, "entity_type": entity_type, "release_id": RELEASE_ID}


def _current_source_matrix_hash() -> str:
    registry = _load_json(ROOT / "research" / "source-registry" / "minimum-source-set.json")
    value = registry.get("source_matrix_snapshot_hash")
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError("current source identity matrix hash is unavailable")
    return value


def _refreshed_inherited_documents() -> dict[str, dict[str, Any]]:
    """Refresh only source identity bindings invalidated by adding Getty TGN.

    The M06 release remains immutable. The M07 overlay carries exact copies of its
    source governance records except for their binding to the now-current canonical
    identity matrix.
    """
    snapshot_hash = _current_source_matrix_hash()
    claims = _load_json(INPUT_RELEASE / "claims.json")
    source_snapshot = _load_json(INPUT_RELEASE / "source-rules-snapshot.json")
    for record in claims.get("records", []):
        data = record.get("data") if isinstance(record, dict) else None
        identity = data.get("registry_identity") if isinstance(data, dict) else None
        if isinstance(identity, dict):
            identity["snapshot_hash"] = snapshot_hash
    for source in source_snapshot.get("sources", []):
        identity = source.get("registry_identity") if isinstance(source, dict) else None
        if isinstance(identity, dict):
            identity["snapshot_hash"] = snapshot_hash
    source_snapshot["generated_at"] = BUILT_AT
    source_snapshot["snapshot_id"] = "source-rules:museum-07-art-time-place-1.3.0"
    return {"claims.json": claims, "source-rules-snapshot.json": source_snapshot}


def _build_artifacts(research: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    places = deepcopy(research["places"])
    episodes = deepcopy(research["episodes"])
    claims = deepcopy(research["claims"])
    holdings = deepcopy(research["holding_locations"])
    artwork_claims = deepcopy(research["artwork_creation_place_dispositions"])
    dispositions = deepcopy(research["research_dispositions"])

    place_names = []
    for place in places:
        for index, name in enumerate(place["names"], 1):
            place_names.append({
                "id": f"place-name:{place['tgn_id']}:{index:02d}", "place_id": place["id"],
                "text": name["text"], "language": name["language"], "name_type": name["name_type"],
                "valid_time": place["valid_time"] if name["name_type"] == "historical" else None,
                "source_id": "source:getty_tgn",
            })
    place_names.sort(key=lambda item: item["id"])

    layer_config = {
        **_base("map-layer-config:museum-07-v1", "map_layer_config"),
        "layers": [
            {"id": "background", "kind": "background", "source": "inline", "interactive": False, "visible_by_default": True},
            {"id": "land", "kind": "land", "source": "basemap/land.geojson", "interactive": False, "visible_by_default": True},
            {"id": "coastline", "kind": "coastline", "source": "basemap/coastline.geojson", "interactive": False, "visible_by_default": True},
            {"id": "lakes", "kind": "lakes", "source": "basemap/lakes.geojson", "interactive": False, "visible_by_default": True},
            {"id": "uncertainty", "kind": "uncertainty", "source": "map-points.geojson", "interactive": False, "visible_by_default": True},
            {"id": "artist-activity", "kind": "artist_episode", "source": "map-points.geojson", "interactive": True, "visible_by_default": True},
            {"id": "artwork-creation", "kind": "artwork_creation", "source": "map-points.geojson", "interactive": True, "visible_by_default": True},
            {"id": "current-holding", "kind": "current_holding", "source": "map-points.geojson", "interactive": True, "visible_by_default": False},
        ],
        "forbidden_layers": ["modern_political_boundaries", "roads", "commercial_poi", "traffic", "user_location", "terrain", "satellite", "3d_buildings", "globe", "travel_routes"],
    }
    style = {
        **_base("map-style:museum-07-v1", "map_style_contract"),
        "renderer": "maplibre-gl-js", "renderer_version": "5.24.0",
        "style": {
            "version": 8,
            "sources": {
                "land": {"type": "geojson", "data": "basemap/land.geojson"},
                "coastline": {"type": "geojson", "data": "basemap/coastline.geojson"},
                "lakes": {"type": "geojson", "data": "basemap/lakes.geojson"},
                "places": {"type": "geojson", "data": "map-points.geojson"},
            },
            "layers": [
                {"id": "background", "type": "background", "paint": {"background-color": "#08151a"}},
                {"id": "land", "type": "fill", "source": "land", "paint": {"fill-color": "#183038", "fill-opacity": 0.88}},
                {"id": "lakes", "type": "fill", "source": "lakes", "paint": {"fill-color": "#071116"}},
                {"id": "coastline", "type": "line", "source": "coastline", "paint": {"line-color": "#68858a", "line-width": 0.8}},
                {"id": "uncertainty-halos", "type": "circle", "source": "places", "filter": [">", ["get", "uncertaintyKm"], 25], "paint": {"circle-color": "#d6b978", "circle-opacity": 0.12, "circle-radius": ["interpolate", ["linear"], ["get", "uncertaintyKm"], 25, 10, 220, 30]}},
                {"id": "place-markers", "type": "circle", "source": "places", "paint": {"circle-color": ["match", ["get", "layer"], "current_holding_institution", "#cf7c68", "artwork_creation_place", "#9bb7e2", "#d6b978"], "circle-radius": 5, "circle-stroke-color": "#f5efe1", "circle-stroke-width": 1.2}},
            ],
        },
        "runtime_guards": {"remote_style": False, "tile_urls": False, "glyphs": False, "sprite": False, "image_urls": False, "geocoder": False, "telemetry": False, "geolocation": False, "pitch": 0, "bearing": 0, "rotation": False, "route_lines": False},
    }

    dated = [value for item in episodes for value in (item["start_year"], item["end_year"]) if value is not None]
    year_range = {"min": min(dated), "max": max(dated)}
    counts = deepcopy(research["counts"])
    counts["mapped_episode_points"] = sum(item["release_status"] == "verified_public" for item in episodes)
    counts["holding_location_points"] = len(holdings)
    artifacts_list = sorted(EXPECTED_OVERLAY)
    map_index = {
        **_base("map-index:museum-07-v1", "map_release_index"),
        "input_release_id": INPUT_RELEASE_ID, "input_release_hash": INPUT_RELEASE_HASH,
        "counts": counts, "year_range": year_range, "artifacts": artifacts_list,
        "performance": {
            "home_gzip_growth_percent_max": 2, "map_route_total_gzip_bytes_max": 550000,
            "renderer_js_css_gzip_bytes_max": 400000, "basemap_geojson_gzip_bytes_max": 250000,
            "place_timeline_filter_gzip_bytes_max": 100000, "desktop_first_interactive_ms_max": 1800,
            "mobile_first_interactive_ms_max": 2500, "filter_timeline_p95_ms_max": 150,
            "marker_selection_p95_ms_max": 100, "mobile_heap_increment_bytes_max": 41943040,
            "cls_max": 0.1, "external_runtime_requests_max": 0, "low_bandwidth_list_first_interactive_ms_max": 2000,
            "media_preload": False,
        },
        "limitations": [
            "Map locations are source-supported place claims, not a single cultural identity.",
            "Modern basemap outlines are not historical political borders.",
            "City centroids are not specific buildings.",
            "Chronological order is not a travel route.",
            "A current holding institution is not a creation place.",
            "An omitted place does not prove no activity occurred there.",
            "This map is not a complete biography.",
        ],
    }
    timeline = {
        **_base("timeline-index:museum-07-v1", "map_timeline_index"),
        "min_year": year_range["min"], "max_year": year_range["max"],
        "entries": [{
            "episode_id": item["id"], "artist_id": item["artist_id"], "place_id": item["place_id"],
            "start_year": item["start_year"], "end_year": item["end_year"], "date_precision": item["date_precision"],
            "release_status": item["release_status"],
        } for item in episodes],
    }
    artists = _load_json(INPUT_RELEASE / "artists.json")["artists"]
    artist_labels = {item["id"]: item["labels"] for item in artists}
    filter_index = {
        **_base("filter-index:museum-07-v1", "map_filter_index"),
        "facets": {
            "artists": [{"id": artist_id, "labels": artist_labels[artist_id], "count": count} for artist_id, count in sorted(Counter(item["artist_id"] for item in episodes).items())],
            "episode_types": [{"id": key, "count": value} for key, value in sorted(Counter(item["episode_type"] for item in episodes).items())],
            "regions": [{"id": key, "count": value} for key, value in sorted(Counter(next(place["region"] for place in places if place["id"] == item["place_id"]) for item in episodes).items())],
            "precisions": [{"id": key, "count": value} for key, value in sorted(Counter(item["place_precision"] for item in episodes).items())],
            "layers": [
                {"id": "artist_activity", "count": len(episodes)},
                {"id": "artwork_creation_place", "count": sum(item["status"] == "verified_public" for item in artwork_claims)},
                {"id": "current_holding_institution", "count": len(holdings)},
            ],
        },
    }
    view_state = {
        **_base("map-view-state:museum-07-v1", "map_view_state_contract"),
        "route": "#/art/map",
        "url_state_allowlist": ["artist", "place", "episodeType", "fromYear", "toYear", "region", "precision", "layer", "view", "episode"],
        "defaults": {"view": "map", "layer": "artist_activity", "extent": "world", "pitch": 0, "bearing": 0, "zoom_min": 0.7, "zoom_max": 8},
        "storage": "none", "external_runtime_api": False, "user_geolocation": False, "analytics": False,
        "history_collection": False, "fallbacks": ["timeline", "place_list"],
    }
    source_basemap = research["basemap_source_record"]
    basemap = {
        **_base("map-basemap-manifest:museum-07-natural-earth-110m", "map_basemap_manifest"),
        "source": source_basemap["source"], "source_page": source_basemap["source_page"],
        "physical_release_version": source_basemap["physical_release_version"], "scale": source_basemap["scale"],
        "downloaded_at": source_basemap["downloaded_at"], "license_decision": source_basemap["license_decision"],
        "attribution": source_basemap["attribution"], "conversion": source_basemap["conversion"],
        "layers": [{**item, "output_path": f"basemap/{item['layer']}.geojson"} for item in source_basemap["layers"]],
        "bundle_hash": source_basemap["bundle_hash"],
    }
    attributions = {
        **_base("map-source-attribution:museum-07-v1", "map_source_attribution_collection"),
        "sources": deepcopy(research["sources"]),
        "renderer_notice": {"name": "MapLibre GL JS", "version": "5.24.0", "license": "BSD-3-Clause", "repository": "https://github.com/maplibre/maplibre-gl-js", "exact_pin": True, "prerelease": False},
    }
    decision = {
        **_base("decision-snapshot:od-006-museum-07", "map_decision_snapshot"),
        "decision_id": "OD-006", "status": "closed", "decided_at": "2026-07-16",
        "basemap": "Natural Earth 1:110m land, coastline, and lakes; fully self-hosted",
        "renderer": "MapLibre GL JS 5.24.0 exact pin with automatic timeline/list fallback",
        "external_tile_provider": "none", "token_required": False, "modern_boundary_layer": False,
        "travel_routes": False, "open_decisions_count": 3, "remaining_open_decisions": ["OD-008", "OD-009", "OD-011"],
        "reopen_triggers": ["Natural Earth or Getty terms materially change", "MapLibre no longer passes local-only, accessibility, security, or bundle gates"],
    }
    artifact_documents = {
        "place-names.json": {**_base("place-name-collection:museum-07-v1", "place_name_collection"), "names": place_names},
        "place-identities.json": {**_base("place-identity-collection:museum-07-v1", "place_identity_collection"), "places": places},
        "geospatial-claims.json": {**_base("geospatial-claim-collection:museum-07-v1", "geospatial_claim_collection"), "claims": claims},
        "artist-place-episodes.json": {**_base("artist-place-episode-collection:museum-07-v1", "artist_place_episode_collection"), "episodes": episodes},
        "artwork-place-claims.json": {**_base("artwork-place-claim-collection:museum-07-v1", "artwork_place_claim_collection"), "claims": artwork_claims},
        "holding-locations.json": {**_base("holding-location-collection:museum-07-v1", "holding_location_collection"), "locations": holdings},
        "map-layer-config.json": layer_config, "map-style.json": style, "map-index.json": map_index,
        "timeline-index.json": timeline, "filter-index.json": filter_index, "map-view-state.json": view_state,
        "basemap-manifest.json": basemap, "map-source-attributions.json": attributions,
        "place-research-dispositions.json": {**_base("place-research-disposition-collection:museum-07-v1", "place_research_disposition_collection"), "dispositions": dispositions},
        "od-006-snapshot.json": decision,
    }
    place_by_id = {item["id"]: item for item in places}
    map_features = []
    for episode in episodes:
        if episode["release_status"] != "verified_public":
            continue
        place = place_by_id[episode["place_id"]]
        map_features.append({
            "type": "Feature", "id": episode["id"], "geometry": {"type": "Point", "coordinates": place["coordinates"]},
            "properties": {"episodeId": episode["id"], "artistId": episode["artist_id"], "placeId": place["id"],
                "episodeType": episode["episode_type"], "precision": episode["place_precision"], "layer": "artist_activity",
                "uncertaintyKm": place["uncertainty_radius_km"] or 0},
        })
    for holding in holdings:
        place = place_by_id[holding["place_id"]]
        map_features.append({
            "type": "Feature", "id": holding["id"], "geometry": {"type": "Point", "coordinates": place["coordinates"]},
            "properties": {"holdingId": holding["id"], "placeId": place["id"], "layer": "current_holding_institution",
                "precision": place["coordinate_precision"], "uncertaintyKm": place["uncertainty_radius_km"] or 0},
        })
    map_features.sort(key=lambda item: item["id"])
    return artifact_documents, {"type": "FeatureCollection", "features": map_features}


def _validate_artifact_documents(artifacts: dict[str, dict[str, Any]]) -> None:
    for filename, document in artifacts.items():
        issues = validate_record(document, requested_schema=SCHEMA_BY_FILE[filename])
        if issues:
            raise ValueError(f"{filename} {issues[0].location}: {issues[0].message}")


def build_museum_07_release(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    predecessor = _load_json(INPUT_RELEASE / "manifest.json")
    if predecessor.get("id") != INPUT_RELEASE_ID or predecessor.get("content_hash") != INPUT_RELEASE_HASH:
        raise ValueError("MUSEUM-06 predecessor hash mismatch")
    if sha256_file(INPUT_RELEASE / "manifest.json") != INPUT_MANIFEST_SHA256:
        raise ValueError("MUSEUM-06 predecessor manifest SHA mismatch")
    research = _load_json(RESEARCH_INPUT)
    if research.get("input_release_hash") != INPUT_RELEASE_HASH or research.get("counts", {}).get("episodes") != 36:
        raise ValueError("MUSEUM-07 reviewed research input is not closed")
    artifacts, map_points = _build_artifacts(research)
    refreshed_inherited = _refreshed_inherited_documents()
    _validate_artifact_documents(artifacts)
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-07-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        staged.mkdir(parents=True)
        for source in INPUT_RELEASE.rglob("*"):
            if not source.is_file() or source.name == "manifest.json":
                continue
            destination = staged / source.relative_to(INPUT_RELEASE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        for filename, document in artifacts.items():
            path = staged / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_json_bytes(document))
        for filename, document in refreshed_inherited.items():
            (staged / filename).write_bytes(canonical_json_bytes(document))
        for layer in ("land", "coastline", "lakes"):
            destination = staged / "basemap" / f"{layer}.geojson"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(BASEMAP_INPUT / f"{layer}.geojson", destination)
        (staged / "map-points.geojson").write_bytes(canonical_json_bytes(map_points))
        entries = [deepcopy(item) for item in predecessor["manifest_files"] if item["path"] not in REFRESHED_INHERITED_FILES]
        inherited_entries = {item["path"]: item for item in predecessor["manifest_files"]}
        for filename in sorted(REFRESHED_INHERITED_FILES):
            path = staged / filename
            entry = deepcopy(inherited_entries[filename])
            entry.update({"bytes": path.stat().st_size, "sha256": sha256_file(path, prefixed=False)})
            entries.append(entry)
        for filename, document in artifacts.items():
            path = staged / filename
            entries.append({"bytes": path.stat().st_size, "path": filename, "record_ids": [document["id"]],
                "record_type": "other", "schema_path": SCHEMA_BY_FILE[filename], "sha256": sha256_file(path, prefixed=False)})
        for filename, record_id in GEOJSON_FILES.items():
            path = staged / filename
            entries.append({"bytes": path.stat().st_size, "path": filename, "record_ids": [record_id],
                "record_type": "other", "schema_path": None, "sha256": sha256_file(path, prefixed=False)})
        entries.sort(key=lambda item: item["path"])
        manifest = deepcopy(predecessor)
        manifest.update({
            "id": RELEASE_ID, "version": RELEASE_VERSION, "build_version": "museum-07-v1", "created_at": BUILT_AT,
            "predecessor": INPUT_RELEASE_ID, "manifest_files": entries,
            "content_hash": release_content_hash(entries),
            "release_notes": "Immutable art time/place overlay with source-closed Getty TGN identities, 36 bounded artist episodes, a separate current-holding layer, explicit not-asserted creation-place dispositions, fully self-hosted Natural Earth 1:110m GeoJSON, and equivalent map/timeline/list experiences. No political borders, inferred travel routes, tile provider, token, runtime geocoder, geolocation, analytics, history collection, or human item-by-item review is added.",
        })
        manifest["source_registry_manifest"] = {
            "path": "source-rules-snapshot.json",
            "sha256": next(item["sha256"] for item in entries if item["path"] == "source-rules-snapshot.json"),
        }
        manifest["schema_versions"] = {**predecessor["schema_versions"], **{
            path.removeprefix("schemas/").removesuffix(".schema.json"): "1.0.0"
            for path in sorted(set(SCHEMA_BY_FILE.values()))
        }}
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        validation = validate_museum_07_release(staged)
        if not validation["ok"]:
            raise ValueError("staged MUSEUM-07 release failed: " + json.dumps(validation["failures"][:16], ensure_ascii=False))
        if output_dir.exists():
            if _file_hashes(output_dir) != _file_hashes(staged):
                raise ValueError(f"immutable output already exists with different bytes: {output_dir}")
        else:
            shutil.copytree(staged, output_dir)
    return validate_museum_07_release(output_dir)


def validate_museum_07_release(release_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    release_root = release_root.resolve()
    if not release_root.is_dir():
        return _result(release_root, [{"code": "release_missing", "message": "release directory missing", "path": "$"}])
    try:
        predecessor = _load_json(INPUT_RELEASE / "manifest.json")
        manifest = _load_json(release_root / "manifest.json")
        places_doc = _load_json(release_root / "place-identities.json")
        episodes_doc = _load_json(release_root / "artist-place-episodes.json")
        claims_doc = _load_json(release_root / "geospatial-claims.json")
        artworks_doc = _load_json(release_root / "artwork-place-claims.json")
        holdings_doc = _load_json(release_root / "holding-locations.json")
        points_doc = _load_json(release_root / "map-points.geojson")
        attributions = _load_json(release_root / "map-source-attributions.json")
        style = _load_json(release_root / "map-style.json")
        basemap = _load_json(release_root / "basemap-manifest.json")
        decision = _load_json(release_root / "od-006-snapshot.json")
        map_index = _load_json(release_root / "map-index.json")
    except (OSError, json.JSONDecodeError, KeyError) as error:
        return _result(release_root, [{"code": "release_json_invalid", "message": str(error), "path": "$"}])
    for key, expected in {"id": RELEASE_ID, "version": RELEASE_VERSION, "predecessor": INPUT_RELEASE_ID, "status": "publishable", "public_release": True}.items():
        if manifest.get(key) != expected:
            _fail(failures, "manifest_profile", f"{key} must be {expected!r}", f"manifest.{key}")
    try:
        for issue in validate_release_directory(release_root, load_schema_environment(ROOT)):
            _fail(failures, f"generic_{issue.code}", issue.message, issue.location)
    except Exception as error:
        _fail(failures, "generic_validator_error", str(error))
    old_entries = {item["path"]: item for item in predecessor["manifest_files"]}
    new_entries = {item["path"]: item for item in manifest.get("manifest_files", [])}
    for path, entry in old_entries.items():
        if path in REFRESHED_INHERITED_FILES:
            continue
        if new_entries.get(path) != entry or not (release_root / path).is_file() or (release_root / path).read_bytes() != (INPUT_RELEASE / path).read_bytes():
            _fail(failures, "predecessor_drift", f"Inherited M06 artifact changed: {path}", path)
    expected_refreshed = _refreshed_inherited_documents()
    for path, document in expected_refreshed.items():
        expected_bytes = canonical_json_bytes(document)
        entry = new_entries.get(path, {})
        if (release_root / path).read_bytes() != expected_bytes or entry.get("sha256") != sha256_file(release_root / path, prefixed=False):
            _fail(failures, "source_identity_refresh", f"M07 source identity refresh is not exact: {path}", path)
    if set(new_entries) - set(old_entries) != EXPECTED_OVERLAY:
        _fail(failures, "overlay_file_set", "M07 overlay file set is not exact")

    places = places_doc.get("places", [])
    episodes = episodes_doc.get("episodes", [])
    claims = claims_doc.get("claims", [])
    artwork_claims = artworks_doc.get("claims", [])
    holdings = holdings_doc.get("locations", [])
    if len(places) != 23 or len(episodes) != 36 or len(artwork_claims) != 44 or len(holdings) != 2:
        _fail(failures, "count_closure", "Expected 23 places, 36 episodes, 44 artwork dispositions, and 2 holding institutions")
    artist_counts = Counter(item.get("artist_id") for item in episodes)
    if len(artist_counts) != 12 or any(not 2 <= count <= 5 for count in artist_counts.values()) or set(artist_counts.values()) != {3}:
        _fail(failures, "artist_episode_coverage", "Each of the 12 artists must have exactly three public/list-only episodes")
    for artist_id in artist_counts:
        types = {item.get("episode_type") for item in episodes if item.get("artist_id") == artist_id}
        if not {"birth", "death"} <= types:
            _fail(failures, "birth_death_coverage", f"{artist_id} lacks birth/death coverage")
    place_ids = {item.get("id") for item in places}
    episode_ids = {item.get("id") for item in episodes}
    claim_ids = {item.get("id") for item in claims}
    source_ids = {item.get("id") for item in attributions.get("sources", [])}
    evidence_ids = {item.get("id") for episode in episodes for item in episode.get("evidence", [])}
    for episode in episodes:
        if episode.get("place_id") not in place_ids or episode.get("claim_id") not in claim_ids:
            _fail(failures, "episode_reference", f"{episode.get('id')} has an unresolved place or claim")
        if set(episode.get("source_ids", [])) - source_ids:
            _fail(failures, "episode_source", f"{episode.get('id')} has an unresolved source")
    for claim in claims:
        if claim.get("episode_id") not in episode_ids or claim.get("place_id") not in place_ids:
            _fail(failures, "claim_reference", f"{claim.get('id')} has an unresolved episode or place")
        if set(claim.get("evidence_ids", [])) - evidence_ids or set(claim.get("source_ids", [])) - source_ids:
            _fail(failures, "claim_evidence_source", f"{claim.get('id')} lacks Claim/Evidence/Source closure")
    for place in places:
        coordinates = place.get("coordinates")
        precision = place.get("coordinate_precision")
        if coordinates is None and (precision != "unknown" or place.get("release_status") != "verified_list_only"):
            _fail(failures, "unknown_coordinate_state", f"{place.get('id')} must remain list-only")
        if precision == "city_centroid" and place.get("geometry_type") != "Point":
            _fail(failures, "city_centroid_geometry", f"{place.get('id')} cannot imply a building")
        if precision == "regional_centroid" and (place.get("uncertainty_radius_km") or 0) < 100:
            _fail(failures, "regional_uncertainty", f"{place.get('id')} needs a visible uncertainty radius")
    point_ids = {item.get("id") for item in points_doc.get("features", [])}
    for feature in points_doc.get("features", []):
        if feature.get("geometry", {}).get("type") != "Point":
            _fail(failures, "route_geometry_forbidden", "Map points must not contain inferred route lines")
    for episode in episodes:
        if (episode.get("release_status") == "verified_public") != (episode.get("id") in point_ids):
            _fail(failures, "map_point_disposition", f"{episode.get('id')} map visibility differs from release disposition")
    formal_artwork_ids = {item["id"] for item in _load_json(INPUT_RELEASE / "artworks.json")["artworks"]}
    if {item.get("artwork_id") for item in artwork_claims} != formal_artwork_ids or any(item.get("status") != "not_asserted" or item.get("place_id") is not None for item in artwork_claims):
        _fail(failures, "creation_place_fail_closed", "All 44 creation places must remain explicit not_asserted without proxy inference")
    if set().union(*(set(item.get("artwork_ids", [])) for item in holdings)) != formal_artwork_ids:
        _fail(failures, "holding_closure", "Holding locations must cover exactly the 44 formal artworks")
    for holding in holdings:
        if "not an artwork creation place" not in holding.get("does_not_prove", ""):
            _fail(failures, "holding_creation_separation", f"{holding.get('id')} does not state the separation")

    runtime_contract = json.dumps({"style": style.get("style"), "view": _load_json(release_root / "map-view-state.json"), "layers": _load_json(release_root / "map-layer-config.json")}, sort_keys=True).lower()
    for token in ("http://", "https://", "tiles", "access_token", "mapbox", "geolocatecontrol", "navigator.geolocation", "glyphs\":", "sprite\":"):
        if token in runtime_contract:
            _fail(failures, "remote_runtime_reference", f"Forbidden runtime token: {token}")
    if decision.get("status") != "closed" or decision.get("open_decisions_count") != 3:
        _fail(failures, "od_006", "OD-006 must be closed with exactly three remaining decisions")
    if style.get("renderer_version") != "5.24.0" or style.get("runtime_guards", {}).get("route_lines") is not False:
        _fail(failures, "renderer_contract", "Stable renderer and no-route contract are not exact")
    if basemap.get("attribution") != "Made with Natural Earth" or basemap.get("license_decision") != "public_domain":
        _fail(failures, "basemap_rights", "Natural Earth public-domain decision and attribution are required")
    for layer in basemap.get("layers", []):
        path = release_root / layer["output_path"]
        if path.stat().st_size != layer["output_bytes"] or sha256_file(path) != layer["output_sha256"]:
            _fail(failures, "basemap_hash", f"Basemap output mismatch: {layer['layer']}")
    basemap_gzip = sum(len(gzip.compress((release_root / f"basemap/{layer}.geojson").read_bytes(), compresslevel=9, mtime=0)) for layer in ("land", "coastline", "lakes"))
    data_gzip = sum(len(gzip.compress((release_root / name).read_bytes(), compresslevel=9, mtime=0)) for name in ("place-identities.json", "artist-place-episodes.json", "timeline-index.json", "filter-index.json", "map-points.geojson"))
    if basemap_gzip > 250000:
        _fail(failures, "basemap_budget", f"Basemap gzip {basemap_gzip} exceeds 250000")
    if data_gzip > 100000:
        _fail(failures, "map_data_budget", f"Map data gzip {data_gzip} exceeds 100000")
    public_map_text = json.dumps({"places": places_doc, "episodes": episodes_doc, "claims": claims_doc}, ensure_ascii=False).lower()
    for token in ("waiting for human", "pending user", "guessed coordinate", "relationship-lead:"):
        if token in public_map_text:
            _fail(failures, "private_or_human_state", f"Forbidden public state: {token}")
    if map_index.get("counts", {}).get("list_only_episodes") != 12:
        _fail(failures, "list_only_count", "Expected 12 list-only episodes")
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        _fail(failures, "content_hash", "Release content hash does not match manifest files")
    return _result(release_root, failures, {
        "place_identity_count": len(places), "artist_episode_count": len(episodes),
        "artwork_creation_place_count": sum(item.get("status") == "verified_public" for item in artwork_claims),
        "holding_institution_count": len(holdings), "list_only_episode_count": sum(item.get("release_status") == "verified_list_only" for item in episodes),
        "basemap_gzip_bytes": basemap_gzip, "map_data_gzip_bytes": data_gzip,
    }, manifest.get("content_hash"))


def _file_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file()}


def _fail(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def _result(root: Path, failures: list[dict[str, str]], counts: dict[str, Any] | None = None, content_hash: str | None = None) -> dict[str, Any]:
    return {"ok": not failures, "phase_id": PHASE_ID, "release_root": str(root), "failures": failures,
        "codes": sorted({item["code"] for item in failures}), "counts": counts or {}, "content_hash": content_hash}
