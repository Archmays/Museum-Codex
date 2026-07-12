from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.config import ROOT, license_rules_snapshot_hash, source_registry_snapshot_hash
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def artifact_ref(path: Path, *, relative_to: Path, record_ids: list[str]) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(relative_to.resolve(strict=True)).as_posix()
    except ValueError as error:
        raise PipelineError("artifact_path_escape", "Run artifact is outside its governed root") from error
    return {
        "path": relative,
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
        "record_ids": sorted(set(record_ids)),
    }


def create_run_manifest(
    *,
    started_at: str,
    status: str,
    network_mode: str,
    adapter_runs: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    commands: list[str],
    errors: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": run_id or f"pipeline-run:{uuid.uuid4()}",
        "entity_type": "pipeline_run",
        "started_at": started_at,
        "finished_at": utc_now() if status != "running" else None,
        "status": status,
        "network_mode": network_mode,
        "source_registry_snapshot_hash": source_registry_snapshot_hash(),
        "license_rules_snapshot_hash": license_rules_snapshot_hash(),
        "adapter_runs": sorted(adapter_runs, key=lambda item: item["source_id"]),
        "inputs": sorted(inputs, key=lambda item: item["path"]),
        "outputs": sorted(outputs, key=lambda item: item["path"]),
        "commands": commands,
        "errors": sorted(errors or []),
        "candidate_data_publicly_exposed": False,
        "media_downloaded": False,
        "public_artifact_scanned": False,
    }


def update_run_outputs(run_dir: Path, paths: list[tuple[Path, list[str]]], command: str) -> dict[str, Any]:
    manifest_path = run_dir / "pipeline-run.json"
    if not manifest_path.exists():
        raise PipelineError("run_manifest_missing", "Pipeline run manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in manifest.get("outputs", [])}
    for path, record_ids in paths:
        reference = artifact_ref(path, relative_to=run_dir, record_ids=record_ids)
        by_path[reference["path"]] = reference
    manifest["outputs"] = [by_path[key] for key in sorted(by_path)]
    manifest["commands"] = [*manifest.get("commands", []), command]
    manifest["finished_at"] = utc_now()
    write_canonical_json(manifest_path, manifest)
    return manifest


def update_run_inputs(run_dir: Path, paths: list[tuple[Path, list[str]]]) -> dict[str, Any]:
    manifest_path = run_dir / "pipeline-run.json"
    if not manifest_path.exists():
        raise PipelineError("run_manifest_missing", "Pipeline run manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in manifest.get("inputs", [])}
    for path, record_ids in paths:
        reference = artifact_ref(path, relative_to=ROOT, record_ids=record_ids)
        by_path[reference["path"]] = reference
    manifest["inputs"] = [by_path[key] for key in sorted(by_path)]
    manifest["finished_at"] = utc_now()
    write_canonical_json(manifest_path, manifest)
    return manifest
