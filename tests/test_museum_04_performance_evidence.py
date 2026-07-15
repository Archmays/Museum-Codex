from __future__ import annotations

import copy
import math
import statistics
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.validate_museum_04_performance_evidence import (
    CURRENT_METRIC_UNITS,
    CURRENT_IMPLEMENTATION_INPUT_FILES,
    FIFTY_K_MODEL_STORAGE_BYTES,
    GOVERNANCE_FIELDS,
    RELEASE_PERFORMANCE_CONTRACT_PATH,
    SCALE_IMPLEMENTATION_INPUT_FILES,
    VISIBLE_CAPS,
    implementation_input_hash,
    current_implementation_input_hash,
    sha256_file,
    validate_current_graph,
    validate_files,
    validate_scale,
)
from scripts.generate_museum_04_scale_fixture import deterministic_sample_hash


def measurement(
    value: float,
    unit: str,
    target: tuple[str, str, float] | None = None,
) -> dict[str, Any]:
    samples = [value * 0.9, value, value * 1.1]
    ordered = sorted(samples)
    result: dict[str, Any] = {
        "unit": unit,
        "samples": samples,
        "median": statistics.median(samples),
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
    }
    if target is not None:
        statistic_name, operator, threshold = target
        actual = result[statistic_name]
        passed = actual <= threshold if operator == "lte" else actual >= threshold
        result["target"] = {
            "statistic": statistic_name,
            "operator": operator,
            "value": threshold,
            "passed": passed,
        }
    return result


def common(benchmark_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "benchmark_id": benchmark_id,
        "evidence_class": "controlled_lab_not_rum",
        "real_user_metric": False,
        "real_device_status": "not_available",
        "real_device_note": "No physical Android device was exposed to this runtime.",
        "captured_at": "2026-07-14T12:00:00+08:00",
        "environment": {
            "host_os": "Windows 11",
            "cpu": "test CPU",
            "memory_gb": 16,
            "browser": "Chromium",
            "browser_version": "140.0.0",
            "node_version": "24.0.0",
            "playwright_version": "1.61.1",
            "runner": "local controlled lab",
            "measurement_method": "Playwright CDP repeated samples",
            "commit_sha": "2be73011cb1dca64cb8d3a2d5830f495671d755b",
            "source_worktree_dirty": True,
        },
    }


def current_payload() -> dict[str, Any]:
    payload = common("museum-04-current-graph")
    payload["environment"]["implementation_input_files"] = CURRENT_IMPLEMENTATION_INPUT_FILES
    payload["environment"]["implementation_input_hash"] = current_implementation_input_hash()
    payload["lab_configuration"] = {
        "browser_console_policy": {
            "application_warnings_and_errors_fail": True,
            "allowlisted_environment_diagnostic": "Chromium WebGL GPU stall due to ReadPixels only",
        },
        "deterministic_gzip_budget": {
            "algorithm": "node:zlib gzip level 9; each file compressed independently",
            "home_initial_gzip_bytes": 90_000,
            "constellation_route_gzip_bytes": 100_000,
            "initial_data_gzip_bytes": 20_000,
            "graph_summary_gzip_bytes": 1_000,
            "manifest": ".vite/manifest.json",
            "status": "pass",
        },
        "media_delivery": {
            "release_id": "release:art-constellation-1.0.0",
            "artwork_rows": 44,
            "media_record_count": 273,
            "physical_derivative_count": 242,
            "physical_derivative_bytes": 35_907_176,
            "initial_image_requests_target": 0,
            "initial_image_bytes_target": 0,
            "media_index_load": "deferred",
            "representative_media_load": "focus_only",
            "detail_media_load": "user_navigation_only",
            "low_bandwidth_default": "metadata_only",
            "thumbnail_widths": [320, 640],
            "detail_widths": [960, 1600],
            "external_runtime_api": False,
            "external_delivery_count": 0,
            "blocked_asset_count": 0,
        }
    }
    runs = []
    for width, height, device, cpu, network in (
        (390, 844, "mobile", 4, "fast_4g"),
        (360, 800, "mobile", 6, "constrained_network"),
        (1366, 768, "desktop", 1, "unthrottled"),
        (1440, 900, "desktop", 1, "unthrottled"),
    ):
        first_limit = 2_500 if device == "mobile" else 1_500
        fps_limit = 30 if device == "mobile" else 45
        targets = {
            "first_interactive_ms": ("median", "lte", first_limit),
            "lcp_ms": ("median", "lte", 2_500),
            "interaction_proxy_ms": ("p95", "lte", 200),
            "node_selection_ms": ("p95", "lte", 100),
            "filter_ms": ("p95", "lte", 200),
            "relationship_detail_ms": ("p95", "lte", 200),
            "keyboard_focus_ms": ("p95", "lte", 100),
            "fps": ("median", "gte", fps_limit),
            "cls": ("p95", "lte", 0.1),
            "initial_image_requests": ("p95", "lte", 0),
            "initial_image_bytes": ("p95", "lte", 0),
            "initial_deferred_data_requests": ("p95", "lte", 0),
        }
        if device == "mobile":
            targets["js_heap_mb"] = ("p95", "lte", 150)
        values = {
            "first_interactive_ms": 1_000,
            "node_selection_ms": 50,
            "filter_ms": 80,
            "relationship_detail_ms": 90,
            "keyboard_focus_ms": 40,
            "fps": 50,
            "js_heap_mb": 80,
            "lcp_ms": 1_000,
            "interaction_proxy_ms": 100,
            "cls": 0.05,
            "initial_image_requests": 0,
            "initial_image_bytes": 0,
            "deferred_image_requests": 1,
            "deferred_image_bytes": 16_000,
            "initial_deferred_data_requests": 0,
            "deferred_data_requests": 3,
        }
        metrics = {
            name: measurement(values.get(name, 10), unit, targets.get(name))
            for name, unit in CURRENT_METRIC_UNITS.items()
        }
        metrics["gzip_bytes"] = {
            "unit": "bytes",
            "samples": [100_000, 100_000, 100_000],
            "median": 100_000,
            "p95": 100_000,
        }
        runs.append(
            {
                "profile_id": f"{device}-{width}x{height}",
                "viewport": {"width": width, "height": height},
                "device_class": device,
                "initial_experience": "list" if width == 360 else "graph",
                "cpu_throttle_rate": cpu,
                "network_profile": network,
                "sample_count": 3,
                "metrics": metrics,
            }
        )
    payload["runs"] = runs
    payload["overall_status"] = "pass"
    return payload


def scale_payload() -> dict[str, Any]:
    payload = common("museum-04-synthetic-scale")
    payload["environment"]["implementation_input_files"] = SCALE_IMPLEMENTATION_INPUT_FILES
    payload["environment"]["implementation_input_hash"] = implementation_input_hash()
    payload["release_performance_contract"] = {
        "path": RELEASE_PERFORMANCE_CONTRACT_PATH,
        "sha256": sha256_file(Path(__file__).resolve().parents[1] / RELEASE_PERFORMANCE_CONTRACT_PATH),
    }
    shared = {
        "synthetic": True,
        "shipped": False,
        "full_initial_render": False,
        "visible_caps": VISIBLE_CAPS,
        "governance_fields_preserved": sorted(GOVERNANCE_FIELDS),
        "sample_count": 3,
    }
    payload["profiles"] = [
        {
            **shared,
            "profile": "1k",
            "fixture_sample_hash": deterministic_sample_hash("1k"),
            "vertices": 1_000,
            "edges": 5_000,
            "actual_renderer": True,
            "renderer": "sigma@3.0.3",
            "device_class": "mobile",
            "rendering_mode": "capped_progressive",
            "visible_rendered": {"vertices": 150, "edges": 600},
            "no_crash": True,
            "interactions_pass": True,
            "metrics": {
                "first_interactive_ms": measurement(3_000, "ms", ("median", "lte", 5_000)),
                "interaction_ms": measurement(80, "ms"),
            },
        },
        {
            **shared,
            "profile": "10k",
            "fixture_sample_hash": deterministic_sample_hash("10k"),
            "vertices": 10_000,
            "edges": 60_000,
            "actual_full_renderer": False,
            "full_render_request_allowed": False,
            "partitioned_index": True,
            "search_ready": True,
            "local_neighborhood_rendered": True,
            "strategy": "partition_search_then_render_capped_neighborhood",
            "visible_rendered": {"vertices": 150, "edges": 600},
            "metrics": {
                "model_build_ms": measurement(200, "ms"),
                "index_build_ms": measurement(100, "ms"),
                "filtered_render_ms": measurement(80, "ms"),
                "js_heap_mb": measurement(100, "MB"),
            },
        },
        {
            **shared,
            "profile": "50k",
            "fixture_sample_hash": deterministic_sample_hash("50k"),
            "vertices": 50_000,
            "edges": 300_000,
            "actual_full_webgl_render": False,
            "rendered_300k_edges": False,
            "full_render_request_allowed": False,
            "safe_fallback": True,
            "no_freeze": True,
            "no_blank_page": True,
            "mobile_full_render_request": "refused",
            "strategy": "refuse_full_render_use_partition_or_list",
            "model_execution": "bounded_typed_array_model_and_chunk_plan",
            "model_facts": {
                "constructed_vertices": 50_000,
                "constructed_edges": 300_000,
                "storage_bytes": FIFTY_K_MODEL_STORAGE_BYTES,
                "checksum": "uint32:0123abcd",
            },
            "chunk_plan": {
                "vertex_chunks": 334,
                "edge_chunks": 500,
                "planned_vertices": 50_000,
                "planned_edges": 300_000,
                "max_vertices_per_chunk": 150,
                "max_edges_per_chunk": 600,
            },
            "work_slice_limit_ms": 50,
            "fallback_visible_during_work": True,
            "assertion_basis": {
                "safe_fallback": "executed_exact_model_and_bounded_plan_without_webgl",
                "no_freeze": "each_model_work_slice_at_or_below_50ms_with_frame_yields",
                "no_blank_page": "fallback_visible_before_during_and_after_model_work",
            },
            "metrics": {
                "model_build_ms": measurement(2_000, "ms"),
                "chunk_plan_ms": measurement(5, "ms"),
                "max_work_slice_ms": measurement(10, "ms", ("p95", "lte", 50)),
                "fallback_paint_ms": measurement(20, "ms"),
                "yield_count": {"unit": "count", "samples": [110, 110, 110], "median": 110, "p95": 110},
                "js_heap_mb": measurement(100, "MB"),
            },
        },
    ]
    payload["overall_status"] = "pass"
    return payload


class Museum04PerformanceEvidenceTests(unittest.TestCase):
    def test_valid_current_graph_contract_passes(self) -> None:
        self.assertIn("src/i18n/translations.ts", CURRENT_IMPLEMENTATION_INPUT_FILES)
        self.assertIn("src/preferences/PreferencesProvider.tsx", CURRENT_IMPLEMENTATION_INPUT_FILES)
        self.assertEqual([], validate_current_graph(current_payload()))

    def test_recomputed_statistics_and_hard_target_fail_closed(self) -> None:
        payload = current_payload()
        payload["runs"][0]["metrics"]["node_selection_ms"]["median"] = 999
        payload["runs"][0]["metrics"]["filter_ms"] = measurement(300, "ms", ("p95", "lte", 200))
        payload["runs"][0]["metrics"]["initial_image_requests"] = measurement(1, "count", ("p95", "lte", 0))
        payload["runs"][0]["metrics"]["initial_deferred_data_requests"] = measurement(1, "count", ("p95", "lte", 0))
        errors = validate_current_graph(payload)
        self.assertTrue(any("median must equal recomputed" in error for error in errors))
        self.assertTrue(any("hard target failed" in error for error in errors))
        self.assertTrue(any("initial_image_requests" in error for error in errors))
        self.assertTrue(any("initial_deferred_data_requests" in error for error in errors))

    def test_one_fast_fps_sample_cannot_hide_two_slow_samples(self) -> None:
        payload = current_payload()
        payload["runs"][0]["metrics"]["fps"] = {
            "unit": "fps",
            "samples": [1, 1, 31],
            "median": 1,
            "p95": 31,
            "target": {"statistic": "median", "operator": "gte", "value": 30, "passed": False},
        }
        errors = validate_current_graph(payload)
        self.assertTrue(any("fps" in error and "hard target failed" in error for error in errors))

    def test_media_delivery_summary_fails_closed(self) -> None:
        payload = current_payload()
        payload["lab_configuration"]["media_delivery"]["physical_derivative_count"] = 241
        payload["lab_configuration"]["media_delivery"]["external_runtime_api"] = True
        errors = validate_current_graph(payload)
        self.assertTrue(any("physical_derivative_count" in error for error in errors))
        self.assertTrue(any("external_runtime_api" in error for error in errors))

    def test_current_implementation_and_static_budget_binding_fail_closed(self) -> None:
        payload = current_payload()
        payload["environment"]["implementation_input_hash"] = "sha256:" + "0" * 64
        payload["lab_configuration"]["deterministic_gzip_budget"]["constellation_route_gzip_bytes"] = 99_999
        errors = validate_current_graph(payload)
        self.assertTrue(any("implementation_input_hash" in error for error in errors))
        self.assertTrue(any("must bind every sample" in error for error in errors))

    def test_valid_scale_contract_passes(self) -> None:
        self.assertEqual([], validate_scale(scale_payload()))

    def test_scale_boundaries_fail_closed(self) -> None:
        payload = scale_payload()
        payload["profiles"][1]["full_initial_render"] = True
        payload["profiles"][2]["mobile_full_render_request"] = "rendered"
        payload["profiles"][2]["rendered_300k_edges"] = True
        payload["profiles"][2]["model_facts"]["constructed_edges"] = 0
        payload["profiles"][2]["metrics"]["max_work_slice_ms"] = measurement(60, "ms", ("p95", "lte", 50))
        errors = validate_scale(payload)
        self.assertTrue(any("full_initial_render" in error for error in errors))
        self.assertTrue(any("mobile_full_render_request must be refused" in error for error in errors))
        self.assertTrue(any("rendered_300k_edges" in error for error in errors))
        self.assertTrue(any("300,000 constructed edges" in error for error in errors))
        self.assertTrue(any("hard target failed" in error for error in errors))

    def test_scale_provenance_and_release_contract_binding_fail_closed(self) -> None:
        payload = scale_payload()
        payload["environment"]["implementation_input_hash"] = "sha256:" + "0" * 64
        payload["release_performance_contract"]["sha256"] = "sha256:" + "1" * 64
        payload["profiles"][0]["rendering_mode"] = "full_initial_render"
        errors = validate_scale(payload)
        self.assertTrue(any("implementation_input_hash" in error for error in errors))
        self.assertTrue(any("release_performance_contract.sha256" in error for error in errors))
        self.assertTrue(any("does not match executed 1k scale evidence" in error for error in errors))

    def test_evidence_files_are_required_without_explicit_preflight_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            errors = validate_files(root / "current.json", root / "scale.json")
            allowed = validate_files(root / "current.json", root / "scale.json", allow_missing=True)
        self.assertEqual(2, len(errors))
        self.assertEqual([], allowed)


if __name__ == "__main__":
    unittest.main()
