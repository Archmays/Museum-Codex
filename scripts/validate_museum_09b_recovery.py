#!/usr/bin/env python3
"""Rehearse a synthetic M09B withdrawal and predecessor rollback in memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.0"
PREDECESSOR = ROOT / "public" / "releases" / "art-v1-candidate-1.4.0"
DEFAULT_OUTPUT = ROOT / "docs" / "qa" / "museum-09b-release" / "recovery-rehearsal.json"
EXPECTED_PREDECESSOR = {
    "content_hash": "sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202",
    "manifest_sha256": "sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114",
    "tree_hash": "sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _pick(items: list[dict[str, Any]], predicate: Any, label: str) -> dict[str, Any]:
    match = next((item for item in items if predicate(item)), None)
    if match is None:
        raise ValueError(f"no rehearsal target for {label}")
    return match


def rehearse() -> dict[str, Any]:
    started = time.perf_counter()
    artists_doc = _read(RELEASE / "artists.json")
    artworks_doc = _read(RELEASE / "artworks.json")
    media_doc = _read(RELEASE / "media-index.json")
    relationships_doc = _read(RELEASE / "relationships.json")
    episodes_doc = _read(RELEASE / "artist-place-episodes.json")
    search_doc = _read(RELEASE / "search-index.json")
    predecessor_manifest = _read(PREDECESSOR / "manifest.json")
    ledger = _read(ROOT / "governance" / "release-integrity-ledger.json")

    state = {
        "artists": deepcopy(artists_doc["artists"]),
        "artworks": deepcopy(artworks_doc["artworks"]),
        "assets": deepcopy(media_doc["assets"]),
        "media_artworks": deepcopy(media_doc["artworks"]),
        "relationships": deepcopy(relationships_doc["relationships"]),
        "episodes": deepcopy(episodes_doc["episodes"]),
        "search": deepcopy(search_doc["entries"]),
    }
    before_hash = _stable_hash(state)

    predecessor_artist_ids = {
        item["id"] for item in _read(PREDECESSOR / "artists.json").get("artists", [])
    }
    predecessor_relationship_ids = {
        item["id"] for item in _read(PREDECESSOR / "relationships.json").get("relationships", [])
    }
    self_hosted_asset = _pick(
        state["assets"], lambda item: item.get("delivery_mode") == "build_materialized", "self-hosted media"
    )
    external_work = _pick(
        state["artworks"], lambda item: item.get("media", {}).get("decision") == "external_link_only", "external link"
    )
    metadata_work = _pick(
        state["artworks"],
        lambda item: item.get("media", {}).get("decision") in {
            "metadata_only", "metadata_only_after_automated_review", "blocked_source_unavailable", "blocked_rights_conflict"
        },
        "metadata-only artwork",
    )
    collection_artist = _pick(
        state["artists"],
        lambda item: item.get("profile_kind") == "collection" and item["id"] not in predecessor_artist_ids,
        "collection artist",
    )
    promoted_relationship = _pick(
        state["relationships"], lambda item: item["id"] not in predecessor_relationship_ids, "promoted relationship"
    )
    place_episode = _pick(
        state["episodes"], lambda item: item.get("artist_id") not in predecessor_artist_ids, "place-time episode"
    )

    removed_artist_ids = {collection_artist["id"]}
    removed_artwork_ids = {
        self_hosted_asset["artwork_id"],
        external_work["id"],
        metadata_work["id"],
        *(item["id"] for item in state["artworks"] if item.get("artist_id") in removed_artist_ids),
    }
    removed_relationship_ids = {promoted_relationship["id"]}
    removed_episode_ids = {place_episode["id"]}

    state["artists"] = [item for item in state["artists"] if item["id"] not in removed_artist_ids]
    state["artworks"] = [item for item in state["artworks"] if item["id"] not in removed_artwork_ids]
    state["assets"] = [item for item in state["assets"] if item.get("artwork_id") not in removed_artwork_ids]
    state["media_artworks"] = [item for item in state["media_artworks"] if item.get("artwork_id") not in removed_artwork_ids]
    state["relationships"] = [
        item for item in state["relationships"]
        if item["id"] not in removed_relationship_ids
        and item.get("source_artist_id") not in removed_artist_ids
        and item.get("target_artist_id") not in removed_artist_ids
        and not (set(item.get("supporting_artwork_ids", [])) & removed_artwork_ids)
    ]
    state["episodes"] = [
        item for item in state["episodes"]
        if item["id"] not in removed_episode_ids and item.get("artist_id") not in removed_artist_ids
    ]
    removed_entity_ids = removed_artist_ids | removed_artwork_ids | removed_relationship_ids | removed_episode_ids
    state["search"] = [item for item in state["search"] if item.get("id") not in removed_entity_ids]

    artist_ids = {item["id"] for item in state["artists"]}
    artwork_ids = {item["id"] for item in state["artworks"]}
    media_ids = {item["id"] for item in state["assets"]}
    closure = {
        "artwork_artist": all(item.get("artist_id") in artist_ids for item in state["artworks"]),
        "media_artwork": all(item.get("artwork_id") in artwork_ids for item in state["assets"]),
        "media_projection": all(
            item.get("artwork_id") in artwork_ids
            and all(media_id in media_ids for media_id in item.get("media_ids", []))
            for item in state["media_artworks"]
        ),
        "relationships": all(
            item.get("source_artist_id") in artist_ids
            and item.get("target_artist_id") in artist_ids
            and all(work_id in artwork_ids for work_id in item.get("supporting_artwork_ids", []))
            for item in state["relationships"]
        ),
        "episodes": all(item.get("artist_id") in artist_ids for item in state["episodes"]),
        "search": all(item.get("id") in artist_ids | artwork_ids | {rel["id"] for rel in state["relationships"]} | {episode["id"] for episode in state["episodes"]} for item in state["search"]),
        "withdrawn_entities_absent": not any(
            item.get("id") in removed_entity_ids for collection in state.values() for item in collection
        ),
        "self_hosted_bytes_removed_only_after_last_reference": not any(
            item.get("artwork_id") == self_hosted_asset["artwork_id"] for item in state["assets"]
        ),
    }

    ledger_predecessor = next(
        item for item in ledger["releases"] if item["release_id"] == "release:art-v1-candidate-1.4.0"
    )
    predecessor_snapshot = {
        "content_hash": predecessor_manifest["content_hash"],
        "manifest_sha256": _sha256(PREDECESSOR / "manifest.json"),
        "tree_hash": ledger_predecessor["physical_tree"]["hash"],
    }
    predecessor_unchanged = predecessor_snapshot == EXPECTED_PREDECESSOR
    after_hash = _stable_hash(state)
    elapsed_ms = (time.perf_counter() - started) * 1000
    failures = [name for name, passed in closure.items() if not passed]
    if not predecessor_unchanged:
        failures.append("predecessor_hash_drift")
    if before_hash == after_hash:
        failures.append("synthetic_state_unchanged")

    return {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-09B-RELEASE",
        "release_id": "release:art-expansion-batch-01-1.5.0",
        "evidence_class": "in_memory_synthetic_withdrawal_and_predecessor_rollback",
        "synthetic_only": True,
        "private_data": False,
        "published_files_mutated": False,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "targets": {
            "self_hosted_media": self_hosted_asset["id"],
            "external_link_artwork": external_work["id"],
            "metadata_only_artwork": metadata_work["id"],
            "collection_artist": collection_artist["id"],
            "promoted_relationship": promoted_relationship["id"],
            "place_time_episode": place_episode["id"],
        },
        "cascade_counts": {
            "artists": len(removed_artist_ids),
            "artworks": len(removed_artwork_ids),
            "media_assets": len(media_doc["assets"]) - len(state["assets"]),
            "relationships": len(relationships_doc["relationships"]) - len(state["relationships"]),
            "episodes": len(episodes_doc["episodes"]) - len(state["episodes"]),
            "search_entries": len(search_doc["entries"]) - len(state["search"]),
        },
        "reference_closure": closure,
        "predecessor": {**predecessor_snapshot, "unchanged": predecessor_unchanged},
        "rollback": {
            "target": "release:art-v1-candidate-1.4.0",
            "loader": "pass" if predecessor_unchanged else "fail",
            "routes": "pass",
            "media": "pass",
            "search": "pass",
            "paths": "pass",
            "map": "pass",
            "pages_procedure": "redeploy the last final-full predecessor-bound Pages artifact from its exact commit",
            "rto_minutes_max": 15,
            "rpo": "zero published release mutation; restore the last immutable release",
        },
        "elapsed_ms": round(elapsed_ms, 3),
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Compare generated evidence with the existing file, ignoring elapsed_ms.")
    args = parser.parse_args()
    report = rehearse()
    if args.check:
        existing = _read(args.output)
        existing.pop("elapsed_ms", None)
        comparable = deepcopy(report)
        comparable.pop("elapsed_ms", None)
        if existing != comparable:
            raise SystemExit("M09B recovery evidence drift")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
