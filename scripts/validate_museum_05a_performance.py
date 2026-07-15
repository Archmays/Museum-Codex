#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "docs" / "qa" / "museum-05a" / "performance.json"
SAMPLE_COUNT = 3
TESTED_URL = "http://127.0.0.1:4173/Museum-Codex/"

UNTHROTTLED_NETWORK = {
    "id": "unthrottled",
    "emulation_enabled": False,
    "connection_type": None,
}
FAST_4G_NETWORK = {
    "id": "fast_4g",
    "emulation_enabled": True,
    "connection_type": "cellular4g",
    "latency_ms": 20,
    "download_throughput_bytes_per_second": 500_000,
    "upload_throughput_bytes_per_second": 375_000,
}

# Dict insertion order is the canonical runner/evidence order.
PROFILE_CONTRACTS: dict[str, dict[str, Any]] = {
    "desktop-artist-index": {
        "viewport": {"width": 1440, "height": 900},
        "route": "#/art/artists",
        "low_bandwidth": False,
        "cpu_throttle_rate": 1,
        "network_profile": UNTHROTTLED_NETWORK,
        "first_interactive_ms": 2_000,
        "lcp_ms": 2_500,
        "initial_image_requests": 8,
        "initial_image_bytes": 2_000_000,
        "transferred_bytes": 3_000_000,
    },
    "mobile-artist-index-low-bandwidth": {
        "viewport": {"width": 390, "height": 844},
        "route": "#/art/artists",
        "low_bandwidth": True,
        "cpu_throttle_rate": 4,
        "network_profile": FAST_4G_NETWORK,
        "first_interactive_ms": 3_500,
        "lcp_ms": 2_500,
        "initial_image_requests": 0,
        "initial_image_bytes": 0,
        "transferred_bytes": 3_000_000,
    },
    "desktop-artwork-detail": {
        "viewport": {"width": 1366, "height": 768},
        "route": "#/art/artworks/artwork%3Amet-334816",
        "low_bandwidth": False,
        "cpu_throttle_rate": 1,
        "network_profile": UNTHROTTLED_NETWORK,
        "first_interactive_ms": 2_000,
        "lcp_ms": 2_500,
        "initial_image_requests": 2,
        "initial_image_bytes": 1_000_000,
        "transferred_bytes": 3_000_000,
    },
    "mobile-artwork-detail": {
        "viewport": {"width": 390, "height": 844},
        "route": "#/art/artworks/artwork%3Amet-334816",
        "low_bandwidth": False,
        "cpu_throttle_rate": 4,
        "network_profile": FAST_4G_NETWORK,
        "first_interactive_ms": 3_500,
        "lcp_ms": 3_500,
        "initial_image_requests": 2,
        "initial_image_bytes": 750_000,
        "transferred_bytes": 3_000_000,
    },
    "mobile-compare-low-bandwidth": {
        "viewport": {"width": 360, "height": 800},
        "route": "#/art/compare?left=artwork%3Amet-334816&right=artwork%3Amet-436243",
        "low_bandwidth": True,
        "cpu_throttle_rate": 4,
        "network_profile": FAST_4G_NETWORK,
        "first_interactive_ms": 3_500,
        "lcp_ms": 2_500,
        "initial_image_requests": 0,
        "initial_image_bytes": 0,
        "transferred_bytes": 3_000_000,
    },
}

EXPECTED_ASSERTIONS = {
    "lcp_observed",
    "transfer_observed",
    "no_console_or_network_errors",
    "no_external_requests",
    "no_horizontal_overflow",
}
EXPECTED_METRICS = {
    "first_interactive_ms",
    "lcp_ms",
    "cls",
    "initial_image_requests",
    "initial_image_bytes",
    "transferred_bytes",
    "horizontal_overflow_px",
}
INTEGER_SAMPLE_METRICS = {
    "initial_image_requests",
    "initial_image_bytes",
    "transferred_bytes",
    "horizontal_overflow_px",
}
EXPECTED_PROFILE_FIELDS = {
    "profile_id",
    "viewport",
    "route",
    "low_bandwidth",
    "cpu_throttle_rate",
    "network_profile",
    "sample_count",
    "metrics",
    "assertions",
    "issues",
    "external_requests",
    "status",
}

CANONICAL_ROOT_INPUTS = (
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "public/releases/art-constellation-1.0.0/manifest.json",
    "scripts/run-museum-05a-lab.mjs",
    "scripts/validate_museum_05a_performance.py",
)
REQUIRED_CANONICAL_INPUTS = {
    "index.html",
    "package-lock.json",
    "src/App.tsx",
    "src/main.tsx",
    "src/data/art-constellation-bootstrap.ts",
    "src/data/release-loader.ts",
    "src/preferences/PreferencesProvider.tsx",
    "src/features/art-constellation/ArtworkImage.tsx",
    "public/releases/art-constellation-1.0.0/manifest.json",
    "scripts/run-museum-05a-lab.mjs",
    "scripts/validate_museum_05a_performance.py",
}


def canonical_implementation_input_files() -> list[str]:
    product_sources = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "src").rglob("*")
        if path.is_file() and not path.relative_to(ROOT).as_posix().startswith("src/tests/")
    ]
    return sorted(set(CANONICAL_ROOT_INPUTS).union(product_sources))


def implementation_input_hash(paths: list[str] | None = None) -> str:
    canonical_paths = canonical_implementation_input_files() if paths is None else paths
    digest = hashlib.sha256()
    for relative_path in canonical_paths:
        path = ROOT / relative_path
        if not path.is_file():
            return "missing"
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_samples(value: Any, *, integers: bool = False) -> bool:
    return (
        isinstance(value, list)
        and len(value) == SAMPLE_COUNT
        and all(_is_finite_number(sample) and sample >= 0 for sample in value)
        and (not integers or all(isinstance(sample, int) and not isinstance(sample, bool) for sample in value))
    )


def _p95(samples: list[int | float]) -> int | float:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _summary_matches(actual: Any, expected: int | float) -> bool:
    return _is_finite_number(actual) and math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-9)


def _metric_contract(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "first_interactive_ms": {"statistic": "median", "operator": "lte", "value": profile["first_interactive_ms"]},
        "lcp_ms": {"statistic": "median", "operator": "lte", "value": profile["lcp_ms"]},
        "cls": {"statistic": "p95", "operator": "lte", "value": 0.1},
        "initial_image_requests": {"statistic": "p95", "operator": "lte", "value": profile["initial_image_requests"]},
        "initial_image_bytes": {"statistic": "p95", "operator": "lte", "value": profile["initial_image_bytes"]},
        "transferred_bytes": {"statistic": "p95", "operator": "lte", "value": profile["transferred_bytes"]},
        "horizontal_overflow_px": {"statistic": "p95", "operator": "lte", "value": 0},
    }


def _valid_capture_time(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _valid_tested_url(value: Any) -> bool:
    if value != TESTED_URL:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port == 4173


def validate(path: Path = DEFAULT_EVIDENCE) -> list[str]:
    failures: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"evidence_unreadable:{error}"]
    if not isinstance(raw, dict):
        return ["evidence_root"]
    evidence: dict[str, Any] = raw

    if evidence.get("schema_version") != "1.0.0" or evidence.get("phase_id") != "MUSEUM-05A":
        failures.append("evidence_identity")
    if evidence.get("evidence_class") != "controlled_lab" or evidence.get("real_user_metric") is not False:
        failures.append("evidence_class")
    if evidence.get("real_device_status") != "not_available" or evidence.get("real_assistive_technology_status") != "not_available":
        failures.append("environment_claim")
    if not _valid_capture_time(evidence.get("captured_at")):
        failures.append("captured_at")

    environment = evidence.get("environment") if isinstance(evidence.get("environment"), dict) else {}
    if environment.get("browser") != "chromium":
        failures.append("browser")
    if not isinstance(environment.get("source_worktree_dirty"), bool):
        failures.append("source_worktree_dirty")
    if not _valid_tested_url(environment.get("tested_url")):
        failures.append("tested_url")
    canonical_inputs = canonical_implementation_input_files()
    if not REQUIRED_CANONICAL_INPUTS.issubset(canonical_inputs) or not all(
        input_path in canonical_inputs
        for input_path in (
            "src/features/art-gallery/ArtGalleryRoute.tsx",
            "src/features/art-gallery/artists/ArtistGalleryPage.tsx",
            "src/features/art-gallery/artwork/ArtworkDetailPage.tsx",
            "src/features/art-gallery/compare/ComparePage.tsx",
        )
    ):
        failures.append("canonical_input_contract")
    if environment.get("implementation_input_files") != canonical_inputs:
        failures.append("implementation_input_files")
    if environment.get("implementation_input_hash") != implementation_input_hash(canonical_inputs):
        failures.append("implementation_input_hash")

    profiles_raw = evidence.get("profiles")
    profiles = profiles_raw if isinstance(profiles_raw, list) else []
    expected_order = list(PROFILE_CONTRACTS)
    profile_ids = [profile.get("profile_id") if isinstance(profile, dict) else None for profile in profiles]
    closure_valid = len(profiles) == len(expected_order) and profile_ids == expected_order
    if not closure_valid:
        failures.append("profile_closure")

    recomputed_profile_passes: list[bool] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            failures.append("profile_record")
            recomputed_profile_passes.append(False)
            continue
        profile_id = profile.get("profile_id")
        contract = PROFILE_CONTRACTS.get(profile_id)
        if contract is None:
            failures.append(f"unknown_profile:{profile_id}")
            recomputed_profile_passes.append(False)
            continue
        profile_failure_start = len(failures)
        if set(profile) != EXPECTED_PROFILE_FIELDS:
            failures.append(f"profile_fields:{profile_id}")
        for field in ("viewport", "route", "low_bandwidth", "cpu_throttle_rate", "network_profile"):
            if profile.get(field) != contract[field]:
                failures.append(f"profile_contract:{profile_id}:{field}")
        if profile.get("sample_count") != SAMPLE_COUNT:
            failures.append(f"sample_count:{profile_id}")

        metrics = profile.get("metrics") if isinstance(profile.get("metrics"), dict) else {}
        if set(metrics) != EXPECTED_METRICS:
            failures.append(f"metric_closure:{profile_id}")
        metric_contract = _metric_contract(contract)
        recomputed_metrics: dict[str, dict[str, Any]] = {}
        for metric_name, expected_target in metric_contract.items():
            metric = metrics.get(metric_name) if isinstance(metrics.get(metric_name), dict) else {}
            if set(metric) != {"samples", "median", "p95", "target"}:
                failures.append(f"metric_fields:{profile_id}:{metric_name}")
            samples = metric.get("samples")
            samples_valid = _valid_samples(samples, integers=metric_name in INTEGER_SAMPLE_METRICS)
            if not samples_valid:
                failures.append(f"metric_samples:{profile_id}:{metric_name}")
                continue
            median_value = statistics.median(samples)
            p95_value = _p95(samples)
            recomputed_metrics[metric_name] = {"median": median_value, "p95": p95_value, "samples": samples}
            if not _summary_matches(metric.get("median"), median_value) or not _summary_matches(metric.get("p95"), p95_value):
                failures.append(f"metric_summary:{profile_id}:{metric_name}")

            target = metric.get("target") if isinstance(metric.get("target"), dict) else {}
            if set(target) != {"statistic", "operator", "value", "passed"}:
                failures.append(f"metric_target_fields:{profile_id}:{metric_name}")
            if any(target.get(field) != expected_target[field] for field in ("statistic", "operator", "value")):
                failures.append(f"metric_target_contract:{profile_id}:{metric_name}")
            observed = {"median": median_value, "p95": p95_value}[expected_target["statistic"]]
            recomputed_passed = observed <= expected_target["value"]
            if target.get("passed") is not recomputed_passed:
                failures.append(f"metric_target_passed:{profile_id}:{metric_name}")
            if not recomputed_passed:
                failures.append(f"metric_threshold:{profile_id}:{metric_name}")

        if recomputed_metrics.get("first_interactive_ms") and not all(
            value > 0 for value in recomputed_metrics["first_interactive_ms"]["samples"]
        ):
            failures.append(f"first_interactive_observed:{profile_id}")
        lcp_observed = bool(recomputed_metrics.get("lcp_ms")) and all(
            value > 0 for value in recomputed_metrics["lcp_ms"]["samples"]
        )
        transfer_observed = bool(recomputed_metrics.get("transferred_bytes")) and all(
            value > 0 for value in recomputed_metrics["transferred_bytes"]["samples"]
        )
        no_horizontal_overflow = bool(recomputed_metrics.get("horizontal_overflow_px")) and all(
            value == 0 for value in recomputed_metrics["horizontal_overflow_px"]["samples"]
        )
        if not lcp_observed:
            failures.append(f"lcp_observed:{profile_id}")
        if not transfer_observed:
            failures.append(f"transfer_observed:{profile_id}")

        issues = profile.get("issues")
        external_requests = profile.get("external_requests")
        if issues != [] or external_requests != []:
            failures.append(f"runtime_issues:{profile_id}")
        recomputed_assertions = {
            "lcp_observed": lcp_observed,
            "transfer_observed": transfer_observed,
            "no_console_or_network_errors": issues == [],
            "no_external_requests": external_requests == [],
            "no_horizontal_overflow": no_horizontal_overflow,
        }
        assertions = profile.get("assertions") if isinstance(profile.get("assertions"), dict) else {}
        if set(assertions) != EXPECTED_ASSERTIONS:
            failures.append(f"assertion_fields:{profile_id}")
        if assertions != recomputed_assertions or not all(recomputed_assertions.values()):
            failures.append(f"assertions:{profile_id}")

        recomputed_pass = len(failures) == profile_failure_start
        recomputed_profile_passes.append(recomputed_pass)
        if profile.get("status") != ("pass" if recomputed_pass else "fail"):
            failures.append(f"profile_status_recomputed:{profile_id}")
        if profile.get("status") != "pass":
            failures.append(f"profile_status:{profile_id}")

    overall_recomputed_pass = closure_valid and len(recomputed_profile_passes) == len(expected_order) and all(recomputed_profile_passes)
    if evidence.get("overall_status") != "pass" or not overall_recomputed_pass:
        failures.append("overall_status")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MUSEUM-05A controlled-lab performance evidence")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    failures = validate(args.path)
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] MUSEUM-05A controlled-lab performance evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
