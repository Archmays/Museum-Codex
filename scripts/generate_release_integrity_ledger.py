#!/usr/bin/env python3
"""Canonical writer for the release-integrity ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file

DEFAULT_OUTPUT = ROOT / "governance" / "release-integrity-ledger.json"
GENERATED_AT = "2026-07-22T12:00:00+08:00"
TREE_ALGORITHM = "sha256(path\\0size\\0file_sha256\\n)"
CLOSURE_PATH_ALGORITHM = "sha256(normalized_lf_text_or_raw_binary)"
TEXT_SUFFIXES = frozenset({
    ".body",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
})

RELEASE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "phase_id": "MUSEUM-04",
        "release_id": "release:art-constellation-1.0.0",
        "directory": "public/releases/art-constellation-1.0.0",
        "builder_paths": ["scripts/build_museum_04_release.py", "museum_pipeline/art/public_release.py"],
        "validator_paths": ["scripts/validate_museum_04_release.py", "museum_pipeline/art/public_release.py"],
        "input_paths": [
            "data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1/manifest.json",
            "data/reviewed/art/museum-03c/media-bundle-v1/manifest.json",
            "data/reviewed/art/museum-03c/media-source-ledger.json",
            "research/source-registry/minimum-source-set.json",
        ],
        "route_consumers": ["#/art/constellation", "#/art/artists", "#/art/artworks/:id", "#/art/compare"],
    },
    {
        "phase_id": "MUSEUM-05B",
        "release_id": "release:art-gallery-interactions-1.1.0",
        "directory": "public/releases/art-gallery-interactions-1.1.0",
        "builder_paths": ["scripts/build_museum_05b_release.py", "museum_pipeline/art/interactions.py"],
        "validator_paths": ["scripts/validate_museum_05b_release.py", "museum_pipeline/art/interactions.py"],
        "input_paths": [
            "public/releases/art-constellation-1.0.0/manifest.json",
            "data/reviewed/art/museum-05b/media-retry-v1.json",
        ],
        "route_consumers": ["#/art/artists", "#/art/artists/:id", "#/art/artworks/:id", "#/art/compare", "#/art/tours", "#/art/tours/:id"],
    },
    {
        "phase_id": "MUSEUM-06",
        "release_id": "release:art-pathways-1.2.0",
        "directory": "public/releases/art-pathways-1.2.0",
        "builder_paths": ["scripts/build_museum_06_release.py", "museum_pipeline/art/pathways.py"],
        "validator_paths": ["scripts/validate_museum_06_release.py", "museum_pipeline/art/pathways.py"],
        "input_paths": [
            "public/releases/art-gallery-interactions-1.1.0/manifest.json",
            "public/releases/art-gallery-interactions-1.1.0/relationships.json",
        ],
        "route_consumers": ["#/art/paths", "#/art/constellation", "#/art/artists/:id"],
    },
    {
        "phase_id": "MUSEUM-07",
        "release_id": "release:art-time-place-1.3.0",
        "directory": "public/releases/art-time-place-1.3.0",
        "builder_paths": ["scripts/build_museum_07_release.py", "museum_pipeline/art/timeplace.py"],
        "validator_paths": ["scripts/validate_museum_07_release.py", "museum_pipeline/art/timeplace.py"],
        "input_paths": [
            "public/releases/art-pathways-1.2.0/manifest.json",
            "research/art/museum-07-place-research.json",
            "data/reviewed/art/museum-07/basemap/basemap-source-record.json",
        ],
        "route_consumers": ["#/art/map", "#/art/paths", "#/art/artists/:id", "#/art/artworks/:id"],
    },
    {
        "phase_id": "MUSEUM-08",
        "release_id": "release:art-v1-candidate-1.4.0",
        "directory": "public/releases/art-v1-candidate-1.4.0",
        "builder_paths": ["scripts/build_museum_08_release.py", "museum_pipeline/art/candidate.py"],
        "validator_paths": ["scripts/validate_museum_08_release.py", "museum_pipeline/art/candidate.py"],
        "input_paths": [
            "public/releases/art-time-place-1.3.0/manifest.json",
            "governance/ci-impact-contract.json",
            "docs/qa/museum-08/admission-evidence.json",
            "docs/qa/museum-08/scale-readiness.json",
        ],
        "route_consumers": ["#/art/search", "#/art/constellation", "#/art/artists/:id", "#/art/artworks/:id", "#/art/compare", "#/art/tours/:id", "#/art/paths", "#/art/map"],
    },
    {
        "phase_id": "MUSEUM-09B-RELEASE",
        "release_id": "release:art-expansion-batch-01-1.5.0",
        "directory": "public/releases/art-expansion-batch-01-1.5.0",
        "builder_paths": ["scripts/build_museum_09b_release.py", "museum_pipeline/art/release_expansion.py"],
        "validator_paths": ["scripts/validate_museum_09b_release.py", "museum_pipeline/art/release_expansion.py"],
        "input_paths": [
            "public/releases/art-v1-candidate-1.4.0/manifest.json",
            "data/reviewed/art/museum-09b/batch-01-formal-candidate-v1/build-manifest.json",
            "data/reviewed/art/museum-09b-media/batch-01-media-bundle-v1/build-manifest.json",
            "docs/qa/museum-09b-release/source-drift-assessment.json",
        ],
        "route_consumers": ["#/art", "#/art/search", "#/art/constellation", "#/art/artists/:slug", "#/art/artworks/:slug", "#/art/compare", "#/art/tours/:id", "#/art/paths", "#/art/map"],
    },
)


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def closure_path_record(path: Path, relative: str) -> dict[str, Any]:
    payload = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return {
        "path": relative,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _path_records(paths: Iterable[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in sorted(set(paths)):
        path = ROOT / relative
        if not path.is_file():
            continue
        records.append(closure_path_record(path, relative))
    return records


def _closure(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": records,
        "hash": _sha256_bytes(canonical_json_bytes(records)),
    }


def physical_tree(root: Path) -> dict[str, Any]:
    files = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    byte_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        file_sha = sha256_file(path).removeprefix("sha256:")
        digest.update(f"{relative}\0{size}\0{file_sha}\n".encode("utf-8"))
        byte_count += size
    return {
        "algorithm": TREE_ALGORITHM,
        "hash": f"sha256:{digest.hexdigest()}",
        "file_count": len(files),
        "byte_count": byte_count,
    }


def _release_entry(spec: dict[str, Any]) -> dict[str, Any] | None:
    release_root = ROOT / spec["directory"]
    manifest_path = release_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_paths = [
        item["schema_path"]
        for item in manifest["manifest_files"]
        if isinstance(item.get("schema_path"), str)
    ]
    source_rights_paths = [
        item["path"]
        for item in manifest["manifest_files"]
        if item.get("record_type") in {
            "source_registry",
            "license_decisions",
            "third_party_notices",
            "attributions",
        }
        or item["path"] in {"rights.json", "source-rules-snapshot.json", "withdrawal-mapping.json"}
    ]
    builder = _closure(_path_records(spec["builder_paths"]))
    validator = _closure(_path_records(spec["validator_paths"]))
    input_closure = _closure(_path_records(spec["input_paths"]))
    schemas = _closure(_path_records(schema_paths))
    source_rights = _closure(_path_records(f"{spec['directory']}/{path}" for path in source_rights_paths))
    trigger_components = {
        "builder": builder["hash"],
        "validator": validator["hash"],
        "input_closure": input_closure["hash"],
        "schemas": schemas["hash"],
        "source_rights": source_rights["hash"],
    }
    return {
        "phase_id": spec["phase_id"],
        "release_id": manifest["id"],
        "version": manifest["version"],
        "directory": spec["directory"],
        "manifest_sha256": sha256_file(manifest_path),
        "content_hash": manifest["content_hash"],
        "physical_tree": physical_tree(release_root),
        "predecessor": manifest.get("predecessor"),
        "immutable": True,
        "builder": builder,
        "validator": validator,
        "input_closure": input_closure,
        "consumed_schemas": schemas,
        "source_rights_closure": source_rights,
        "rebuild_trigger_hash": _sha256_bytes(canonical_json_bytes(trigger_components)),
        "route_consumers": spec["route_consumers"],
        "shard_input_closures": [],
    }


def build_ledger() -> dict[str, Any]:
    releases = [entry for spec in RELEASE_SPECS if (entry := _release_entry(spec)) is not None]
    return {
        "schema_version": "1.0.0",
        "id": "release-integrity-ledger:museum-v1",
        "generated_at": GENERATED_AT,
        "default_historical_behavior": "hash_only",
        "rebuild_rule": "builder_validator_input_schema_source_rights_or_release_bytes_changed",
        "tree_hash_algorithm": TREE_ALGORITHM,
        "closure_path_hash_algorithm": CLOSURE_PATH_ALGORITHM,
        "current_release_id": releases[-1]["release_id"] if releases else None,
        "releases": releases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail unless the committed ledger is byte-identical")
    args = parser.parse_args()
    payload = canonical_json_bytes(build_ledger())
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_bytes() != payload:
            print(json.dumps({"ok": False, "reason": "ledger_not_deterministic_or_stale"}, indent=2))
            return 1
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    print(json.dumps({"ok": True, "path": str(output), "sha256": _sha256_bytes(payload)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
