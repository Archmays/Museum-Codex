from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from museum_pipeline.hashing import sha256_file
from museum_pipeline.media.constants import (
    MAX_DECODE_PIXELS,
    PHASE_ID,
    PIPELINE_EXECUTOR,
    TARGET_WIDTHS,
    artwork_slug,
    artwork_vault,
)
from museum_pipeline.media.image_processing import compare_preview_visual_match, inspect_image_bytes, phash_distance
from museum_pipeline.media.inputs import load_media_inputs
from museum_pipeline.media.state import load_json, replace_generated, utc_now


def cross_check_all() -> dict[str, Any]:
    inputs = load_media_inputs()
    assessments = inputs.assessment_by_artwork
    generated = reused = 0
    closures: Counter[str] = Counter()
    seen_hashes: dict[str, str] = {}
    seen_phashes: list[tuple[str, str]] = []
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        directory = artwork_vault(artwork["id"])
        cross_path = directory / "identity-rights-cross-check.json"
        quality_path = directory / "quality-assessment.json"
        request = load_json(directory / "acquisition-request.json")
        assessment = assessments[artwork["id"]]
        discovery = load_json(directory / "discovery.json") if (directory / "discovery.json").exists() else None
        byte_record = load_json(directory / "byte-record.json") if (directory / "byte-record.json").exists() else None
        discovery_failed = (directory / "discovery-failure.json").exists()
        acquisition_failed = (directory / "acquisition-failure.json").exists()
        if discovery is None and not discovery_failed:
            raise ValueError(f"discovery is not terminal for {artwork['id']}")
        if discovery and discovery["media"].get("source_url") and byte_record is None and not acquisition_failed:
            raise ValueError(f"media acquisition is not terminal for {artwork['id']}")
        cross = _cross_check_record(request, assessment, discovery, byte_record)
        changed = _store_derived(cross_path, cross, "checked_at")
        generated += int(changed)
        reused += int(not changed)
        closures[cross["closure_status"]] += 1
        if byte_record:
            quality = _quality_record(directory, byte_record, seen_hashes, seen_phashes)
            _store_derived(quality_path, quality, "assessed_at")
            seen_hashes[byte_record["sha256"]] = artwork["id"]
            seen_phashes.append((artwork["id"], byte_record["phash"]))
        elif quality_path.exists():
            raise ValueError(f"quality assessment exists without byte record for {artwork['id']}")
    return {
        "ok": True,
        "summary": "44 identity, rights, byte and quality cross-checks evaluated",
        "total": len(inputs.artworks),
        "generated": generated,
        "reused": reused,
        "closure_counts": dict(sorted(closures.items())),
    }


def assess_all() -> dict[str, Any]:
    inputs = load_media_inputs()
    generated = reused = 0
    counts: Counter[str] = Counter()
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        directory = artwork_vault(artwork["id"])
        output = directory / "automated-review.json"
        request = load_json(directory / "acquisition-request.json")
        cross = load_json(directory / "identity-rights-cross-check.json")
        byte_record = load_json(directory / "byte-record.json") if (directory / "byte-record.json").exists() else None
        quality = load_json(directory / "quality-assessment.json") if (directory / "quality-assessment.json").exists() else None
        alternative = load_json(directory / "alternative-source-search.json") if (directory / "alternative-source-search.json").exists() else None
        failure = None
        if byte_record is None:
            for name in ("acquisition-failure.json", "discovery-failure.json"):
                if (directory / name).exists():
                    failure = load_json(directory / name)
                    break
        decision, reasons, mandatory = _final_decision(cross, byte_record, quality, alternative, failure)
        derivative_ids = _predicted_derivative_ids(artwork["id"], byte_record) if decision == "approved_self_hosted" else []
        review = {
            "schema_version": "1.0.0",
            "id": f"media-review:{artwork_slug(artwork['id'])}",
            "entity_type": "media_automated_review",
            "branch_id": "art",
            "phase_id": PHASE_ID,
            "executor": PIPELINE_EXECUTOR,
            "human_review_dependency": False,
            "artwork_id": artwork["id"],
            "cross_check_id": cross["id"],
            "byte_record_id": byte_record["id"] if byte_record else None,
            "quality_assessment_id": quality["id"] if quality else None,
            "alternative_source_search_id": alternative["id"] if alternative else None,
            "mandatory_closure": mandatory,
            "decision": decision,
            "decision_reason_codes": reasons,
            "derivative_ids": derivative_ids,
            "decided_at": utc_now(),
            "data_version": "1.0.0",
        }
        changed = _store_derived(output, review, "decided_at")
        counts[decision] += 1
        generated += int(changed)
        reused += int(not changed)
    return {
        "ok": True,
        "summary": "44 terminal automated media decisions recorded",
        "total": len(inputs.artworks),
        "generated": generated,
        "reused": reused,
        "counts": dict(sorted(counts.items())),
        "human_review_dependency": False,
    }


def _cross_check_record(
    request: dict[str, Any],
    assessment: dict[str, Any],
    discovery: dict[str, Any] | None,
    byte_record: dict[str, Any] | None,
) -> dict[str, Any]:
    expected = request["expected_identity"]
    if discovery:
        observed = discovery["observed_identity"]
        matches = discovery["identity_matches"]
        live_rights = discovery["rights"]
        snapshot_hash = discovery["metadata_response_sha256"]
    else:
        observed = {
            "official_object_id": expected["official_object_id"],
            "accession": expected["accession"],
            "artist": expected["artist"],
            "title": expected["title"],
            "date": expected["date"],
            "institution": expected["institution"],
            "object_url": expected["object_url"],
            "source_identity": request["source_id"],
        }
        matches = {key: False for key in (
            "official_object_id_match", "accession_match", "artist_match", "title_match",
            "date_match", "institution_match", "object_url_match", "source_identity_match",
        )}
        live_rights = {"media_id": None, "object_open": False, "conflict": False}
        snapshot_hash = expected["source_snapshot_hash"]
    license_record = assessment.get("media_license") or {
        "identifier": "UNKNOWN",
        "version": None,
        "url": None,
        "attribution_required": False,
        "share_alike": False,
        "redistribution_allowed": False,
        "modification_allowed": False,
        "commercial_use_allowed": False,
    }
    permissions = assessment["permissions"]
    status = _rights_object_status(assessment, live_rights)
    rights_pass = bool(
        live_rights.get("object_open")
        and not live_rights.get("conflict")
        and license_record["redistribution_allowed"]
        and license_record["modification_allowed"]
        and license_record["commercial_use_allowed"]
        and assessment["withdrawal_or_revocation"]["status"] == "active"
    )
    identity_pass = bool(discovery and discovery["identity_closure"])
    closure = "source_unavailable" if discovery is None else "identity_conflict" if not identity_pass else "pass" if rights_pass else "rights_conflict"
    return {
        "schema_version": "1.0.0",
        "id": f"media-cross-check:{artwork_slug(request['artwork_id'])}",
        "entity_type": "media_identity_rights_cross_check",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "artwork_id": request["artwork_id"],
        "source_id": request["source_id"],
        "byte_record_id": byte_record["id"] if byte_record else None,
        "identity": {
            "official_object_id": str(observed["official_object_id"]),
            "accession": observed.get("accession"),
            "artist": str(observed["artist"]),
            "title": str(observed["title"]),
            "date": str(observed.get("date") or expected["date"]),
            "institution": str(observed["institution"]),
            "object_url": str(observed["object_url"]),
            "media_id": live_rights.get("media_id"),
            "source_identity": str(observed["source_identity"]),
            "snapshot_hash": snapshot_hash,
            "object_id_match": bool(matches["official_object_id_match"]),
            "accession_match": bool(matches["accession_match"]),
            "artist_match": bool(matches["artist_match"]),
            "title_match": bool(matches["title_match"]),
            "date_match": bool(matches["date_match"]),
            "institution_match": bool(matches["institution_match"]),
            "media_id_match": bool(live_rights.get("media_id") or not live_rights.get("object_open")),
            "source_identity_match": bool(matches["source_identity_match"]),
        },
        "rights": {
            "object_status": status,
            "license": license_record,
            "rights_url": assessment["rights_statement_url"],
            "source_rule_id": assessment["source_license_bindings"][0]["rule_id"],
            "redistribution": permissions["redistribution"],
            "derivatives": permissions["modification"],
            "commercial_use": permissions["commercial_use"],
            "attribution": assessment.get("attribution") or "No attribution supplied by the official object record.",
            "share_alike": permissions["share_alike"],
            "platforms": ["all_platforms"] if rights_pass else ["not_approved"],
            "purposes": ["all_purposes"] if rights_pass else ["not_approved"],
            "territories": ["worldwide"] if rights_pass else ["not_approved"],
            "revoked_at": assessment["withdrawal_or_revocation"].get("effective_at"),
            "expires_at": assessment.get("permission_expires_at"),
            "verified_at": assessment["verified_at"].split("T", 1)[0],
            "reverify_by": assessment["reverify_by"],
            "evidence_hash": snapshot_hash,
        },
        "closure_status": closure,
        "checked_at": utc_now(),
        "data_version": "1.0.0",
    }


def _rights_object_status(assessment: dict[str, Any], live_rights: dict[str, Any]) -> str:
    if live_rights.get("conflict"):
        return "restricted"
    value = assessment.get("media_rights_status")
    if value in {"public_domain", "cc0", "cc_by", "cc_by_sa", "licensed", "restricted", "unknown", "revoked", "expired"}:
        return value
    return "unknown"


def _quality_record(
    directory: Path,
    byte_record: dict[str, Any],
    seen_hashes: dict[str, str],
    seen_phashes: list[tuple[str, str]],
) -> dict[str, Any]:
    source_path = directory / "original.jpg"
    source_bytes = source_path.read_bytes()
    if len(source_bytes) != byte_record["byte_length"] or sha256_file(source_path) != byte_record["sha256"]:
        raise ValueError(f"quality source bytes no longer match {byte_record['id']}")
    details = inspect_image_bytes(source_bytes, byte_record["magic_mime"], max_pixels=MAX_DECODE_PIXELS)
    if details["phash"]["value"].replace("phash64:", "phash:") != byte_record["phash"]:
        raise ValueError(f"quality source pHash no longer matches {byte_record['id']}")
    flags = details["quality"]["flags"]
    preview_path = directory / "official-preview.jpg"
    preview = None
    if preview_path.is_file() and not preview_path.is_symlink():
        preview = compare_preview_visual_match(
            source_bytes,
            byte_record["magic_mime"],
            preview_path.read_bytes(),
            "image/jpeg",
            max_pixels=MAX_DECODE_PIXELS,
        )
    exact_duplicate = byte_record["sha256"] in seen_hashes
    distances = [
        phash_distance(
            byte_record["phash"].replace("phash:", "phash64:"),
            other.replace("phash:", "phash64:"),
        )
        for _, other in seen_phashes
    ]
    nearest = min(distances) if distances else None
    hard_failures: list[str] = []
    if flags["blank"] or flags["placeholder_suspected"] or flags["tracking_pixel"]:
        hard_failures.append("invalid_visual_payload")
    if exact_duplicate:
        hard_failures.append("exact_duplicate_other_artwork")
    if preview is not None and not preview["matched"]:
        hard_failures.append("official_preview_mismatch")
    if preview is not None and preview["watermark_overlay_suspected"]:
        hard_failures.append("watermark_overlay_suspected")
    if preview is not None and preview["site_chrome_suspected"]:
        hard_failures.append("site_chrome_suspected")
    low_resolution = flags["low_resolution"]
    quality_status = "fail" if hard_failures else "low_resolution" if low_resolution else "pass"
    check = lambda passed: "pass" if passed else "fail"  # noqa: E731
    return {
        "schema_version": "1.0.0",
        "id": f"media-quality:{artwork_slug(byte_record['artwork_id'])}",
        "entity_type": "media_quality_assessment",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "artwork_id": byte_record["artwork_id"],
        "byte_record_id": byte_record["id"],
        "checks": {
            "decode": "pass",
            "mime_match": "pass",
            "aspect_ratio": "not_applicable" if preview is None else check(preview["aspect_ratio_delta"] <= preview["max_aspect_ratio_delta"]),
            "blur": check(not (flags["blurred"] and details["quality"]["entropy_bits"] < 2.0)),
            "entropy": check(details["quality"]["entropy_bits"] >= 1.0),
            "blank_or_monochrome": check(not flags["blank"] and (not flags["monochrome"] or bool(preview and preview["matched"]))),
            "corrupt_scanlines": check(details["decode"]["ok"]),
            "placeholder": check(not flags["placeholder_suspected"]),
            "watermark": "not_applicable" if preview is None else check(not preview["watermark_overlay_suspected"]),
            "site_chrome": "not_applicable" if preview is None else check(not preview["site_chrome_suspected"]),
            "borders": check(not flags["border_suspected"] or bool(preview and preview["border_geometry_matches"])),
            "orientation": check(details["orientation"]["read_error"] is None),
            "duplicate": check(not exact_duplicate),
            "wrong_crop": "not_applicable" if preview is None else check(preview["matched"]),
            "decompression_bomb": check(details["pixels"] <= MAX_DECODE_PIXELS),
        },
        "metrics": {
            "width": byte_record["width"],
            "height": byte_record["height"],
            "pixels": byte_record["pixels"],
            "aspect_ratio": round(byte_record["width"] / byte_record["height"], 6),
            "blur_score": details["quality"]["blur_laplacian_variance"],
            "entropy": details["quality"]["entropy_bits"],
            "phash": byte_record["phash"],
            "near_duplicate_distance": nearest,
        },
        "observations": {
            "preview_available": preview is not None,
            "preview_phash_distance": preview["phash_distance"] if preview is not None else None,
            "monochrome": flags["monochrome"],
            "border_suspected": flags["border_suspected"],
            "border_edges": flags["border_edges"],
            "border_interpretation": (
                "none"
                if not flags["border_suspected"]
                else "official_preview_matched_artwork_margin"
                if preview is not None and preview["border_geometry_matches"]
                else "unexpected_border_geometry"
            ),
            "watermark_overlay_suspected": bool(preview and preview["watermark_overlay_suspected"]),
            "site_chrome_suspected": bool(preview and preview["site_chrome_suspected"]),
            "corrupt_scanlines_suspected": not details["decode"]["ok"],
        },
        "quality_status": quality_status,
        "failure_codes": hard_failures,
        "assessed_at": utc_now(),
        "data_version": "1.0.0",
    }


def _store_derived(path: Path, value: dict[str, Any], timestamp_field: str) -> bool:
    """Replace a reproducible decision only when its upstream evidence changed."""

    if path.exists():
        existing = load_json(path)
        candidate = dict(value)
        candidate[timestamp_field] = existing.get(timestamp_field, candidate[timestamp_field])
        if candidate == existing:
            return False
        value[timestamp_field] = utc_now()
    replace_generated(path, value)
    return True


def _final_decision(
    cross: dict[str, Any],
    byte_record: dict[str, Any] | None,
    quality: dict[str, Any] | None,
    alternative: dict[str, Any] | None,
    failure: dict[str, Any] | None,
) -> tuple[str, list[str], dict[str, str]]:
    identity_pass = all(
        cross["identity"][field]
        for field in (
            "object_id_match", "accession_match", "artist_match", "title_match", "date_match",
            "institution_match", "media_id_match", "source_identity_match",
        )
    )
    rights_pass = cross["closure_status"] == "pass"
    bytes_pass = byte_record is not None
    quality_pass = quality is not None and quality["quality_status"] in {"pass", "low_resolution"}
    mandatory = {
        "identity": "pass" if identity_pass else "fail",
        "rights": "pass" if rights_pass else "fail",
        "bytes": "pass" if bytes_pass else "not_applicable" if alternative else "fail",
        "quality": "pass" if quality_pass else "not_applicable" if not byte_record else "fail",
    }
    if cross["closure_status"] == "source_unavailable":
        return "blocked_source_unavailable", ["official_source_unavailable"], mandatory
    if not identity_pass:
        return "blocked_identity_conflict", ["mandatory_identity_mismatch"], mandatory
    if cross["rights"]["object_status"] == "restricted":
        return "blocked_rights_conflict", ["object_level_rights_conflict"], mandatory
    if alternative and not bytes_pass:
        return "metadata_only_after_automated_review", ["no_approved_media_after_alternative_search"], mandatory
    if failure:
        quality_codes = {"placeholder_detected", "decode_failed", "decompression_bomb", "pixel_limit_exceeded", "mime_magic_mismatch"}
        if failure["error_code"] in quality_codes:
            return "blocked_quality_failure", [failure["error_code"]], mandatory
        return "blocked_source_unavailable", [failure["error_code"]], mandatory
    if not bytes_pass:
        return "blocked_source_unavailable", ["approved_locator_bytes_missing"], mandatory
    if not quality_pass:
        return "blocked_quality_failure", quality["failure_codes"] or ["quality_closure_failed"], mandatory
    if not rights_pass:
        return "blocked_rights_conflict", ["rights_closure_failed"], mandatory
    reasons = ["identity_rights_bytes_quality_closed"]
    if quality["quality_status"] == "low_resolution":
        reasons.append("low_resolution_disclosed")
    return "approved_self_hosted", reasons, mandatory


def _predicted_derivative_ids(artwork_id: str, byte_record: dict[str, Any] | None) -> list[str]:
    if not byte_record:
        return []
    slug = artwork_slug(artwork_id)
    return [
        f"media-derivative:{slug}-{width}w-{format_name}"
        for width in TARGET_WIDTHS
        if width <= byte_record["width"]
        for format_name in ("jpeg", "webp")
    ]
