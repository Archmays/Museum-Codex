#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import warnings
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
import sys

import shapefile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import canonical_sha256, sha256_file


PHASE_ID = "MUSEUM-07"
BUILT_AT = "2026-07-16T14:00:00+08:00"
TGN_ROOT = ROOT / "data" / "map-source" / "getty-tgn" / "2026-07-16"
NE_ROOT = ROOT / "data" / "map-source" / "natural-earth" / "5.1.0"
KOLLWITZ_BIOGRAPHY = ROOT / "data" / "map-source" / "official" / "kollwitz-museum" / "2026-07-16" / "biography.html"
BASEMAP_OUTPUT = ROOT / "data" / "reviewed" / "art" / "museum-07" / "basemap"
RESEARCH_OUTPUT = ROOT / "research" / "art" / "museum-07-place-research.json"
ART_RELEASE = ROOT / "public" / "releases" / "art-pathways-1.2.0"

NE_LAYERS = {
    "land": {"archive": "ne_110m_land.zip", "stem": "ne_110m_land", "theme_version": "4.0.0"},
    "coastline": {"archive": "ne_110m_coastline.zip", "stem": "ne_110m_coastline", "theme_version": "4.1.0"},
    "lakes": {"archive": "ne_110m_lakes.zip", "stem": "ne_110m_lakes", "theme_version": "5.0.0"},
}

ARTISTS = {
    "artist:albrecht-durer": "500115493",
    "artist:francisco-de-goya": "500118936",
    "artist:henry-ossawa-tanner": "500005351",
    "artist:jose-guadalupe-posada": "500032573",
    "artist:julia-margaret-cameron": "500118804",
    "artist:kathe-kollwitz": "500016751",
    "artist:katsushika-hokusai": "500060426",
    "artist:kitagawa-utamaro": "500054492",
    "artist:mary-cassatt": "500012368",
    "artist:raja-ravi-varma": "500122641",
    "artist:shen-zhou": "500121310",
    "artist:vincent-van-gogh": "500115588",
}

KOLLWITZ_PLACES = {"born": "7013050", "died": "7012846"}

PLACE_OVERRIDES = {
    "1000110": {"current": "Sri Lanka", "historical": "Ceylon", "zh": "斯里兰卡（历史称锡兰）", "region": "South Asia", "precision": "regional_centroid", "radius": 220},
    "1016954": {"current": "Aguascalientes", "historical": "Aguascalientes", "zh": "阿瓜斯卡连特斯", "region": "Mexico", "precision": "city_centroid", "radius": 25},
    "1080492": {"current": "Kawagoe", "historical": "Kawagoe", "zh": "川越", "region": "East Asia", "precision": "city_centroid", "radius": 25},
    "1139797": {"current": "Xiangcheng, Suzhou", "historical": "Xiangcheng in the Suzhou region", "zh": "苏州相城地区", "region": "East Asia", "precision": "city_centroid", "radius": 25},
    "7003712": {"current": "Berlin", "historical": "Berlin", "zh": "柏林", "region": "Central Europe", "precision": "city_centroid", "radius": 25},
    "7004334": {"current": "Nuremberg", "historical": "Nuremberg", "zh": "纽伦堡", "region": "Central Europe", "precision": "city_centroid", "radius": 25},
    "7004472": {"current": "Tokyo", "historical": "Edo", "zh": "江户（今东京）", "region": "East Asia", "precision": "city_centroid", "radius": 25, "valid_time": {"historical_label_until": 1868}},
    "7006823": {"current": "Zundert", "historical": "Zundert", "zh": "津德尔特", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7007227": {"current": "Mexico City", "historical": "Mexico City", "zh": "墨西哥城", "region": "Mexico", "precision": "unknown", "radius": None, "coordinate_issue": "upstream_invalid_coordinate_string"},
    "7007567": {"current": "New York City", "historical": "New York", "zh": "纽约市", "region": "North America", "precision": "city_centroid", "radius": 25},
    "7008030": {"current": "Auvers-sur-Oise", "historical": "Auvers-sur-Oise", "zh": "奥维尔-叙尔-瓦兹", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7008038": {"current": "Paris", "historical": "Paris", "zh": "巴黎", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7008161": {"current": "Bordeaux", "historical": "Bordeaux", "zh": "波尔多", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7008775": {"current": "Arles", "historical": "Arles", "zh": "阿尔勒", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7012846": {"current": "Moritzburg", "historical": "Moritzburg near Dresden", "zh": "德累斯顿附近莫里茨堡", "region": "Central Europe", "precision": "city_centroid", "radius": 25},
    "7013050": {"current": "Kaliningrad", "historical": "Königsberg", "zh": "柯尼斯堡（今加里宁格勒）", "region": "Baltic region", "precision": "city_centroid", "radius": 25, "valid_time": {"historical_label_until": 1946}},
    "7013596": {"current": "Chicago", "historical": "Chicago", "zh": "芝加哥", "region": "North America", "precision": "city_centroid", "radius": 25},
    "7013927": {"current": "Pittsburgh", "historical": "Pittsburgh", "zh": "匹兹堡", "region": "North America", "precision": "city_centroid", "radius": 25},
    "7029464": {"current": "Le Mesnil-Théribus", "historical": "Le Mesnil-Théribus", "zh": "勒梅尼勒-泰里比斯", "region": "Western Europe", "precision": "city_centroid", "radius": 25},
    "7029465": {"current": "Allegheny City", "historical": "Allegheny City", "zh": "阿勒格尼城", "region": "North America", "precision": "unknown", "radius": None, "coordinate_issue": "source_has_no_coordinate"},
    "7030444": {"current": "Fuendetodos", "historical": "Fuendetodos", "zh": "丰德托多斯", "region": "Iberia", "precision": "city_centroid", "radius": 25},
    "7030776": {"current": "Kolkata", "historical": "Calcutta", "zh": "加尔各答", "region": "South Asia", "precision": "city_centroid", "radius": 25},
    "7574482": {"current": "Kilimanoor", "historical": "Kilimanoor in Travancore", "zh": "基利马诺尔（特拉凡哥尔）", "region": "South Asia", "precision": "city_centroid", "radius": 25},
}

ACTIVITY_EPISODES = {
    "artist:albrecht-durer": {"place": "7004334", "type": "documented_activity", "role": "activity scope", "start": None, "end": None, "precision": "unknown", "basis": "claim:albrecht-durer-activity-scope"},
    "artist:francisco-de-goya": {"place": "7008161", "type": "residence", "role": "activity scope includes Bordeaux", "start": None, "end": None, "precision": "unknown", "basis": "claim:francisco-de-goya-activity-scope"},
    "artist:henry-ossawa-tanner": {"place": "7008038", "type": "documented_activity", "role": "activity scope includes Paris", "start": None, "end": None, "precision": "unknown", "basis": "claim:henry-ossawa-tanner-activity-scope"},
    "artist:jose-guadalupe-posada": {"place": "7007227", "type": "publication_or_print_activity", "role": "print activity scope includes Mexico City", "start": None, "end": None, "precision": "unknown", "basis": "claim:jose-guadalupe-posada-activity-scope"},
    "artist:julia-margaret-cameron": {"place": "1000110", "type": "residence", "role": "activity scope includes British Ceylon", "start": None, "end": None, "precision": "unknown", "basis": "claim:julia-margaret-cameron-activity-scope"},
    "artist:kathe-kollwitz": {"place": "7003712", "type": "studio", "role": "lived and worked in Berlin", "start": 1891, "end": 1943, "precision": "year_range", "basis": "https://www.kollwitz.de/biography", "official": True},
    "artist:katsushika-hokusai": {"place": "7004472", "type": "documented_activity", "role": "documented activity in Edo", "start": 1780, "end": 1849, "precision": "year_range", "basis": "http://vocab.getty.edu/ulan/time/active/133371"},
    "artist:kitagawa-utamaro": {"place": "7004472", "type": "publication_or_print_activity", "role": "activity scope in Edo", "start": None, "end": None, "precision": "unknown", "basis": "claim:kitagawa-utamaro-activity-scope"},
    "artist:mary-cassatt": {"place": "7008038", "type": "documented_activity", "role": "activity scope includes Paris", "start": None, "end": None, "precision": "unknown", "basis": "claim:mary-cassatt-activity-scope"},
    "artist:raja-ravi-varma": {"place": "7574482", "type": "documented_activity", "role": "activity scope includes Kilimanoor", "start": None, "end": None, "precision": "unknown", "basis": "claim:raja-ravi-varma-activity-scope"},
    "artist:shen-zhou": {"place": "1139797", "type": "documented_activity", "role": "activity scope in the Suzhou region", "start": None, "end": None, "precision": "unknown", "basis": "claim:shen-zhou-activity-scope"},
    "artist:vincent-van-gogh": {"place": "7008775", "type": "documented_activity", "role": "activity scope includes Arles", "start": None, "end": None, "precision": "unknown", "basis": "claim:vincent-van-gogh-activity-scope"},
}


def _round_coordinates(value: Any) -> Any:
    if isinstance(value, list):
        return [_round_coordinates(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _iter_positions(value: Any):
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_positions(item)


def build_basemap() -> dict[str, Any]:
    BASEMAP_OUTPUT.mkdir(parents=True, exist_ok=True)
    layer_records = []
    for layer, config in NE_LAYERS.items():
        archive_path = NE_ROOT / config["archive"]
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            stem = config["stem"]
            reader = shapefile.Reader(
                shp=io.BytesIO(archive.read(f"{stem}.shp")),
                shx=io.BytesIO(archive.read(f"{stem}.shx")),
                dbf=io.BytesIO(archive.read(f"{stem}.dbf")),
            )
            features = []
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for shape in reader.iterShapes():
                    geometry = _round_coordinates(shape.__geo_interface__)
                    geometry.pop("bbox", None)
                    for position in _iter_positions(geometry.get("coordinates")):
                        if not -180 <= position[0] <= 180 or not -90 <= position[1] <= 90:
                            raise ValueError(f"{layer} has an invalid WGS84 coordinate")
                    features.append({"type": "Feature", "properties": {}, "geometry": geometry})
        features.sort(key=lambda item: canonical_sha256(item["geometry"]))
        for index, feature in enumerate(features, 1):
            feature["id"] = f"natural-earth:{layer}:{index:04d}"
        collection = {"type": "FeatureCollection", "features": features}
        output_path = BASEMAP_OUTPUT / f"{layer}.geojson"
        output_path.write_bytes(canonical_json_bytes(collection))
        layer_records.append({
            "layer": layer,
            "theme_version": config["theme_version"],
            "source_filename": config["archive"],
            "source_bytes": archive_path.stat().st_size,
            "source_sha256": sha256_file(archive_path),
            "output_path": output_path.relative_to(ROOT).as_posix(),
            "output_bytes": output_path.stat().st_size,
            "output_sha256": sha256_file(output_path),
            "feature_count": len(features),
        })
    manifest = {
        "schema_version": "1.0.0",
        "id": "map-basemap-source:museum-07-natural-earth-110m",
        "entity_type": "map_basemap_source_record",
        "phase_id": PHASE_ID,
        "source": "Natural Earth",
        "source_page": "https://www.naturalearthdata.com/downloads/110m-physical-vectors/",
        "official_archive_host": "naturalearth.s3.amazonaws.com",
        "physical_release_version": "5.1.0",
        "scale": "1:110m",
        "downloaded_at": "2026-07-16",
        "license_decision": "public_domain",
        "attribution": "Made with Natural Earth",
        "conversion": {
            "tool": "pyshp",
            "version": shapefile.__version__,
            "recipe_version": "museum-ne-shapefile-to-canonical-geojson-1.0.0",
            "crs": "WGS84",
            "properties": "removed",
            "coordinate_rounding_decimals": 6,
            "simplification": "none",
            "antimeridian_policy": "preserve source WGS84 coordinates in [-180,180] without jitter or route wrapping",
            "stable_order": "canonical geometry hash",
        },
        "layers": layer_records,
        "status": "verified",
    }
    manifest["bundle_hash"] = canonical_sha256({"layers": layer_records, "conversion": manifest["conversion"]})
    (BASEMAP_OUTPUT / "basemap-source-record.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def _load_ulan_records() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    records: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted((ROOT / "data" / "raw" / "getty_ulan").rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = manifest.get("source_object_ids", [])
        body_path = manifest_path.parent / "response.body"
        if not body_path.is_file():
            continue
        body = json.loads(body_path.read_text(encoding="utf-8"))
        if len(ids) != 1 and isinstance(body, dict) and isinstance(body.get("id"), str):
            ids = [body["id"].rsplit("/", 1)[-1]]
        if len(ids) != 1 or ids[0] not in set(ARTISTS.values()):
            continue
        records[ids[0]] = body
        evidence[ids[0]] = {
            "uri": f"https://vocab.getty.edu/ulan/{ids[0]}.json",
            "record_sha256": sha256_file(body_path),
            "snapshot_id": manifest.get("snapshot_id"),
            "fetched_at": manifest.get("fetched_at"),
        }
    missing = set(ARTISTS.values()) - set(records)
    if missing:
        raise ValueError(f"Missing ULAN source snapshots: {sorted(missing)}")
    return records, evidence


def _parse_coordinate(document: dict[str, Any]) -> tuple[list[float] | None, str | None]:
    for item in document.get("identified_by", []):
        if not isinstance(item, dict):
            continue
        labels = [part.get("_label") for part in item.get("classified_as", []) if isinstance(part, dict)]
        if "GeoJSON Coordinate Point" not in labels:
            continue
        raw = item.get("value")
        if not isinstance(raw, str):
            return None, "source_has_no_coordinate"
        try:
            coordinate = json.loads(raw)
        except json.JSONDecodeError:
            return None, "upstream_invalid_coordinate_string"
        if (
            not isinstance(coordinate, list) or len(coordinate) != 2
            or not all(isinstance(value, (int, float)) for value in coordinate)
            or not -180 <= coordinate[0] <= 180 or not -90 <= coordinate[1] <= 90
        ):
            return None, "upstream_invalid_coordinate_value"
        return [round(float(coordinate[0]), 6), round(float(coordinate[1]), 6)], None
    return None, "source_has_no_coordinate"


def _names(document: dict[str, Any], override: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in document.get("identified_by", []):
        if not isinstance(item, dict) or item.get("type") != "Name" or not isinstance(item.get("content"), str):
            continue
        classifications = " ".join(
            part.get("_label", "") for part in item.get("classified_as", []) if isinstance(part, dict)
        ).lower()
        language = "und"
        if isinstance(item.get("language"), list) and item["language"] and isinstance(item["language"][0], dict):
            language = item["language"][0].get("_label", "und")
        name_type = "historical" if "historical term" in classifications else "preferred" if "preferred term" in classifications else "alternate"
        candidate = {"text": item["content"], "language": language, "name_type": name_type}
        if candidate not in output and (name_type != "alternate" or language in {"en", "und"}):
            output.append(candidate)
    for candidate in (
        {"text": override["historical"], "language": "en", "name_type": "historical"},
        {"text": override["current"], "language": "en", "name_type": "current"},
        {"text": override["zh"], "language": "zh-Hans", "name_type": "translated_display"},
    ):
        if candidate not in output:
            output.append(candidate)
    return sorted(output, key=lambda item: (item["name_type"], item["language"], item["text"]))[:12]


def _tgn_places() -> dict[str, dict[str, Any]]:
    places: dict[str, dict[str, Any]] = {}
    for tgn_id, override in sorted(PLACE_OVERRIDES.items()):
        path = TGN_ROOT / f"{tgn_id}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("id") != f"http://vocab.getty.edu/tgn/{tgn_id}":
            raise ValueError(f"TGN identity mismatch: {tgn_id}")
        coordinate, issue = _parse_coordinate(document)
        expected_issue = override.get("coordinate_issue")
        if expected_issue and issue != expected_issue:
            raise ValueError(f"TGN coordinate issue drift: {tgn_id}: {issue}")
        if override["precision"] == "unknown":
            coordinate = None
        parents = [
            {"authority_id": item.get("id"), "label": item.get("_label")}
            for item in document.get("part_of", []) if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        place_types = sorted({
            item.get("_label") for item in document.get("classified_as", [])
            if isinstance(item, dict) and isinstance(item.get("_label"), str)
        })
        places[tgn_id] = {
            "schema_version": "1.0.0",
            "id": f"place:tgn-{tgn_id}",
            "entity_type": "place_identity",
            "tgn_id": tgn_id,
            "tgn_uri": f"http://vocab.getty.edu/tgn/{tgn_id}",
            "preferred_historical_label": override["historical"],
            "current_common_label": override["current"],
            "labels": {"zh-Hans": override["zh"], "en": override["current"], "source": document["_label"]},
            "names": _names(document, override),
            "place_types": place_types or ["place"],
            "broader_hierarchy": parents,
            "coordinates": coordinate,
            "coordinate_source": f"http://vocab.getty.edu/tgn/{tgn_id}",
            "coordinate_precision": override["precision"],
            "geometry_type": "Point" if coordinate is not None else "none",
            "uncertainty_radius_km": override["radius"],
            "valid_time": override.get("valid_time"),
            "modern_jurisdiction": parents[0]["label"] if parents else None,
            "modern_jurisdiction_role": "secondary_context_only",
            "region": override["region"],
            "source_ids": ["source:getty_tgn"],
            "license_rule_id": "getty_tgn:data:c8bbe41cb024",
            "record_sha256": sha256_file(path),
            "coordinate_issue": issue,
            "review_state": "verified",
            "release_status": "verified_list_only" if coordinate is None else "verified_public",
            "status_history": [
                {"at": BUILT_AT, "from": None, "to": "candidate", "actor": "automated_museum_07_pipeline", "reason": "Extracted from a bounded ULAN/TGN lead."},
                {"at": BUILT_AT, "from": "candidate", "to": "verified", "actor": "automated_museum_07_pipeline", "reason": "TGN identity, hierarchy, names, coordinate state, and source hash closed."},
            ],
        }
    return places


def _year(event: dict[str, Any]) -> int:
    timespan = event.get("timespan", {})
    value = timespan.get("begin_of_the_begin") or timespan.get("end_of_the_end")
    if not isinstance(value, str) or not value[:4].isdigit():
        raise ValueError("ULAN life event lacks a usable year")
    return int(value[:4])


def _event_place(event: dict[str, Any]) -> str | None:
    places = event.get("took_place_at", [])
    if not places or not isinstance(places[0], dict):
        return None
    identifier = places[0].get("id")
    return identifier.rsplit("/", 1)[-1] if isinstance(identifier, str) else None


def _episode(
    *, artist_id: str, event_type: str, place: dict[str, Any], start: int | None, end: int | None,
    date_precision: str, role: str, source_ids: list[str], evidence: list[dict[str, Any]],
    basis: str, confidence: str = "high", uncertain: bool = False,
) -> dict[str, Any]:
    slug = artist_id.split(":", 1)[1]
    episode_id = f"episode:{slug}:{event_type}"
    claim_id = f"geo-claim:{slug}:{event_type}"
    list_only = place["coordinates"] is None or date_precision == "unknown"
    return {
        "schema_version": "1.0.0",
        "id": episode_id,
        "entity_type": "artist_place_episode",
        "artist_id": artist_id,
        "place_id": place["id"],
        "episode_type": event_type,
        "start_year": start,
        "end_year": end,
        "date_precision": date_precision,
        "place_precision": place["coordinate_precision"],
        "role": role,
        "claim_id": claim_id,
        "evidence": evidence,
        "source_ids": source_ids,
        "confidence": confidence,
        "uncertain": uncertain or list_only,
        "public_wording": {
            "zh-Hans": f"{place['preferred_historical_label']}：{role}。",
            "en": f"{place['preferred_historical_label']}: {role}.",
        },
        "what_it_proves": "The cited sources support this artist-place assertion at the stated time and precision.",
        "does_not_prove": "It does not prove a travel route, continuous presence, exclusive cultural identity, influence, or an exact building.",
        "research_basis": basis,
        "review_state": "verified",
        "release_status": "verified_list_only" if list_only else "verified_public",
        "release_id": "release:art-time-place-1.3.0",
        "status_history": [
            {"at": BUILT_AT, "from": None, "to": "candidate", "actor": "automated_museum_07_pipeline"},
            {"at": BUILT_AT, "from": "candidate", "to": "verified_list_only" if list_only else "verified_public", "actor": "automated_museum_07_pipeline"},
        ],
    }


def build_place_research(basemap: dict[str, Any]) -> dict[str, Any]:
    artists_document = json.loads((ART_RELEASE / "artists.json").read_text(encoding="utf-8"))
    artworks_document = json.loads((ART_RELEASE / "artworks.json").read_text(encoding="utf-8"))
    artists = {item["id"]: item for item in artists_document["artists"]}
    artworks = artworks_document["artworks"]
    if set(artists) != set(ARTISTS) or len(artworks) != 44:
        raise ValueError("M07 input artist/artwork scope drift")
    ulan_records, ulan_evidence = _load_ulan_records()
    if not KOLLWITZ_BIOGRAPHY.is_file():
        raise FileNotFoundError(KOLLWITZ_BIOGRAPHY)
    kollwitz_biography_text = KOLLWITZ_BIOGRAPHY.read_text(encoding="utf-8")
    for required_text in ("born on 8 July 1867", "moved to Berlin", "summer 1943", "Moritzburg"):
        if required_text not in kollwitz_biography_text:
            raise ValueError(f"Kollwitz official biography evidence drift: {required_text}")
    kollwitz_biography_hash = sha256_file(KOLLWITZ_BIOGRAPHY)
    places = _tgn_places()
    episodes = []
    claims = []
    dispositions = []

    for artist_id, ulan_id in sorted(ARTISTS.items()):
        record = ulan_records[ulan_id]
        for key, event_type in (("born", "birth"), ("died", "death")):
            event = record.get(key, {})
            tgn_id = _event_place(event) or (KOLLWITZ_PLACES[key] if artist_id == "artist:kathe-kollwitz" else None)
            if tgn_id is None or tgn_id not in places:
                raise ValueError(f"Unclosed {event_type} place: {artist_id}")
            year = _year(event)
            date_precision = "year"
            start = end = year
            confidence = "high"
            uncertain = False
            if artist_id == "artist:kitagawa-utamaro" and event_type == "birth":
                start, end, date_precision, confidence, uncertain = 1750, 1759, "decade", "medium", True
            source_ids = ["source:getty_ulan", "source:getty_tgn"]
            evidence = [
                {"id": f"map-evidence:{artist_id.split(':',1)[1]}:{event_type}:ulan", "source_id": "source:getty_ulan", "locator": ulan_evidence[ulan_id]["uri"], "record_sha256": ulan_evidence[ulan_id]["record_sha256"], "stance": "supports"},
                {"id": f"map-evidence:{artist_id.split(':',1)[1]}:{event_type}:tgn", "source_id": "source:getty_tgn", "locator": places[tgn_id]["tgn_uri"], "record_sha256": places[tgn_id]["record_sha256"], "stance": "supports"},
            ]
            basis = f"{record.get(key, {}).get('id', ulan_evidence[ulan_id]['uri'])} + {places[tgn_id]['tgn_uri']}"
            if artist_id == "artist:kathe-kollwitz":
                source_ids.append("source:kollwitz_museum")
                evidence.append({
                    "id": f"map-evidence:kathe-kollwitz:{event_type}:official-biography",
                    "source_id": "source:kollwitz_museum", "locator": "https://www.kollwitz.de/biography",
                    "record_sha256": kollwitz_biography_hash, "stance": "supports",
                })
                basis += " + https://www.kollwitz.de/biography"
            episode = _episode(
                artist_id=artist_id, event_type=event_type, place=places[tgn_id], start=start, end=end,
                date_precision=date_precision, role=f"documented {event_type} place", source_ids=source_ids,
                evidence=evidence, basis=basis, confidence=confidence, uncertain=uncertain,
            )
            episodes.append(episode)

        activity = ACTIVITY_EPISODES[artist_id]
        tgn_id = activity["place"]
        source_ids = ["source:getty_ulan", "source:getty_tgn"]
        if activity.get("official"):
            source_ids.append("source:kollwitz_museum")
        evidence = [
            {"id": f"map-evidence:{artist_id.split(':',1)[1]}:activity:ulan", "source_id": "source:getty_ulan", "locator": ulan_evidence[ulan_id]["uri"], "record_sha256": ulan_evidence[ulan_id]["record_sha256"], "stance": "supports"},
            {"id": f"map-evidence:{artist_id.split(':',1)[1]}:activity:tgn", "source_id": "source:getty_tgn", "locator": places[tgn_id]["tgn_uri"], "record_sha256": places[tgn_id]["record_sha256"], "stance": "supports"},
        ]
        if activity.get("official"):
            evidence.append({"id": "map-evidence:kathe-kollwitz:activity:official-biography", "source_id": "source:kollwitz_museum", "locator": activity["basis"], "record_sha256": kollwitz_biography_hash, "stance": "supports"})
        episode = _episode(
            artist_id=artist_id, event_type=activity["type"], place=places[tgn_id], start=activity["start"],
            end=activity["end"], date_precision=activity["precision"], role=activity["role"], source_ids=source_ids,
            evidence=evidence, basis=activity["basis"], confidence="high" if activity["precision"] != "unknown" else "medium",
            uncertain=activity["precision"] == "unknown",
        )
        episodes.append(episode)

    if len(episodes) != 36 or Counter(item["artist_id"] for item in episodes) != Counter({artist_id: 3 for artist_id in ARTISTS}):
        raise ValueError("Artist episode target is not exact")

    for episode in episodes:
        claims.append({
            "schema_version": "1.0.0", "id": episode["claim_id"], "entity_type": "geospatial_claim",
            "subject_id": episode["artist_id"], "predicate": episode["episode_type"], "place_id": episode["place_id"],
            "episode_id": episode["id"], "evidence_ids": [item["id"] for item in episode["evidence"]],
            "source_ids": episode["source_ids"], "confidence": episode["confidence"], "status": episode["release_status"],
            "what_it_proves": episode["what_it_proves"], "does_not_prove": episode["does_not_prove"],
        })
        dispositions.append({
            "schema_version": "1.0.0", "id": f"place-disposition:{episode['id'].split(':',1)[1]}",
            "entity_type": "place_research_disposition", "candidate_id": episode["id"],
            "artist_id": episode["artist_id"], "place_id": episode["place_id"],
            "disposition": episode["release_status"], "reason_codes": [
                "identity_time_coordinate_closed" if episode["release_status"] == "verified_public" else "time_or_coordinate_requires_list_only"
            ], "human_review_dependency": False,
        })

    holdings_by_institution: dict[str, list[str]] = {}
    for artwork in artworks:
        holdings_by_institution.setdefault(artwork["institution"]["id"], []).append(artwork["id"])
    institution_places = {
        "museum_institution:art-institute-of-chicago": ("7013596", "source:aic_api"),
        "museum_institution:metropolitan-museum-of-art": ("7007567", "source:met_open_access"),
    }
    holdings = []
    for institution_id, artwork_ids in sorted(holdings_by_institution.items()):
        tgn_id, source_id = institution_places[institution_id]
        holdings.append({
            "schema_version": "1.0.0", "id": f"holding-location:{institution_id.split(':',1)[1]}",
            "entity_type": "holding_location", "institution_id": institution_id, "place_id": places[tgn_id]["id"],
            "artwork_ids": sorted(artwork_ids), "layer": "current_holding_institution", "source_ids": [source_id, "source:getty_tgn"],
            "what_it_proves": "The current release identifies this institution as the present holder for the listed objects.",
            "does_not_prove": "The holding institution is not an artwork creation place or an artist activity place.",
            "review_state": "verified", "release_status": "verified_public",
        })
    creation_dispositions = [{
        "schema_version": "1.0.0", "id": f"artwork-place-claim:{artwork['id'].split(':',1)[1]}",
        "entity_type": "artwork_place_claim", "artwork_id": artwork["id"], "place_id": None,
        "claim_id": None, "status": "not_asserted",
        "reason": "The retained official release record does not explicitly assert a creation place; residence, title, subject, and holding location were not used as proxies.",
        "source_ids": artwork["source_ids"],
    } for artwork in sorted(artworks, key=lambda item: item["id"])]

    sources = [
        {"id": "source:getty_ulan", "name": "Getty ULAN", "tier": 1, "url": "https://www.getty.edu/research/tools/vocabularies/ulan/", "license": "ODC-BY-1.0", "attribution": "Getty Research Institute, ULAN; changes marked."},
        {"id": "source:getty_tgn", "name": "Getty TGN", "tier": 1, "url": "https://www.getty.edu/research/tools/vocabularies/tgn/", "license": "ODC-BY-1.0", "attribution": "Getty Research Institute, TGN; changes and coordinate-precision interpretation marked."},
        {"id": "source:kollwitz_museum", "name": "Käthe Kollwitz Museum Köln", "tier": 1, "url": "https://www.kollwitz.de/biography", "license": "source_citation", "attribution": "Käthe Kollwitz Museum Köln, Biography."},
        {"id": "source:met_open_access", "name": "The Metropolitan Museum of Art Open Access", "tier": 1, "url": "https://metmuseum.github.io/", "license": "CC0-1.0", "attribution": None},
        {"id": "source:aic_api", "name": "Art Institute of Chicago API", "tier": 1, "url": "https://api.artic.edu/docs/", "license": "CC0-1.0 selected fields", "attribution": None},
        {"id": "source:natural_earth", "name": "Natural Earth", "tier": 1, "url": "https://www.naturalearthdata.com/downloads/110m-physical-vectors/", "license": "public_domain", "attribution": "Made with Natural Earth"},
    ]
    document = {
        "schema_version": "1.0.0", "id": "place-research:museum-07-v1", "entity_type": "museum_07_place_research",
        "phase_id": PHASE_ID, "input_release_id": "release:art-pathways-1.2.0",
        "input_release_hash": "sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3",
        "generated_at": BUILT_AT, "places": [places[key] for key in sorted(places)],
        "episodes": sorted(episodes, key=lambda item: item["id"]), "claims": sorted(claims, key=lambda item: item["id"]),
        "holding_locations": holdings, "artwork_creation_place_dispositions": creation_dispositions,
        "research_dispositions": sorted(dispositions, key=lambda item: item["id"]), "sources": sources,
        "basemap_source_record": basemap,
        "counts": {
            "artists": len(artists), "artworks": len(artworks), "places": len(places), "episodes": len(episodes),
            "verified_public_episodes": sum(item["release_status"] == "verified_public" for item in episodes),
            "list_only_episodes": sum(item["release_status"] == "verified_list_only" for item in episodes),
            "creation_places": 0, "holding_institutions": len(holdings),
            "precision": dict(sorted(Counter(item["place_precision"] for item in episodes).items())),
        },
        "human_review_dependency": False,
    }
    document["research_hash"] = canonical_sha256({key: document[key] for key in (
        "places", "episodes", "claims", "holding_locations", "artwork_creation_place_dispositions", "research_dispositions", "sources",
    )})
    RESEARCH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_OUTPUT.write_bytes(canonical_json_bytes(document))
    return document


def main() -> int:
    basemap = build_basemap()
    research = build_place_research(basemap)
    print(json.dumps({
        "ok": True,
        "basemap_bundle_hash": basemap["bundle_hash"],
        "basemap_total_bytes": sum(item["output_bytes"] for item in basemap["layers"]),
        "place_identity_count": research["counts"]["places"],
        "artist_episode_count": research["counts"]["episodes"],
        "list_only_episode_count": research["counts"]["list_only_episodes"],
        "research_hash": research["research_hash"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
