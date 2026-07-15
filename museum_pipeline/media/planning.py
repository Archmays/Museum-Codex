from __future__ import annotations

from typing import Any

from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.media.constants import (
    MAX_MEDIA_BYTES,
    MEDIA_VAULT,
    PHASE_ID,
    PIPELINE_EXECUTOR,
    SOURCE_POLICIES,
    artwork_slug,
    artwork_vault,
)
from museum_pipeline.media.inputs import MediaInputs, load_media_inputs
from museum_pipeline.media.state import replace_generated, utc_now, write_once


def build_plan_record(
    artwork: dict[str, Any],
    assessment: dict[str, Any],
    artist: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    artwork_id = artwork["id"]
    official = artwork["official_object_record"]
    source_id = official["source_id"]
    policy = SOURCE_POLICIES[source_id]
    candidate_url = None
    if assessment["outcome"] == "external_iiif_candidate":
        base = assessment["technical_delivery"].get("official_iiif_url")
        candidate_url = f"{base}/full/full/0/default.jpg" if base else None
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": f"media-request:{artwork_slug(artwork_id)}",
        "entity_type": "media_acquisition_request",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "data_version": "1.0.0",
        "artwork_id": artwork_id,
        "source_id": source_id,
        "source_object_id": str(official["source_object_id"]),
        "canonical_object_url": official["official_object_url"],
        "candidate_media_url": candidate_url,
        "network_mode": "live",
        "download_media": True,
        "concurrency": 1,
        "timeout_seconds": 90,
        "max_bytes": MAX_MEDIA_BYTES,
        "max_redirects": 3,
        "trusted_https_hosts": sorted({policy["metadata_host"], *policy["media_hosts"]}),
        "conditional_request": {"etag": None, "last_modified": None},
        "arbitrary_url_allowed": False,
        "cookies_allowed": False,
        "created_at": created_at,
        "request_hash": "",
        "expected_identity": {
            "official_object_id": str(official["source_object_id"]),
            "accession": artwork.get("accession_number"),
            "artist": artist["labels"].get("en") or next(iter(artist["labels"].values())),
            "title": artwork["labels"].get("en") or next(iter(artwork["labels"].values())),
            "date": artwork.get("creation_span", {}).get("description"),
            "institution": policy["institution"],
            "object_url": official["official_object_url"],
            "source_snapshot_id": official["raw_snapshot_id"],
            "source_snapshot_hash": official["raw_snapshot_hash"],
        },
        "baseline_media_assessment": {
            "assessment_id": assessment["id"],
            "outcome": assessment["outcome"],
            "media_rights_status": assessment["media_rights_status"],
            "source_rule_id": assessment["source_license_bindings"][0]["rule_id"],
            "rights_statement_url": assessment["rights_statement_url"],
            "verified_at": assessment["verified_at"],
            "reverify_by": assessment["reverify_by"] + "T00:00:00Z",
        },
    }
    payload["request_hash"] = canonical_sha256({key: value for key, value in payload.items() if key != "request_hash"})
    return payload


def create_plan(inputs: MediaInputs | None = None) -> dict[str, Any]:
    inputs = inputs or load_media_inputs()
    MEDIA_VAULT.mkdir(parents=True, exist_ok=True)
    existing_plan = MEDIA_VAULT / "plan.json"
    created_at = utc_now()
    if existing_plan.exists():
        import json

        prior = json.loads(existing_plan.read_text(encoding="utf-8"))
        created_at = prior["created_at"]
    artists = inputs.artist_by_id
    assessments = inputs.assessment_by_artwork
    request_ids: list[str] = []
    created = 0
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        record = build_plan_record(artwork, assessments[artwork["id"]], artists[artwork["approved_artist_id"]], created_at=created_at)
        directory = artwork_vault(artwork["id"])
        directory.mkdir(parents=True, exist_ok=True)
        created += int(write_once(directory / "acquisition-request.json", record))
        request_ids.append(record["id"])
    plan = {
        "phase_id": PHASE_ID,
        "network_default": "offline",
        "live_acquisition_requires": ["--live", "--download-media"],
        "concurrency": 1,
        "m03b_package_hash": inputs.manifest["content_hash"],
        "m03b_graph_hash": inputs.graph["content_hash"],
        "artwork_count": len(inputs.artworks),
        "request_ids": request_ids,
        "created_at": created_at,
    }
    replace_generated(existing_plan, plan)
    return {"ok": True, "summary": "44 governed media acquisition requests planned", "created": created, **plan}
