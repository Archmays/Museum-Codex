#!/usr/bin/env python3
"""Verify deployed M09B identity and complete release/runtime byte closure."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIRECTORY = "art-expansion-batch-01-1.5.0"
RELEASE_ID = "release:art-expansion-batch-01-1.5.0"
DEFAULT_OUTPUT = ROOT / "docs" / "qa" / "museum-09b-release" / "online-closure.json"
EXPECTED_COUNTS = {
    "artists": 62,
    "artworks": 532,
    "gallery_profiles": 24,
    "collection_profiles": 38,
    "self_hosted_works": 71,
    "external_link_only_works": 25,
    "metadata_only_works": 436,
    "new_derivatives": 318,
    "new_public_originals": 0,
}


def _sha256_bytes(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _release_content_hash(entries: list[dict[str, Any]]) -> str:
    lines = [
        f"{item['path']}\0{item['sha256']}\0{item['bytes']}\n"
        for item in sorted(entries, key=lambda item: item["path"])
    ]
    return "sha256:" + hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _url(base: str, relative: str) -> str:
    return urllib.parse.urljoin(base, relative)


def _fetch(url: str, *, timeout: float = 30.0, attempts: int = 3) -> tuple[bytes, dict[str, str], float]:
    error: Exception | None = None
    for attempt in range(attempts):
        started = time.perf_counter()
        request = urllib.request.Request(
            url,
            headers={"Accept": "*/*", "Cache-Control": "no-cache", "User-Agent": "Museum-Codex-M09B-closure/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), {key.lower(): value for key, value in response.headers.items()}, (time.perf_counter() - started) * 1000
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as caught:
            error = caught
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise RuntimeError(f"GET {url} failed after {attempts} attempts: {error}")


def _wait_for_commit(base: str, expected_commit: str) -> tuple[dict[str, Any], int]:
    last: object = None
    for attempt in range(12):
        try:
            body, _, _ = _fetch(_url(base, "museum-build.json"), timeout=15, attempts=1)
            last = json.loads(body)
            if isinstance(last, dict) and last.get("commit") == expected_commit:
                return last, attempt + 1
        except (RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            last = str(error)
        if attempt < 11:
            time.sleep(5)
    raise RuntimeError(f"deployed commit did not converge to {expected_commit}: {last!r}")


def _verify_file(base: str, entry: dict[str, Any]) -> dict[str, Any]:
    body, headers, elapsed_ms = _fetch(_url(base, entry["url_path"]))
    actual_sha = _sha256_bytes(body)
    if len(body) != entry["bytes"] or actual_sha != entry["sha256"]:
        raise RuntimeError(
            f"{entry['url_path']}: bytes/hash {len(body)}/{actual_sha} != {entry['bytes']}/{entry['sha256']}"
        )
    return {
        "path": entry["url_path"],
        "classes": sorted(entry["classes"]),
        "bytes": len(body),
        "sha256": actual_sha,
        "elapsed_ms": elapsed_ms,
        "content_encoding": headers.get("content-encoding"),
    }


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int((len(ordered) * ratio) + 0.999999) - 1))]


def _add_entry(closure: dict[str, dict[str, Any]], path: str, sha256: str, byte_count: int, kind: str) -> None:
    normalized = path.lstrip("/")
    existing = closure.get(normalized)
    if existing:
        if existing["sha256"] != sha256 or existing["bytes"] != byte_count:
            raise ValueError(f"conflicting byte contract for {normalized}")
        existing["classes"].add(kind)
        return
    closure[normalized] = {
        "url_path": normalized,
        "sha256": sha256 if sha256.startswith("sha256:") else f"sha256:{sha256}",
        "bytes": byte_count,
        "classes": {kind},
    }


def verify_online(base_url: str, commit: str) -> dict[str, Any]:
    base = base_url.rstrip("/") + "/"
    release_prefix = f"releases/{RELEASE_DIRECTORY}"
    failures: list[str] = []
    started = time.perf_counter()
    build_identity: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    validation_summary: dict[str, Any] = {}
    convergence_attempts = 0
    manifest_sha = "missing"
    closure: dict[str, dict[str, Any]] = {}
    file_results: list[dict[str, Any]] = []
    cold_probe_ms: list[float] = []
    class_counts: dict[str, int] = {}
    try:
        build_identity, convergence_attempts = _wait_for_commit(base, commit)
        if build_identity.get("gate") != "final-full":
            failures.append(f"online build gate is {build_identity.get('gate')!r}, expected 'final-full'")

        manifest_body, _, _ = _fetch(_url(base, f"{release_prefix}/manifest.json"))
        manifest_sha = _sha256_bytes(manifest_body)
        manifest = json.loads(manifest_body)
        local_manifest_sha = _sha256_bytes((ROOT / "public" / "releases" / RELEASE_DIRECTORY / "manifest.json").read_bytes())
        if manifest_sha != local_manifest_sha:
            failures.append("online manifest SHA differs from the deployed commit checkout")
        if manifest.get("id") != RELEASE_ID:
            failures.append(f"online release ID is {manifest.get('id')!r}")
        manifest_entries = manifest.get("manifest_files", [])
        if not isinstance(manifest_entries, list) or not manifest_entries:
            raise ValueError("online release manifest has no physical file entries")
        if manifest.get("content_hash") != _release_content_hash(manifest_entries):
            failures.append("online release content hash is not closed")
        for entry in manifest_entries:
            _add_entry(closure, f"{release_prefix}/{entry['path']}", entry["sha256"], entry["bytes"], "release_manifest")

        asset_body, _, _ = _fetch(_url(base, f"{release_prefix}/asset-resolution-manifest.json"))
        asset_manifest = json.loads(asset_body)
        if asset_manifest.get("release_id") != RELEASE_ID:
            failures.append("asset-resolution manifest release ID mismatch")
        if asset_manifest.get("runtime_external_image_request_count") != 0:
            failures.append("asset-resolution manifest permits external image requests")
        referenced = asset_manifest.get("referenced_files", [])
        materialized = asset_manifest.get("materialized_asset_files", [])
        if len(referenced) != asset_manifest.get("referenced_file_count"):
            failures.append("referenced asset count mismatch")
        if len(materialized) != asset_manifest.get("materialized_asset_count"):
            failures.append("materialized asset count mismatch")
        for entry in referenced:
            _add_entry(closure, entry["resolved_path"], entry["sha256"], entry["bytes"], "predecessor_reference")
        for entry in materialized:
            _add_entry(closure, entry["path"], entry["sha256"], entry["bytes"], "build_materialized")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_verify_file, base, entry): path for path, entry in closure.items()}
            for future in concurrent.futures.as_completed(futures):
                path = futures[future]
                try:
                    file_results.append(future.result())
                except Exception as error:
                    failures.append(f"{path}: {error}")
        file_results.sort(key=lambda item: item["path"])
        for result in file_results:
            for kind in result["classes"]:
                class_counts[kind] = class_counts.get(kind, 0) + 1

        summary_body, _, _ = _fetch(_url(base, f"{release_prefix}/validation-summary.json"))
        validation_summary = json.loads(summary_body)
        for key, expected in EXPECTED_COUNTS.items():
            if validation_summary.get("counts", {}).get(key) != expected:
                failures.append(f"online count {key} != {expected}")
        if validation_summary.get("status") != "pass":
            failures.append("online validation summary is not pass")

        for index in range(3):
            _, _, elapsed_ms = _fetch(_url(base, f"index.html?museum09b_cold_probe={index}-{commit[:12]}"), timeout=20)
            cold_probe_ms.append(elapsed_ms)
    except Exception as error:
        failures.append(str(error))

    expected_bytes = sum(item["bytes"] for item in closure.values())
    report = {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-09B-RELEASE",
        "evidence_class": "bounded_public_cold_probe_and_complete_release_runtime_byte_closure",
        "real_user_metric": False,
        "base_url": base,
        "commit": commit,
        "build_identity": build_identity,
        "convergence_attempts": convergence_attempts,
        "release_id": manifest.get("id") if isinstance(manifest, dict) else None,
        "manifest_sha256": manifest_sha,
        "content_hash": manifest.get("content_hash") if isinstance(manifest, dict) else None,
        "release_counts": validation_summary.get("counts", {}) if isinstance(validation_summary, dict) else {},
        "expected_file_count": len(closure),
        "verified_file_count": len(file_results),
        "expected_byte_count": expected_bytes,
        "verified_byte_count": sum(item["bytes"] for item in file_results),
        "closure_class_counts": class_counts,
        "cold_probe": {
            "runs": len(cold_probe_ms),
            "samples_ms": cold_probe_ms,
            "median_ms": statistics.median(cold_probe_ms) if cold_probe_ms else None,
            "p95_ms": _percentile(cold_probe_ms, 0.95),
            "environment": "GitHub Actions runner to GitHub Pages; bounded synthetic probe; not RUM",
        },
        "elapsed_seconds": time.perf_counter() - started,
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_online(args.base_url, args.commit)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
