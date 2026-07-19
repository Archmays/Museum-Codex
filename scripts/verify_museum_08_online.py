#!/usr/bin/env python3
"""Verify the deployed M08 build identity and complete candidate byte closure."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.hashing import sha256_file
from scripts.validate_governance_foundation import release_content_hash

CANDIDATE_DIRECTORY = "art-v1-candidate-1.4.0"
CANDIDATE_ID = "release:art-v1-candidate-1.4.0"
DEFAULT_OUTPUT = ROOT / "docs" / "qa" / "museum-08" / "online-closure.json"


def _url(base: str, relative: str) -> str:
    return urllib.parse.urljoin(base, relative)


def _fetch(url: str, *, timeout: float = 30.0, attempts: int = 3) -> tuple[bytes, dict[str, str], float]:
    error: Exception | None = None
    for attempt in range(attempts):
        started = time.perf_counter()
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "User-Agent": "Museum-Codex-M08-closure/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                headers = {key.lower(): value for key, value in response.headers.items()}
                return body, headers, (time.perf_counter() - started) * 1000
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as caught:
            error = caught
            if attempt + 1 < attempts:
                time.sleep(1.0 + attempt)
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


def _verify_file(base: str, release_prefix: str, entry: dict[str, Any]) -> dict[str, Any]:
    relative = str(entry["path"])
    body, headers, elapsed_ms = _fetch(_url(base, f"{release_prefix}/{relative}"))
    digest = hashlib.sha256(body).hexdigest()
    expected_digest = str(entry["sha256"]).removeprefix("sha256:")
    if len(body) != entry["bytes"] or digest != expected_digest:
        raise RuntimeError(
            f"{relative}: bytes/hash {len(body)}/{digest} != {entry['bytes']}/{expected_digest}"
        )
    return {
        "path": relative,
        "bytes": len(body),
        "sha256": f"sha256:{digest}",
        "elapsed_ms": elapsed_ms,
        "content_encoding": headers.get("content-encoding"),
    }


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int((len(ordered) * ratio) + 0.999999) - 1))]


def verify_online(base_url: str, commit: str) -> dict[str, Any]:
    base = base_url.rstrip("/") + "/"
    failures: list[str] = []
    started = time.perf_counter()
    build_identity: dict[str, Any] = {}
    convergence_attempts = 0
    manifest: dict[str, Any] = {}
    manifest_sha = "missing"
    file_results: list[dict[str, Any]] = []
    cold_probe_ms: list[float] = []
    try:
        build_identity, convergence_attempts = _wait_for_commit(base, commit)
        if build_identity.get("gate") != "final-full":
            failures.append(f"online build gate is {build_identity.get('gate')!r}, expected 'final-full'")
        release_prefix = f"releases/{CANDIDATE_DIRECTORY}"
        manifest_body, _, _ = _fetch(_url(base, f"{release_prefix}/manifest.json"))
        manifest_sha = f"sha256:{hashlib.sha256(manifest_body).hexdigest()}"
        manifest = json.loads(manifest_body)
        local_manifest = ROOT / "public" / "releases" / CANDIDATE_DIRECTORY / "manifest.json"
        if manifest_sha != sha256_file(local_manifest):
            failures.append("online manifest SHA differs from the deployed commit checkout")
        if manifest.get("id") != CANDIDATE_ID:
            failures.append(f"online candidate ID is {manifest.get('id')!r}")
        if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
            failures.append("online manifest content hash is not closed")

        entries = manifest.get("manifest_files", [])
        if not isinstance(entries, list) or not entries:
            failures.append("online manifest has no physical file entries")
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(_verify_file, base, release_prefix, entry): entry["path"]
                    for entry in entries
                }
                for future in concurrent.futures.as_completed(futures):
                    relative = futures[future]
                    try:
                        file_results.append(future.result())
                    except Exception as error:
                        failures.append(f"{relative}: {error}")
            file_results.sort(key=lambda item: item["path"])

        for index in range(3):
            probe_url = _url(base, f"index.html?museum08_cold_probe={index}-{commit[:12]}")
            _, _, elapsed_ms = _fetch(probe_url, timeout=20)
            cold_probe_ms.append(elapsed_ms)
    except Exception as error:
        failures.append(str(error))

    expected_entries = manifest.get("manifest_files", []) if isinstance(manifest, dict) else []
    expected_bytes = sum(
        item.get("bytes", 0)
        for item in expected_entries
        if isinstance(item, dict) and isinstance(item.get("bytes"), int)
    )
    report = {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-08",
        "evidence_class": "bounded_public_cold_probe_and_complete_candidate_byte_closure",
        "real_user_metric": False,
        "base_url": base,
        "commit": commit,
        "build_identity": build_identity,
        "convergence_attempts": convergence_attempts,
        "candidate_release_id": manifest.get("id") if isinstance(manifest, dict) else None,
        "candidate_manifest_sha256": manifest_sha,
        "candidate_content_hash": manifest.get("content_hash") if isinstance(manifest, dict) else None,
        "expected_file_count": len(expected_entries),
        "verified_file_count": len(file_results),
        "expected_byte_count": expected_bytes,
        "verified_byte_count": sum(item["bytes"] for item in file_results),
        "cold_probe": {
            "runs": len(cold_probe_ms),
            "samples_ms": cold_probe_ms,
            "median_ms": statistics.median(cold_probe_ms) if cold_probe_ms else None,
            "p95_ms": _percentile(cold_probe_ms, 0.95) if cold_probe_ms else None,
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = verify_online(args.base_url, args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
