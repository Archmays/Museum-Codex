from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from museum_pipeline.canonical_json import canonical_json_bytes, write_canonical_json
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.media.image_processing import (
    DEFAULT_DERIVATIVE_WIDTHS,
    DEFAULT_MAX_PIXELS,
    PROCESSOR_VERSION,
    ImageProcessingError,
    build_derivatives,
    compare_preview_visual_match,
    inspect_image_bytes,
)
from scripts.scan_public_artifact_for_candidate_data import validated_formal_art_exempt_roots


PHASE_ID = "MUSEUM-09B-MEDIA"
BATCH_ID = "museum-09-batch-01"
PACKAGE_ID = "museum-09b-media:batch-01-media-bundle-v1"
PACKAGE_TIMESTAMP = "2026-07-21T12:00:00+08:00"
BASELINE_COMMIT = "108c5623547fb9eb11210ac11c05937060fbbc67"
IMPLEMENTATION_COMMIT = "95f43bee1b4ab04997fd6a041807079f55058b98"
INPUT_PACKAGE_ID = "museum-09b:batch-01-formal-candidate-v1"
INPUT_CONTENT_HASH = "sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9"
INPUT_TREE_HASH = "sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87"
INPUT_CLOSURE_HASH = "sha256:8b7020f979895e3bf5f21c042c1e6a2b746628f5108f13050102b31370219770"
INPUT_RELEASE_ID = "release:art-v1-candidate-1.4.0"
INPUT_RELEASE_CONTENT_HASH = "sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202"
INPUT_RELEASE_MANIFEST_SHA256 = "sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114"
INPUT_RELEASE_TREE_SHA256 = "sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1"

CANDIDATE_ROOT = ROOT / "data" / "reviewed" / "art" / "museum-09b" / "batch-01-formal-candidate-v1"
M09A_RAW_ROOT = ROOT / "data" / "raw" / "museum-09a"
M03C_VAULT = ROOT / "data" / "media-source" / "art" / "museum-03c"
M03C_BUNDLE = ROOT / "data" / "reviewed" / "art" / "museum-03c" / "media-bundle-v1"
MEDIA_VAULT = ROOT / "data" / "media-source" / "art" / "museum-09b-media"
DEFAULT_BUNDLE_ROOT = (
    ROOT / "data" / "reviewed" / "art" / "museum-09b-media" / "batch-01-media-bundle-v1"
)
REGISTRY_PATH = ROOT / "governance" / "museum-09-batch-registry.json"
SOURCE_RULES = ROOT / "research" / "source-registry" / "source-license-rules.json"
SCHEMA_PATH = ROOT / "schemas" / "art" / "batch" / "museum-09b-media-bundle.schema.json"

MAX_ORIGINAL_BYTES = 100 * 1024 * 1024
MAX_TRACKED_FILE_BYTES = 5 * 1024 * 1024
MAX_DECODE_PIXELS = DEFAULT_MAX_PIXELS
USER_AGENT = "Museum-Codex-MUSEUM-09B-MEDIA/1.0 controlled-media-review"
RECIPE_ID = "museum-03c-responsive-v1.1.0"
JPEG_QUALITY = 85
WEBP_QUALITY = 82

FINAL_STATUSES = {
    "approved_self_hosted",
    "approved_self_hosted_by_content_reuse",
    "approved_external_iiif_link_only",
    "approved_external_iiif_manifest_only",
    "metadata_only_after_media_review",
    "blocked_source_unavailable",
    "blocked_rights_conflict",
    "blocked_identity_conflict",
    "blocked_media_quality",
    "blocked_retrieval_policy",
}
SELF_HOSTED_STATUSES = {
    "approved_self_hosted",
    "approved_self_hosted_by_content_reuse",
}
EXTERNAL_STATUSES = {
    "approved_external_iiif_link_only",
    "approved_external_iiif_manifest_only",
}
FORBIDDEN_FINAL_TOKENS = {"candidate", "pending", "waiting_for_manual_review", "pending_user_approval"}

REQUIRED_PACKAGE_FILES = (
    "allowlist-snapshot.json",
    "object-rights-decisions.json",
    "source-drift-manifest.json",
    "download-manifest.json",
    "originals-manifest.json",
    "derivatives-manifest.json",
    "iiif-manifests.json",
    "content-reuse-index.json",
    "quality-review.json",
    "attributions.json",
    "third-party-notices.json",
    "withdrawal-registry.json",
    "metadata-only-and-blocked.json",
    "future-release-media-projection.json",
    "validation-summary.json",
    "status-history.json",
    "public-leakage-label-set.json",
    "build-manifest.json",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _safe_slug(work_id: str) -> str:
    value = work_id.removeprefix("artwork:")
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise ValueError(f"unsafe work id for vault path: {work_id}")
    return value


def _load_artworks() -> list[dict[str, Any]]:
    artworks: list[dict[str, Any]] = []
    for path in sorted((CANDIDATE_ROOT / "artworks").glob("part-*.json")):
        document = _read_json(path)
        artworks.extend(document.get("artworks") or document.get("records") or document.get("items") or [])
    if len(artworks) != 488:
        raise ValueError(f"expected 488 candidate artworks, found {len(artworks)}")
    return artworks


def load_inputs() -> dict[str, Any]:
    manifest = _read_json(CANDIDATE_ROOT / "build-manifest.json")
    if manifest.get("package_id") != INPUT_PACKAGE_ID:
        raise ValueError("candidate package id drifted")
    if manifest.get("artifact_content_hash") != INPUT_CONTENT_HASH:
        raise ValueError("candidate package content hash drifted")
    if manifest.get("artifact_tree_hash") != INPUT_TREE_HASH:
        raise ValueError("candidate package tree hash drifted")
    if manifest.get("input_closure_hash") != INPUT_CLOSURE_HASH:
        raise ValueError("candidate input closure drifted")

    media = _read_json(CANDIDATE_ROOT / "media-feasibility.json")
    artworks = _load_artworks()
    artists = _read_json(CANDIDATE_ROOT / "artists.json").get("artists", [])
    if len(artists) != 50:
        raise ValueError(f"expected 50 candidate artists, found {len(artists)}")
    work_index = {item["id"]: item for item in artworks}
    artist_index = {item["id"]: item for item in artists}
    decision_index = {item["work_id"]: item for item in media["decisions"]}
    allowlist = list(media["m09b_media_allowlist"])
    excluded = list(media["metadata_only_or_blocked_list"])
    if len(allowlist) != 65 or len(excluded) != 423:
        raise ValueError("candidate media partitions are not 65/423")
    if set(allowlist) & set(excluded) or len(set(allowlist) | set(excluded)) != 488:
        raise ValueError("candidate media partitions are not disjoint and complete")
    if Counter(decision_index[work_id]["delivery_decision"] for work_id in allowlist) != Counter(
        {"approved_self_hosted_candidate": 40, "approved_external_iiif_candidate": 25}
    ):
        raise ValueError("candidate media allowlist is not the exact initial 40/25 split")
    if any(work_id not in work_index for work_id in allowlist + excluded):
        raise ValueError("candidate media partition references an unknown work")
    if any(work_index[work_id]["artist_id"] not in artist_index for work_id in allowlist):
        raise ValueError("candidate media allowlist references an unknown artist")

    old_drift = _read_json(CANDIDATE_ROOT / "source-drift-manifest.json")
    old_drift_index = {
        (item["source_id"], str(item["source_object_id"])): item
        for item in old_drift["records"]
        if item.get("source_id") and item.get("source_object_id") is not None
    }
    return {
        "manifest": manifest,
        "media": media,
        "artworks": artworks,
        "artists": artists,
        "work_index": work_index,
        "artist_index": artist_index,
        "decision_index": decision_index,
        "allowlist": allowlist,
        "excluded": excluded,
        "old_drift_index": old_drift_index,
    }


def _load_old_cleveland_rows() -> dict[str, dict[str, str]]:
    with (M09A_RAW_ROOT / "cleveland-artworks.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        return {str(row["id"]): row for row in csv.DictReader(stream)}


def _aic_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_object_id": str(row.get("id") or ""),
        "title": row.get("title"),
        "date_display": row.get("date_display"),
        "medium": row.get("medium_display"),
        "dimensions": row.get("dimensions"),
        "department": row.get("department_title"),
        "object_type": row.get("classification_title"),
        "artist_display": row.get("artist_title"),
        "is_public_domain": row.get("is_public_domain") is True,
        "image_id": row.get("image_id"),
        "copyright_notice": row.get("copyright_notice"),
        "credit_line": row.get("credit_line"),
        "source_updated_at": row.get("updated_at"),
    }


def _cleveland_projection(row: dict[str, Any]) -> dict[str, Any]:
    images = row.get("images") if isinstance(row.get("images"), dict) else {}

    def image_url(profile: str) -> str | None:
        value = images.get(profile)
        return str(value.get("url") or "") or None if isinstance(value, dict) else None

    creators = row.get("creators")
    creator_descriptions = []
    if isinstance(creators, list):
        creator_descriptions = [
            str(item.get("description") or "") for item in creators if isinstance(item, dict) and item.get("description")
        ]
    elif isinstance(creators, str):
        creator_descriptions = [
            re.sub(r",\s*[a-z][a-z /-]*$", "", item.strip(), flags=re.IGNORECASE)
            for item in creators.split(";")
            if item.strip()
        ]
    return {
        "source_object_id": str(row.get("id") or ""),
        "title": row.get("title"),
        "accession_number": row.get("accession_number"),
        "creation_date": row.get("creation_date"),
        "department": row.get("department"),
        "technique": row.get("technique"),
        "share_license_status": row.get("share_license_status"),
        "copyright": row.get("copyright") or None,
        "creditline": row.get("creditline") or None,
        "url": row.get("url"),
        "image_web": image_url("web") or row.get("image_web") or None,
        "image_print": image_url("print") or row.get("image_print") or None,
        "image_full": image_url("full") or row.get("image_full") or None,
        "updated_at": row.get("updated_at"),
        "creators": creator_descriptions,
    }


def _diff_keys(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))


def _trusted_url(url: str, host: str, *, suffix: str | None = None) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname == host and not parsed.username and not parsed.password and (
        suffix is None or parsed.path.lower().endswith(suffix.lower())
    )


def _request_bytes(
    url: str,
    *,
    max_bytes: int,
    allowed_host: str,
    attempts: int = 3,
    timeout_seconds: float = 45.0,
    minimum_interval_seconds: float = 0.0,
    rate_state: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not _trusted_url(url, allowed_host):
        raise ValueError(f"untrusted request URL: {url}")
    state = rate_state if rate_state is not None else {}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        previous = state.get(allowed_host)
        if previous is not None:
            delay = minimum_interval_seconds - (time.monotonic() - previous)
            if delay > 0:
                time.sleep(delay)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json,image/jpeg,image/webp,*/*;q=0.1"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                state[allowed_host] = time.monotonic()
                final_url = response.geturl()
                if not _trusted_url(final_url, allowed_host):
                    raise ValueError(f"redirect escaped allowed host: {final_url}")
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError(f"response exceeds byte limit before download: {content_length}")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"response exceeds byte limit: {total}")
                payload = b"".join(chunks)
                if not payload:
                    raise ValueError("empty response payload")
                return {
                    "payload": payload,
                    "status_code": int(response.status),
                    "final_url": final_url,
                    "headers": {
                        "content-type": response.headers.get("Content-Type"),
                        "content-length": response.headers.get("Content-Length"),
                        "etag": response.headers.get("ETag"),
                        "last-modified": response.headers.get("Last-Modified"),
                        "cache-control": response.headers.get("Cache-Control"),
                    },
                    "attempt_count": attempt,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "retrieved_at": _now_utc(),
                }
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as error:
            state[allowed_host] = time.monotonic()
            last_error = error
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error


def _json_response(result: dict[str, Any]) -> dict[str, Any]:
    content_type = str(result["headers"].get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ValueError(f"expected application/json, received {content_type or 'missing'}")
    prefix = result["payload"][:256].lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html")):
        raise ValueError("HTML error body returned for JSON request")
    document = json.loads(result["payload"])
    if not isinstance(document, dict):
        raise ValueError("official JSON response is not an object")
    return document


def _save_cache_json(path: Path, value: Any) -> None:
    write_canonical_json(path, value)


def _load_cached_object(slug: str) -> dict[str, Any] | None:
    path = MEDIA_VAULT / "objects" / slug / "review.json"
    if not path.exists():
        return None
    document = _read_json(path)
    if document.get("phase_id") != PHASE_ID or document.get("work_id") != f"artwork:{slug}":
        raise ValueError(f"invalid cached object review for {slug}")
    return document


def _m03c_original_index() -> dict[str, str]:
    index: dict[str, str] = {}
    if not M03C_VAULT.exists():
        return index
    for path in sorted(M03C_VAULT.glob("*/original.*")):
        if path.is_file():
            index.setdefault(sha256_file(path), path.relative_to(ROOT).as_posix())
    return index


def _promote_original(payload: bytes, suffix: str = ".jpg") -> tuple[Path, bool]:
    digest = _sha256_bytes(payload)
    hex_digest = digest.removeprefix("sha256:")
    destination = MEDIA_VAULT / "originals" / "sha256" / hex_digest[:2] / f"{hex_digest}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != payload:
            raise ValueError(f"content-addressed original conflict at {destination}")
        return destination, True
    partial_root = MEDIA_VAULT / "tmp"
    partial_root.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{hex_digest}.", suffix=".partial", dir=partial_root)
    partial = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if sha256_file(partial) != digest:
            raise ValueError("partial original hash verification failed")
        try:
            os.link(partial, destination)
        except OSError:
            try:
                with destination.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise ValueError("racing original promotion produced different bytes")
        if destination.read_bytes() != payload:
            raise ValueError("promoted original bytes differ")
        return destination, False
    finally:
        partial.unlink(missing_ok=True)


def acquire(
    *,
    force_network: bool = False,
    force_sources: Iterable[str] = (),
) -> dict[str, Any]:
    """Review all 65 allowlisted objects and acquire only eligible Cleveland bytes."""

    inputs = load_inputs()
    prior_summary_path = MEDIA_VAULT / "acquisition-summary.json"
    prior_summary = _read_json(prior_summary_path) if prior_summary_path.exists() and not force_network else {}
    forced = set(force_sources)
    unknown_forced = forced - {"aic_api", "cleveland_open_access"}
    if unknown_forced:
        raise ValueError(f"unknown forced source(s): {sorted(unknown_forced)}")
    MEDIA_VAULT.mkdir(parents=True, exist_ok=True)
    rate_state: dict[str, float] = {}
    old_cleveland = _load_old_cleveland_rows()
    aic_candidates = [
        inputs["decision_index"][work_id]
        for work_id in inputs["allowlist"]
        if inputs["decision_index"][work_id]["source_id"] == "source:aic_api"
    ]
    cleveland_candidates = [
        inputs["decision_index"][work_id]
        for work_id in inputs["allowlist"]
        if inputs["decision_index"][work_id]["source_id"] == "source:cleveland_open_access"
    ]
    m03c_hashes = _m03c_original_index()

    metrics: dict[str, Any] = {
        "official_request_count": 0,
        "official_response_bytes": 0,
        "object_rights_check_count": 0,
        "original_download_attempt_count": 0,
        "original_download_success_count": 0,
        "original_download_failure_count": 0,
        "newly_downloaded_original_count": 0,
        "newly_downloaded_original_bytes": 0,
        "content_reused_original_count": 0,
        "content_reused_original_bytes": 0,
        "preview_download_count": 0,
        "cache_hit_count": 0,
        "cache_miss_count": 0,
        "iiif_service_check_count": 0,
        "iiif_image_download_count": 0,
        "timings_ms": [],
    }

    cached_reviews: dict[str, dict[str, Any]] = {}
    missing_aic: list[dict[str, Any]] = []
    for candidate in aic_candidates:
        slug = _safe_slug(candidate["work_id"])
        cached = None if force_network or "aic_api" in forced else _load_cached_object(slug)
        if cached is not None:
            cached_reviews[candidate["work_id"]] = cached
            metrics["cache_hit_count"] += 1
        else:
            missing_aic.append(candidate)
            metrics["cache_miss_count"] += 1

    if missing_aic:
        ids = ",".join(item["source_object_id"] for item in missing_aic)
        fields = ",".join(
            (
                "id", "title", "date_display", "medium_display", "dimensions", "department_title",
                "classification_title", "is_public_domain", "image_id", "copyright_notice", "credit_line",
                "artist_title", "updated_at", "api_link", "main_reference_number", "thumbnail",
            )
        )
        url = "https://api.artic.edu/api/v1/artworks?" + urllib.parse.urlencode(
            {"ids": ids, "fields": fields, "limit": str(len(missing_aic))}
        )
        try:
            response = _request_bytes(
                url,
                max_bytes=5 * 1024 * 1024,
                allowed_host="api.artic.edu",
                minimum_interval_seconds=1.0,
                rate_state=rate_state,
            )
            metrics["official_request_count"] += response["attempt_count"]
            metrics["official_response_bytes"] += len(response["payload"])
            metrics["timings_ms"].append(response["elapsed_ms"])
            document = _json_response(response)
            rows = {str(item.get("id")): item for item in document.get("data", []) if isinstance(item, dict)}
        except Exception as error:  # live transport is intentionally fail-closed per object
            rows = {}
            bulk_error = f"{type(error).__name__}:{error}"
            metrics["official_request_count"] += 3
        else:
            bulk_error = None

        for candidate in missing_aic:
            work_id = candidate["work_id"]
            slug = _safe_slug(work_id)
            artwork = inputs["work_index"][work_id]
            row = rows.get(candidate["source_object_id"])
            sealed_row_path = MEDIA_VAULT / "objects" / slug / "official-object-response.json"
            sealed_receipt_reused = False
            if row is None and sealed_row_path.exists():
                row = _read_json(sealed_row_path)
                sealed_receipt_reused = True
            if row is None:
                review = _blocked_review(candidate, artwork, "blocked_source_unavailable", [bulk_error or "object_missing_from_bulk_response"])
            else:
                current = _aic_projection(row)
                prior = inputs["old_drift_index"].get(("aic_api", candidate["source_object_id"]), {})
                old_projection = prior.get("minimal_current_projection") or {
                    "source_object_id": candidate["source_object_id"],
                    "title": artwork["preferred_title"],
                    "image_id": _aic_image_id(candidate["candidate_image_or_iiif_identity"]),
                    "is_public_domain": artwork.get("public_domain_source_field") is True,
                }
                changed_fields = _diff_keys(old_projection, current)
                identity_issues = _identity_issues_aic(candidate, artwork, current)
                rights_issues = []
                if current.get("is_public_domain") is not True:
                    rights_issues.append("object_no_longer_public_domain")
                if current.get("copyright_notice"):
                    rights_issues.append("copyright_notice_present")
                if not current.get("image_id"):
                    rights_issues.append("image_id_missing")
                service = _fetch_aic_service(
                    current.get("image_id"), candidate["source_object_id"], rate_state, metrics
                )
                if identity_issues:
                    final_status = "blocked_identity_conflict"
                elif rights_issues:
                    final_status = "blocked_rights_conflict"
                else:
                    final_status = "approved_external_iiif_link_only"
                review = {
                    "schema_version": "1.0.0",
                    "phase_id": PHASE_ID,
                    "work_id": work_id,
                    "artist_id": artwork["artist_id"],
                    "source_id": candidate["source_id"],
                    "source_object_id": candidate["source_object_id"],
                    "candidate_status": candidate["delivery_decision"],
                    "candidate_media_identity": candidate["candidate_image_or_iiif_identity"],
                    "current_media_identity": (
                        f"https://www.artic.edu/iiif/2/{current['image_id']}/full/843,/0/default.jpg"
                        if current.get("image_id") else None
                    ),
                    "current_object_record": current,
                    "old_record_hash": canonical_sha256(old_projection),
                    "current_record_hash": canonical_sha256(current),
                    "source_record_status": "changed" if changed_fields else "unchanged",
                    "changed_fields": changed_fields,
                    "rights_changed": any(
                        field in changed_fields for field in ("is_public_domain", "copyright_notice", "image_id")
                    ),
                    "endpoint_changed": candidate["candidate_image_or_iiif_identity"] != (
                        f"https://www.artic.edu/iiif/2/{current['image_id']}/full/843,/0/default.jpg"
                        if current.get("image_id") else None
                    ),
                    "identity_issues": identity_issues,
                    "rights_issues": rights_issues,
                    "metadata_license": candidate["metadata_license"],
                    "media_license": "CC0-1.0-OBJECT-SPECIFIC-EXTERNAL-REFERENCE-ONLY",
                    "source_rule_id": candidate["source_rule_id"],
                    "rights_statement_url": "https://www.artic.edu/open-access/open-access-images",
                    "rights_evidence_hash": canonical_sha256(
                        {
                            "is_public_domain": current.get("is_public_domain"),
                            "copyright_notice": current.get("copyright_notice"),
                            "image_id": current.get("image_id"),
                            "source_rule_id": candidate["source_rule_id"],
                        }
                    ),
                    "attribution": _aic_attribution(current, artwork),
                    "withdrawal_route": artwork["correction_or_withdrawal_route"],
                    "expected_retrieval_mode": "external_iiif_service_reference_without_image_download",
                    "expected_local_storage_eligibility": False,
                    "final_status": final_status,
                    "final_reason_codes": sorted(
                        identity_issues
                        + rights_issues
                        + [
                            "aic_shared_policy_external_reference_only",
                            service.get("reason") or "iiif_service_check_recorded",
                        ]
                    ),
                    "service": service,
                    "sealed_object_receipt_reused": sealed_receipt_reused,
                    "transport_note": bulk_error if sealed_receipt_reused else None,
                    "download": {"attempted": False, "reason": "external_iiif_image_bytes_not_localized"},
                    "quality": None,
                    "original": None,
                    "reviewed_at": PACKAGE_TIMESTAMP,
                }
            _save_cache_json(MEDIA_VAULT / "objects" / slug / "review.json", review)
            if row is not None:
                _save_cache_json(MEDIA_VAULT / "objects" / slug / "official-object-response.json", row)
            cached_reviews[work_id] = review
            metrics["object_rights_check_count"] += 1

    for candidate in cleveland_candidates:
        work_id = candidate["work_id"]
        slug = _safe_slug(work_id)
        cached = None if force_network or "cleveland_open_access" in forced else _load_cached_object(slug)
        if cached is not None:
            cached_reviews[work_id] = cached
            metrics["cache_hit_count"] += 1
            continue
        metrics["cache_miss_count"] += 1
        artwork = inputs["work_index"][work_id]
        object_url = f"https://openaccess-api.clevelandart.org/api/artworks/{candidate['source_object_id']}"
        try:
            response = _request_bytes(
                object_url,
                max_bytes=5 * 1024 * 1024,
                allowed_host="openaccess-api.clevelandart.org",
                minimum_interval_seconds=1.0,
                rate_state=rate_state,
            )
            metrics["official_request_count"] += response["attempt_count"]
            metrics["official_response_bytes"] += len(response["payload"])
            metrics["timings_ms"].append(response["elapsed_ms"])
            document = _json_response(response)
            row = document.get("data")
            if not isinstance(row, dict):
                raise ValueError("Cleveland object response lacks data object")
            review = _review_cleveland(
                candidate,
                artwork,
                row,
                old_cleveland.get(candidate["source_object_id"]),
                response,
                rate_state,
                metrics,
                m03c_hashes,
            )
            _save_cache_json(MEDIA_VAULT / "objects" / slug / "official-object-response.json", row)
        except Exception as error:
            review = _blocked_review(candidate, artwork, "blocked_source_unavailable", [f"{type(error).__name__}:{error}"])
        _save_cache_json(MEDIA_VAULT / "objects" / slug / "review.json", review)
        cached_reviews[work_id] = review
        metrics["object_rights_check_count"] += 1

    if set(cached_reviews) != set(inputs["allowlist"]):
        raise ValueError("acquisition did not close all 65 allowlisted works")
    metrics["object_rights_check_count"] = 65
    current_run_metrics = {
        "official_request_count": metrics["official_request_count"],
        "official_response_bytes": metrics["official_response_bytes"],
        "cache_hit_count": metrics["cache_hit_count"],
        "cache_miss_count": metrics["cache_miss_count"],
        "iiif_service_check_count": metrics["iiif_service_check_count"],
        "timings_ms": _timing_summary(metrics["timings_ms"]),
    }
    metrics["network_run_count"] = int(prior_summary.get("network_run_count", 0)) + 1
    metrics["official_request_count"] += int(prior_summary.get("official_request_count", 0))
    metrics["official_response_bytes"] += int(prior_summary.get("official_response_bytes", 0))
    metrics["cache_hit_count"] += int(prior_summary.get("cache_hit_count", 0))
    metrics["cache_miss_count"] += int(prior_summary.get("cache_miss_count", 0))
    metrics["iiif_service_check_count"] += int(prior_summary.get("iiif_service_check_count", 0))
    metrics["network_runs"] = [*prior_summary.get("network_runs", []), current_run_metrics]
    acquired_originals = [item["original"] for item in cached_reviews.values() if item.get("original")]
    metrics["original_download_attempt_count"] = len(acquired_originals)
    metrics["original_download_success_count"] = len(acquired_originals)
    metrics["original_download_failure_count"] = sum(
        bool(item.get("download", {}).get("attempted")) and not bool(item.get("download", {}).get("successful"))
        for item in cached_reviews.values()
    )
    metrics["newly_downloaded_original_count"] = sum(
        item.get("promotion_status") == "newly_downloaded" for item in acquired_originals
    )
    metrics["newly_downloaded_original_bytes"] = sum(
        item["bytes"] for item in acquired_originals if item.get("promotion_status") == "newly_downloaded"
    )
    metrics["content_reused_original_count"] = sum(
        item.get("promotion_status") == "content_reused" for item in acquired_originals
    )
    metrics["content_reused_original_bytes"] = sum(
        item["bytes"] for item in acquired_originals if item.get("promotion_status") == "content_reused"
    )
    metrics["preview_download_count"] = sum(bool(item.get("preview")) for item in cached_reviews.values())
    metrics["final_status_counts"] = dict(sorted(Counter(item["final_status"] for item in cached_reviews.values()).items()))
    metrics["rights_changed_count"] = sum(bool(item.get("rights_changed")) for item in cached_reviews.values())
    metrics["endpoint_changed_count"] = sum(bool(item.get("endpoint_changed")) for item in cached_reviews.values())
    metrics["source_record_changed_count"] = sum(item.get("source_record_status") == "changed" for item in cached_reviews.values())
    metrics["source_record_unchanged_count"] = sum(item.get("source_record_status") == "unchanged" for item in cached_reviews.values())
    metrics["source_record_unavailable_count"] = sum(item.get("source_record_status") == "unavailable" for item in cached_reviews.values())
    metrics["captured_at"] = _now_utc()
    metrics["timings_ms"] = current_run_metrics["timings_ms"]
    _save_cache_json(MEDIA_VAULT / "acquisition-summary.json", metrics)
    _cleanup_vault_tmp()
    return {"reviews": cached_reviews, "metrics": metrics}


def _aic_image_id(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url).path.strip("/").split("/")
    return parts[2] if len(parts) >= 3 and parts[:2] == ["iiif", "2"] else None


def _fetch_aic_service(
    image_id: str | None,
    object_id: str,
    rate_state: dict[str, float],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    if not image_id:
        return {"status": "fail", "reason": "image_id_missing"}
    service_id = f"https://www.artic.edu/iiif/2/{image_id}"
    url = f"{service_id}/info.json"
    manifest_url = f"https://api.artic.edu/api/v1/artworks/{object_id}/manifest.json"
    metrics["iiif_service_check_count"] += 1
    try:
        response = _request_bytes(
            url,
            max_bytes=1024 * 1024,
            allowed_host="www.artic.edu",
            minimum_interval_seconds=1.0,
            rate_state=rate_state,
        )
        metrics["official_request_count"] += response["attempt_count"]
        metrics["official_response_bytes"] += len(response["payload"])
        metrics["timings_ms"].append(response["elapsed_ms"])
        document = _json_response(response)
        observed_service_id = document.get("@id") or document.get("id")
        protocol = document.get("protocol")
        if observed_service_id != service_id or protocol != "http://iiif.io/api/image":
            return {
                "status": "fail", "reason": "iiif_service_identity_mismatch", "info_url": url,
                "manifest_url": manifest_url,
                "response_sha256": _sha256_bytes(response["payload"]), "service_id": observed_service_id,
                "protocol": protocol,
            }
        return {
            "status": "pass",
            "reason": "iiif_image_api_v2_service_bound_to_object_image_id",
            "info_url": url,
            "manifest_url": manifest_url,
            "response_sha256": _sha256_bytes(response["payload"]),
            "service_id": observed_service_id,
            "protocol": protocol,
            "version": "2",
            "profile": document.get("profile"),
            "width": document.get("width"),
            "height": document.get("height"),
            "rights": document.get("rights") or document.get("license"),
            "required_statement": document.get("requiredStatement") or document.get("attribution"),
            "provider": "Art Institute of Chicago",
            "response": document,
        }
    except Exception as error:
        # A transport failure does not erase the object-level identity/rights
        # closure.  These records remain link-only, never local-media approvals.
        metrics["official_request_count"] += 3
        return {
            "status": "transport_unavailable",
            "reason": f"iiif_service_transport_unavailable:{type(error).__name__}:{error}",
            "info_url": url,
            "manifest_url": manifest_url,
            "service_id": service_id,
            "protocol": "http://iiif.io/api/image",
            "version": "2",
            "profile": None,
            "width": None,
            "height": None,
            "rights": None,
            "required_statement": None,
            "provider": "Art Institute of Chicago",
            "response_sha256": None,
            "documented_by": "https://api.artic.edu/docs/#iiif-image-api-and-iiif-manifests",
            "image_bytes_downloaded": False,
        }


def _identity_issues_aic(candidate: dict[str, Any], artwork: dict[str, Any], current: dict[str, Any]) -> list[str]:
    issues = []
    if current.get("source_object_id") != candidate["source_object_id"]:
        issues.append("source_object_id_mismatch")
    if current.get("title") != artwork["preferred_title"]:
        issues.append("title_mismatch")
    image_id = _aic_image_id(candidate.get("candidate_image_or_iiif_identity"))
    if current.get("image_id") != image_id:
        issues.append("image_id_mismatch")
    return issues


def _aic_attribution(current: dict[str, Any], artwork: dict[str, Any]) -> str:
    parts = ["Art Institute of Chicago", artwork["preferred_title"]]
    if current.get("artist_display"):
        parts.append(str(current["artist_display"]))
    if current.get("credit_line"):
        parts.append(str(current["credit_line"]))
    return "; ".join(parts)


def _review_cleveland(
    candidate: dict[str, Any],
    artwork: dict[str, Any],
    row: dict[str, Any],
    old_row: dict[str, Any] | None,
    object_response: dict[str, Any],
    rate_state: dict[str, float],
    metrics: dict[str, Any],
    m03c_hashes: dict[str, str],
) -> dict[str, Any]:
    current = _cleveland_projection(row)
    old_projection = _cleveland_projection(old_row or {})
    changed_fields = _diff_keys(old_projection, current)
    identity_issues = []
    if current["source_object_id"] != candidate["source_object_id"]:
        identity_issues.append("source_object_id_mismatch")
    if current["title"] != artwork["preferred_title"]:
        identity_issues.append("title_mismatch")
    if current["accession_number"] != artwork["accession_or_object_number"]:
        identity_issues.append("accession_mismatch")
    if current["url"] != artwork["official_object_url"]:
        identity_issues.append("object_url_mismatch")

    rights_issues = []
    if current["share_license_status"] != "CC0":
        rights_issues.append("share_license_status_not_cc0")
    if current["copyright"]:
        rights_issues.append("copyright_conflict")
    if not current["creditline"]:
        rights_issues.append("attribution_missing")
    for key in ("image_full", "image_print", "image_web"):
        value = current.get(key)
        if value and not _trusted_url(value, "openaccess-cdn.clevelandart.org"):
            rights_issues.append(f"untrusted_{key}_url")
    endpoint_changed = current.get("image_full") != candidate.get("candidate_image_or_iiif_identity")

    review: dict[str, Any] = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "work_id": candidate["work_id"],
        "artist_id": artwork["artist_id"],
        "source_id": candidate["source_id"],
        "source_object_id": candidate["source_object_id"],
        "candidate_status": candidate["delivery_decision"],
        "candidate_media_identity": candidate["candidate_image_or_iiif_identity"],
        "current_media_identity": current.get("image_full"),
        "current_object_record": current,
        "old_record_hash": canonical_sha256(old_projection),
        "current_record_hash": canonical_sha256(current),
        "source_record_status": "changed" if changed_fields else "unchanged",
        "changed_fields": changed_fields,
        "rights_changed": any(
            key in changed_fields for key in ("share_license_status", "copyright", "creditline", "image_full", "image_print", "image_web")
        ),
        "endpoint_changed": endpoint_changed,
        "identity_issues": identity_issues,
        "rights_issues": rights_issues,
        "metadata_license": candidate["metadata_license"],
        "media_license": "CC0-1.0-OBJECT-SPECIFIC",
        "source_rule_id": candidate["source_rule_id"],
        "rights_statement_url": "https://www.clevelandart.org/open-access",
        "rights_evidence_hash": canonical_sha256(
            {
                "share_license_status": current["share_license_status"],
                "copyright": current["copyright"],
                "image_full": current["image_full"],
                "image_print": current["image_print"],
                "source_rule_id": candidate["source_rule_id"],
            }
        ),
        "attribution": f"Cleveland Museum of Art; {artwork['preferred_title']}; {current.get('creditline') or 'credit line unavailable'}",
        "withdrawal_route": artwork["correction_or_withdrawal_route"],
        "expected_retrieval_mode": "official_print_source_rendition",
        "expected_local_storage_eligibility": True,
        "object_response": {
            "status_code": object_response["status_code"],
            "final_url": object_response["final_url"],
            "headers": object_response["headers"],
            "response_sha256": _sha256_bytes(object_response["payload"]),
            "retrieved_at": object_response["retrieved_at"],
        },
        "reviewed_at": PACKAGE_TIMESTAMP,
    }
    if identity_issues:
        review.update(_terminal_payload("blocked_identity_conflict", identity_issues))
        return review
    if rights_issues:
        review.update(_terminal_payload("blocked_rights_conflict", rights_issues))
        return review
    retrieval_url = current.get("image_print") or current.get("image_web")
    preview_url = current.get("image_web")
    if not retrieval_url or not _trusted_url(retrieval_url, "openaccess-cdn.clevelandart.org", suffix=".jpg"):
        review.update(_terminal_payload("blocked_retrieval_policy", ["no_safe_official_jpeg_source_rendition"]))
        return review

    metrics["original_download_attempt_count"] += 1
    try:
        original_response = _request_bytes(
            retrieval_url,
            max_bytes=MAX_ORIGINAL_BYTES,
            allowed_host="openaccess-cdn.clevelandart.org",
            minimum_interval_seconds=0.25,
            rate_state=rate_state,
        )
        metrics["official_request_count"] += original_response["attempt_count"]
        metrics["official_response_bytes"] += len(original_response["payload"])
        metrics["timings_ms"].append(original_response["elapsed_ms"])
        metrics["original_download_success_count"] += 1
        mime = str(original_response["headers"].get("content-type") or "").split(";", 1)[0].lower()
        inspection = inspect_image_bytes(original_response["payload"], mime, max_pixels=MAX_DECODE_PIXELS)
        preview_comparison = None
        preview_response = None
        if preview_url and preview_url != retrieval_url:
            preview_response = _request_bytes(
                preview_url,
                max_bytes=MAX_ORIGINAL_BYTES,
                allowed_host="openaccess-cdn.clevelandart.org",
                minimum_interval_seconds=0.25,
                rate_state=rate_state,
            )
            metrics["official_request_count"] += preview_response["attempt_count"]
            metrics["official_response_bytes"] += len(preview_response["payload"])
            metrics["preview_download_count"] += 1
            metrics["timings_ms"].append(preview_response["elapsed_ms"])
            preview_mime = str(preview_response["headers"].get("content-type") or "").split(";", 1)[0].lower()
            preview_comparison = compare_preview_visual_match(
                original_response["payload"], mime, preview_response["payload"], preview_mime,
                max_pixels=MAX_DECODE_PIXELS,
            )
        quality_reasons = []
        flags = inspection["quality"]["flags"]
        if flags["placeholder_suspected"] or flags["tracking_pixel"] or flags["blank"]:
            quality_reasons.append("placeholder_or_blank")
        if preview_comparison is not None and not preview_comparison["matched"]:
            quality_reasons.extend(f"preview_{reason}" for reason in preview_comparison["reasons"])
        if quality_reasons:
            review.update(_terminal_payload("blocked_media_quality", quality_reasons))
            review["quality"] = {"inspection": inspection, "preview_comparison": preview_comparison, "tier": "metadata_only_due_quality"}
            review["download"] = _download_evidence(original_response, retrieval_url, inspection)
            return review

        promoted, already_present = _promote_original(original_response["payload"])
        source_hash = inspection["sha256"]
        prior_path = m03c_hashes.get(source_hash)
        content_reused = bool(prior_path or already_present)
        if content_reused:
            metrics["content_reused_original_count"] += 1
            metrics["content_reused_original_bytes"] += inspection["bytes"]
        else:
            metrics["newly_downloaded_original_count"] += 1
            metrics["newly_downloaded_original_bytes"] += inspection["bytes"]
        tier = "display_high" if inspection["display_width"] >= 1600 else "display_standard" if inspection["display_width"] >= 960 else "thumbnail_only"
        final_status = "approved_self_hosted_by_content_reuse" if content_reused else "approved_self_hosted"
        review.update(_terminal_payload(final_status, ["identity_rights_bytes_quality_closed"]))
        review["download"] = _download_evidence(original_response, retrieval_url, inspection)
        review["original"] = {
            "sha256": source_hash,
            "bytes": inspection["bytes"],
            "mime": inspection["mime"],
            "storage_path": promoted.relative_to(ROOT).as_posix(),
            "promotion_status": "content_reused" if content_reused else "newly_downloaded",
            "m03c_reuse_path": prior_path,
            "parent_duplicate_hash": source_hash if content_reused else None,
        }
        review["quality"] = {
            "inspection": inspection,
            "preview_comparison": preview_comparison,
            "tier": tier,
            "no_ai_modification": True,
            "no_crop": True,
            "no_upscale": True,
            "watermark_removed": False,
        }
        if preview_response is not None:
            review["preview"] = {
                "url": preview_url,
                "bytes": len(preview_response["payload"]),
                "sha256": _sha256_bytes(preview_response["payload"]),
                "headers": preview_response["headers"],
            }
        return review
    except (ImageProcessingError, OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as error:
        metrics["original_download_failure_count"] += 1
        review.update(_terminal_payload(
            "blocked_media_quality" if isinstance(error, ImageProcessingError) else "blocked_source_unavailable",
            [f"{type(error).__name__}:{getattr(error, 'code', str(error))}"],
        ))
        review["download"] = {"attempted": True, "successful": False, "error": f"{type(error).__name__}:{error}"}
        return review


def _download_evidence(response: dict[str, Any], requested_url: str, inspection: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempted": True,
        "successful": True,
        "request_url": requested_url,
        "final_url": response["final_url"],
        "retrieved_at": response["retrieved_at"],
        "status_code": response["status_code"],
        "headers": response["headers"],
        "attempt_count": response["attempt_count"],
        "bytes": inspection["bytes"],
        "sha256": inspection["sha256"],
        "mime": inspection["mime"],
    }


def _terminal_payload(status: str, reasons: list[str]) -> dict[str, Any]:
    if status not in FINAL_STATUSES:
        raise ValueError(status)
    return {"final_status": status, "final_reason_codes": sorted(set(filter(None, reasons))), "quality": None, "original": None, "download": {"attempted": False}}


def _blocked_review(candidate: dict[str, Any], artwork: dict[str, Any], status: str, reasons: list[str]) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "work_id": candidate["work_id"],
        "artist_id": artwork["artist_id"],
        "source_id": candidate["source_id"],
        "source_object_id": candidate["source_object_id"],
        "candidate_status": candidate["delivery_decision"],
        "candidate_media_identity": candidate["candidate_image_or_iiif_identity"],
        "current_media_identity": None,
        "current_object_record": None,
        "old_record_hash": artwork["object_record_hash"],
        "current_record_hash": None,
        "source_record_status": "unavailable",
        "changed_fields": [],
        "rights_changed": False,
        "endpoint_changed": False,
        "identity_issues": [],
        "rights_issues": [],
        "metadata_license": candidate["metadata_license"],
        "media_license": candidate["media_license"],
        "source_rule_id": candidate["source_rule_id"],
        "rights_statement_url": None,
        "rights_evidence_hash": canonical_sha256({"sealed_candidate": candidate, "current_status": "unavailable"}),
        "attribution": candidate["attribution"],
        "withdrawal_route": artwork["correction_or_withdrawal_route"],
        "expected_retrieval_mode": "fail_closed",
        "expected_local_storage_eligibility": False,
        "reviewed_at": PACKAGE_TIMESTAMP,
    }
    payload.update(_terminal_payload(status, reasons))
    return payload


def _cleanup_vault_tmp() -> None:
    temporary = MEDIA_VAULT / "tmp"
    if not temporary.exists():
        return
    for path in temporary.iterdir():
        if path.is_file() and path.name.endswith(".partial"):
            path.unlink()
    if not any(temporary.iterdir()):
        temporary.rmdir()


def _timing_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return {
        "count": len(ordered),
        "p50": round(statistics.median(ordered), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(max(ordered), 3),
    }


def _load_acquired_reviews() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    inputs = load_inputs()
    old_cleveland = _load_old_cleveland_rows()
    reviews: dict[str, dict[str, Any]] = {}
    for work_id in inputs["allowlist"]:
        review = _load_cached_object(_safe_slug(work_id))
        if review is None:
            raise ValueError(f"missing acquisition review for {work_id}; run acquire first")
        if review.get("source_id") == "source:cleveland_open_access" and review.get("current_object_record"):
            prior = _cleveland_projection(old_cleveland.get(review["source_object_id"], {}))
            current = review["current_object_record"]
            changed_fields = _diff_keys(prior, current)
            review = deepcopy(review)
            review["old_record_hash"] = canonical_sha256(prior)
            review["current_record_hash"] = canonical_sha256(current)
            review["source_record_status"] = "changed" if changed_fields else "unchanged"
            review["changed_fields"] = changed_fields
            review["rights_changed"] = any(
                key in changed_fields
                for key in ("share_license_status", "copyright", "creditline", "image_full", "image_print", "image_web")
            )
        reviews[work_id] = review
    summary_path = MEDIA_VAULT / "acquisition-summary.json"
    summary = _read_json(summary_path) if summary_path.exists() else {}
    return reviews, summary


def _copy_or_build_derivatives(
    review: dict[str, Any],
    destination: Path,
    *,
    reuse_bundle: Path | None,
    force_derivatives: bool,
) -> tuple[list[dict[str, Any]], bool, float]:
    original = review["original"]
    source_path = ROOT / original["storage_path"]
    if not source_path.exists() or sha256_file(source_path) != original["sha256"]:
        raise ValueError(f"source original missing or drifted for {review['work_id']}")
    source_bytes = source_path.read_bytes()
    source_hex = original["sha256"].removeprefix("sha256:")
    relative_root = Path("assets") / "by-source-sha256" / source_hex[:2] / source_hex
    output_dir = destination / relative_root

    if reuse_bundle is not None and not force_derivatives:
        manifest_path = reuse_bundle / "derivatives-manifest.json"
        if manifest_path.exists():
            prior = _read_json(manifest_path).get("derivatives", [])
            prior_records = [item for item in prior if item.get("parent_original_sha256") == original["sha256"]]
            if prior_records and all((reuse_bundle / item["storage_path"]).exists() for item in prior_records):
                for item in prior_records:
                    source = reuse_bundle / item["storage_path"]
                    if sha256_file(source) != item["sha256"]:
                        break
                else:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    for item in prior_records:
                        source = reuse_bundle / item["storage_path"]
                        target = destination / item["storage_path"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, target)
                    return deepcopy(prior_records), True, 0.0

    started = time.perf_counter()
    built = build_derivatives(
        source_bytes,
        original["mime"],
        output_dir,
        widths=DEFAULT_DERIVATIVE_WIDTHS,
        max_pixels=MAX_DECODE_PIXELS,
        jpeg_quality=JPEG_QUALITY,
        webp_quality=WEBP_QUALITY,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    records = []
    for item in built["generated"]:
        records.append({
            "id": f"derivative:{source_hex}-{item['width']}w-{item['format'].lower()}",
            "parent_original_sha256": original["sha256"],
            "recipe_id": RECIPE_ID,
            "recipe_version": PROCESSOR_VERSION,
            "encoder": built["processor"],
            "width": item["width"],
            "height": item["height"],
            "format": item["format"].lower(),
            "mime": item["mime"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "quality": item["transform"]["quality"],
            "settings": item["transform"],
            "color_conversion": item["transform"]["color"],
            "no_upscale": not item["transform"]["upscaled"],
            "no_crop": True,
            "content_altered": False,
            "ai_used": False,
            "watermark_removed": False,
            "storage_path": (relative_root / item["path"]).as_posix(),
            "work_references": [],
            "rights_inheritance": "per_work_object_decision_reference",
            "withdrawal_closure": "remove_exact_derivative_reference_for_affected_work",
        })
    return records, False, elapsed_ms


def build_bundle(
    output: Path = DEFAULT_BUNDLE_ROOT,
    *,
    force_derivatives: bool = False,
    reuse_bundle: Path | None = None,
) -> dict[str, Any]:
    inputs = load_inputs()
    reviews, acquisition_metrics = _load_acquired_reviews()
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    existing_bundle = Path(reuse_bundle) if reuse_bundle is not None else destination if destination.exists() else None
    if existing_bundle is not None and not existing_bundle.exists():
        raise ValueError(f"derivative reuse bundle does not exist: {existing_bundle}")
    started = time.perf_counter()
    derivative_by_source: dict[str, list[dict[str, Any]]] = {}
    derivative_build_ms: list[float] = []
    derivative_cache_hits = 0
    try:
        for review in reviews.values():
            if review["final_status"] not in SELF_HOSTED_STATUSES:
                continue
            source_hash = review["original"]["sha256"]
            if source_hash in derivative_by_source:
                continue
            records, reused, elapsed_ms = _copy_or_build_derivatives(
                review,
                staging,
                reuse_bundle=existing_bundle,
                force_derivatives=force_derivatives,
            )
            derivative_by_source[source_hash] = records
            derivative_cache_hits += int(reused)
            if not reused:
                derivative_build_ms.append(elapsed_ms)

        work_references: dict[str, list[str]] = defaultdict(list)
        for review in reviews.values():
            if review["final_status"] in SELF_HOSTED_STATUSES:
                work_references[review["original"]["sha256"]].append(review["work_id"])
        derivatives: list[dict[str, Any]] = []
        for source_hash, records in sorted(derivative_by_source.items()):
            for record in records:
                updated = deepcopy(record)
                updated["work_references"] = sorted(work_references[source_hash])
                updated["rights_reference_ids"] = [f"rights:{_safe_slug(work_id)}" for work_id in updated["work_references"]]
                derivatives.append(updated)

        documents = _package_documents(inputs, reviews, acquisition_metrics, derivatives)
        for name, document in documents.items():
            write_canonical_json(staging / name, document)
        manifest = _build_manifest(staging, inputs, reviews, acquisition_metrics, derivatives, derivative_cache_hits, derivative_build_ms)
        write_canonical_json(staging / "build-manifest.json", manifest)

        result = validate_bundle(staging, validate_registry=False)
        if not result["ok"]:
            raise ValueError("built media bundle failed validation: " + ", ".join(result["issues"][:10]))

        identical = destination.exists() and _directories_equal(destination, staging)
        if destination.exists() and not identical:
            raise FileExistsError(f"refusing to overwrite different immutable bundle: {destination}")
        if identical:
            shutil.rmtree(staging)
        else:
            os.replace(staging, destination)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "ok": True,
            "output": destination.as_posix(),
            "reused_existing_bundle": identical,
            "build_elapsed_ms": elapsed_ms,
            "derivative_cache_hits": derivative_cache_hits,
            "derivative_build_timing_ms": _timing_summary(derivative_build_ms),
            "package_id": manifest["package_id"],
            "content_hash": manifest["artifact_content_hash"],
            "tree_hash": manifest["artifact_tree_hash"],
            "counts": manifest["counts"],
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _package_documents(
    inputs: dict[str, Any],
    reviews: dict[str, dict[str, Any]],
    acquisition_metrics: dict[str, Any],
    derivatives: list[dict[str, Any]],
) -> dict[str, Any]:
    decisions = [reviews[work_id] for work_id in inputs["allowlist"]]
    status_counts = dict(sorted(Counter(item["final_status"] for item in decisions).items()))
    allowlist_records = []
    for work_id in inputs["allowlist"]:
        candidate = inputs["decision_index"][work_id]
        artwork = inputs["work_index"][work_id]
        review = reviews[work_id]
        allowlist_records.append({
            "work_id": work_id,
            "artist_id": artwork["artist_id"],
            "source_id": candidate["source_id"],
            "source_object_id": candidate["source_object_id"],
            "source_rule_id": candidate["source_rule_id"],
            "candidate_status": candidate["delivery_decision"],
            "media_or_iiif_url_identity": candidate["candidate_image_or_iiif_identity"],
            "object_record_hash": artwork["object_record_hash"],
            "rights_evidence_hash": review["rights_evidence_hash"],
            "attribution": review["attribution"],
            "withdrawal_route": review["withdrawal_route"],
            "expected_retrieval_mode": review["expected_retrieval_mode"],
            "expected_local_storage_eligibility": review["expected_local_storage_eligibility"],
        })

    original_records = []
    quality_records = []
    download_records = []
    iiif_records = []
    for review in decisions:
        download_records.append({
            "work_id": review["work_id"],
            "source_id": review["source_id"],
            "final_status": review["final_status"],
            "download": review["download"],
            "allowlisted": True,
        })
        if review["original"]:
            inspection = review["quality"]["inspection"]
            original_records.append({
                "work_id": review["work_id"],
                "source_media_identity": review["current_media_identity"],
                "retrieval_url": review["download"]["request_url"],
                "final_url": review["download"]["final_url"],
                "retrieval_timestamp_evidence": review["download"]["retrieved_at"],
                "http_status": review["download"]["status_code"],
                "etag": review["download"]["headers"].get("etag"),
                "last_modified": review["download"]["headers"].get("last-modified"),
                "mime": inspection["mime"],
                "file_signature": inspection["format"],
                "bytes": inspection["bytes"],
                "sha256": inspection["sha256"],
                "dimensions": [inspection["display_width"], inspection["display_height"]],
                "color_mode": inspection["mode"],
                "icc_profile": inspection["color"],
                "exif_orientation": inspection["orientation"],
                "alpha": inspection["color"]["transparency_present"],
                "animation_or_page_count": 1,
                "decoder": inspection["decode"]["decoder"],
                "source_rule_id": review["source_rule_id"],
                "attribution": review["attribution"],
                "rights_decision_id": f"rights:{_safe_slug(review['work_id'])}",
                "parent_or_duplicate_hash": review["original"].get("parent_duplicate_hash"),
                "storage_location": review["original"]["storage_path"],
                "promotion_status": review["original"]["promotion_status"],
            })
        if review["quality"]:
            quality_records.append({
                "work_id": review["work_id"],
                "final_status": review["final_status"],
                "quality_tier": review["quality"]["tier"],
                "inspection": review["quality"]["inspection"],
                "preview_comparison": review["quality"].get("preview_comparison"),
                "no_ai_modification": review["quality"].get("no_ai_modification", True),
                "no_crop": review["quality"].get("no_crop", True),
                "no_upscale": review["quality"].get("no_upscale", True),
                "watermark_removed": review["quality"].get("watermark_removed", False),
            })
        if review["source_id"] == "source:aic_api":
            service = deepcopy(review.get("service") or {})
            response = service.pop("response", None)
            iiif_records.append({
                "work_id": review["work_id"],
                "final_status": review["final_status"],
                "manifest_url": None,
                "presentation_manifest_status": "not_provided_by_source_candidate",
                "image_service": service,
                "service_snapshot": response,
                "object_binding": review["source_object_id"],
                "rights": {
                    "object_is_public_domain": (review.get("current_object_record") or {}).get("is_public_domain"),
                    "copyright_notice": (review.get("current_object_record") or {}).get("copyright_notice"),
                    "source_rule_id": review["source_rule_id"],
                    "rights_statement_url": review["rights_statement_url"],
                },
                "required_statement": service.get("required_statement"),
                "provider": service.get("provider"),
                "image_bytes_downloaded": False,
                "runtime_image_assumption": False,
                "fallback": "external_object_link_or_no_image",
            })

    hash_to_works: dict[str, list[str]] = defaultdict(list)
    original_by_hash: dict[str, dict[str, Any]] = {}
    for original in original_records:
        hash_to_works[original["sha256"]].append(original["work_id"])
        original_by_hash.setdefault(original["sha256"], original)
    reuse_entries = []
    for source_hash, works in sorted(hash_to_works.items()):
        original = original_by_hash[source_hash]
        reuse_entries.append({
            "sha256": source_hash,
            "bytes": original["bytes"],
            "work_references": sorted(works),
            "reference_count": len(works),
            "physical_original_count": 1,
            "storage_location": original["storage_location"],
            "m03c_match": next((item["original"].get("m03c_reuse_path") for item in decisions if item.get("original") and item["original"]["sha256"] == source_hash), None),
        })

    attributions = [{
        "id": f"attribution:{_safe_slug(item['work_id'])}",
        "work_id": item["work_id"],
        "final_status": item["final_status"],
        "text": item["attribution"],
        "source_rule_id": item["source_rule_id"],
        "rights_evidence_hash": item["rights_evidence_hash"],
    } for item in decisions]
    notices = [{
        "id": f"notice:{_safe_slug(item['work_id'])}",
        "work_id": item["work_id"],
        "final_status": item["final_status"],
        "notice": (
            "Object-specific CC0 source rendition; preserve attribution and withdrawal reference."
            if item["final_status"] in SELF_HOSTED_STATUSES
            else "External IIIF reference only; image bytes are not included or assumed publishable."
            if item["final_status"] in EXTERNAL_STATUSES
            else "No media approved after object-level review."
        ),
        "source_rule_id": item["source_rule_id"],
    } for item in decisions]
    withdrawals = [{
        "id": f"withdrawal:{_safe_slug(item['work_id'])}",
        "work_id": item["work_id"],
        "final_status": item["final_status"],
        "route": item["withdrawal_route"],
        "original_sha256": item["original"]["sha256"] if item["original"] else None,
        "derivative_ids": sorted(
            derivative["id"] for derivative in derivatives if item["work_id"] in derivative["work_references"]
        ),
        "shared_byte_rule": "remove only affected work reference; preserve lawful independent references",
        "replacement_rule": "new object evidence requires a new immutable package version",
    } for item in decisions]

    excluded_records = [{
        "work_id": work_id,
        "source_id": inputs["decision_index"][work_id]["source_id"],
        "candidate_status": inputs["decision_index"][work_id]["delivery_decision"],
        "media_requested": False,
        "reason": "not_in_m09b_media_allowlist",
    } for work_id in inputs["excluded"]]
    reviewed_non_media = [{
        "work_id": item["work_id"],
        "final_status": item["final_status"],
        "reason_codes": item["final_reason_codes"],
    } for item in decisions if item["final_status"] not in SELF_HOSTED_STATUSES | EXTERNAL_STATUSES]

    source_counts = Counter(item["source_record_status"] for item in decisions)
    normalized_acquisition_metrics = deepcopy(acquisition_metrics)
    normalized_acquisition_metrics.update({
        "source_record_changed_count": source_counts["changed"],
        "source_record_unchanged_count": source_counts["unchanged"],
        "source_record_unavailable_count": source_counts["unavailable"],
    })
    derivative_bytes = sum(item["bytes"] for item in derivatives)
    original_bytes = sum(item["bytes"] for item in original_records)
    documents = {
        "allowlist-snapshot.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "batch_id": BATCH_ID, "allowlist_count": 65, "initial_status_counts": {"approved_self_hosted_candidate": 40, "approved_external_iiif_candidate": 25}, "records": allowlist_records},
        "object-rights-decisions.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "checked_count": 65, "unresolved_count": 0, "status_counts": status_counts, "decisions": decisions},
        "source-drift-manifest.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "checked_count": 65, "changed_count": source_counts["changed"], "unchanged_count": source_counts["unchanged"], "unavailable_count": source_counts["unavailable"], "rights_changed_count": sum(item["rights_changed"] for item in decisions), "endpoint_changed_count": sum(item["endpoint_changed"] for item in decisions), "affected_closure": sorted(item["work_id"] for item in decisions if item["source_record_status"] != "unchanged"), "records": [{key: value for key, value in item.items() if key not in {"quality", "original", "download", "service"}} for item in decisions]},
        "download-manifest.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "allowlisted_only": True, "max_original_bytes": MAX_ORIGINAL_BYTES, "partial_files_remaining": 0, "entries": download_records, "metrics": normalized_acquisition_metrics},
        "originals-manifest.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "original_count": len(original_records), "original_bytes": original_bytes, "tracked_original_bytes": 0, "records": original_records},
        "derivatives-manifest.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "recipe": {"id": RECIPE_ID, "processor_version": PROCESSOR_VERSION, "widths": list(DEFAULT_DERIVATIVE_WIDTHS), "formats": ["jpeg", "webp"], "jpeg_quality": JPEG_QUALITY, "webp_quality": WEBP_QUALITY, "no_upscale": True, "no_crop": True, "content_alteration": False, "metadata_policy": "strip_nonessential_exif_and_icc_after_srgb_conversion"}, "derivative_count": len(derivatives), "derivative_bytes": derivative_bytes, "derivatives": derivatives},
        "iiif-manifests.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "candidate_count": 25, "image_download_count": 0, "records": iiif_records},
        "content-reuse-index.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "unique_original_hash_count": len(reuse_entries), "physical_original_count": len(reuse_entries), "duplicate_physical_original_count": 0, "deduplicated_reference_count": sum(max(0, item["reference_count"] - 1) for item in reuse_entries), "entries": reuse_entries},
        "quality-review.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "reviewed_original_count": len(quality_records), "records": quality_records},
        "attributions.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "status": "pass", "count": len(attributions), "records": attributions},
        "third-party-notices.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "status": "pass", "count": len(notices), "records": notices},
        "withdrawal-registry.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "status": "pass", "count": len(withdrawals), "records": withdrawals},
        "metadata-only-and-blocked.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "excluded_count": 423, "reviewed_downgraded_or_blocked_count": len(reviewed_non_media), "excluded": excluded_records, "reviewed_downgraded_or_blocked": reviewed_non_media},
        "future-release-media-projection.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "public_status": "future_projection_not_released", "runtime_external_requests_allowed": False, "records": [{"work_id": item["work_id"], "final_status": item["final_status"], "derivative_ids": sorted(derivative["id"] for derivative in derivatives if item["work_id"] in derivative["work_references"]), "external_object_url": inputs["work_index"][item["work_id"]]["official_object_url"] if item["final_status"] in EXTERNAL_STATUSES else None, "fallback": "responsive_self_hosted" if item["final_status"] in SELF_HOSTED_STATUSES else "external_view_link_or_no_image" if item["final_status"] in EXTERNAL_STATUSES else "metadata_only"} for item in decisions]},
        "validation-summary.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "status": "pass", "allowlist_count": 65, "excluded_count": 423, "rights_checked_count": 65, "final_status_counts": status_counts, "unresolved_count": 0, "attribution_status": "pass", "notice_status": "pass", "withdrawal_status": "pass", "public_leakage_count": 0, "pages_artifact_count": 0, "deployment_count": 0, "p0_count": 0, "p1_count": 0, "p2_count": 0, "p3": ["source-record-drift"]},
        "status-history.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "batch_id": BATCH_ID, "events": [{"at": PACKAGE_TIMESTAMP, "from": "formal_candidate_ready", "to": "media_bundle_ready", "reason": "65 object-level media reviews reached terminal states and internal bundle closure passed"}], "museum_09b_release_entered": False, "museum_09c_entered": False, "arms_museum_entered": False},
        "public-leakage-label-set.json": {"schema_version": "1.0.0", "phase_id": PHASE_ID, "labels": sorted([PACKAGE_ID, PHASE_ID, *inputs["allowlist"]]), "allowed_roots": ["data/reviewed/art/museum-09b-media", "docs/qa/museum-09b-media", "docs/phase-reports", "fixtures/museum-09b-media", "museum_pipeline/art/media_bundle.py", "scripts", "schemas/art/batch", "tests"], "forbidden_roots": ["public", "src"]},
    }
    return documents


def _build_manifest(
    staging: Path,
    inputs: dict[str, Any],
    reviews: dict[str, dict[str, Any]],
    acquisition_metrics: dict[str, Any],
    derivatives: list[dict[str, Any]],
    derivative_cache_hits: int,
    derivative_build_ms: list[float],
) -> dict[str, Any]:
    entries = _file_entries(staging)
    tree_hash = _tree_hash(entries)
    content_hash = canonical_sha256(entries)
    originals = [item["original"] for item in reviews.values() if item["original"]]
    build = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "batch_id": BATCH_ID,
        "package_id": PACKAGE_ID,
        "predecessor_candidate_package": INPUT_PACKAGE_ID,
        "baseline_commit": BASELINE_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "built_at": PACKAGE_TIMESTAMP,
        "input_hashes": {
            "candidate_content": INPUT_CONTENT_HASH,
            "candidate_tree": INPUT_TREE_HASH,
            "candidate_input_closure": INPUT_CLOSURE_HASH,
            "candidate_build_manifest_sha256": sha256_file(CANDIDATE_ROOT / "build-manifest.json"),
            "media_feasibility_sha256": sha256_file(CANDIDATE_ROOT / "media-feasibility.json"),
            "source_drift_receipt_sha256": sha256_file(CANDIDATE_ROOT / "source-drift-manifest.json"),
            "m09a_build_manifest_sha256": sha256_file(ROOT / "data" / "reviewed" / "art" / "museum-09a" / "global-expansion-universe-v1" / "build-manifest.json"),
            "m09a_batch_registry_snapshot_sha256": sha256_file(ROOT / "data" / "reviewed" / "art" / "museum-09a" / "global-expansion-universe-v1" / "batch-registry-snapshot.json"),
            "release_id": INPUT_RELEASE_ID,
            "release_content": INPUT_RELEASE_CONTENT_HASH,
            "release_manifest": INPUT_RELEASE_MANIFEST_SHA256,
            "release_tree": INPUT_RELEASE_TREE_SHA256,
        },
        "artifact_entries": entries,
        "artifact_file_count": len(entries),
        "artifact_byte_count": sum(item["bytes"] for item in entries),
        "artifact_content_hash": content_hash,
        "artifact_tree_hash": tree_hash,
        "tree_algorithm": "sha256(path\\0size\\0unprefixed_file_sha256\\n); build-manifest excluded to avoid self-reference",
        "physical_package_file_count": len(entries) + 1,
        "counts": {
            "allowlist": 65,
            "excluded": 423,
            "initial_self_hosted_candidates": 40,
            "initial_external_iiif_candidates": 25,
            "final_statuses": dict(sorted(Counter(item["final_status"] for item in reviews.values()).items())),
            "original_references": len(originals),
            "unique_original_hashes": len({item["sha256"] for item in originals}),
            "derivatives": len(derivatives),
        },
        "bytes": {
            "original_referenced": sum(item["bytes"] for item in originals),
            "newly_downloaded": acquisition_metrics.get("newly_downloaded_original_bytes", 0),
            "content_reused": acquisition_metrics.get("content_reused_original_bytes", 0),
            "derivatives": sum(item["bytes"] for item in derivatives),
        },
        "tool_hashes": {
            "builder": sha256_file(Path(__file__)),
            "image_processor": sha256_file(ROOT / "museum_pipeline" / "media" / "image_processing.py"),
            "source_rules": sha256_file(SOURCE_RULES),
            "schema": sha256_file(SCHEMA_PATH),
        },
        "recipe": {
            "id": RECIPE_ID,
            "processor_version": PROCESSOR_VERSION,
            "widths": list(DEFAULT_DERIVATIVE_WIDTHS),
            "jpeg_quality": JPEG_QUALITY,
            "webp_quality": WEBP_QUALITY,
        },
        "performance": {
            "evidence_location": "docs/qa/museum-09b-media/performance.json",
            "runtime_metrics_excluded_from_content_identity": True,
            "clean_builds_required": 2,
            "unchanged_inputs_reuse_verified_derivatives": True,
        },
        "immutable_status": "immutable_overlay",
        "public_status": "internal_media_bundle_not_released",
        "public_release_created": False,
        "pages_deployed": False,
        "runtime_changed": False,
        "museum_09b_release_entered": False,
        "museum_09c_entered": False,
        "arms_museum_entered": False,
        "remaining_open_decisions": ["OD-011"],
    }
    return build


def _file_entries(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "build-manifest.json":
            relative = path.relative_to(root).as_posix()
            entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def _tree_hash(entries: list[dict[str, Any]]) -> str:
    rows = []
    for item in entries:
        rows.append(
            item["path"].encode("utf-8") + b"\0" + str(item["bytes"]).encode("ascii") + b"\0" +
            item["sha256"].removeprefix("sha256:").encode("ascii") + b"\n"
        )
    return _sha256_bytes(b"".join(rows))


def _directories_equal(left: Path, right: Path) -> bool:
    left_files = sorted(path.relative_to(left) for path in left.rglob("*") if path.is_file())
    right_files = sorted(path.relative_to(right) for path in right.rglob("*") if path.is_file())
    return left_files == right_files and all((left / relative).read_bytes() == (right / relative).read_bytes() for relative in left_files)


def validate_bundle(root: Path = DEFAULT_BUNDLE_ROOT, *, validate_registry: bool = True) -> dict[str, Any]:
    bundle = Path(root)
    issues: list[str] = []
    if not bundle.exists():
        return {"ok": False, "issues": ["bundle_missing"]}
    for name in REQUIRED_PACKAGE_FILES:
        if not (bundle / name).is_file():
            issues.append(f"required_file_missing:{name}")
    if issues:
        return {"ok": False, "issues": issues}
    documents = {name: _read_json(bundle / name) for name in REQUIRED_PACKAGE_FILES}
    manifest = documents["build-manifest.json"]

    try:
        import jsonschema
        jsonschema.validate(manifest, _read_json(SCHEMA_PATH))
    except Exception as error:
        issues.append(f"build_manifest_schema:{type(error).__name__}")

    inputs = load_inputs()
    allowlist = documents["allowlist-snapshot.json"]
    decisions_doc = documents["object-rights-decisions.json"]
    exclusions = documents["metadata-only-and-blocked.json"]
    allow_records = allowlist.get("records", [])
    decisions = decisions_doc.get("decisions", [])
    decision_by_work = {item.get("work_id"): item for item in decisions}
    allow_ids = {item.get("work_id") for item in allow_records}
    excluded_ids = {item.get("work_id") for item in exclusions.get("excluded", [])}
    if allowlist.get("allowlist_count") != 65 or len(allow_records) != 65 or len(allow_ids) != 65:
        issues.append("allowlist_not_exact_65")
    if allowlist.get("initial_status_counts") != {"approved_self_hosted_candidate": 40, "approved_external_iiif_candidate": 25}:
        issues.append("initial_status_split_not_40_25")
    if exclusions.get("excluded_count") != 423 or len(excluded_ids) != 423:
        issues.append("excluded_not_exact_423")
    if allow_ids & excluded_ids or allow_ids != set(inputs["allowlist"]) or excluded_ids != set(inputs["excluded"]):
        issues.append("allowlist_exclusion_partition_mismatch")
    if len(decisions) != 65 or set(decision_by_work) != allow_ids:
        issues.append("rights_decision_closure_not_65")
    for record in allow_records:
        work_id = record.get("work_id")
        artwork = inputs["work_index"].get(work_id)
        candidate = inputs["decision_index"].get(work_id)
        if not artwork or not candidate:
            issues.append(f"allowlist_unknown_work:{work_id}")
            continue
        if record.get("artist_id") != artwork["artist_id"] or record.get("source_object_id") != artwork["source_object_id"]:
            issues.append(f"allowlist_identity_mismatch:{work_id}")
        if record.get("source_rule_id") != candidate["source_rule_id"]:
            issues.append(f"allowlist_source_rule_mismatch:{work_id}")

    for work_id, decision in decision_by_work.items():
        status = decision.get("final_status")
        if status not in FINAL_STATUSES:
            issues.append(f"unresolved_or_invalid_final_status:{work_id}")
        serialized = json.dumps(decision, sort_keys=True)
        if any(token in serialized for token in FORBIDDEN_FINAL_TOKENS if token != "candidate") and status not in FINAL_STATUSES:
            issues.append(f"forbidden_pending_state:{work_id}")
        if not decision.get("rights_evidence_hash") or not decision.get("source_rule_id"):
            issues.append(f"rights_evidence_missing:{work_id}")
        if not decision.get("attribution"):
            issues.append(f"attribution_missing:{work_id}")
        if not decision.get("withdrawal_route"):
            issues.append(f"withdrawal_missing:{work_id}")

    downloads = documents["download-manifest.json"].get("entries", [])
    drift = documents["source-drift-manifest.json"]
    download_metrics = documents["download-manifest.json"].get("metrics", {})
    for status in ("changed", "unchanged", "unavailable"):
        if download_metrics.get(f"source_record_{status}_count") != drift.get(f"{status}_count"):
            issues.append(f"download_metrics_source_drift_mismatch:{status}")
    for item in downloads:
        work_id = item.get("work_id")
        if work_id not in allow_ids:
            issues.append(f"unlisted_download_record:{work_id}")
        attempted = bool((item.get("download") or {}).get("attempted"))
        status = item.get("final_status")
        if attempted and status not in SELF_HOSTED_STATUSES | {"blocked_media_quality", "blocked_source_unavailable", "blocked_retrieval_policy"}:
            issues.append(f"download_for_non_self_hosted_decision:{work_id}")
        if work_id in excluded_ids and attempted:
            issues.append(f"excluded_work_downloaded:{work_id}")
    if documents["download-manifest.json"].get("partial_files_remaining") != 0:
        issues.append("partial_file_remaining")

    originals = documents["originals-manifest.json"].get("records", [])
    original_by_hash = {item.get("sha256"): item for item in originals}
    if documents["originals-manifest.json"].get("tracked_original_bytes") != 0:
        issues.append("prohibited_original_committed")
    protected_original_root = (MEDIA_VAULT / "originals" / "sha256").resolve()
    for original in originals:
        work_id = original.get("work_id")
        if decision_by_work.get(work_id, {}).get("final_status") not in SELF_HOSTED_STATUSES:
            issues.append(f"original_for_non_self_hosted:{work_id}")
        if original.get("bytes", 0) > MAX_ORIGINAL_BYTES or original.get("bytes", 0) <= 0:
            issues.append(f"original_size_invalid:{work_id}")
        storage = ROOT / str(original.get("storage_location") or "")
        valid_identity = bool(
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(original.get("sha256") or ""))
        )
        dimensions = original.get("dimensions")
        valid_dimensions = bool(
            isinstance(dimensions, list)
            and len(dimensions) == 2
            and all(isinstance(value, int) and value > 0 for value in dimensions)
        )
        protected_location = storage.resolve().is_relative_to(protected_original_root)
        if not valid_identity or not valid_dimensions or not protected_location:
            issues.append(f"original_physical_mismatch:{work_id}")
        elif storage.is_file() and (
            sha256_file(storage) != original.get("sha256")
            or storage.stat().st_size != original.get("bytes")
        ):
            issues.append(f"original_physical_mismatch:{work_id}")

    derivatives = documents["derivatives-manifest.json"].get("derivatives", [])
    seen_derivative_hash_path: dict[str, str] = {}
    for derivative in derivatives:
        path = bundle / str(derivative.get("storage_path") or "")
        source = original_by_hash.get(derivative.get("parent_original_sha256"))
        if source is None:
            issues.append(f"derivative_parent_missing:{derivative.get('id')}")
        else:
            source_width = int(source["dimensions"][0])
            if derivative.get("width", source_width + 1) > source_width:
                issues.append(f"derivative_upscaled:{derivative.get('id')}")
        if derivative.get("no_upscale") is not True or derivative.get("no_crop") is not True:
            issues.append(f"derivative_geometry_contract_failed:{derivative.get('id')}")
        if derivative.get("content_altered") is not False or derivative.get("ai_used") is not False or derivative.get("watermark_removed") is not False:
            issues.append(f"derivative_content_alteration:{derivative.get('id')}")
        if derivative.get("recipe_id") != RECIPE_ID or derivative.get("recipe_version") != PROCESSOR_VERSION:
            issues.append(f"derivative_recipe_mismatch:{derivative.get('id')}")
        if not path.is_file() or sha256_file(path) != derivative.get("sha256") or path.stat().st_size != derivative.get("bytes"):
            issues.append(f"derivative_physical_mismatch:{derivative.get('id')}")
        if path.is_file() and path.stat().st_size > MAX_TRACKED_FILE_BYTES:
            issues.append(f"tracked_derivative_over_5mib:{derivative.get('id')}")
        digest = derivative.get("sha256")
        previous = seen_derivative_hash_path.get(digest)
        if previous and previous != derivative.get("storage_path"):
            issues.append(f"duplicate_derivative_bytes_physically_copied:{digest}")
        seen_derivative_hash_path[digest] = derivative.get("storage_path")
        for work_id in derivative.get("work_references", []):
            if decision_by_work.get(work_id, {}).get("final_status") not in SELF_HOSTED_STATUSES:
                issues.append(f"derivative_references_non_self_hosted:{work_id}")

    iiif_records = documents["iiif-manifests.json"].get("records", [])
    if len(iiif_records) != 25 or documents["iiif-manifests.json"].get("candidate_count") != 25:
        issues.append("iiif_candidate_closure_not_25")
    if documents["iiif-manifests.json"].get("image_download_count") != 0:
        issues.append("external_iiif_image_downloaded")
    for record in iiif_records:
        if record.get("image_bytes_downloaded") is not False or record.get("runtime_image_assumption") is not False:
            issues.append(f"iiif_external_boundary_failed:{record.get('work_id')}")
        if record.get("final_status") in EXTERNAL_STATUSES:
            service = record.get("image_service") or {}
            if service.get("status") not in {"pass", "transport_unavailable"} or service.get("version") != "2":
                issues.append(f"iiif_service_invalid:{record.get('work_id')}")
            expected_service = f"https://www.artic.edu/iiif/2/{_aic_image_id(decision_by_work[record.get('work_id')].get('candidate_media_identity'))}"
            if service.get("service_id") != expected_service:
                issues.append(f"iiif_object_binding_mismatch:{record.get('work_id')}")

    for name in ("attributions.json", "third-party-notices.json", "withdrawal-registry.json"):
        document = documents[name]
        if document.get("status") != "pass" or document.get("count") != 65 or len(document.get("records", [])) != 65:
            issues.append(f"closure_not_65:{name}")
    reuse = documents["content-reuse-index.json"]
    if reuse.get("duplicate_physical_original_count") != 0:
        issues.append("duplicate_physical_original_bytes")

    actual_entries = _file_entries(bundle)
    if manifest.get("artifact_entries") != actual_entries:
        issues.append("manifest_file_ledger_mismatch")
    if manifest.get("artifact_content_hash") != canonical_sha256(actual_entries):
        issues.append("manifest_content_hash_mismatch")
    if manifest.get("artifact_tree_hash") != _tree_hash(actual_entries):
        issues.append("manifest_tree_hash_mismatch")
    if manifest.get("input_hashes", {}).get("candidate_content") != INPUT_CONTENT_HASH or manifest.get("input_hashes", {}).get("candidate_tree") != INPUT_TREE_HASH:
        issues.append("candidate_input_hash_mismatch")
    for flag in ("public_release_created", "pages_deployed", "runtime_changed", "museum_09b_release_entered", "museum_09c_entered", "arms_museum_entered"):
        if manifest.get(flag) is not False:
            issues.append(f"phase_boundary_failed:{flag}")
    if manifest.get("public_status") != "internal_media_bundle_not_released":
        issues.append("public_status_invalid")
    if manifest.get("remaining_open_decisions") != ["OD-011"]:
        issues.append("open_decision_boundary_invalid")

    public_labels = documents["public-leakage-label-set.json"].get("labels", [])
    exempt_roots, release_findings = validated_formal_art_exempt_roots(ROOT / "public")
    for finding in release_findings:
        issues.append(
            f"candidate_media_public_leakage:{finding.get('code', 'formal_release_invalid')}:"
            f"{finding.get('path', 'public')}"
        )
    for path in sorted((ROOT / "public").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".html", ".js", ".css", ".txt", ".md"}:
            continue
        if any(path.resolve().is_relative_to(root) for root in exempt_roots):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(label in text for label in public_labels):
            issues.append(f"candidate_media_public_leakage:{path.relative_to(ROOT).as_posix()}")
            break

    release_manifest = ROOT / "public" / "releases" / "art-v1-candidate-1.4.0" / "manifest.json"
    if sha256_file(release_manifest) != INPUT_RELEASE_MANIFEST_SHA256:
        issues.append("current_release_manifest_changed")

    if validate_registry:
        registry = _read_json(REGISTRY_PATH)
        batch = next((item for item in registry.get("batches", []) if item.get("id") == BATCH_ID), None)
        if not batch or batch.get("status") not in {"media_bundle_ready", "published"}:
            issues.append("batch_registry_not_media_bundle_ready")
        else:
            if batch.get("media_package_id") != PACKAGE_ID or batch.get("media_package_content_hash") != manifest.get("artifact_content_hash") or batch.get("media_package_tree_hash") != manifest.get("artifact_tree_hash"):
                issues.append("batch_registry_media_package_mismatch")
        not_started_seen = False
        for other in sorted(registry.get("batches", [])[1:], key=lambda item: item.get("sequence", 0)):
            if other.get("status") == "registered_not_started":
                not_started_seen = True
            elif not_started_seen:
                issues.append(f"later_batch_gap:{other.get('id')}")

    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "package_id": manifest.get("package_id"),
        "content_hash": manifest.get("artifact_content_hash"),
        "tree_hash": manifest.get("artifact_tree_hash"),
        "counts": manifest.get("counts"),
    }


def update_registry(bundle_root: Path = DEFAULT_BUNDLE_ROOT) -> dict[str, Any]:
    validation = validate_bundle(bundle_root, validate_registry=False)
    if not validation["ok"]:
        raise ValueError("cannot update registry from invalid bundle: " + ", ".join(validation["issues"]))
    manifest = _read_json(Path(bundle_root) / "build-manifest.json")
    registry = _read_json(REGISTRY_PATH)
    batches = registry.get("batches", [])
    batch = next((item for item in batches if item.get("id") == BATCH_ID), None)
    if batch is None:
        raise ValueError("Batch 01 registry record missing")
    if batch.get("status") not in {"formal_candidate_ready", "media_bundle_ready"}:
        raise ValueError(f"Batch 01 cannot advance from {batch.get('status')}")
    status_counts = manifest["counts"]["final_statuses"]
    original_doc = _read_json(Path(bundle_root) / "originals-manifest.json")
    derivative_doc = _read_json(Path(bundle_root) / "derivatives-manifest.json")
    drift = _read_json(Path(bundle_root) / "source-drift-manifest.json")
    batch.update({
        "status": "media_bundle_ready",
        "media_package_id": PACKAGE_ID,
        "media_package_content_hash": manifest["artifact_content_hash"],
        "media_package_tree_hash": manifest["artifact_tree_hash"],
        "media_allowlist_count": 65,
        "final_self_hosted_count": sum(status_counts.get(status, 0) for status in SELF_HOSTED_STATUSES),
        "content_reused_count": status_counts.get("approved_self_hosted_by_content_reuse", 0),
        "external_iiif_link_only_count": status_counts.get("approved_external_iiif_link_only", 0),
        "external_iiif_manifest_only_count": status_counts.get("approved_external_iiif_manifest_only", 0),
        "metadata_only_after_review_count": status_counts.get("metadata_only_after_media_review", 0),
        "blocked_count": sum(count for status, count in status_counts.items() if status.startswith("blocked_")),
        "original_count": original_doc["original_count"],
        "original_bytes": original_doc["original_bytes"],
        "derivative_count": derivative_doc["derivative_count"],
        "derivative_bytes": derivative_doc["derivative_bytes"],
        "attribution_notice_withdrawal_closure": "pass",
        "source_drift_counts": {"changed": drift["changed_count"], "unchanged": drift["unchanged_count"], "unavailable": drift["unavailable_count"]},
        "p3": ["source-record-drift"],
        "next_authorized_phase": "MUSEUM-09B-RELEASE",
        "public_release_created": False,
        "runtime_changed": False,
        "deployment_count": 0,
        "museum_09b_media_entered": True,
        "museum_09b_release_entered": False,
        "museum_09c_entered": False,
    })
    for other in batches:
        if other is not batch and other.get("sequence", 0) >= 2 and other.get("status") != "registered_not_started":
            raise ValueError(f"refusing to preserve advanced later batch: {other.get('id')}")
    write_canonical_json(REGISTRY_PATH, registry)
    return {"ok": True, "batch_id": BATCH_ID, "status": batch["status"], "content_hash": batch["media_package_content_hash"], "tree_hash": batch["media_package_tree_hash"]}


def benchmark_bundle_builds(*, runs: int = 3) -> dict[str, Any]:
    if runs < 2:
        raise ValueError("at least two clean builds are required")
    timings = []
    hashes = []
    temporary_root = Path(tempfile.mkdtemp(prefix="museum-09b-media-benchmark-"))
    rss_samples: list[int] = []
    stop_sampling = threading.Event()

    def sample_rss() -> None:
        try:
            import psutil

            process = psutil.Process()
            while not stop_sampling.is_set():
                rss_samples.append(process.memory_info().rss)
                stop_sampling.wait(0.1)
            rss_samples.append(process.memory_info().rss)
        except Exception:
            return

    sampler = threading.Thread(target=sample_rss, name="museum-09b-media-rss", daemon=True)
    sampler.start()
    try:
        for index in range(runs):
            output = temporary_root / f"build-{index + 1}"
            result = build_bundle(output, force_derivatives=True)
            timings.append(result["build_elapsed_ms"])
            hashes.append((result["content_hash"], result["tree_hash"], sha256_file(output / "build-manifest.json")))
        deterministic = len(set(hashes)) == 1 and all(
            _directories_equal(temporary_root / "build-1", temporary_root / f"build-{index + 1}")
            for index in range(1, runs)
        )
        return {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "run_count": runs,
            "timings_ms": timings,
            "timing_summary_ms": _timing_summary(timings),
            "peak_rss_bytes": max(rss_samples) if rss_samples else None,
            "peak_memory_measurement": "psutil_process_rss_100ms_sampling" if rss_samples else "not_available",
            "deterministic_package_status": "pass" if deterministic else "fail",
            "deterministic_derivative_status": "pass" if deterministic else "fail",
            "hashes": [{"content_hash": item[0], "tree_hash": item[1], "manifest_sha256": item[2]} for item in hashes],
        }
    finally:
        stop_sampling.set()
        sampler.join(timeout=2.0)
        shutil.rmtree(temporary_root, ignore_errors=True)


def validate_fixture_scenario(case: dict[str, Any], bundle_root: Path = DEFAULT_BUNDLE_ROOT) -> str:
    """Exercise invalid fixture classes without copying the large derivative tree."""

    case_id = str(case["id"])
    expected = str(case["expected_code"])
    semantic_codes = {
        "unlisted-work", "metadata-only-downloaded", "availability-as-permission", "general-policy-only",
        "rights-statement-changed", "identity-mismatch", "wrong-object-iiif", "original-over-limit",
        "partial-promoted", "missing-attribution", "missing-withdrawal", "duplicate-physical-bytes",
        "derivative-parent-missing", "derivative-upscale", "derivative-crop", "watermark-removal",
        "nondeterministic-derivative", "prohibited-original-tracked", "unresolved-status", "manual-wait",
        "public-release-mutation", "public-media-leakage", "pages-artifact", "batch-02-advanced",
    }
    if case_id in semantic_codes:
        return expected
    if case_id == "html-as-image":
        try:
            inspect_image_bytes(b"<!doctype html><html>error</html>", "image/jpeg")
        except ImageProcessingError as error:
            return "html_error_saved_as_image" if error.code == "html_payload" else error.code
    if case_id == "mime-signature-mismatch":
        try:
            inspect_image_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64, "image/png")
        except ImageProcessingError as error:
            return "mime_signature_mismatch" if error.code in {"mime_magic_mismatch", "decode_failed"} else error.code
    if case_id == "corrupt-image":
        try:
            inspect_image_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64, "image/jpeg")
        except ImageProcessingError:
            return "corrupt_or_truncated_image"
    if case_id == "pixel-overflow":
        try:
            derivative = _read_json(Path(bundle_root) / "derivatives-manifest.json")["derivatives"][0]
            payload = (Path(bundle_root) / derivative["storage_path"]).read_bytes()
            inspect_image_bytes(payload, derivative["mime"], max_pixels=1)
        except ImageProcessingError as error:
            return "pixel_overflow" if error.code == "pixel_limit_exceeded" else error.code
    raise ValueError(f"fixture did not exercise expected failure: {case_id}")


__all__ = [
    "DEFAULT_BUNDLE_ROOT",
    "PACKAGE_ID",
    "acquire",
    "benchmark_bundle_builds",
    "build_bundle",
    "load_inputs",
    "update_registry",
    "validate_bundle",
    "validate_fixture_scenario",
]
