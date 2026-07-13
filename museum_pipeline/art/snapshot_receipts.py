from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from museum_pipeline.config import ROOT
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file


DEFAULT_IDENTITY_SEED = ROOT / "research" / "art" / "museum-03b-identity-decisions.json"
DEFAULT_LEDGER = ROOT / "research" / "art" / "museum-03b-snapshot-receipts.json"
CURATION_RAW = ROOT / "data" / "raw" / "curation_museum03a" / "20260713-survey-final"
BUNDLE_REF = {
    "bundle_id": "selection-review-bundle:3843c34b-7a65-5581-baec-1385d53326c5",
    "bundle_hash": "sha256:ba7640dbfe554c938fc9bf65ac5fa1eb42514ced015e0b4e56598870428072c7",
    "source_snapshots_sha256": "sha256:e8d1bcc06c6fe00e5660d7966aea08e385b0ff50d788e1b13cfc5f5cebcff38d",
}


def build_identity_snapshot_receipt_ledger(
    *,
    seed_path: Path = DEFAULT_IDENTITY_SEED,
    output_path: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    manifests = _pipeline_manifests()
    entries: dict[str, dict[str, Any]] = {}
    for artist in seed.get("artists", []):
        ulan = str(artist["external_ids"]["ulan"])
        getty_snapshot = artist["getty_snapshot"]
        receipt = _pipeline_receipt(getty_snapshot["snapshot_id"], [ulan], manifests)
        _add(entries, receipt)

        collection = artist["collection_record"]
        receipt = _legacy_receipt(
            source_id=collection["source_id"],
            object_id=str(collection["object_id"]),
            expected_sha256=collection["body_sha256"],
        )
        _add(entries, receipt)

        resolution = artist.get("external_id_resolution")
        if resolution:
            for prefix in ("accepted", "quarantined"):
                receipt = _pipeline_receipt(
                    resolution[f"{prefix}_snapshot_id"],
                    [str(resolution[f"{prefix}_wikidata"])],
                    manifests,
                )
                _add(entries, receipt)
        elif qid := artist.get("external_ids", {}).get("wikidata"):
            receipt = _legacy_receipt(source_id="wikidata", object_id=str(qid))
            _add(entries, receipt)

    ledger = {
        "schema_version": "1.0.0",
        "id": "snapshot-receipt-ledger:museum-03b-first-slate-v1",
        "entity_type": "snapshot_receipt_ledger",
        "batch_id": seed["batch_id"],
        "verified_at": "2026-07-13T13:35:00+08:00",
        "entries": sorted(entries.values(), key=lambda item: (item["source_id"], item["source_object_ids"], item["snapshot_id"])),
    }
    ledger["content_hash"] = canonical_sha256(ledger)
    serialized = json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output_path.exists() and output_path.read_text(encoding="utf-8") != serialized:
        raise PipelineError("snapshot_receipt_ledger_conflict", f"Refusing to overwrite different ledger: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not output_path.exists():
        output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return ledger


def _pipeline_manifests() -> dict[str, tuple[dict[str, Any], Path]]:
    result: dict[str, tuple[dict[str, Any], Path]] = {}
    for source_id in ("getty_ulan", "wikidata"):
        for path in (ROOT / "data" / "raw" / source_id).rglob("manifest.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            snapshot_id = manifest.get("snapshot_id")
            if isinstance(snapshot_id, str):
                result[snapshot_id] = (manifest, path)
    return result


def _pipeline_receipt(
    snapshot_id: str,
    source_object_ids: list[str],
    manifests: dict[str, tuple[dict[str, Any], Path]],
) -> dict[str, Any]:
    try:
        manifest, manifest_path = manifests[snapshot_id]
    except KeyError as error:
        raise PipelineError("snapshot_manifest_missing", f"No raw manifest for {snapshot_id}") from error
    body_manifest = manifest
    body_manifest_path = manifest_path
    reused = manifest.get("reused_body_snapshot_id")
    while reused:
        try:
            body_manifest, body_manifest_path = manifests[reused]
        except KeyError as error:
            raise PipelineError("snapshot_reuse_missing", f"No reused raw manifest for {reused}") from error
        reused = body_manifest.get("reused_body_snapshot_id")
    response_path = body_manifest.get("response_body_path")
    if not isinstance(response_path, str):
        raise PipelineError("snapshot_body_path_missing", f"No body path for {snapshot_id}")
    body_path = (body_manifest_path.parent / response_path).resolve()
    return _receipt(
        snapshot_id=snapshot_id,
        snapshot_id_basis="pipeline_manifest",
        source_id=str(manifest["source_id"]),
        source_object_ids=source_object_ids,
        body_sha256=str(manifest["body_sha256"]),
        declared_bytes=int(manifest["body_bytes"]),
        content_type=str(manifest["content_type"]),
        raw_receipt_path=manifest_path,
        raw_body_path=body_path,
        reused_body_snapshot_id=manifest.get("reused_body_snapshot_id"),
        bundle_ref=None,
    )


def _legacy_receipt(
    *,
    source_id: str,
    object_id: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    candidates = []
    paths = (
        (CURATION_RAW / source_id).glob("*-entity-1.metadata.json")
        if source_id == "wikidata"
        else (CURATION_RAW / source_id).glob(f"*-{object_id}.metadata.json")
    )
    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if source_id == "wikidata" and not str(metadata.get("final_url", "")).endswith(f"/{object_id}.json"):
            continue
        if expected_sha256 is None or metadata.get("sha256") == expected_sha256:
            candidates.append((path, metadata))
    if not candidates:
        raise PipelineError("legacy_snapshot_receipt_missing", f"No curation receipt for {source_id}:{object_id}")
    receipt_path, metadata = sorted(candidates, key=lambda item: item[0].name)[0]
    body_path = receipt_path.with_name(receipt_path.name.replace(".metadata.json", ".body"))
    body_sha256 = str(metadata["sha256"])
    snapshot_id = f"snapshot:curation_museum03a:{source_id}:{object_id.lower()}:{body_sha256[7:19]}"
    return _receipt(
        snapshot_id=snapshot_id,
        snapshot_id_basis="legacy_receipt_derived",
        source_id=source_id,
        source_object_ids=[object_id],
        body_sha256=body_sha256,
        declared_bytes=int(metadata["bytes"]),
        content_type=str(metadata["content_type"]),
        raw_receipt_path=receipt_path,
        raw_body_path=body_path,
        reused_body_snapshot_id=None,
        bundle_ref=BUNDLE_REF,
    )


def _receipt(
    *,
    snapshot_id: str,
    snapshot_id_basis: str,
    source_id: str,
    source_object_ids: list[str],
    body_sha256: str,
    declared_bytes: int,
    content_type: str,
    raw_receipt_path: Path,
    raw_body_path: Path,
    reused_body_snapshot_id: str | None,
    bundle_ref: dict[str, str] | None,
) -> dict[str, Any]:
    if not raw_body_path.is_file():
        raise PipelineError("snapshot_body_missing", f"Raw body is absent: {raw_body_path}")
    observed_hash = sha256_file(raw_body_path)
    observed_bytes = raw_body_path.stat().st_size
    if observed_hash != body_sha256 or observed_bytes != declared_bytes:
        raise PipelineError("snapshot_body_verification_failed", f"Raw body mismatch: {raw_body_path}")
    slug = re.sub(r"[^a-z0-9._-]+", "-", f"{source_id}-{source_object_ids[0]}-{body_sha256[7:19]}".lower()).strip("-")
    return {
        "receipt_id": f"snapshot-receipt:{slug}",
        "snapshot_id": snapshot_id,
        "snapshot_id_basis": snapshot_id_basis,
        "source_id": source_id,
        "source_object_ids": source_object_ids,
        "body_sha256": body_sha256,
        "body_bytes": declared_bytes,
        "content_type": content_type,
        "raw_receipt_path": raw_receipt_path.relative_to(ROOT).as_posix(),
        "raw_body_path": raw_body_path.relative_to(ROOT).as_posix(),
        "reused_body_snapshot_id": reused_body_snapshot_id,
        "bundle_ref": bundle_ref,
        "verification": {"body_present": True, "hash_match": True, "byte_count_match": True},
    }


def _add(entries: dict[str, dict[str, Any]], receipt: dict[str, Any]) -> None:
    snapshot_id = receipt["snapshot_id"]
    existing = entries.get(snapshot_id)
    if existing is not None and existing != receipt:
        raise PipelineError("snapshot_receipt_duplicate_conflict", f"Conflicting receipt for {snapshot_id}")
    entries[snapshot_id] = receipt
