from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from museum_pipeline.hashing import sha256_file
from museum_pipeline.media.acquisition import acquire_all, discover_all
from museum_pipeline.media.bundle import build_bundle, validate_bundle
from museum_pipeline.media.constants import BUNDLE_ROOT, LEDGER_PATH, MEDIA_VAULT, artwork_vault
from museum_pipeline.media.inputs import load_media_inputs
from museum_pipeline.media.planning import create_plan
from museum_pipeline.media.review import assess_all, cross_check_all
from museum_pipeline.media.state import load_json


def plan_media() -> dict[str, Any]:
    return create_plan()


def discover_media(*, live: bool) -> dict[str, Any]:
    return discover_all(live=live)


def acquire_media(*, live: bool, download_media: bool) -> dict[str, Any]:
    return acquire_all(live=live, download_media=download_media)


def cross_check_media() -> dict[str, Any]:
    return cross_check_all()


def assess_rights() -> dict[str, Any]:
    return assess_all()


def build_derivatives_and_bundle() -> dict[str, Any]:
    return build_bundle()


def validate_media_bundle() -> dict[str, Any]:
    result = validate_bundle()
    return {**result, "summary": "M03C media bundle validation"}


def explain_artwork(artwork_id: str) -> dict[str, Any]:
    inputs = load_media_inputs()
    artwork = next((item for item in inputs.artworks if item["id"] == artwork_id), None)
    if artwork is None:
        raise ValueError("artwork ID is not in the sealed MUSEUM-03B package")
    directory = artwork_vault(artwork_id)
    names = {
        "request": "acquisition-request.json",
        "discovery": "discovery.json",
        "alternative_search": "alternative-source-search.json",
        "byte_record": "byte-record.json",
        "cross_check": "identity-rights-cross-check.json",
        "quality": "quality-assessment.json",
        "review": "automated-review.json",
        "acquisition_failure": "acquisition-failure.json",
        "discovery_failure": "discovery-failure.json",
    }
    evidence = {key: load_json(directory / name) for key, name in names.items() if (directory / name).exists()}
    return {
        "ok": True,
        "summary": "governed media decision evidence",
        "artwork_id": artwork_id,
        "evidence": evidence,
        "original_bytes_embedded": False,
    }


def report_coverage() -> dict[str, Any]:
    inputs = load_media_inputs()
    artist_by_id = inputs.artist_by_id
    counts: Counter[str] = Counter()
    per_artist: dict[str, dict[str, Any]] = {
        artist_id: {
            "artist_id": artist_id,
            "label": artist["labels"].get("en") or next(iter(artist["labels"].values())),
            "reviewed_artworks": 0,
            "approved_self_hosted": 0,
            "metadata_only": 0,
            "blocked": 0,
            "derivative_count": 0,
        }
        for artist_id, artist in artist_by_id.items()
    }
    original_downloads = original_bytes = 0
    for artwork in inputs.artworks:
        entry = per_artist[artwork["approved_artist_id"]]
        entry["reviewed_artworks"] += 1
        directory = artwork_vault(artwork["id"])
        if (directory / "byte-record.json").exists():
            byte_record = load_json(directory / "byte-record.json")
            original_downloads += 1
            original_bytes += byte_record["byte_length"]
        if not (directory / "automated-review.json").exists():
            counts["not_yet_reviewed"] += 1
            continue
        review = load_json(directory / "automated-review.json")
        decision = review["decision"]
        counts[decision] += 1
        if decision == "approved_self_hosted":
            entry["approved_self_hosted"] += 1
            entry["derivative_count"] += len(review["derivative_ids"])
        elif decision == "metadata_only_after_automated_review":
            entry["metadata_only"] += 1
        elif decision.startswith("blocked_"):
            entry["blocked"] += 1
    bundle = validate_bundle() if BUNDLE_ROOT.exists() else {"ok": False, "counts": {}, "bundle_content_hash": None}
    return {
        "ok": counts.get("not_yet_reviewed", 0) == 0,
        "summary": "M03C 44-work media coverage",
        "total_artworks": 44,
        "decision_counts": dict(sorted(counts.items())),
        "original_downloads": original_downloads,
        "original_bytes": original_bytes,
        "per_artist": sorted(per_artist.values(), key=lambda item: item["artist_id"]),
        "bundle_valid": bundle["ok"],
        "bundle_counts": bundle.get("counts", {}),
        "bundle_content_hash": bundle.get("bundle_content_hash"),
        "ledger_sha256": sha256_file(LEDGER_PATH) if LEDGER_PATH.exists() else None,
        "vault_tracked": False,
    }
