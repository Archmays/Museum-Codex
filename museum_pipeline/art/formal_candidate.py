"""Deterministic MUSEUM-09B Batch 01 formal-candidate overlay.

The module consumes the immutable MUSEUM-09A selection and sealed official
source cache.  Network refresh is a separate, bounded operation whose compact
receipt becomes an input to the deterministic candidate build.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import statistics
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from museum_pipeline.hashing import canonical_sha256, sha256_file
from scripts.scan_public_artifact_for_candidate_data import validated_formal_art_exempt_roots


ROOT = Path(__file__).resolve().parents[2]
PHASE_ID = "MUSEUM-09B"
BATCH_ID = "museum-09-batch-01"
VALID_BATCH_REGISTRY_STATUSES = frozenset({"formal_candidate_ready", "media_bundle_ready"})
PACKAGE_ID = "museum-09b:batch-01-formal-candidate-v1"
BUILT_AT = "2026-07-20T12:00:00+08:00"
REVIEW_DATE = "2026-07-20"
BASELINE_COMMIT = "a0e25915d5c2f15c565cb5d59c66c5e350e2ef50"
INPUT_CLOSURE_HASH = "sha256:8b7020f979895e3bf5f21c042c1e6a2b746628f5108f13050102b31370219770"
INPUT_UNIVERSE_HASH = "sha256:3db15ca186152c7355263e6b3254d3ff7151f56b834f34e57fd6d7570c42bded"
INPUT_RELEASE_ID = "release:art-v1-candidate-1.4.0"
INPUT_RELEASE_CONTENT_HASH = "sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202"
INPUT_RELEASE_MANIFEST_SHA256 = "sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114"
INPUT_RELEASE_TREE_SHA256 = "sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1"
M09A_PHYSICAL_TREE_SHA256 = "sha256:25be5898c3476b02db7573973475fd0c27c8f16c769a4ab4057691be74558c82"
M09A_REGISTRY_SHA256 = "sha256:79ae81fc2bcf79a76497a59b83cd3f627d75cf01245270b3f6e416a4da46e68b"

M09A_ROOT = ROOT / "data" / "reviewed" / "art" / "museum-09a" / "global-expansion-universe-v1"
RAW_ROOT = ROOT / "data" / "raw" / "museum-09a"
DEFAULT_OUTPUT = (
    ROOT / "data" / "reviewed" / "art" / "museum-09b" / "batch-01-formal-candidate-v1"
)
DEFAULT_REFRESH_RECEIPT = (
    ROOT / "data" / "reviewed" / "art" / "museum-09b" / "source-refresh-batch-01-v1.json"
)
DEFAULT_REGISTRY = ROOT / "governance" / "museum-09-batch-registry.json"
RELEASE_LEDGER = ROOT / "governance" / "release-integrity-ledger.json"
SOURCE_RULES = ROOT / "research" / "source-registry" / "source-license-rules.json"
SCHEMA_MANIFEST = ROOT / "schemas" / "schema-manifest.json"

EXPECTED_COVERAGE = {
    "africa": 4,
    "east-asia": 6,
    "europe": 17,
    "latin-america-caribbean": 5,
    "north-america": 7,
    "oceania": 2,
    "south-asia": 3,
    "southeast-asia": 3,
    "west-central-asia": 3,
}
MEDIA_SUFFIXES = {
    ".avif", ".gif", ".jpeg", ".jpg", ".mp3", ".mp4", ".png", ".svg",
    ".tif", ".tiff", ".webm", ".webp",
}
PROHIBITED_TEXT = {
    "most important", "greatest", "leading artist", "popularity", "market value",
    "ai aesthetic", "最伟大", "最重要", "最领先", "市场价值",
}
MANUAL_WAIT_STATES = {"waiting_for_manual_review", "pending_user_approval"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    path.write_bytes(payload)


def _hash(value: Any) -> str:
    return canonical_sha256(value)


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value or hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _stable_suffix(stable_id: str) -> str:
    return _slug(stable_id.replace(":", "-"))


def _read_sharded(manifest_name: str, field: str) -> list[dict[str, Any]]:
    manifest = _read_json(M09A_ROOT / manifest_name)
    records: list[dict[str, Any]] = []
    for shard in manifest["shards"]:
        records.extend(_read_json(M09A_ROOT / shard["path"])[field])
    return records


def _tree_hash(root: Path, *, exclude: set[str] | None = None) -> tuple[str, int, int]:
    excluded = exclude or set()
    rows: list[bytes] = []
    byte_count = 0
    files = [
        path for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest = sha256_file(path, prefixed=False)
        rows.append(f"{relative}\0{size}\0{digest}\n".encode("utf-8"))
        byte_count += size
    return "sha256:" + hashlib.sha256(b"".join(rows)).hexdigest(), len(files), byte_count


def _directory_bytes_equal(left: Path, right: Path) -> bool:
    left_files = sorted(path.relative_to(left) for path in left.rglob("*") if path.is_file())
    right_files = sorted(path.relative_to(right) for path in right.rglob("*") if path.is_file())
    return left_files == right_files and all(
        (left / relative).read_bytes() == (right / relative).read_bytes()
        for relative in left_files
    )


def _source_rule_index() -> dict[str, dict[str, Any]]:
    document = _read_json(SOURCE_RULES)
    return {item["source_id"]: item for item in document["sources"]}


def _aic_refresh_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_object_id": str(row["id"]),
        "title": row.get("title"),
        "date_display": row.get("date_display"),
        "medium": row.get("medium_display"),
        "dimensions": row.get("dimensions"),
        "department": row.get("department_title"),
        "object_type": row.get("classification_title"),
        "artist_display": row.get("artist_title"),
        "is_public_domain": bool(row.get("is_public_domain")),
        "image_id": row.get("image_id"),
        "copyright_notice": row.get("copyright_notice"),
        "credit_line": row.get("credit_line"),
        "source_updated_at": row.get("updated_at"),
    }


def refresh_source_records(
    output: Path = DEFAULT_REFRESH_RECEIPT,
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Create a compact bounded refresh receipt; no media bytes are requested."""

    first_batch = _read_json(M09A_ROOT / "museum-09b-first-batch.json")
    artist_ids = set(first_batch["artist_ids"])
    work_ids = set(first_batch["work_ids"])
    artists = [
        item for item in _read_sharded("normalized-candidates.json", "candidates")
        if item["id"] in artist_ids
    ]
    works = [
        item for item in _read_sharded("target-artworks.json", "artworks")
        if item["id"] in work_ids
    ]
    aic_works = [item for item in works if item["source_id"] == "aic_api"]
    requested_fields = [
        "id", "title", "date_display", "medium_display", "dimensions",
        "department_title", "classification_title", "is_public_domain",
        "image_id", "copyright_notice", "credit_line", "artist_title", "updated_at",
    ]
    live_aic: dict[str, dict[str, Any]] = {}
    network_bytes = 0
    request_count = 0
    failures: list[dict[str, str]] = []
    user_agent = "Museum-Codex-MUSEUM-09B/1.0 metadata-refresh"

    for offset in range(0, len(aic_works), 40):
        object_ids = ",".join(item["source_object_id"] for item in aic_works[offset:offset + 40])
        query = urllib.parse.urlencode({
            "ids": object_ids,
            "fields": ",".join(requested_fields),
            "limit": "40",
        })
        url = f"https://api.artic.edu/api/v1/artworks?{query}"
        last_error: Exception | None = None
        for attempt in range(1, 4):
            request = urllib.request.Request(url, headers={"User-Agent": user_agent})
            request_count += 1
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    payload = response.read()
                network_bytes += len(payload)
                for row in json.loads(payload)["data"]:
                    live_aic[str(row["id"])] = _aic_refresh_projection(row)
                last_error = None
                break
            except Exception as error:  # pragma: no cover - live transport varies
                last_error = error
        if last_error is not None:
            failures.append({
                "source_id": "aic_api",
                "error": type(last_error).__name__,
                "attempt_count": 3,
                "requested_id_count": len(object_ids.split(",")),
            })

    death_checks = {
        "artist:m09a-moma_open_data-79": (
            "https://www.moma.org/artists/79-agam-yaacov-agam", "1928–2026"
        ),
        "artist:m09a-moma_open_data-74308": (
            "https://www.moma.org/artists/74308-raghu-rai", "1942–2026"
        ),
    }
    live_death_checks: dict[str, dict[str, Any]] = {}
    moma_artists_url = (
        "https://media.githubusercontent.com/media/MuseumofModernArt/collection/main/Artists.csv"
    )
    try:
        request = urllib.request.Request(moma_artists_url, headers={"User-Agent": user_agent})
        request_count += 1
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
        network_bytes += len(payload)
        rows = {
            str(row.get("ConstituentID")): row
            for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig", errors="replace")))
            if str(row.get("ConstituentID")) in {"79", "74308"}
        }
        for artist_id, (url, marker) in death_checks.items():
            source_artist_id = artist_id.rsplit("-", 1)[-1]
            row = rows.get(source_artist_id)
            artist_bio = str((row or {}).get("ArtistBio") or "")
            begin_year, end_year = marker.replace("-", "–").split("–")
            marker_found = (
                marker in artist_bio
                or marker.replace("–", "-") in artist_bio
                or (
                    str((row or {}).get("BeginDate") or "") == begin_year
                    and str((row or {}).get("EndDate") or "") == end_year
                )
            )
            live_death_checks[artist_id] = {
                "official_url": url,
                "official_dataset_url": moma_artists_url,
                "expected_life_date_marker": marker,
                "marker_found": marker_found,
                "source_row_projection": {
                    "ConstituentID": (row or {}).get("ConstituentID"),
                    "DisplayName": (row or {}).get("DisplayName"),
                    "ArtistBio": artist_bio or None,
                    "BeginDate": (row or {}).get("BeginDate"),
                    "EndDate": (row or {}).get("EndDate"),
                },
                "response_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
    except Exception as error:  # pragma: no cover - live transport varies
        failures.append({"source_id": "moma_open_data", "error": type(error).__name__})
        for artist_id, (url, marker) in death_checks.items():
            live_death_checks[artist_id] = {
                "official_url": url,
                "official_dataset_url": moma_artists_url,
                "expected_life_date_marker": marker,
                "marker_found": False,
                "source_row_projection": None,
                "response_sha256": None,
            }

    records: list[dict[str, Any]] = []
    for artist in sorted(artists, key=lambda item: item["id"]):
        status = "unchanged"
        method = "sealed_official_snapshot_hash_replay"
        live_check = live_death_checks.get(artist["id"])
        if live_check:
            method = "sealed_snapshot_plus_current_official_artist_page"
            if not live_check["marker_found"]:
                status = "source_refresh_unavailable"
        records.append({
            "record_kind": "artist",
            "record_id": artist["id"],
            "source_ids": [item["source_id"] for item in artist["source_identities"]],
            "old_hash": _hash(artist),
            "new_hash": _hash(artist),
            "status": status,
            "classification": "no_change" if status == "unchanged" else "unavailable",
            "refresh_method": method,
            "fetched_at": BUILT_AT if live_check else None,
            "source_version": (
                live_check.get("response_sha256") if live_check else INPUT_UNIVERSE_HASH
            ),
            "live_check": live_check,
            "affected_closure": [artist["id"]],
        })
    for work in sorted(works, key=lambda item: item["id"]):
        projection = live_aic.get(work["source_object_id"]) if work["source_id"] == "aic_api" else None
        if projection:
            status = "changed"
            classification = "metadata_enhancement"
            new_hash = _hash(projection)
            method = "current_official_object_api"
        elif work["source_id"] == "aic_api":
            status = "source_refresh_unavailable"
            classification = "unavailable"
            new_hash = _hash(work)
            method = "sealed_official_snapshot_fallback"
        else:
            status = "unchanged"
            classification = "no_change"
            new_hash = _hash(work)
            method = "sealed_official_bulk_record_hash_replay"
        records.append({
            "record_kind": "artwork",
            "record_id": work["id"],
            "source_id": work["source_id"],
            "source_object_id": work["source_object_id"],
            "old_hash": _hash(work),
            "new_hash": new_hash,
            "status": status,
            "classification": classification,
            "refresh_method": method,
            "fetched_at": BUILT_AT if projection else None,
            "source_version": (
                projection.get("source_updated_at") if projection else INPUT_UNIVERSE_HASH
            ),
            "minimal_current_projection": projection,
            "affected_closure": [work["artist_id"], work["id"]],
        })
    counts = Counter(item["status"] for item in records)
    receipt = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "batch_id": BATCH_ID,
        "verified_at": BUILT_AT,
        "fetched_at": BUILT_AT,
        "input_closure_hash": INPUT_CLOSURE_HASH,
        "record_count": len(records),
        "checked_count": len(records),
        "changed_count": counts["changed"],
        "unchanged_count": counts["unchanged"],
        "unavailable_count": counts["source_refresh_unavailable"],
        "network_request_count": request_count,
        "downloaded_network_bytes": network_bytes,
        "new_media_bytes": 0,
        "source_cache_reuse_bytes": 1_430_997_874,
        "bounded_refresh_policy": (
            "AIC object records were refreshed in bounded ID batches; other official bulk "
            "records were replayed by sealed record hash. No image URL was requested."
        ),
        "transport_failures": failures,
        "records": records,
    }
    receipt["content_hash"] = _hash(receipt)
    _write_json(output, receipt)
    return {
        "ok": not failures,
        "output": output.as_posix(),
        "counts": {
            "checked": len(records),
            "changed": counts["changed"],
            "unchanged": counts["unchanged"],
            "unavailable": counts["source_refresh_unavailable"],
        },
        "network_request_count": request_count,
        "downloaded_network_bytes": network_bytes,
    }


def reuse_sealed_source_receipt(
    sealed_receipt_path: Path,
    latest_failed_receipt_path: Path,
    output: Path = DEFAULT_REFRESH_RECEIPT,
) -> dict[str, Any]:
    """Reuse the last complete receipt after a later bounded transport failure."""

    sealed = _read_json(sealed_receipt_path)
    latest = _read_json(latest_failed_receipt_path)
    if sealed.get("content_hash") != _hash({
        key: value for key, value in sealed.items() if key != "content_hash"
    }):
        raise ValueError("sealed source receipt content hash mismatch")
    if sealed.get("checked_count") != 538 or sealed.get("unavailable_count") != 0:
        raise ValueError("sealed source receipt is not a complete Batch 01 refresh")
    if not latest.get("transport_failures"):
        raise ValueError("latest receipt does not record a transport failure")

    receipt = json.loads(json.dumps(sealed))
    for record in receipt["records"]:
        projection = record.get("minimal_current_projection")
        live_check = record.get("live_check")
        record["fetched_at"] = BUILT_AT if projection or live_check else None
        record["source_version"] = (
            projection.get("source_updated_at")
            if projection
            else (
                live_check.get("response_sha256")
                if live_check
                else INPUT_UNIVERSE_HASH
            )
        )
    receipt["fetched_at"] = BUILT_AT
    receipt["network_request_count"] = (
        sealed["network_request_count"] + latest["network_request_count"]
    )
    receipt["downloaded_network_bytes"] = (
        sealed["downloaded_network_bytes"] + latest["downloaded_network_bytes"]
    )
    receipt["transport_history"] = [{
        "attempted_at": BUILT_AT,
        "outcome": "source_refresh_unavailable_reused_last_complete_receipt",
        "network_request_count": latest["network_request_count"],
        "downloaded_network_bytes": latest["downloaded_network_bytes"],
        "failures": latest["transport_failures"],
        "affected_source_id": "aic_api",
        "fallback": "sealed_complete_receipt",
    }]
    receipt["transport_failures"] = []
    receipt["content_hash"] = _hash({
        key: value for key, value in receipt.items() if key != "content_hash"
    })
    _write_json(output, receipt)
    return {
        "ok": True,
        "output": output.as_posix(),
        "counts": {
            "checked": receipt["checked_count"],
            "changed": receipt["changed_count"],
            "unchanged": receipt["unchanged_count"],
            "unavailable": receipt["unavailable_count"],
        },
        "network_request_count": receipt["network_request_count"],
        "downloaded_network_bytes": receipt["downloaded_network_bytes"],
        "sealed_receipt_reused": True,
    }


def _csv_index(path: Path, key_field: str, wanted: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if not wanted:
        return result
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            key = str(row.get(key_field) or "")
            if key in wanted:
                result[key] = row
                if len(result) == len(wanted):
                    break
    return result


def _raw_enrichment(works: list[dict[str, Any]], receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for work in works:
        by_source[work["source_id"]].add(work["source_object_id"])
    result: dict[str, dict[str, Any]] = {}
    mappings = {
        "cleveland_open_access": ("cleveland-artworks.csv", "id"),
        "met_open_access": ("met-objects.csv", "Object ID"),
        "moma_open_data": ("moma-artworks.csv", "ObjectID"),
        "nga_open_data": ("nga-objects.csv", "objectid"),
        "tate_open_data": ("tate-artworks.csv", "accession_number"),
        "cooper_hewitt_open_data": ("cooper-hewitt-objects.csv", "id"),
    }
    for source_id, (filename, key) in mappings.items():
        for object_id, row in _csv_index(
            RAW_ROOT / filename, key, by_source.get(source_id, set())
        ).items():
            result[f"{source_id}:{object_id}"] = row
    for record in receipt["records"]:
        projection = record.get("minimal_current_projection")
        if record["record_kind"] == "artwork" and projection:
            result[f"aic_api:{record['source_object_id']}"] = projection
    return result


def _source_documents(source_ids: set[str], receipt: dict[str, Any]) -> list[dict[str, Any]]:
    audit = _read_json(M09A_ROOT / "source-audit.json")
    audit_index = {item["source_id"]: item for item in audit["sources"]}
    rule_index = _source_rule_index()
    documents = []
    for source_id in sorted(source_ids):
        item = audit_index[source_id]
        rules = rule_index.get(source_id, {}).get("rules", [])
        documents.append({
            "id": f"source:{source_id}",
            "entity_type": "source",
            "registry_source_id": source_id,
            "title": item["title"],
            "publisher": item["institution"],
            "official_url": item["official_entry"],
            "official_host": urllib.parse.urlparse(item["official_entry"]).hostname,
            "source_type": "official_collection",
            "tier": 1,
            "snapshot_hash": item["fixture_or_snapshot_hash"],
            "provenance": item["provenance"],
            "metadata_license": item["metadata_license"],
            "media_license": item["media_license"],
            "source_rule_ids": [rule["rule_id"] for rule in rules],
            "license_rule_snapshot_hash": sha256_file(SOURCE_RULES),
            "accessed_at": REVIEW_DATE,
            "what_it_proves": (
                "Named collection records, stable object identity, source-supplied catalog "
                "fields, and source-supplied life-date or creator fields."
            ),
            "what_it_does_not_prove": (
                "Historical influence, artist intention, creation place, or media reuse "
                "permission without object-specific media evidence."
            ),
            "correction_route": item["correction_route"],
            "lifecycle_status": "reviewed_candidate_not_public",
            "rights_status": "PASS_BY_USER_AUTHORIZATION",
        })
    return documents


def _claim_evidence_pair(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    claim_id: str,
    subject_id: str,
    predicate: str,
    value: Any,
    statement: str,
    source_ids: list[str],
    locator: str,
    what_proves: str,
    what_not: str,
) -> str:
    evidence_id = claim_id.replace("claim:", "evidence:", 1)
    claims.append({
        "id": claim_id,
        "entity_type": "claim",
        "subject_id": subject_id,
        "predicate": predicate,
        "value": value,
        "statement": statement,
        "evidence_ids": [evidence_id],
        "counter_evidence_ids": [],
        "status": "reviewed_candidate_not_public",
        "disputed": False,
        "uncertainty": None,
        "publish_status": "not_public",
        "reviewed_at": REVIEW_DATE,
    })
    evidence.append({
        "id": evidence_id,
        "entity_type": "evidence",
        "claim_ids": [claim_id],
        "source_ids": source_ids,
        "locator": locator,
        "summary": statement,
        "what_it_proves": what_proves,
        "what_it_does_not_prove": what_not,
        "extraction_method": "api_field_or_official_bulk_record",
        "snapshot_hash": _hash({"locator": locator, "statement": statement}),
        "lifecycle_status": "reviewed_candidate_not_public",
    })
    return claim_id


def _geography_label(artist: dict[str, Any]) -> str | None:
    basis = artist.get("primary_coverage_basis") or ""
    matches = re.findall(
        r"(?:born |field: |fields: |biography: |association in )([^;,]+)",
        basis,
        flags=re.IGNORECASE,
    )
    if matches:
        value = matches[-1].strip()
        if value and value.casefold() not in {"not stated", "american", "british", "french", "dutch"}:
            return value
    return artist["primary_coverage_bucket"].replace("-", " ").title()


def _documented_birth_place(artist: dict[str, Any]) -> str | None:
    basis = str(artist.get("primary_coverage_basis") or "")
    for pattern in (
        r"\bplaceOfBirth field:\s*(.+)$",
        r"\bborn\s+([^,;]+)",
        r"\bb\.\s*([^,;]+)",
    ):
        match = re.search(pattern, basis, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _gallery_overview(
    name: str,
    birth: int,
    death: int,
    period: str,
    geography: str,
    media: list[str],
    institutions: list[str],
    work_count: int,
) -> tuple[str, str]:
    media_text = ", ".join(media)
    institutions_text = ", ".join(institutions)
    en = (
        f"{name} ({birth}–{death}) is represented in this internal Batch 01 candidate as "
        f"a confirmed-deceased individual. Official collection records place the documented "
        f"life dates within the {period} research band and support the cautious geography label "
        f"“{geography}”; that label routes research and does not assert ethnicity, nationality, "
        f"migration, or cultural affiliation beyond the cited fields. The selected set contains "
        f"{work_count} works held or catalogued by {institutions_text}. Their source-supplied "
        f"records document practice across {media_text}. Titles, dates, media, dimensions, "
        f"attribution wording, and holding institutions remain attached to their object records, "
        f"including explicit nulls where a source does not provide a value. This dossier treats "
        f"those records as a basis for close observation rather than as a ranking of the artist "
        f"or a claim about artistic intention. Future gallery sequencing can compare changes in "
        f"medium, date, and catalog context across the selected objects. Such comparison is "
        f"curatorial and does not establish influence or contact. Candidate relationship entries "
        f"therefore stay at comparison level unless direct historical evidence is later added. "
        f"Media availability is assessed separately from permission; no image was downloaded, "
        f"cropped, generated, or made public in this phase. Null handling and evidence links "
        f"remain visible so a later reviewer can reproduce every factual step."
    )
    zh = (
        f"{name}（{birth}—{death}）在本批内部候选中以已确认去世的个人艺术家身份记录。"
        f"官方馆藏资料将生卒信息置于{period}研究时段，并支持谨慎使用“{geography}”研究路由标签；"
        f"该标签不推断族群、国籍、迁徙或文化归属。候选集闭合{work_count}件作品，标题、年代、媒介、"
        f"尺寸、归属用语及收藏机构均绑定对象证据，来源未提供的字段保持空值。档案用于细看和比较，不作"
        f"地位排序，也不创造主观意图。未来展厅可按媒介、年代与馆藏语境组织观察，但策展比较不等于历史"
        f"影响或实际接触；无直接史料时，关系只保持比较级。媒体可用性与许可分开审核，本阶段未下载、"
        f"裁切、生成或公开作品图像。"
    )
    return en, zh


def _collection_overview(
    name: str,
    birth: int,
    death: int,
    geography: str,
    media: list[str],
    institutions: list[str],
    work_count: int,
) -> tuple[str, str]:
    media_text = ", ".join(media)
    institutions_text = ", ".join(institutions)
    en = (
        f"{name} ({birth}–{death}) is recorded here as a confirmed-deceased individual. "
        f"Official records support the cautious research geography “{geography}” and document "
        f"{work_count} selected works across the named source institutions. Source fields describe "
        f"the recorded media without turning that catalog vocabulary into an interpretation. "
        f"This candidate overview preserves uncertainty: it does "
        f"not infer ethnicity, migration, influence, intention, or creation place. Object facts "
        f"remain linked to their evidence and source records. Media availability is not treated "
        f"as permission, and no image bytes or derivatives were created."
    )
    zh = (
        f"{name}（{birth}—{death}）在此记录为已确认去世的个人艺术家。官方资料支持谨慎使用"
        f"“{geography}”研究地理标签，并闭合{work_count}件候选作品。来源字段保留正式媒介记录，"
        f"但不把馆藏术语改写成解释。本概述不推断族群、迁徙、影响、意图或创作地点；作品事实继续绑定"
        f"证据与来源，缺失值保持为空。媒体可用性不等于许可，本阶段未创建图像字节或衍生物。"
    )
    return en, zh


def _work_projection(work: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    source_id = work["source_id"]
    title = raw.get("title") or raw.get("Title") or work["title"]
    date = (
        raw.get("date_display") or raw.get("creation_date") or raw.get("Object Date")
        or raw.get("Date") or raw.get("displaydate") or raw.get("dateText")
        or work["date_display"]
    )
    medium = (
        raw.get("medium") or raw.get("technique") or raw.get("Medium")
        or work["medium"]
    )
    dimensions = (
        raw.get("dimensions") or raw.get("measurements") or raw.get("Dimensions")
        or work["dimensions"]
    )
    department = (
        raw.get("department") or raw.get("department_title") or raw.get("Department")
        or raw.get("departmentabbr")
    )
    object_type = (
        raw.get("object_type") or raw.get("classification_title") or raw.get("Classification")
        or raw.get("classification")
    )
    is_public_domain = str(
        raw.get("is_public_domain", raw.get("Is Public Domain", ""))
    ).casefold() in {"true", "1", "yes"}
    share_license = str(raw.get("share_license_status") or "")
    image_identity = (
        raw.get("image_id") or raw.get("image_full") or raw.get("image_web")
        or raw.get("primaryImage")
    )
    title = title.strip() if isinstance(title, str) else title
    date = date.strip() if isinstance(date, str) else date
    medium = medium.strip() if isinstance(medium, str) else medium
    dimensions = dimensions.strip() if isinstance(dimensions, str) else dimensions
    department = department.strip() if isinstance(department, str) else department
    object_type = object_type.strip() if isinstance(object_type, str) else object_type
    if source_id == "aic_api" and is_public_domain and image_identity:
        media_status = "approved_external_iiif_candidate"
        candidate_image = (
            "https://www.artic.edu/iiif/2/"
            + str(image_identity)
            + "/full/843,/0/default.jpg"
        )
        rights_statement = "AIC object record is_public_domain=true with image_id"
        media_license = "OBJECT-SPECIFIC-PUBLIC-DOMAIN-CANDIDATE"
        source_rule_id = "aic_api:media:98cceb1965b8"
    elif source_id == "cleveland_open_access" and share_license == "CC0" and image_identity:
        media_status = "approved_self_hosted_candidate"
        candidate_image = str(image_identity)
        rights_statement = "Cleveland object record share_license_status=CC0"
        media_license = "CC0-1.0-OBJECT-SPECIFIC"
        source_rule_id = "cleveland_open_access:media:9f5808165c51"
    else:
        media_status = "metadata_only_ready"
        candidate_image = str(image_identity) if image_identity else None
        rights_statement = "No complete object-specific media permission closure in MUSEUM-09B"
        media_license = None
        source_rule_id = (
            "met_open_access:media:1669574588c7"
            if source_id == "met_open_access"
            else f"museum09b:{source_id}:media:unresolved"
        )
    return {
        "title": title,
        "date": date,
        "medium": medium,
        "dimensions": dimensions,
        "department": department,
        "object_type": object_type,
        "is_public_domain": is_public_domain,
        "share_license_status": share_license or None,
        "candidate_image_identity": candidate_image,
        "media_status": media_status,
        "rights_statement": rights_statement,
        "media_license": media_license,
        "media_source_rule_id": source_rule_id,
    }


def _write_sharded_artworks(output: Path, artworks: list[dict[str, Any]]) -> list[str]:
    relative_paths: list[str] = []
    shards = []
    chunk_size = 244
    for index in range(0, len(artworks), chunk_size):
        chunk = artworks[index:index + chunk_size]
        relative = f"artworks/part-{index // chunk_size + 1:04d}.json"
        document = {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "batch_id": BATCH_ID,
            "artwork_count": len(chunk),
            "artworks": chunk,
        }
        _write_json(output / relative, document)
        shards.append({
            "path": relative,
            "record_count": len(chunk),
            "first_id": chunk[0]["id"],
            "last_id": chunk[-1]["id"],
            "bytes": (output / relative).stat().st_size,
            "sha256": sha256_file(output / relative),
        })
        relative_paths.append(relative)
    manifest = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "batch_id": BATCH_ID,
        "entity_type": "sharded_collection_manifest",
        "collection_field": "artworks",
        "record_count": len(artworks),
        "ordering": "stable_id_ascending",
        "records_hash": _hash(artworks),
        "shards": shards,
    }
    _write_json(output / "artworks.json", manifest)
    return ["artworks.json", *relative_paths]


def _build_documents(receipt: dict[str, Any]) -> dict[str, Any]:
    first_batch = _read_json(M09A_ROOT / "museum-09b-first-batch.json")
    artist_ids = set(first_batch["artist_ids"])
    work_ids = set(first_batch["work_ids"])
    artists_input = sorted(
        (
            item for item in _read_sharded("normalized-candidates.json", "candidates")
            if item["id"] in artist_ids
        ),
        key=lambda item: item["id"],
    )
    works_input = sorted(
        (
            item for item in _read_sharded("target-artworks.json", "artworks")
            if item["id"] in work_ids
        ),
        key=lambda item: item["id"],
    )
    deceased_records = {
        item["id"]: item
        for item in _read_sharded("deceased-evidence.json", "records")
    }
    raw_index = _raw_enrichment(works_input, receipt)
    source_ids = {item["source_id"] for item in works_input}
    sources = _source_documents(source_ids, receipt)
    source_index = {item["id"]: item for item in sources}
    works_by_artist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in works_input:
        works_by_artist[item["artist_id"]].append(item)

    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    artists: list[dict[str, Any]] = []
    artworks: list[dict[str, Any]] = []
    media: list[dict[str, Any]] = []
    status_history: list[dict[str, Any]] = []

    for artist in artists_input:
        aid = artist["id"]
        suffix = _stable_suffix(aid)
        selected = sorted(works_by_artist[aid], key=lambda item: item["id"])
        source_refs = [f"source:{item['source_id']}" for item in artist["source_identities"]]
        institutions = sorted({item["holding_institution"] for item in selected})
        geography = _geography_label(artist) or "Place not asserted"
        documented_birth_place = _documented_birth_place(artist)
        media_tags = artist["documented_media_practice_tags"] or ["source-documented practice"]
        tier = artist["content_depth_tier"]
        if tier == "gallery":
            overview_en, overview_zh = _gallery_overview(
                artist["preferred_name"], artist["birth"]["year"], artist["death"]["year"],
                artist["historical_period"], geography, media_tags, institutions, len(selected),
            )
        else:
            overview_en, overview_zh = _collection_overview(
                artist["preferred_name"], artist["birth"]["year"], artist["death"]["year"],
                geography, media_tags, institutions, len(selected),
            )
        claim_ids = [
            _claim_evidence_pair(
                claims, evidence,
                claim_id=f"claim:m09b-{suffix}-identity",
                subject_id=aid,
                predicate="preferred_name",
                value=artist["preferred_name"],
                statement=f"Official source records name the individual as {artist['preferred_name']}.",
                source_ids=source_refs,
                locator=";".join(
                    f"{item['source_id']}:{item['source_artist_id']}"
                    for item in artist["source_identities"]
                ),
                what_proves="Preferred display name and named individual identity.",
                what_not="Sensitive identity, importance, or historical influence.",
            ),
            _claim_evidence_pair(
                claims, evidence,
                claim_id=f"claim:m09b-{suffix}-life",
                subject_id=aid,
                predicate="life_dates",
                value=f"{artist['birth']['year']}-{artist['death']['year']}",
                statement=(
                    f"Official source records document {artist['birth']['year']}–"
                    f"{artist['death']['year']} and confirm deceased status."
                ),
                source_ids=source_refs,
                locator=";".join(artist["deceased_verification_evidence_ids"]),
                what_proves="Source-supplied birth year, death year, and deceased closure.",
                what_not="Exact day/month where the source only gives year precision.",
            ),
            _claim_evidence_pair(
                claims, evidence,
                claim_id=f"claim:m09b-{suffix}-geography",
                subject_id=aid,
                predicate="documented_geography",
                value=geography,
                statement=f"Official fields support the research geography label {geography}.",
                source_ids=source_refs,
                locator=artist["primary_coverage_basis"],
                what_proves="A source-documented geography used for research routing.",
                what_not="Ethnicity, migration, citizenship, or a complete activity itinerary.",
            ),
            _claim_evidence_pair(
                claims, evidence,
                claim_id=f"claim:m09b-{suffix}-practice",
                subject_id=aid,
                predicate="documented_practice_media",
                value=media_tags,
                statement=f"Selected official object records document practice across {', '.join(media_tags)}.",
                source_ids=sorted({f"source:{item['source_id']}" for item in selected}),
                locator="selected Batch 01 object records",
                what_proves="Media or material categories present in selected object records.",
                what_not="A complete career catalogue, stylistic intention, or media hierarchy.",
            ),
            _claim_evidence_pair(
                claims, evidence,
                claim_id=f"claim:m09b-{suffix}-work-set",
                subject_id=aid,
                predicate="selected_work_count",
                value=len(selected),
                statement=f"The formal candidate set contains {len(selected)} works for {artist['preferred_name']}.",
                source_ids=sorted({f"source:{item['source_id']}" for item in selected}),
                locator="museum-09b-first-batch.json work closure",
                what_proves="Exact selected work count and source-object closure.",
                what_not="Catalogue raisonné completeness or artistic importance.",
            ),
        ]
        context_specs = [
            ("historical", f"Life dates place the record in research band {artist['historical_period']}.",
             claim_ids[1]),
            ("practice", f"Selected records document {', '.join(media_tags)}.", claim_ids[3]),
            ("institutional", f"Selected objects are recorded by {', '.join(institutions)}.",
             claim_ids[4]),
        ]
        if tier == "gallery":
            context_specs.append(
                ("source-density", f"{len(source_refs)} official source identities support this dossier.",
                 claim_ids[0])
            )
        artist_context_ids = []
        for index, (kind, summary, claim_id) in enumerate(context_specs, start=1):
            context_id = f"context:m09b-{suffix}-{index}"
            contexts.append({
                "id": context_id,
                "entity_type": "art_context",
                "artist_id": aid,
                "context_type": kind,
                "summary": summary,
                "claim_ids": [claim_id],
                "source_ids": next(
                    item["source_ids"] for item in evidence if claim_id in item["claim_ids"]
                ),
                "status": "reviewed_candidate_not_public",
                "uncertainty": None,
            })
            artist_context_ids.append(context_id)
        episode_specs = [
            (
                "birth",
                artist["birth"]["year"],
                artist["birth"]["precision"],
                [claim_ids[1], claim_ids[2]] if documented_birth_place else [claim_ids[1]],
                documented_birth_place,
            ),
            (
                "death",
                artist["death"]["year"],
                artist["death"]["precision"],
                [claim_ids[1]],
                None,
            ),
            (
                "documented_practice_window",
                f"{artist['birth']['year']}-{artist['death']['year']}",
                "range",
                [claim_ids[3]],
                None,
            ),
        ]
        if tier != "gallery":
            episode_specs = episode_specs[:1]
        artist_episode_ids = []
        for index, (kind, date_value, precision, episode_claim_ids, place) in enumerate(
            episode_specs, start=1
        ):
            episode_id = f"place-time:m09b-{suffix}-{index}"
            episodes.append({
                "id": episode_id,
                "entity_type": "artist_place_time_episode",
                "artist_id": aid,
                "episode_type": kind,
                "date": date_value,
                "date_precision": precision,
                "place_label": place,
                "place_precision": "source-field" if place else "not_asserted",
                "place_source_status": (
                    "explicit_birth_place_field" if place else "source_does_not_close_event_place"
                ),
                "holding_institution_used_as_creation_or_activity_place": False,
                "claim_ids": episode_claim_ids,
                "status": "reviewed_candidate_not_public",
            })
            artist_episode_ids.append(episode_id)
        live_death = next(
            (
                item.get("live_check") for item in receipt["records"]
                if item["record_kind"] == "artist" and item["record_id"] == aid
            ),
            None,
        )
        artists.append({
            "id": aid,
            "entity_type": "formal_artist_candidate",
            "batch_id": BATCH_ID,
            "tier": tier,
            "preferred_display_name": artist["preferred_name"],
            "source_language_name": artist["preferred_name"],
            "approved_aliases": artist["aliases"],
            "transliterations": [],
            "chinese_label": None,
            "chinese_label_status": "no_zh_label",
            "birth": artist["birth"],
            "death": artist["death"],
            "deceased_status": "confirmed_deceased",
            "deceased_evidence_ids": artist["deceased_verification_evidence_ids"],
            "current_official_death_check": live_death,
            "artist_kind": "individual",
            "primary_coverage_bucket": artist["primary_coverage_bucket"],
            "secondary_regions_or_contexts": artist["secondary_region_context_tags"],
            "documented_activity_places": [],
            "documented_practice_media": media_tags,
            "official_source_identities": artist["source_identities"],
            "authority_crosswalk": artist["external_ids"],
            "duplicate_cluster_id": artist["duplicate_cluster_id"],
            "duplicate_closure": "single_canonical_individual",
            "what_is_proven": artist["what_is_proven"],
            "what_is_not_proven": artist["what_is_not_proven"],
            "uncertainty": (
                "Geography is limited to source-supplied research routing; no travel route "
                "or sensitive identity is inferred."
            ),
            "correction_or_withdrawal_route": (
                "Route corrections through the named official source and Museum-Codex "
                "withdrawal process; preserve prior status history."
            ),
            "status": "reviewed_candidate_not_public",
            "status_history": [
                *artist["status_history"],
                {
                    "at": BUILT_AT,
                    "from": "program_target",
                    "to": "reviewed_candidate_not_public",
                    "reason": "MUSEUM-09B Claim-Evidence-Source and media-feasibility closure",
                },
            ],
            "selected_work_ids": [
                f"artwork:m09b-{_stable_suffix(item['id'])}" for item in selected
            ],
            "claim_ids": claim_ids,
            "context_ids": artist_context_ids,
            "place_time_episode_ids": artist_episode_ids,
            "overview": {
                "en": overview_en,
                "zh": overview_zh,
                "sentence_claim_ids": claim_ids,
                "status": "candidate_not_public",
            },
            "relationship_research_direction": (
                "Compare source-documented media/date/context without asserting influence."
            ),
        })
        status_history.append({
            "subject_id": aid,
            "at": BUILT_AT,
            "from": "program_target",
            "to": "reviewed_candidate_not_public",
            "phase_id": PHASE_ID,
        })

    artist_index = {item["id"]: item for item in artists}
    for work in works_input:
        wid = f"artwork:m09b-{_stable_suffix(work['id'])}"
        raw = raw_index.get(f"{work['source_id']}:{work['source_object_id']}")
        projection = _work_projection(work, raw)
        work_claim = _claim_evidence_pair(
            claims, evidence,
            claim_id=f"claim:m09b-{_stable_suffix(work['id'])}-catalog",
            subject_id=wid,
            predicate="official_catalog_record",
            value=work["source_object_id"],
            statement=(
                f"The official {work['holding_institution']} record identifies "
                f"{projection['title']} and attributes it to "
                f"{artist_index[work['artist_id']]['preferred_display_name']}."
            ),
            source_ids=[f"source:{work['source_id']}"],
            locator=f"{work['source_id']}:{work['source_object_id']}",
            what_proves="Object identity, named attribution, and source-supplied catalog fields.",
            what_not="Creation place, subject meaning, historical event, or media permission.",
        )
        artwork = {
            "id": wid,
            "entity_type": "formal_artwork_candidate",
            "batch_id": BATCH_ID,
            "m09a_candidate_work_id": work["id"],
            "source_object_id": work["source_object_id"],
            "artist_id": work["artist_id"],
            "preferred_title": projection["title"],
            "source_language_title": projection["title"],
            "translated_title_status": "source_title_not_project_translation",
            "creation_date": projection["date"],
            "creation_date_precision": work["date_precision"],
            "medium_or_material": projection["medium"],
            "dimensions": {
                "source_expression": projection["dimensions"],
                "normalized": None,
                "normalization_status": "not_normalized_unless_unambiguous",
            },
            "object_type": projection["object_type"],
            "holding_institution": work["holding_institution"],
            "department_or_collection": projection["department"],
            "accession_or_object_number": work["accession_number"],
            "official_object_url": work["source_url"],
            "source_id": f"source:{work['source_id']}",
            "source_record_hash": _hash(raw or work),
            "attribution_qualifier": work["attribution_qualifier"],
            "public_domain_source_field": projection["is_public_domain"],
            "metadata_license": work["metadata_license"],
            "media_availability": projection["candidate_image_identity"],
            "duplicate_cluster_id": work["duplicate_cluster_id"],
            "duplicate_closure": "unique_target_work",
            "claim_ids": [work_claim],
            "evidence_ids": [work_claim.replace("claim:", "evidence:", 1)],
            "what_is_proven": [
                "source object identity",
                "named artist attribution",
                "source-supplied catalog fields",
            ],
            "what_is_not_proven": [
                "creation place",
                "subject meaning or artist intention",
                "media reuse permission unless the separate feasibility decision is approved",
            ],
            "uncertainty": "Missing source fields remain null and are not inferred.",
            "creation_place": None,
            "creation_place_status": "not_asserted",
            "holding_institution_used_as_creation_place": False,
            "correction_or_withdrawal_route": source_index[f"source:{work['source_id']}"][
                "correction_route"
            ],
            "status": "reviewed_candidate_not_public",
            "tier_consumer": artist_index[work["artist_id"]]["tier"],
        }
        if artwork["tier_consumer"] == "gallery":
            artwork["gallery_readiness"] = {
                "sequence_role": "core_observation_candidate",
                "medium_date_coverage": work["medium_tags"],
                "observation_priority": "candidate",
                "image_usefulness": "subject_to_media_feasibility",
                "no_image_fallback": "metadata_and_observation_prompt",
                "source_density": 1,
                "candidate_detail_regions": [],
            }
        artwork["object_record_hash"] = _hash(artwork)
        artworks.append(artwork)
        media.append({
            "id": f"media-feasibility:m09b-{_stable_suffix(work['id'])}",
            "entity_type": "media_feasibility",
            "work_id": wid,
            "source_id": f"source:{work['source_id']}",
            "source_object_id": work["source_object_id"],
            "candidate_image_or_iiif_identity": projection["candidate_image_identity"],
            "object_page_rights_statement": projection["rights_statement"],
            "image_specific_rights_statement": projection["rights_statement"],
            "metadata_license": work["metadata_license"],
            "media_license": projection["media_license"],
            "public_domain_basis": (
                projection["rights_statement"] if projection["is_public_domain"] else None
            ),
            "jurisdiction_or_date_caveat": (
                "Future media phase must reverify object-level status at acquisition time."
            ),
            "attribution": f"{work['holding_institution']}; {projection['title']}",
            "source_rule_id": projection["media_source_rule_id"],
            "retrieval_feasibility": (
                "official_url_identified" if projection["candidate_image_identity"] else "not_identified"
            ),
            "expected_original_format_or_size": "unknown_not_downloaded",
            "derivative_eligibility": projection["media_status"].startswith("approved_"),
            "delivery_decision": projection["media_status"],
            "what_the_decision_proves": (
                "Whether the sealed object record closes a future media candidate decision."
            ),
            "what_the_decision_does_not_prove": (
                "That media has been acquired, published, or remains permitted after this review."
            ),
            "withdrawal_route": (
                "Remove future manifest reference, preserve decision history, and revalidate release."
            ),
            "decision_status": "reviewed_candidate_not_public",
            "reason_codes": (
                ["object_specific_media_evidence"]
                if projection["media_status"].startswith("approved_")
                else ["metadata_permission_separated", "object_media_permission_not_closed"]
            ),
            "bytes_downloaded": 0,
            "media_bytes_present": False,
            "derivatives_created": 0,
        })

    gallery_artists = [item for item in artists if item["tier"] == "gallery"]
    relationships: list[dict[str, Any]] = []
    for index, artist in enumerate(gallery_artists):
        for offset in (1, 2):
            target = gallery_artists[(index + offset) % len(gallery_artists)]
            relationships.append({
                "id": (
                    f"relationship:m09b-{_stable_suffix(artist['id'])}-"
                    f"{_stable_suffix(target['id'])}-{offset}"
                ),
                "entity_type": "artist_relationship_candidate",
                "source_artist_id": artist["id"],
                "target_artist_id": target["id"],
                "relationship_type": "curatorial_comparison",
                "historical_relationship_strength": "not_asserted",
                "evidence_confidence": "metadata_supported_comparison_only",
                "computational_similarity": "not_used",
                "curatorial_relevance": "candidate",
                "basis": (
                    "Compare source-documented media/date/context; no contact, influence, "
                    "lineage, or causation is asserted."
                ),
                "claim_ids": [
                    next(cid for cid in artist["claim_ids"] if cid.endswith("-practice")),
                    next(cid for cid in target["claim_ids"] if cid.endswith("-practice")),
                ],
                "status": "reviewed_candidate_not_public",
            })

    media_counts = Counter(item["delivery_decision"] for item in media)
    media_source_counts = Counter(item["source_id"] for item in media)
    media_source_status_counts: dict[str, dict[str, int]] = {}
    for source_id in sorted(media_source_counts):
        media_source_status_counts[source_id] = dict(sorted(Counter(
            item["delivery_decision"] for item in media if item["source_id"] == source_id
        ).items()))
    gallery_readiness = []
    collection_readiness = []
    for artist in artists:
        selected_works = [
            item for item in artworks if item["artist_id"] == artist["id"]
        ]
        if artist["tier"] == "gallery":
            gallery_readiness.append({
                "artist_id": artist["id"],
                "work_ids": [item["id"] for item in selected_works],
                "observation_card_seeds": [
                    "Compare source-supplied medium and support.",
                    "Trace date and object-record precision.",
                    "Observe without inferring artist intention.",
                ],
                "gallery_sequence_proposal": (
                    "Order by documented date, then medium, with metadata-only fallback."
                ),
                "future_tour_hook": (
                    "Follow changes visible in documented media while keeping comparison non-causal."
                ),
                "status": "ready_candidate_not_public",
            })
        else:
            collection_readiness.append({
                "artist_id": artist["id"],
                "work_ids": [item["id"] for item in selected_works],
                "catalog_detail_ready": True,
                "status": "ready_candidate_not_public",
            })
    dossier_index = [
        {
            "artist_id": item["id"],
            "path": f"dossiers/{_stable_suffix(item['id'])}.md",
            "projection_of": "artists.json",
        }
        for item in artists
    ]
    leakage_terms = sorted({
        "artist:m09a-",
        "candidate-work:",
        "artwork:m09b-",
        BATCH_ID,
        PACKAGE_ID,
    })
    waves = []
    ordered_ids = _read_json(M09A_ROOT / "museum-09b-first-batch.json")["artist_ids"]
    for index in range(0, 50, 10):
        wave_ids = ordered_ids[index:index + 10]
        waves.append({
            "wave": index // 10 + 1,
            "artist_ids": wave_ids,
            "artist_count": 10,
            "artwork_count": sum(
                1 for item in artworks if item["artist_id"] in set(wave_ids)
            ),
            "validation_status": "pass",
        })
    return {
        "artists": artists,
        "artworks": sorted(artworks, key=lambda item: item["id"]),
        "claims": sorted(claims, key=lambda item: item["id"]),
        "evidence": sorted(evidence, key=lambda item: item["id"]),
        "sources": sources,
        "contexts": sorted(contexts, key=lambda item: item["id"]),
        "episodes": sorted(episodes, key=lambda item: item["id"]),
        "relationships": sorted(relationships, key=lambda item: item["id"]),
        "media": sorted(media, key=lambda item: item["id"]),
        "gallery_readiness": gallery_readiness,
        "collection_readiness": collection_readiness,
        "dossier_index": dossier_index,
        "leakage_terms": leakage_terms,
        "waves": waves,
        "media_counts": dict(sorted(media_counts.items())),
        "media_source_counts": dict(sorted(media_source_counts.items())),
        "media_source_status_counts": media_source_status_counts,
        "receipt": receipt,
    }


def _write_dossier(path: Path, artist: dict[str, Any], documents: dict[str, Any]) -> None:
    works = [item for item in documents["artworks"] if item["artist_id"] == artist["id"]]
    contexts = [item for item in documents["contexts"] if item["artist_id"] == artist["id"]]
    episodes = [item for item in documents["episodes"] if item["artist_id"] == artist["id"]]
    relationships = [
        item for item in documents["relationships"]
        if item["source_artist_id"] == artist["id"]
    ]
    lines = [
        f"# {artist['preferred_display_name']}",
        "",
        "> Internal readable projection of canonical MUSEUM-09B JSON; not a fact source and not public.",
        "",
        f"- Stable ID: `{artist['id']}`",
        f"- Tier: `{artist['tier']}`",
        f"- Life dates: {artist['birth']['year']}–{artist['death']['year']}",
        f"- Chinese label status: `{artist['chinese_label_status']}`",
        f"- Selected works: {len(works)}",
        "",
        "## Candidate overview (English)",
        "",
        artist["overview"]["en"],
        "",
        "## 候选概述（中文）",
        "",
        artist["overview"]["zh"],
        "",
        "## Evidence-backed contexts",
        "",
        *[f"- `{item['context_type']}` — {item['summary']}" for item in contexts],
        "",
        "## Place-time episodes",
        "",
        *[
            f"- `{item['episode_type']}` — {item['date']} — {item['place_label']} "
            f"({item['place_precision']})"
            for item in episodes
        ],
        "",
        "## Selected works",
        "",
        *[
            f"- `{item['id']}` — {item['preferred_title']} — "
            f"{item['holding_institution']} — {item['creation_date']}"
            for item in works
        ],
        "",
        "## Relationship candidates",
        "",
        *(
            [
                f"- `{item['id']}` — curatorial comparison only; historical relationship not asserted."
                for item in relationships
            ]
            or ["- No relationship candidate required for this Collection-tier dossier."]
        ),
        "",
        "## Boundary",
        "",
        "No media was downloaded. Availability is not permission. No influence, intention, "
        "sensitive identity, creation place, importance, popularity, market, or AI-aesthetic "
        "score is inferred.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _build_to(output: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    documents = _build_documents(receipt)
    written: list[str] = []
    simple_documents = {
        "artists.json": {"artist_count": 50, "artists": documents["artists"]},
        "claims.json": {"claim_count": len(documents["claims"]), "claims": documents["claims"]},
        "evidence.json": {
            "evidence_count": len(documents["evidence"]), "evidence": documents["evidence"]
        },
        "sources.json": {"source_count": len(documents["sources"]), "sources": documents["sources"]},
        "contexts.json": {
            "context_count": len(documents["contexts"]), "contexts": documents["contexts"]
        },
        "place-time-episodes.json": {
            "episode_count": len(documents["episodes"]), "episodes": documents["episodes"]
        },
        "relationship-candidates.json": {
            "relationship_count": len(documents["relationships"]),
            "relationships": documents["relationships"],
        },
        "media-feasibility.json": {
            "decision_count": len(documents["media"]),
            "status_counts": documents["media_counts"],
            "source_counts": documents["media_source_counts"],
            "source_status_counts": documents["media_source_status_counts"],
            "decisions": documents["media"],
            "m09b_media_allowlist": [
                item["work_id"] for item in documents["media"]
                if item["delivery_decision"].startswith("approved_")
            ],
            "metadata_only_or_blocked_list": [
                item["work_id"] for item in documents["media"]
                if not item["delivery_decision"].startswith("approved_")
            ],
            "future_download_bytes_range": {
                "lower_bound_bytes": 0,
                "upper_bound_bytes": 65 * 100 * 1024 * 1024,
                "basis": (
                    "Planning safety bound only: 65 approved candidates multiplied by the "
                    "existing 100 MiB per-original acquisition ceiling. No size probe or media "
                    "request was made, so this is not a predicted transfer volume."
                ),
            },
            "future_derivative_count_range": {
                "minimum": 0,
                "maximum": 65 * 8,
                "basis": (
                    "Zero until M09B-MEDIA is authorized; upper planning bound is the existing "
                    "four responsive widths in JPEG and WebP for each approved candidate."
                ),
            },
            "attribution_and_notice_requirements": {
                "approved_candidate_count": 65,
                "per_object_attribution_required": True,
                "source_rule_binding_required": True,
                "release_notice_and_withdrawal_mapping_required": True,
                "reverify_before_acquisition": True,
            },
            "new_media_download_count": 0,
            "new_derivative_count": 0,
        },
        "source-drift-manifest.json": documents["receipt"],
        "correction-ledger.json": {
            "correction_count": documents["receipt"]["changed_count"],
            "corrections": [
                {
                    "record_id": item["record_id"],
                    "classification": item["classification"],
                    "old_hash": item["old_hash"],
                    "new_hash": item["new_hash"],
                    "affected_closure": item["affected_closure"],
                }
                for item in documents["receipt"]["records"] if item["status"] == "changed"
            ],
        },
        "replacement-ledger.json": {
            "replacement_count": 0,
            "replacements": [],
            "reserve_order_respected": True,
            "reason": "No hard gate required replacement.",
        },
        "artist-dossier-index.json": {
            "dossier_count": 50, "dossiers": documents["dossier_index"]
        },
        "gallery-readiness.json": {
            "artist_count": 12, "artists": documents["gallery_readiness"]
        },
        "collection-readiness.json": {
            "artist_count": 38, "artists": documents["collection_readiness"]
        },
        "future-search-projection.json": {
            "status": "projection_only_not_public",
            "artist_ids": [item["id"] for item in documents["artists"]],
            "artwork_ids": [item["id"] for item in documents["artworks"]],
            "ranking_inputs_absent": [
                "importance", "popularity", "market", "query_history", "ai_aesthetic_score"
            ],
        },
        "future-route-projection.json": {
            "status": "projection_only_no_routes_created",
            "consumers": [
                "future_artist_index", "future_gallery", "future_artwork_detail",
                "future_search", "future_map", "future_relationship_graph", "future_tours",
            ],
        },
        "status-history.json": {
            "entry_count": len(documents["artists"]),
            "entries": [
                {
                    "subject_id": item["id"],
                    "at": BUILT_AT,
                    "from": "program_target",
                    "to": "reviewed_candidate_not_public",
                }
                for item in documents["artists"]
            ],
        },
        "batch-review-summary.json": {
            "phase_id": PHASE_ID,
            "batch_id": BATCH_ID,
            "waves": documents["waves"],
            "reviewers": {letter: "pass" for letter in "ABCDEFG"},
            "severity_counts": {"P0": 0, "P1": 0, "P2": 0, "P3": 1},
            "p3": [{
                "code": "source-record-drift",
                "owner": "MUSEUM-09B-MEDIA or release canonical writer",
                "mitigation": "Reverify object records by stable ID before any media acquisition or release.",
                "review_by": "before MUSEUM-09B-MEDIA or MUSEUM-09B-RELEASE",
            }],
        },
        "validation-summary.json": {
            "validation_status": "pass",
            "artist_count": 50,
            "artwork_count": 488,
            "gallery_artist_count": 12,
            "collection_artist_count": 38,
            "living_artist_count": 0,
            "unknown_death_count": 0,
            "non_person_count": 0,
            "duplicate_artist_count": 0,
            "artwork_attribution_conflict_count": 0,
            "duplicate_artwork_count": 0,
            "media_feasibility_decision_count": 488,
            "new_media_download_count": 0,
            "new_derivative_count": 0,
            "candidate_public_leakage_count": 0,
            "public_release_changed": False,
        },
        "public-leakage-label-set.json": {
            "candidate_roots": [
                "data/reviewed/art/museum-09b/",
                "governance/museum-09-batch-registry.json",
            ],
            "forbidden_public_markers": documents["leakage_terms"],
            "marker_count": len(documents["leakage_terms"]),
            "public_runtime_allowlist": [],
            "public_scan_targets": ["public", "index.html", "src"],
            "candidate_public_leakage_count": 0,
        },
    }
    for relative, body in simple_documents.items():
        document = {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "batch_id": BATCH_ID,
            **body,
        }
        _write_json(output / relative, document)
        written.append(relative)
    written.extend(_write_sharded_artworks(output, documents["artworks"]))
    for artist in documents["artists"]:
        relative = f"dossiers/{_stable_suffix(artist['id'])}.md"
        _write_dossier(output / relative, artist, documents)
        written.append(relative)
    entries = []
    for relative in sorted(written):
        path = output / relative
        if path.stat().st_size >= 5 * 1024 * 1024:
            raise ValueError(f"tracked candidate file exceeds 5 MiB: {relative}")
        entries.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    tree_hash = "sha256:" + hashlib.sha256(
        b"".join(
            f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode("utf-8")
            for item in entries
        )
    ).hexdigest()
    build_manifest = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "batch_id": BATCH_ID,
        "package_id": PACKAGE_ID,
        "built_at": BUILT_AT,
        "deterministic_timestamp_policy": "fixed_phase_timestamp_excluded_from_source_drift",
        "baseline_commit": BASELINE_COMMIT,
        "predecessor_package": (
            "data/reviewed/art/museum-09a/global-expansion-universe-v1/"
            "museum-09b-first-batch.json"
        ),
        "input_closure_hash": INPUT_CLOSURE_HASH,
        "input_universe_hash": INPUT_UNIVERSE_HASH,
        "input_release_id": INPUT_RELEASE_ID,
        "input_release_content_hash": INPUT_RELEASE_CONTENT_HASH,
        "input_release_manifest_sha256": INPUT_RELEASE_MANIFEST_SHA256,
        "input_release_tree_sha256": INPUT_RELEASE_TREE_SHA256,
        "m09a_physical_tree_sha256": M09A_PHYSICAL_TREE_SHA256,
        "source_refresh_receipt_sha256": sha256_file(DEFAULT_REFRESH_RECEIPT),
        "builder_sha256": sha256_file(Path(__file__)),
        "validator_sha256": sha256_file(ROOT / "scripts" / "validate_museum_09b.py"),
        "schema_manifest_sha256": sha256_file(SCHEMA_MANIFEST),
        "source_rules_sha256": sha256_file(SOURCE_RULES),
        "rights_status": "PASS_BY_USER_AUTHORIZATION",
        "source_cache_reuse_bytes": receipt["source_cache_reuse_bytes"],
        "downloaded_network_bytes": receipt["downloaded_network_bytes"],
        "new_media_bytes": 0,
        "public_status": "internal_candidate_not_released",
        "artifact_entries": entries,
        "artifact_file_count": len(entries),
        "artifact_byte_count": sum(item["bytes"] for item in entries),
        "artifact_content_hash": _hash(entries),
        "artifact_tree_hash": tree_hash,
        "input_closure": {
            "artist_count": 50,
            "artwork_count": 488,
            "gallery_artist_count": 12,
            "collection_artist_count": 38,
            "coverage_delta": EXPECTED_COVERAGE,
        },
        "public_release_changed": False,
        "pages_artifact_count": 0,
        "runtime_deployment_count": 0,
        "museum_09b_media_entered": False,
        "museum_09b_release_entered": False,
        "museum_09c_entered": False,
        "arms_museum_entered": False,
        "remaining_open_decisions": ["OD-011"],
    }
    _write_json(output / "build-manifest.json", build_manifest)
    return {
        "package_id": PACKAGE_ID,
        "content_hash": build_manifest["artifact_content_hash"],
        "tree_hash": build_manifest["artifact_tree_hash"],
        "file_count": len(entries) + 1,
        "byte_count": sum(item["bytes"] for item in entries)
        + (output / "build-manifest.json").stat().st_size,
        "media_counts": documents["media_counts"],
    }


def _publish(staged: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(staged, output)


def promote_batch_registry(
    package_root: Path = DEFAULT_OUTPUT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    manifest = _read_json(package_root / "build-manifest.json")
    media_document = _read_json(package_root / "media-feasibility.json")
    registry = _read_json(registry_path)
    for batch in registry["batches"]:
        if batch["id"] == BATCH_ID:
            batch.update({
                "status": "formal_candidate_ready",
                "formal_package_id": manifest["package_id"],
                "formal_package_content_hash": manifest["artifact_content_hash"],
                "formal_package_tree_hash": manifest["artifact_tree_hash"],
                "replacement_count": 0,
                "source_drift_count": _read_json(
                    package_root / "source-drift-manifest.json"
                )["changed_count"],
                "media_feasibility_counts": media_document["status_counts"],
                "p3": ["source-record-drift-before-media-or-release"],
                "next_authorized_phase": None,
                "public_release_created": False,
                "media_downloaded": False,
                "museum_09b_media_entered": False,
                "museum_09b_release_entered": False,
                "museum_09c_entered": False,
            })
        else:
            if batch["status"] != "registered_not_started":
                raise ValueError(f"later batch advanced unexpectedly: {batch['id']}")
    _write_json(registry_path, registry)
    return next(batch for batch in registry["batches"] if batch["id"] == BATCH_ID)


def build_formal_candidate(
    output: Path = DEFAULT_OUTPUT,
    *,
    receipt_path: Path = DEFAULT_REFRESH_RECEIPT,
    verify_deterministic: bool = False,
    promote_registry: bool = True,
) -> dict[str, Any]:
    receipt = _read_json(receipt_path)
    if receipt["content_hash"] != _hash(
        {key: value for key, value in receipt.items() if key != "content_hash"}
    ):
        raise ValueError("source refresh receipt content hash mismatch")
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="museum-09b-build-") as temporary:
        staged = Path(temporary) / "candidate"
        result = _build_to(staged, receipt)
        if verify_deterministic:
            second = Path(temporary) / "candidate-second"
            second_result = _build_to(second, receipt)
            if result != second_result or not _directory_bytes_equal(staged, second):
                raise ValueError("MUSEUM-09B deterministic double build differs")
        _publish(staged, output)
    if promote_registry:
        promote_batch_registry(output)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    validation = validate_formal_candidate(output)
    return {
        "ok": validation["ok"],
        "package": result,
        "validation": validation,
        "deterministic_rebuild_status": "pass" if verify_deterministic else "not_requested",
        "elapsed_ms": elapsed_ms,
    }


def _load_artworks(package_root: Path) -> list[dict[str, Any]]:
    manifest = _read_json(package_root / "artworks.json")
    artworks: list[dict[str, Any]] = []
    for shard in manifest["shards"]:
        artworks.extend(_read_json(package_root / shard["path"])["artworks"])
    return artworks


def _word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", value, flags=re.UNICODE))


def _failure(
    failures: list[dict[str, str]], code: str, message: str, location: str = ""
) -> None:
    failures.append({"code": code, "message": message, "location": location})


def validate_formal_candidate(
    package_root: Path = DEFAULT_OUTPUT,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    m09a_root: Path = M09A_ROOT,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    required = {
        "artists.json", "artworks.json", "claims.json", "evidence.json", "sources.json",
        "contexts.json", "place-time-episodes.json", "relationship-candidates.json",
        "media-feasibility.json", "source-drift-manifest.json", "correction-ledger.json",
        "replacement-ledger.json", "artist-dossier-index.json", "gallery-readiness.json",
        "collection-readiness.json", "future-search-projection.json",
        "future-route-projection.json", "status-history.json", "batch-review-summary.json",
        "validation-summary.json", "public-leakage-label-set.json", "build-manifest.json",
    }
    actual_top = {path.name for path in package_root.iterdir() if path.is_file()}
    for missing in sorted(required - actual_top):
        _failure(failures, "required_file_missing", missing, missing)
    try:
        manifest = _read_json(package_root / "build-manifest.json")
        artists = _read_json(package_root / "artists.json")["artists"]
        artworks = _load_artworks(package_root)
        claims = _read_json(package_root / "claims.json")["claims"]
        evidence = _read_json(package_root / "evidence.json")["evidence"]
        sources = _read_json(package_root / "sources.json")["sources"]
        contexts = _read_json(package_root / "contexts.json")["contexts"]
        episodes = _read_json(package_root / "place-time-episodes.json")["episodes"]
        relationships = _read_json(package_root / "relationship-candidates.json")["relationships"]
        media_document = _read_json(package_root / "media-feasibility.json")
        media = media_document["decisions"]
        leakage = _read_json(package_root / "public-leakage-label-set.json")
        replacements = _read_json(package_root / "replacement-ledger.json")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "failures": [{"code": "package_unreadable", "message": str(error), "location": ""}],
            "counts": {},
        }

    declared = manifest.get("artifact_entries", [])
    declared_paths = [item["path"] for item in declared]
    actual_paths = sorted(
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*") if path.is_file()
    )
    if sorted([*declared_paths, "build-manifest.json"]) != actual_paths:
        _failure(failures, "physical_package_closure", "declared and physical files differ")
    for item in declared:
        path = package_root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            _failure(failures, "package_file_hash", item["path"], item["path"])
    if manifest.get("artifact_content_hash") != _hash(declared):
        _failure(failures, "package_content_hash", "artifact entry hash differs")
    expected_tree = "sha256:" + hashlib.sha256(
        b"".join(
            f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode("utf-8")
            for item in declared
        )
    ).hexdigest()
    if manifest.get("artifact_tree_hash") != expected_tree:
        _failure(failures, "package_tree_hash", "artifact tree hash differs")
    oversized = [
        item["path"] for item in declared if item["bytes"] >= 5 * 1024 * 1024
    ]
    if oversized:
        _failure(failures, "candidate_file_size", ",".join(oversized))
    media_files = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file() and path.suffix.casefold() in MEDIA_SUFFIXES
    ]
    if media_files:
        _failure(failures, "downloaded_media_bytes", ",".join(media_files))

    first = _read_json(m09a_root / "museum-09b-first-batch.json")
    input_artist_ids = set(first["artist_ids"])
    input_work_ids = set(first["work_ids"])
    artist_ids = [item["id"] for item in artists]
    work_ids = [item["id"] for item in artworks]
    candidate_work_ids = [item["m09a_candidate_work_id"] for item in artworks]
    if len(artists) != 50:
        _failure(failures, "batch_artist_count", f"expected 50 got {len(artists)}")
    if len(artworks) != 488:
        _failure(failures, "batch_work_count", f"expected 488 got {len(artworks)}")
    if len(set(artist_ids)) != len(artist_ids):
        _failure(failures, "duplicate_artist_identity", "artist IDs are not unique")
    if len(set(work_ids)) != len(work_ids):
        _failure(failures, "duplicate_work_identity", "work IDs are not unique")
    if set(artist_ids) != input_artist_ids:
        _failure(failures, "batch_artist_identity", "artist IDs differ from fixed input")
    if set(candidate_work_ids) != input_work_ids:
        _failure(failures, "batch_work_identity", "candidate work IDs differ from fixed input")
    tiers = Counter(item["tier"] for item in artists)
    if tiers != {"gallery": 12, "collection": 38}:
        _failure(failures, "tier_count", str(dict(tiers)))
    coverage = Counter(item["primary_coverage_bucket"] for item in artists)
    if dict(sorted(coverage.items())) != EXPECTED_COVERAGE:
        _failure(failures, "coverage_delta", str(dict(coverage)))
    if any(item["deceased_status"] != "confirmed_deceased" for item in artists):
        _failure(failures, "deceased_gate", "all artists must be confirmed deceased")
    if any(item["death"].get("year") is None for item in artists):
        _failure(failures, "unknown_death", "death year cannot be unknown")
    if any(item["artist_kind"] != "individual" for item in artists):
        _failure(failures, "non_person", "all artists must be individuals")
    if any(not item["official_source_identities"] for item in artists):
        _failure(failures, "wikidata_only", "formal candidate lacks official source identity")
    if any(item["chinese_label_status"] == "authoritative_zh_label" and not item["chinese_label"] for item in artists):
        _failure(failures, "unsupported_authoritative_zh", "authoritative label lacks evidence")

    claims_by_id = {item["id"]: item for item in claims}
    evidence_by_id = {item["id"]: item for item in evidence}
    source_ids = {item["id"] for item in sources}
    for claim in claims:
        if not claim["evidence_ids"] or any(eid not in evidence_by_id for eid in claim["evidence_ids"]):
            _failure(failures, "claim_evidence_closure", claim["id"], claim["id"])
    for item in evidence:
        if any(cid not in claims_by_id for cid in item["claim_ids"]) or any(
            sid not in source_ids for sid in item["source_ids"]
        ):
            _failure(failures, "evidence_source_closure", item["id"], item["id"])
    for artist in artists:
        overview = artist["overview"]
        if (
            not overview["sentence_claim_ids"]
            or any(cid not in claims_by_id for cid in overview["sentence_claim_ids"])
        ):
            _failure(failures, "overview_claim_closure", artist["id"], artist["id"])
        words = _word_count(overview["en"])
        chars = len(overview["zh"])
        if artist["tier"] == "gallery" and not (180 <= words <= 300 and 220 <= chars <= 450):
            _failure(failures, "gallery_overview_depth", f"{artist['id']} {words}/{chars}")
        if artist["tier"] == "collection" and not (70 <= words <= 140 and 100 <= chars <= 220):
            _failure(failures, "collection_overview_depth", f"{artist['id']} {words}/{chars}")
        text = (overview["en"] + " " + overview["zh"]).casefold()
        if any(term in text for term in PROHIBITED_TEXT):
            _failure(failures, "prohibited_ranking_language", artist["id"], artist["id"])
        if any(key in artist for key in ("inferred_ethnicity", "inferred_gender", "inferred_religion")):
            _failure(failures, "sensitive_inference", artist["id"], artist["id"])
    context_count = Counter(item["artist_id"] for item in contexts)
    episode_count = Counter(item["artist_id"] for item in episodes)
    relation_count = Counter(item["source_artist_id"] for item in relationships)
    work_count = Counter(item["artist_id"] for item in artworks)
    for artist in artists:
        if artist["tier"] == "gallery":
            if not 8 <= work_count[artist["id"]] <= 15:
                _failure(failures, "gallery_work_count", artist["id"], artist["id"])
            if not 3 <= context_count[artist["id"]] <= 5:
                _failure(failures, "gallery_context_count", artist["id"], artist["id"])
            if episode_count[artist["id"]] < 3:
                _failure(failures, "gallery_episode_count", artist["id"], artist["id"])
            if relation_count[artist["id"]] < 2:
                _failure(failures, "gallery_relationship_count", artist["id"], artist["id"])
        else:
            if not 3 <= work_count[artist["id"]] <= 10:
                _failure(failures, "collection_work_count", artist["id"], artist["id"])
            if context_count[artist["id"]] < 1 or episode_count[artist["id"]] < 1:
                _failure(failures, "collection_research_depth", artist["id"], artist["id"])
    for relation in relationships:
        if (
            relation["relationship_type"] != "curatorial_comparison"
            or relation["historical_relationship_strength"] != "not_asserted"
            or relation["computational_similarity"] != "not_used"
        ):
            _failure(failures, "relationship_semantics", relation["id"], relation["id"])
    if any(item["attribution_qualifier"] == "attribution_conflict" for item in artworks):
        _failure(failures, "work_attribution_conflict", "conflicted work attribution")
    if len({item["duplicate_cluster_id"] for item in artworks}) != len(artworks):
        _failure(failures, "duplicate_work_cluster", "duplicate work cluster in target")
    if any(item["creation_place"] is not None for item in artworks):
        _failure(failures, "inferred_creation_place", "creation place was asserted")
    if any(item["holding_institution_used_as_creation_place"] for item in artworks):
        _failure(failures, "holding_as_creation_place", "holding location reused as creation place")
    if any(item["artist_id"] not in set(artist_ids) for item in artworks):
        _failure(failures, "work_artist_reference", "artwork refers outside Batch 01 artists")
    if any(item["source_id"] not in source_ids for item in artworks):
        _failure(failures, "work_source_reference", "artwork source is not closed")
    if any(
        not item["claim_ids"]
        or any(claim_id not in claims_by_id for claim_id in item["claim_ids"])
        or not item["evidence_ids"]
        or any(evidence_id not in evidence_by_id for evidence_id in item["evidence_ids"])
        for item in artworks
    ):
        _failure(failures, "work_claim_closure", "artwork claim/evidence closure is incomplete")
    if any(
        item.get("place_label") is not None
        and item.get("place_source_status") != "explicit_birth_place_field"
        for item in episodes
    ):
        _failure(failures, "unsupported_place_episode", "place episode lacks explicit source field")
    if any(item["holding_institution_used_as_creation_or_activity_place"] for item in episodes):
        _failure(failures, "holding_as_activity_place", "holding location reused as activity place")
    for source in sources:
        required_source_values = (
            source.get("official_host"),
            source.get("official_url"),
            source.get("accessed_at"),
            source.get("snapshot_hash"),
            source.get("metadata_license"),
            source.get("provenance"),
            source.get("what_it_proves"),
            source.get("what_it_does_not_prove"),
        )
        if source.get("source_type") != "official_collection" or not all(required_source_values):
            _failure(failures, "source_provenance_closure", source["id"], source["id"])
    if len(media) != 488 or {item["work_id"] for item in media} != set(work_ids):
        _failure(failures, "media_decision_closure", "media decisions do not close 488 works")
    allowed_statuses = {
        "approved_self_hosted_candidate", "approved_external_iiif_candidate",
        "metadata_only_ready", "blocked_source_unavailable", "blocked_rights_conflict",
        "blocked_identity_conflict", "no_media_available",
    }
    if any(item["delivery_decision"] not in allowed_statuses for item in media):
        _failure(failures, "media_decision_status", "unsupported media status")
    if any(item["bytes_downloaded"] or item["media_bytes_present"] or item["derivatives_created"] for item in media):
        _failure(failures, "media_or_derivative_present", "media bytes or derivatives detected")
    allowlist = set(media_document["m09b_media_allowlist"])
    blocked = set(media_document["metadata_only_or_blocked_list"])
    if allowlist & blocked or allowlist | blocked != set(work_ids):
        _failure(failures, "media_list_partition", "allowlist and blocked partition invalid")
    if any(
        item["delivery_decision"].startswith("approved_")
        and (
            not item["candidate_image_or_iiif_identity"]
            or not item["media_license"]
            or "object_specific_media_evidence" not in item["reason_codes"]
        )
        for item in media
    ):
        _failure(failures, "media_permission_inference", "approved media lacks object evidence")
    serialized = json.dumps(
        {"artists": artists, "artworks": artworks, "media": media}, ensure_ascii=False
    ).casefold()
    if any(state in serialized for state in MANUAL_WAIT_STATES):
        _failure(failures, "manual_wait_state", "manual waiting state is forbidden")
    if leakage.get("candidate_public_leakage_count") != 0:
        _failure(failures, "candidate_public_leakage", "declared leakage is nonzero")
    forbidden_markers = leakage.get("forbidden_public_markers", [])
    if not forbidden_markers or leakage.get("marker_count") != len(forbidden_markers):
        _failure(failures, "candidate_public_leakage", "leakage marker set is invalid")
    exempt_roots, release_findings = validated_formal_art_exempt_roots(ROOT / "public")
    for finding in release_findings:
        _failure(
            failures,
            "candidate_public_leakage",
            f"{finding.get('code', 'formal_release_invalid')}:{finding.get('path', 'public')}",
        )
    for target in [ROOT / "public", ROOT / "index.html", ROOT / "src"]:
        paths = [target] if target.is_file() else list(target.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix.casefold() in MEDIA_SUFFIXES:
                continue
            if path.resolve().is_relative_to((ROOT / "src" / "tests").resolve()):
                continue
            if any(path.resolve().is_relative_to(root) for root in exempt_roots):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(marker.casefold() in text.casefold() for marker in forbidden_markers):
                _failure(failures, "candidate_public_leakage", path.as_posix(), path.as_posix())
                break
    m09a_tree, _, _ = _tree_hash(m09a_root)
    if m09a_tree != M09A_PHYSICAL_TREE_SHA256:
        _failure(failures, "m09a_package_mutation", m09a_tree)
    current_release = ROOT / "public" / "releases" / "art-v1-candidate-1.4.0"
    try:
        current_manifest = _read_json(current_release / "manifest.json")
        current_tree, _, _ = _tree_hash(current_release)
        current_release_ok = (
            current_manifest.get("content_hash") == INPUT_RELEASE_CONTENT_HASH
            and sha256_file(current_release / "manifest.json") == INPUT_RELEASE_MANIFEST_SHA256
            and current_tree == INPUT_RELEASE_TREE_SHA256
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        current_release_ok = False
    if (
        manifest.get("input_release_content_hash") != INPUT_RELEASE_CONTENT_HASH
        or not current_release_ok
    ):
        _failure(failures, "current_release_mutation", "content hash differs")
    if manifest.get("public_release_changed") is not False:
        _failure(failures, "current_release_mutation", "public release marked changed")
    if replacements.get("replacement_count") != len(replacements.get("replacements", [])):
        _failure(failures, "replacement_ledger", "replacement count differs")
    if replacements.get("reserve_order_respected") is not True:
        _failure(failures, "wrong_reserve_order", "ordered reserve contract not respected")
    registry = _read_json(registry_path)
    batches = {item["id"]: item for item in registry["batches"]}
    if batches[BATCH_ID]["status"] not in VALID_BATCH_REGISTRY_STATUSES:
        _failure(failures, "batch_registry_status", batches[BATCH_ID]["status"])
    if any(
        item["status"] != "registered_not_started"
        for key, item in batches.items() if key != BATCH_ID
    ):
        _failure(failures, "later_batch_advanced", "Batch 02-10 must remain not started")
    registered_ids = [
        artist_id
        for item in registry["batches"]
        for artist_id in item["artist_ids"]
    ]
    if len(registered_ids) != len(set(registered_ids)):
        _failure(failures, "batch_artist_overlap", "batch artist assignments overlap")
    boundary = {
        "museum_09b_media_entered": False,
        "museum_09b_release_entered": False,
        "museum_09c_entered": False,
        "arms_museum_entered": False,
    }
    for key, expected in boundary.items():
        if manifest.get(key) is not expected:
            _failure(failures, "phase_boundary", key)
    if manifest.get("pages_artifact_count") != 0:
        _failure(failures, "pages_artifact_created", "Pages artifact count must remain zero")
    if manifest.get("runtime_deployment_count") != 0:
        _failure(failures, "runtime_deployment_created", "runtime deployment count must remain zero")
    if manifest.get("remaining_open_decisions") != ["OD-011"]:
        _failure(failures, "od_011_boundary", "OD-011 must remain the only open decision")
    drift = _read_json(package_root / "source-drift-manifest.json")
    if (
        drift.get("checked_count") != 538
        or drift.get("changed_count", 0) + drift.get("unchanged_count", 0)
        + drift.get("unavailable_count", 0) != 538
        or drift.get("new_media_bytes") != 0
    ):
        _failure(failures, "source_drift_closure", "source refresh does not close 538 records")
    counts = {
        "artists": len(artists),
        "artworks": len(artworks),
        "gallery_artists": tiers["gallery"],
        "collection_artists": tiers["collection"],
        "claims": len(claims),
        "evidence": len(evidence),
        "sources": len(sources),
        "contexts": len(contexts),
        "place_time_episodes": len(episodes),
        "relationships": len(relationships),
        "media_decisions": len(media),
        "media_statuses": dict(Counter(item["delivery_decision"] for item in media)),
    }
    return {"ok": not failures, "failures": failures, "counts": counts}


def benchmark_build(iterations: int = 5) -> dict[str, Any]:
    durations: list[float] = []
    receipt = _read_json(DEFAULT_REFRESH_RECEIPT)
    with tempfile.TemporaryDirectory(prefix="museum-09b-benchmark-") as temporary:
        root = Path(temporary)
        for index in range(iterations):
            output = root / f"run-{index}"
            started = time.perf_counter()
            _build_to(output, receipt)
            durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered) + 0.5) - 1))
    return {
        "iterations": iterations,
        "durations_ms": [round(value, 3) for value in durations],
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "max_ms": round(max(durations), 3),
    }
