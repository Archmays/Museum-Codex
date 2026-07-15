from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import statistics
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.validate_museum_05a_performance import (
    EXPECTED_ASSERTIONS,
    PROFILE_CONTRACTS,
    REQUIRED_CANONICAL_INPUTS,
    ROOT,
    SAMPLE_COUNT,
    TESTED_URL,
    canonical_implementation_input_files,
    implementation_input_hash,
    validate,
)


RUNNER = ROOT / "scripts" / "run-museum-05a-lab.mjs"


def p95(samples: list[int | float]) -> int | float:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def metric(samples: list[int | float], statistic: str, value: int | float) -> dict[str, Any]:
    summary = {
        "samples": samples,
        "median": statistics.median(samples),
        "p95": p95(samples),
    }
    summary["target"] = {
        "statistic": statistic,
        "operator": "lte",
        "value": value,
        "passed": summary[statistic] <= value,
    }
    return summary


def valid_evidence() -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_id, contract in PROFILE_CONTRACTS.items():
        image_requests = [0, 0, 0] if contract["initial_image_requests"] == 0 else [1, 1, 1]
        image_bytes = [0, 0, 0] if contract["initial_image_bytes"] == 0 else [10_000, 12_000, 14_000]
        metrics = {
            "first_interactive_ms": metric([1_000.0, 1_100.0, 1_200.0], "median", contract["first_interactive_ms"]),
            "lcp_ms": metric([900.0, 1_000.0, 1_100.0], "median", contract["lcp_ms"]),
            "cls": metric([0.01, 0.02, 0.03], "p95", 0.1),
            "initial_image_requests": metric(image_requests, "p95", contract["initial_image_requests"]),
            "initial_image_bytes": metric(image_bytes, "p95", contract["initial_image_bytes"]),
            "transferred_bytes": metric([500_000, 550_000, 600_000], "p95", contract["transferred_bytes"]),
            "horizontal_overflow_px": metric([0, 0, 0], "p95", 0),
        }
        profiles.append(
            {
                "profile_id": profile_id,
                "viewport": deepcopy(contract["viewport"]),
                "route": contract["route"],
                "low_bandwidth": contract["low_bandwidth"],
                "cpu_throttle_rate": contract["cpu_throttle_rate"],
                "network_profile": deepcopy(contract["network_profile"]),
                "sample_count": SAMPLE_COUNT,
                "metrics": metrics,
                "assertions": {name: True for name in EXPECTED_ASSERTIONS},
                "issues": [],
                "external_requests": [],
                "status": "pass",
            }
        )
    input_files = canonical_implementation_input_files()
    return {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-05A",
        "evidence_class": "controlled_lab",
        "real_user_metric": False,
        "real_device_status": "not_available",
        "real_assistive_technology_status": "not_available",
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "environment": {
            "browser": "chromium",
            "source_worktree_dirty": True,
            "implementation_input_files": input_files,
            "implementation_input_hash": implementation_input_hash(input_files),
            "tested_url": TESTED_URL,
        },
        "profiles": profiles,
        "overall_status": "pass",
    }


def validate_value(value: dict[str, Any]) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "evidence.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return validate(path)


class Museum05APerformanceEvidenceTests(unittest.TestCase):
    def test_valid_canonical_five_profile_evidence_passes(self) -> None:
        evidence = valid_evidence()
        self.assertEqual([], validate_value(evidence))
        self.assertEqual(
            [
                "desktop-artist-index",
                "mobile-artist-index-low-bandwidth",
                "desktop-artwork-detail",
                "mobile-artwork-detail",
                "mobile-compare-low-bandwidth",
            ],
            [profile["profile_id"] for profile in evidence["profiles"]],
        )

    def test_runner_and_validator_share_the_exact_canonical_inputs(self) -> None:
        result = subprocess.run(
            ["node", str(RUNNER), "--print-input-contract"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        runner_contract = json.loads(result.stdout)
        expected = canonical_implementation_input_files()
        self.assertEqual(expected, runner_contract["files"])
        self.assertEqual(implementation_input_hash(expected), runner_contract["hash"])
        self.assertTrue(REQUIRED_CANONICAL_INPUTS.issubset(expected))
        gallery_files = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "src" / "features" / "art-gallery").rglob("*")
            if path.is_file()
        )
        self.assertTrue(gallery_files)
        self.assertTrue(set(gallery_files).issubset(expected))

    def test_runner_rejects_noncanonical_sample_count_without_starting_lab(self) -> None:
        result = subprocess.run(
            ["node", str(RUNNER), "--print-input-contract", "--samples", "2"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("--samples is fixed at 3", result.stderr)

    def test_missing_evidence_fails(self) -> None:
        self.assertTrue(validate(Path("missing-museum-05a-evidence.json")))

    def test_self_selected_input_list_and_matching_forged_hash_fail(self) -> None:
        evidence = valid_evidence()
        reduced_inputs = evidence["environment"]["implementation_input_files"][1:]
        evidence["environment"]["implementation_input_files"] = reduced_inputs
        evidence["environment"]["implementation_input_hash"] = implementation_input_hash(reduced_inputs)
        failures = validate_value(evidence)
        self.assertIn("implementation_input_files", failures)
        self.assertIn("implementation_input_hash", failures)

    def test_forged_target_passed_cannot_hide_a_threshold_failure(self) -> None:
        evidence = valid_evidence()
        profile = evidence["profiles"][0]
        measured = profile["metrics"]["first_interactive_ms"]
        measured["samples"] = [5_000.0, 5_100.0, 5_200.0]
        measured["median"] = 5_100.0
        measured["p95"] = 5_200.0
        measured["target"]["passed"] = True
        failures = validate_value(evidence)
        self.assertIn("metric_target_passed:desktop-artist-index:first_interactive_ms", failures)
        self.assertIn("metric_threshold:desktop-artist-index:first_interactive_ms", failures)
        self.assertIn("profile_status_recomputed:desktop-artist-index", failures)
        self.assertIn("overall_status", failures)

    def test_forged_median_and_p95_fail_recomputation(self) -> None:
        evidence = valid_evidence()
        metric_record = evidence["profiles"][2]["metrics"]["lcp_ms"]
        metric_record["median"] = 1
        metric_record["p95"] = 1
        failures = validate_value(evidence)
        self.assertIn("metric_summary:desktop-artwork-detail:lcp_ms", failures)

    def test_profile_contract_and_sample_count_are_fixed(self) -> None:
        evidence = valid_evidence()
        profile = evidence["profiles"][3]
        profile["viewport"] = {"width": 320, "height": 640}
        profile["route"] = "#/art/artists"
        profile["low_bandwidth"] = True
        profile["cpu_throttle_rate"] = 1
        profile["network_profile"] = {"id": "invented"}
        profile["sample_count"] = 1
        failures = validate_value(evidence)
        for field in ("viewport", "route", "low_bandwidth", "cpu_throttle_rate", "network_profile"):
            self.assertIn(f"profile_contract:mobile-artwork-detail:{field}", failures)
        self.assertIn("sample_count:mobile-artwork-detail", failures)

    def test_nonfinite_samples_zero_lcp_and_zero_transfer_fail(self) -> None:
        evidence = valid_evidence()
        profile = evidence["profiles"][1]
        profile["metrics"]["cls"]["samples"] = [0.01, float("nan"), 0.02]
        profile["metrics"]["lcp_ms"] = metric([0.0, 0.0, 0.0], "median", 2_500)
        profile["metrics"]["transferred_bytes"] = metric([0, 0, 0], "p95", 3_000_000)
        failures = validate_value(evidence)
        self.assertIn("metric_samples:mobile-artist-index-low-bandwidth:cls", failures)
        self.assertIn("lcp_observed:mobile-artist-index-low-bandwidth", failures)
        self.assertIn("transfer_observed:mobile-artist-index-low-bandwidth", failures)
        self.assertIn("assertions:mobile-artist-index-low-bandwidth", failures)

    def test_assertions_are_exact_and_derived_from_runtime_fields(self) -> None:
        evidence = valid_evidence()
        profile = evidence["profiles"][4]
        profile["assertions"]["invented_pass"] = True
        profile["issues"] = ["console error: forged"]
        profile["external_requests"] = ["https://example.invalid/tracker"]
        failures = validate_value(evidence)
        self.assertIn("assertion_fields:mobile-compare-low-bandwidth", failures)
        self.assertIn("assertions:mobile-compare-low-bandwidth", failures)
        self.assertIn("runtime_issues:mobile-compare-low-bandwidth", failures)

    def test_target_fields_and_thresholds_are_canonical(self) -> None:
        evidence = valid_evidence()
        target = evidence["profiles"][0]["metrics"]["lcp_ms"]["target"]
        target["operator"] = "gte"
        target["statistic"] = "p95"
        target["value"] = 99_999
        target["extra"] = True
        failures = validate_value(evidence)
        self.assertIn("metric_target_fields:desktop-artist-index:lcp_ms", failures)
        self.assertIn("metric_target_contract:desktop-artist-index:lcp_ms", failures)

    def test_mobile_normal_detail_image_transfer_limit_is_enforced(self) -> None:
        evidence = valid_evidence()
        profile = evidence["profiles"][3]
        image_metric = profile["metrics"]["initial_image_bytes"]
        image_metric["samples"] = [800_000, 810_000, 820_000]
        image_metric["median"] = 810_000
        image_metric["p95"] = 820_000
        image_metric["target"]["passed"] = True
        failures = validate_value(evidence)
        self.assertIn("metric_target_passed:mobile-artwork-detail:initial_image_bytes", failures)
        self.assertIn("metric_threshold:mobile-artwork-detail:initial_image_bytes", failures)

    def test_profile_closure_rejects_omitted_mobile_normal_detail(self) -> None:
        evidence = valid_evidence()
        evidence["profiles"] = [
            profile for profile in evidence["profiles"] if profile["profile_id"] != "mobile-artwork-detail"
        ]
        failures = validate_value(evidence)
        self.assertIn("profile_closure", failures)
        self.assertIn("overall_status", failures)


if __name__ == "__main__":
    unittest.main()
