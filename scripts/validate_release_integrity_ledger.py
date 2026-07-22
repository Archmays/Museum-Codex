#!/usr/bin/env python3
"""Validate immutable release hashes without rebuilding historical releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file
from scripts.generate_release_integrity_ledger import (
    CLOSURE_PATH_ALGORITHM,
    DEFAULT_OUTPUT,
    closure_path_record,
    physical_tree,
)
from scripts.validate_governance_foundation import release_content_hash


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _fail(failures: list[dict[str, str]], code: str, path: str, message: str) -> None:
    failures.append({"code": code, "path": path, "message": message})


def _validate_closure(
    failures: list[dict[str, str]],
    entry: dict[str, Any],
    key: str,
) -> None:
    closure = entry.get(key)
    if not isinstance(closure, dict) or not isinstance(closure.get("items"), list):
        _fail(failures, "ledger_closure_shape", f"{entry.get('release_id')}.{key}", "closure is missing")
        return
    records: list[dict[str, Any]] = []
    for item in closure["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            _fail(failures, "ledger_closure_item_shape", f"{entry.get('release_id')}.{key}", "invalid closure item")
            continue
        path = ROOT / item["path"]
        if not path.is_file():
            _fail(failures, f"{key}_path_missing", item["path"], "recorded closure path is missing")
            continue
        actual = closure_path_record(path, item["path"])
        records.append(actual)
        if actual != item:
            _fail(failures, f"{key}_drift", item["path"], "recorded path bytes or hash drifted")
    expected_hash = _sha256_bytes(canonical_json_bytes(records))
    if closure.get("hash") != expected_hash:
        _fail(failures, f"{key}_hash_drift", f"{entry.get('release_id')}.{key}", "closure hash drifted")


def validate_ledger(
    ledger_path: Path = DEFAULT_OUTPUT,
    *,
    require_candidate: bool = False,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return {"ok": False, "failures": [{"code": "ledger_unreadable", "path": str(ledger_path), "message": str(error)}]}
    releases = ledger.get("releases")
    if (
        ledger.get("schema_version") != "1.0.0"
        or ledger.get("default_historical_behavior") != "hash_only"
        or ledger.get("closure_path_hash_algorithm") != CLOSURE_PATH_ALGORITHM
        or not isinstance(releases, list)
    ):
        _fail(failures, "ledger_contract", str(ledger_path), "ledger header is invalid")
        releases = releases if isinstance(releases, list) else []
    ids = [entry.get("release_id") for entry in releases if isinstance(entry, dict)]
    if len(ids) != len(set(ids)):
        _fail(failures, "ledger_duplicate_release", str(ledger_path), "release IDs must be unique")
    if require_candidate and "release:art-v1-candidate-1.4.0" not in ids:
        _fail(failures, "candidate_missing", str(ledger_path), "M08 candidate is required")
    if ids and ledger.get("current_release_id") != ids[-1]:
        _fail(failures, "current_release_id", str(ledger_path), "current release must be the final immutable ledger entry")

    validated: list[str] = []
    total_files = 0
    total_bytes = 0
    for entry in releases:
        if not isinstance(entry, dict):
            _fail(failures, "ledger_entry_shape", str(ledger_path), "release entry is not an object")
            continue
        release_id = entry.get("release_id", "unknown")
        directory = entry.get("directory")
        if entry.get("immutable") is not True or not isinstance(directory, str):
            _fail(failures, "immutable_contract", str(release_id), "release must be immutable with a directory")
            continue
        root = ROOT / directory
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            _fail(failures, "release_missing", directory, "release manifest is missing")
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            _fail(failures, "manifest_unreadable", str(manifest_path), str(error))
            continue
        if manifest.get("id") != release_id:
            _fail(failures, "release_id_drift", str(manifest_path), "manifest ID differs from ledger")
        actual_manifest_sha = sha256_file(manifest_path)
        if actual_manifest_sha != entry.get("manifest_sha256"):
            _fail(failures, "manifest_sha_drift", str(manifest_path), "manifest SHA differs from ledger")
        actual_content_hash = release_content_hash([
            *manifest.get("manifest_files", []),
            *manifest.get("referenced_files", []),
            *manifest.get("materialized_asset_files", []),
        ])
        if manifest.get("content_hash") != actual_content_hash or entry.get("content_hash") != actual_content_hash:
            _fail(failures, "content_hash_drift", str(manifest_path), "content hash differs from manifest files or ledger")
        for item in manifest.get("manifest_files", []):
            path = root / item.get("path", "")
            if not path.is_file():
                _fail(failures, "manifest_file_missing", str(path), "manifest file is missing")
                continue
            if (
                path.stat().st_size != item.get("bytes")
                or sha256_file(path).removeprefix("sha256:")
                != str(item.get("sha256", "")).removeprefix("sha256:")
            ):
                _fail(failures, "manifest_file_drift", str(path), "manifest file bytes or hash drifted")
        for section in ("referenced_files", "materialized_asset_files"):
            for item in manifest.get(section, []):
                source_path = ROOT / item.get("source_path", "")
                if (
                    not source_path.is_file()
                    or source_path.stat().st_size != item.get("bytes")
                    or sha256_file(source_path).removeprefix("sha256:") != str(item.get("sha256", "")).removeprefix("sha256:")
                ):
                    _fail(failures, f"{section}_drift", str(source_path), "resolved release source bytes drifted")
        tree = physical_tree(root)
        if tree != entry.get("physical_tree"):
            _fail(failures, "physical_tree_drift", directory, "physical tree differs from ledger")
        total_files += tree["file_count"]
        total_bytes += tree["byte_count"]
        for key in ("builder", "validator", "input_closure", "consumed_schemas", "source_rights_closure"):
            _validate_closure(failures, entry, key)
        trigger_components = {
            "builder": entry.get("builder", {}).get("hash"),
            "validator": entry.get("validator", {}).get("hash"),
            "input_closure": entry.get("input_closure", {}).get("hash"),
            "schemas": entry.get("consumed_schemas", {}).get("hash"),
            "source_rights": entry.get("source_rights_closure", {}).get("hash"),
        }
        if entry.get("rebuild_trigger_hash") != _sha256_bytes(canonical_json_bytes(trigger_components)):
            _fail(failures, "rebuild_trigger_hash_drift", str(release_id), "trigger hash is inconsistent")
        validated.append(str(release_id))

    return {
        "ok": not failures,
        "mode": "historical_hash_only",
        "validated_releases": validated,
        "release_count": len(validated),
        "file_count": total_files,
        "byte_count": total_bytes,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-candidate", action="store_true")
    args = parser.parse_args()
    result = validate_ledger(args.ledger.resolve(), require_candidate=args.require_candidate)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
