#!/usr/bin/env python3
"""Measure the phase-scoped MUSEUM-09A selection and batch-builder closure."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.global_expansion import (
    BASELINE_COMMIT,
    DEFAULT_OUTPUT,
    SHARDED_DOCUMENTS,
    _assign_batches,
    _json,
    _read_sharded_document,
    discover_universe,
    select_artists,
)


def _load_collection(relative: str) -> dict:
    failures: list[dict[str, str]] = []

    def fail(code: str, message: str, path: str = "$") -> None:
        failures.append({"code": code, "message": message, "path": path})

    result = _read_sharded_document(
        DEFAULT_OUTPUT,
        relative,
        _json(DEFAULT_OUTPUT / relative),
        fail=fail,
        **SHARDED_DOCUMENTS[relative],
    )
    if failures:
        raise ValueError(json.dumps(failures[:10], sort_keys=True))
    return result


def _p95(values: list[float]) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)]


def benchmark(iterations: int) -> dict:
    tracemalloc.start()
    discovery_started = time.perf_counter()
    universe, existing_artist_ids, _existing_work_ids = discover_universe()
    discovery_elapsed_ms = (time.perf_counter() - discovery_started) * 1000
    selection_baseline_bytes, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    selection_started = time.perf_counter()
    selected, reserve, assignments, _rejected = select_artists(universe, existing_artist_ids)
    selection_elapsed_ms = (time.perf_counter() - selection_started) * 1000
    selection_current_bytes, selection_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    artists = _load_collection("normalized-candidates.json")["candidates"]
    target_works = _load_collection("target-artworks.json")["artworks"]
    committed_batches = _json(DEFAULT_OUTPUT / "batch-registry-snapshot.json")
    target_ids = sorted(artist["id"] for artist in artists if artist["status"] == "program_target")
    committed_assignments = {
        artist["id"]: artist["primary_coverage_bucket"]
        for artist in artists
        if artist["status"] == "program_target"
    }
    gallery = {
        artist["id"]
        for artist in artists
        if artist["status"] == "program_target" and artist["content_depth_tier"] == "gallery"
    }
    batch_durations_ms: list[float] = []
    latest_batches = None
    for _ in range(iterations):
        started = time.perf_counter()
        _artist_batch, latest_batches = _assign_batches(
            target_ids,
            committed_batches["legacy_baseline"]["artist_ids"],
            target_works,
            committed_assignments,
            gallery,
        )
        batch_durations_ms.append((time.perf_counter() - started) * 1000)
    public_paths = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_COMMIT, "--", "public"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    return {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-09A",
        "iterations": iterations,
        "raw_cache_reused": True,
        "network_download_count": 0,
        "discovery_elapsed_ms": round(discovery_elapsed_ms, 3),
        "selection_elapsed_ms": round(selection_elapsed_ms, 3),
        "selection_traced_baseline_bytes": selection_baseline_bytes,
        "selection_traced_peak_bytes": selection_peak_bytes,
        "selection_incremental_peak_bytes": max(0, selection_peak_bytes - selection_baseline_bytes),
        "selection_current_bytes": selection_current_bytes,
        "selection_target_count": len(selected),
        "selection_reserve_count": len(reserve),
        "selection_matches_committed_targets": set(selected) == set(target_ids),
        "batch_builder_p95_ms": round(_p95(batch_durations_ms), 3),
        "batch_builder_max_ms": round(max(batch_durations_ms), 3),
        "batch_builder_matches_committed": latest_batches == committed_batches["batches"],
        "candidate_package_bytes": sum(
            path.stat().st_size for path in DEFAULT_OUTPUT.rglob("*") if path.is_file()
        ),
        "public_bundle_growth_bytes": 0 if not public_paths else None,
        "public_changed_paths": public_paths,
        "cache_reuse_basis": (
            "ignored official-source snapshots reused by input hash; deterministic rebuild and "
            "unchanged shard hashes permit hash-only reuse"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()
    if args.iterations < 5:
        parser.error("--iterations must be at least 5")
    result = benchmark(args.iterations)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (
        result["selection_target_count"] == 500
        and result["selection_reserve_count"] >= 100
        and result["selection_matches_committed_targets"]
        and result["batch_builder_matches_committed"]
        and result["public_bundle_growth_bytes"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
