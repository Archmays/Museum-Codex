from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.generate_museum_04_scale_fixture import deterministic_sample_hash
except ModuleNotFoundError:  # Direct `python scripts/...` invocation.
    from generate_museum_04_scale_fixture import deterministic_sample_hash


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT = ROOT / "docs" / "qa" / "museum-04" / "performance-current-graph.json"
DEFAULT_SCALE = ROOT / "docs" / "qa" / "museum-04" / "performance-scale-benchmarks.json"
RELEASE_PERFORMANCE_CONTRACT_PATH = "public/releases/art-constellation-0.1.0/performance-contract.json"
SCALE_IMPLEMENTATION_INPUT_FILES = [
    "benchmarks/museum-04/main.ts",
    "museum_pipeline/art/public_release.py",
    "package-lock.json",
    RELEASE_PERFORMANCE_CONTRACT_PATH,
    "schemas/art/release/art-constellation-artifact.schema.json",
    "scripts/generate_museum_04_scale_fixture.py",
    "scripts/run-museum-04-scale-lab.mjs",
    "scripts/validate_museum_04_performance_evidence.py",
]
FIFTY_K_MODEL_STORAGE_BYTES = 50_000 * 4 + 300_000 * 4 * 2
REAL_DEVICE_STATUSES = {"pass", "fail", "not_available"}
REQUIRED_ENVIRONMENT_STRINGS = (
    "host_os",
    "cpu",
    "browser",
    "browser_version",
    "node_version",
    "playwright_version",
    "runner",
    "measurement_method",
)
CURRENT_PROFILES = {
    (390, 844): {"class": "mobile", "cpu": 4, "network": "fast_4g", "experience": "graph"},
    (360, 800): {"class": "mobile", "cpu": 6, "network": "constrained_network", "experience": "list"},
    (1366, 768): {"class": "desktop", "cpu": 1, "network": "unthrottled", "experience": "graph"},
    (1440, 900): {"class": "desktop", "cpu": 1, "network": "unthrottled", "experience": "graph"},
}
CURRENT_METRIC_UNITS = {
    "route_load_ms": "ms",
    "data_load_ms": "ms",
    "chunk_load_ms": "ms",
    "first_interactive_ms": "ms",
    "node_selection_ms": "ms",
    "filter_ms": "ms",
    "relationship_detail_ms": "ms",
    "keyboard_focus_ms": "ms",
    "list_switch_ms": "ms",
    "fps": "fps",
    "js_heap_mb": "MB",
    "cls": "score",
    "long_tasks_count": "count",
    "transferred_bytes": "bytes",
    "gzip_bytes": "bytes",
    "lcp_ms": "ms",
    "interaction_proxy_ms": "ms",
}
SCALE_COUNTS = {
    "1k": (1_000, 5_000),
    "10k": (10_000, 60_000),
    "50k": (50_000, 300_000),
}
VISIBLE_CAPS = {
    "mobile": {"vertices": 150, "edges": 600},
    "desktop": {"vertices": 300, "edges": 1_200},
}
GOVERNANCE_FIELDS = {
    "evidence_level",
    "evidence_confidence",
    "curatorial_relevance",
    "historical_relationship_strength",
    "computational_similarity",
    "claim_ids",
    "evidence_ids",
    "source_ids",
    "limitations",
}


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def implementation_input_hash(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for relative_path in SCALE_IMPLEMENTATION_INPUT_FILES:
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative_path).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _error(errors: list[str], location: str, message: str) -> None:
    errors.append(f"{location}: {message}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _nearest_rank_p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _numbers_close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-3)


def _target_passes(actual: float, operator: str, value: float) -> bool:
    if operator == "lte":
        return actual <= value
    if operator == "gte":
        return actual >= value
    raise ValueError(f"unsupported operator {operator}")


def _validate_common(payload: Any, benchmark_id: str, location: str, errors: list[str]) -> None:
    if not isinstance(payload, dict):
        _error(errors, location, "root must be an object")
        return
    if payload.get("schema_version") != "1.0.0":
        _error(errors, location, "schema_version must be 1.0.0")
    if payload.get("benchmark_id") != benchmark_id:
        _error(errors, location, f"benchmark_id must be {benchmark_id}")
    if payload.get("evidence_class") != "controlled_lab_not_rum":
        _error(errors, location, "evidence_class must be controlled_lab_not_rum")
    if payload.get("real_user_metric") is not False:
        _error(errors, location, "real_user_metric must be false")
    status = payload.get("real_device_status")
    if status not in REAL_DEVICE_STATUSES:
        _error(errors, location, f"real_device_status must be one of {sorted(REAL_DEVICE_STATUSES)}")
    if status == "not_available" and not str(payload.get("real_device_note", "")).strip():
        _error(errors, location, "real_device_note is required when real_device_status is not_available")
    captured_at = payload.get("captured_at")
    if not isinstance(captured_at, str):
        _error(errors, location, "captured_at must be an ISO-8601 string")
    else:
        try:
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            _error(errors, location, "captured_at must be a valid ISO-8601 timestamp")

    environment = payload.get("environment")
    if not isinstance(environment, dict):
        _error(errors, location, "environment must be an object")
        return
    for field in REQUIRED_ENVIRONMENT_STRINGS:
        if not isinstance(environment.get(field), str) or not environment[field].strip():
            _error(errors, f"{location}.environment.{field}", "must be a non-empty string")
    if not re.fullmatch(r"[0-9a-f]{40}", str(environment.get("commit_sha", ""))):
        _error(errors, f"{location}.environment.commit_sha", "must be a 40-character lowercase Git SHA")
    if not isinstance(environment.get("source_worktree_dirty"), bool):
        _error(errors, f"{location}.environment.source_worktree_dirty", "must be a boolean")
    if not _is_number(environment.get("memory_gb")) or environment["memory_gb"] <= 0:
        _error(errors, f"{location}.environment.memory_gb", "must be a positive finite number")


def _validate_measurement(
    measurement: Any,
    location: str,
    errors: list[str],
    *,
    sample_count: int,
    unit: str,
    required_target: tuple[str, str, float] | None = None,
) -> None:
    if not isinstance(measurement, dict):
        _error(errors, location, "must be an object")
        return
    if measurement.get("unit") != unit:
        _error(errors, location, f"unit must be {unit}")
    raw_samples = measurement.get("samples")
    if not isinstance(raw_samples, list) or len(raw_samples) != sample_count:
        _error(errors, location, f"samples must contain exactly sample_count={sample_count} values")
        return
    if any(not _is_number(value) or value < 0 for value in raw_samples):
        _error(errors, location, "samples must be finite non-negative numbers")
        return
    samples = [float(value) for value in raw_samples]
    expected_median = float(statistics.median(samples))
    expected_p95 = float(_nearest_rank_p95(samples))
    reported_median = measurement.get("median")
    reported_p95 = measurement.get("p95")
    if not _is_number(reported_median) or not _numbers_close(float(reported_median), expected_median):
        _error(errors, location, f"median must equal recomputed median {expected_median:g}")
    if not _is_number(reported_p95) or not _numbers_close(float(reported_p95), expected_p95):
        _error(errors, location, f"p95 must equal nearest-rank p95 {expected_p95:g}")

    target = measurement.get("target")
    if required_target is None and target is None:
        return
    if not isinstance(target, dict):
        _error(errors, location, "target must be an object")
        return
    statistic_name = target.get("statistic")
    operator = target.get("operator")
    value = target.get("value")
    if statistic_name not in {"median", "p95"}:
        _error(errors, location, "target.statistic must be median or p95")
        return
    if operator not in {"lte", "gte"}:
        _error(errors, location, "target.operator must be lte or gte")
        return
    if not _is_number(value):
        _error(errors, location, "target.value must be a finite number")
        return
    if required_target is not None:
        expected_statistic, expected_operator, expected_value = required_target
        if (statistic_name, operator) != (expected_statistic, expected_operator) or not _numbers_close(
            float(value), float(expected_value)
        ):
            _error(
                errors,
                location,
                f"target must be {expected_statistic} {expected_operator} {expected_value:g}",
            )
    actual = expected_median if statistic_name == "median" else expected_p95
    evaluated = _target_passes(actual, operator, float(value))
    if target.get("passed") is not evaluated:
        _error(errors, location, f"target.passed must be {str(evaluated).lower()}")
    if not evaluated:
        _error(errors, location, f"hard target failed: {actual:g} {operator} {float(value):g}")


def validate_current_graph(payload: Any) -> list[str]:
    errors: list[str] = []
    location = "current_graph"
    _validate_common(payload, "museum-04-current-graph", location, errors)
    if not isinstance(payload, dict):
        return errors
    runs = payload.get("runs")
    if not isinstance(runs, list):
        _error(errors, location, "runs must be an array")
        return errors
    found: dict[tuple[int, int], dict[str, Any]] = {}
    for index, run in enumerate(runs):
        run_location = f"{location}.runs[{index}]"
        if not isinstance(run, dict):
            _error(errors, run_location, "must be an object")
            continue
        viewport = run.get("viewport")
        if not isinstance(viewport, dict) or not isinstance(viewport.get("width"), int) or not isinstance(
            viewport.get("height"), int
        ):
            _error(errors, run_location, "viewport must contain integer width and height")
            continue
        key = (viewport["width"], viewport["height"])
        if key in found:
            _error(errors, run_location, f"duplicate viewport {key[0]}x{key[1]}")
            continue
        found[key] = run
        expected = CURRENT_PROFILES.get(key)
        if expected is None:
            _error(errors, run_location, f"unexpected viewport {key[0]}x{key[1]}")
            continue
        if run.get("device_class") != expected["class"]:
            _error(errors, run_location, f"device_class must be {expected['class']}")
        if run.get("cpu_throttle_rate") != expected["cpu"]:
            _error(errors, run_location, f"cpu_throttle_rate must be {expected['cpu']}")
        if run.get("network_profile") != expected["network"]:
            _error(errors, run_location, f"network_profile must be {expected['network']}")
        if run.get("initial_experience") != expected["experience"]:
            _error(errors, run_location, f"initial_experience must be {expected['experience']}")
        sample_count = run.get("sample_count")
        if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 3:
            _error(errors, run_location, "sample_count must be an integer >= 3")
            continue
        metrics = run.get("metrics")
        if not isinstance(metrics, dict):
            _error(errors, run_location, "metrics must be an object")
            continue
        first_interactive_limit = 2_500 if expected["class"] == "mobile" else 1_500
        fps_limit = 30 if expected["class"] == "mobile" else 45
        targets: dict[str, tuple[str, str, float]] = {
            "first_interactive_ms": ("median", "lte", first_interactive_limit),
            "lcp_ms": ("median", "lte", 2_500),
            "interaction_proxy_ms": ("p95", "lte", 200),
            "node_selection_ms": ("p95", "lte", 100),
            "filter_ms": ("p95", "lte", 200),
            "relationship_detail_ms": ("p95", "lte", 200),
            "keyboard_focus_ms": ("p95", "lte", 100),
            "fps": ("p95", "gte", fps_limit),
            "cls": ("p95", "lte", 0.1),
        }
        if expected["class"] == "mobile":
            targets["js_heap_mb"] = ("p95", "lte", 150)
        for metric_name, unit in CURRENT_METRIC_UNITS.items():
            _validate_measurement(
                metrics.get(metric_name),
                f"{run_location}.metrics.{metric_name}",
                errors,
                sample_count=sample_count,
                unit=unit,
                required_target=targets.get(metric_name),
            )
    missing = sorted(set(CURRENT_PROFILES) - set(found))
    if missing:
        _error(errors, location, f"missing required viewports: {', '.join(f'{w}x{h}' for w, h in missing)}")
    if payload.get("overall_status") != "pass":
        _error(errors, location, "overall_status must be pass for the hard gate")
    return errors


def _validate_visible_caps(value: Any, location: str, errors: list[str]) -> None:
    if value != VISIBLE_CAPS:
        _error(errors, location, f"must equal {VISIBLE_CAPS}")


def _validate_rendered_cap(value: Any, location: str, errors: list[str], device: str = "mobile") -> None:
    if not isinstance(value, dict):
        _error(errors, location, "must be an object")
        return
    for key in ("vertices", "edges"):
        count = value.get(key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > VISIBLE_CAPS[device][key]:
            _error(errors, f"{location}.{key}", f"must be an integer from 0 to {VISIBLE_CAPS[device][key]}")


def _require_true(profile: dict[str, Any], field: str, location: str, errors: list[str]) -> None:
    if profile.get(field) is not True:
        _error(errors, f"{location}.{field}", "must be true")


def _require_false(profile: dict[str, Any], field: str, location: str, errors: list[str]) -> None:
    if profile.get(field) is not False:
        _error(errors, f"{location}.{field}", "must be false")


def _validate_scale_provenance(payload: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    location = "scale"
    environment = payload.get("environment")
    if not isinstance(environment, dict):
        return None
    if environment.get("implementation_input_files") != SCALE_IMPLEMENTATION_INPUT_FILES:
        _error(
            errors,
            f"{location}.environment.implementation_input_files",
            f"must equal the exact ordered scale inputs {SCALE_IMPLEMENTATION_INPUT_FILES}",
        )
    expected_implementation_hash = implementation_input_hash()
    if environment.get("implementation_input_hash") != expected_implementation_hash:
        _error(
            errors,
            f"{location}.environment.implementation_input_hash",
            f"must equal current exact scale input hash {expected_implementation_hash}",
        )

    binding = payload.get("release_performance_contract")
    if not isinstance(binding, dict):
        _error(errors, f"{location}.release_performance_contract", "must be an object")
        return None
    if binding.get("path") != RELEASE_PERFORMANCE_CONTRACT_PATH:
        _error(
            errors,
            f"{location}.release_performance_contract.path",
            f"must equal {RELEASE_PERFORMANCE_CONTRACT_PATH}",
        )
    contract_path = ROOT / RELEASE_PERFORMANCE_CONTRACT_PATH
    try:
        expected_hash = sha256_file(contract_path)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _error(errors, f"{location}.release_performance_contract", f"cannot load canonical contract: {error}")
        return None
    if binding.get("sha256") != expected_hash:
        _error(
            errors,
            f"{location}.release_performance_contract.sha256",
            f"must equal canonical contract hash {expected_hash}",
        )
    return contract


def _cross_validate_release_contract(
    contract: dict[str, Any] | None,
    profiles: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if contract is None:
        return
    location = "scale.release_performance_contract"
    budgets = contract.get("budgets")
    if not isinstance(budgets, dict):
        _error(errors, location, "canonical contract budgets must be an object")
        return
    if (
        budgets.get("mobile_visible_vertices_max") != VISIBLE_CAPS["mobile"]["vertices"]
        or budgets.get("mobile_visible_edges_max") != VISIBLE_CAPS["mobile"]["edges"]
    ):
        _error(errors, location, "canonical mobile visible budgets must equal 150 vertices / 600 edges")
    boundaries = contract.get("scale_boundaries")
    if not isinstance(boundaries, dict):
        _error(errors, location, "canonical contract scale_boundaries must be an object")
        return
    expected_one_k = {
        "vertices": 1_000,
        "edges": 5_000,
        "full_initial_render": False,
        "rendering_mode": "capped_progressive",
        "initial_visible_vertices": 150,
        "initial_visible_edges": 600,
    }
    if boundaries.get("one_k") != expected_one_k:
        _error(errors, f"{location}.scale_boundaries.one_k", f"must equal {expected_one_k}")
    one_k = profiles.get("1k")
    if one_k is not None:
        rendered = one_k.get("visible_rendered")
        if (
            one_k.get("vertices") != expected_one_k["vertices"]
            or one_k.get("edges") != expected_one_k["edges"]
            or one_k.get("full_initial_render") is not expected_one_k["full_initial_render"]
            or one_k.get("rendering_mode") != expected_one_k["rendering_mode"]
            or rendered != {
                "vertices": expected_one_k["initial_visible_vertices"],
                "edges": expected_one_k["initial_visible_edges"],
            }
        ):
            _error(errors, f"{location}.scale_boundaries.one_k", "does not match executed 1k scale evidence")
    ten_k = profiles.get("10k")
    if ten_k is not None and boundaries.get("ten_k") != {
        "vertices": ten_k.get("vertices"),
        "edges": ten_k.get("edges"),
        "full_initial_render": ten_k.get("full_initial_render"),
    }:
        _error(errors, f"{location}.scale_boundaries.ten_k", "does not match executed 10k scale evidence")
    fifty_k = profiles.get("50k")
    if fifty_k is not None and boundaries.get("fifty_k") != {
        "vertices": fifty_k.get("vertices"),
        "edges": fifty_k.get("edges"),
        "mobile_full_render": fifty_k.get("mobile_full_render_request"),
    }:
        _error(errors, f"{location}.scale_boundaries.fifty_k", "does not match executed 50k scale evidence")


def validate_scale(payload: Any) -> list[str]:
    errors: list[str] = []
    location = "scale"
    _validate_common(payload, "museum-04-synthetic-scale", location, errors)
    if not isinstance(payload, dict):
        return errors
    release_contract = _validate_scale_provenance(payload, errors)
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        _error(errors, location, "profiles must be an array")
        return errors
    found: dict[str, dict[str, Any]] = {}
    for index, profile in enumerate(profiles):
        profile_location = f"{location}.profiles[{index}]"
        if not isinstance(profile, dict):
            _error(errors, profile_location, "must be an object")
            continue
        name = profile.get("profile")
        if name not in SCALE_COUNTS:
            _error(errors, profile_location, f"profile must be one of {sorted(SCALE_COUNTS)}")
            continue
        if name in found:
            _error(errors, profile_location, f"duplicate profile {name}")
            continue
        found[name] = profile
        expected_vertices, expected_edges = SCALE_COUNTS[name]
        if profile.get("vertices") != expected_vertices or profile.get("edges") != expected_edges:
            _error(errors, profile_location, f"counts must be {expected_vertices} vertices / {expected_edges} edges")
        _require_true(profile, "synthetic", profile_location, errors)
        _require_false(profile, "shipped", profile_location, errors)
        _require_false(profile, "full_initial_render", profile_location, errors)
        _validate_visible_caps(profile.get("visible_caps"), f"{profile_location}.visible_caps", errors)
        fields = profile.get("governance_fields_preserved")
        if not isinstance(fields, list) or not GOVERNANCE_FIELDS.issubset(set(fields)):
            _error(errors, profile_location, f"governance_fields_preserved must include {sorted(GOVERNANCE_FIELDS)}")
        expected_hash = deterministic_sample_hash(name)
        if profile.get("fixture_sample_hash") != expected_hash:
            _error(errors, profile_location, f"fixture_sample_hash must equal deterministic generator hash {expected_hash}")
        sample_count = profile.get("sample_count")
        if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 3:
            _error(errors, profile_location, "sample_count must be an integer >= 3")
            continue
        metrics = profile.get("metrics")
        if not isinstance(metrics, dict):
            _error(errors, profile_location, "metrics must be an object")
            continue

        if name == "1k":
            _require_true(profile, "actual_renderer", profile_location, errors)
            _require_true(profile, "no_crash", profile_location, errors)
            _require_true(profile, "interactions_pass", profile_location, errors)
            if profile.get("renderer") != "sigma@3.0.3":
                _error(errors, profile_location, "renderer must be sigma@3.0.3")
            if profile.get("device_class") != "mobile":
                _error(errors, profile_location, "device_class must be mobile")
            if profile.get("rendering_mode") != "capped_progressive":
                _error(errors, profile_location, "rendering_mode must be capped_progressive")
            _validate_rendered_cap(profile.get("visible_rendered"), f"{profile_location}.visible_rendered", errors)
            if profile.get("visible_rendered") != {"vertices": 150, "edges": 600}:
                _error(errors, f"{profile_location}.visible_rendered", "must equal the executed 150 vertex / 600 edge initial render")
            _validate_measurement(
                metrics.get("first_interactive_ms"),
                f"{profile_location}.metrics.first_interactive_ms",
                errors,
                sample_count=sample_count,
                unit="ms",
                required_target=("median", "lte", 5_000),
            )
            _validate_measurement(
                metrics.get("interaction_ms"),
                f"{profile_location}.metrics.interaction_ms",
                errors,
                sample_count=sample_count,
                unit="ms",
            )
        elif name == "10k":
            _require_false(profile, "actual_full_renderer", profile_location, errors)
            _require_false(profile, "full_render_request_allowed", profile_location, errors)
            for field in ("partitioned_index", "search_ready", "local_neighborhood_rendered"):
                _require_true(profile, field, profile_location, errors)
            if profile.get("strategy") != "partition_search_then_render_capped_neighborhood":
                _error(errors, profile_location, "strategy must partition/search before a capped neighborhood render")
            _validate_rendered_cap(profile.get("visible_rendered"), f"{profile_location}.visible_rendered", errors)
            for metric_name, unit in (
                ("model_build_ms", "ms"),
                ("index_build_ms", "ms"),
                ("filtered_render_ms", "ms"),
                ("js_heap_mb", "MB"),
            ):
                _validate_measurement(
                    metrics.get(metric_name),
                    f"{profile_location}.metrics.{metric_name}",
                    errors,
                    sample_count=sample_count,
                    unit=unit,
                )
        else:
            _require_false(profile, "actual_full_webgl_render", profile_location, errors)
            _require_false(profile, "rendered_300k_edges", profile_location, errors)
            _require_false(profile, "full_render_request_allowed", profile_location, errors)
            for field in ("safe_fallback", "no_freeze", "no_blank_page"):
                _require_true(profile, field, profile_location, errors)
            if profile.get("mobile_full_render_request") != "refused":
                _error(errors, profile_location, "mobile_full_render_request must be refused")
            if profile.get("strategy") != "refuse_full_render_use_partition_or_list":
                _error(errors, profile_location, "strategy must refuse full render and use partition or list")
            if profile.get("model_execution") != "bounded_typed_array_model_and_chunk_plan":
                _error(errors, profile_location, "model_execution must record the executed bounded model and chunk plan")
            model_facts = profile.get("model_facts")
            if not isinstance(model_facts, dict):
                _error(errors, f"{profile_location}.model_facts", "must be an object")
            else:
                if model_facts.get("constructed_vertices") != 50_000 or model_facts.get("constructed_edges") != 300_000:
                    _error(errors, f"{profile_location}.model_facts", "must record 50,000 constructed vertices / 300,000 constructed edges")
                if model_facts.get("storage_bytes") != FIFTY_K_MODEL_STORAGE_BYTES:
                    _error(errors, f"{profile_location}.model_facts.storage_bytes", f"must equal {FIFTY_K_MODEL_STORAGE_BYTES}")
                if not re.fullmatch(r"uint32:[0-9a-f]{8}", str(model_facts.get("checksum", ""))):
                    _error(errors, f"{profile_location}.model_facts.checksum", "must be a deterministic uint32 checksum")
            expected_chunk_plan = {
                "vertex_chunks": 334,
                "edge_chunks": 500,
                "planned_vertices": 50_000,
                "planned_edges": 300_000,
                "max_vertices_per_chunk": 150,
                "max_edges_per_chunk": 600,
            }
            if profile.get("chunk_plan") != expected_chunk_plan:
                _error(errors, f"{profile_location}.chunk_plan", f"must equal {expected_chunk_plan}")
            if profile.get("work_slice_limit_ms") != 50:
                _error(errors, f"{profile_location}.work_slice_limit_ms", "must equal 50")
            _require_true(profile, "fallback_visible_during_work", profile_location, errors)
            expected_basis = {
                "safe_fallback": "executed_exact_model_and_bounded_plan_without_webgl",
                "no_freeze": "each_model_work_slice_at_or_below_50ms_with_frame_yields",
                "no_blank_page": "fallback_visible_before_during_and_after_model_work",
            }
            if profile.get("assertion_basis") != expected_basis:
                _error(errors, f"{profile_location}.assertion_basis", "must bind pass assertions to executed work")
            for metric_name, unit, required_target in (
                ("model_build_ms", "ms", None),
                ("chunk_plan_ms", "ms", None),
                ("max_work_slice_ms", "ms", ("p95", "lte", 50)),
                ("fallback_paint_ms", "ms", None),
                ("yield_count", "count", None),
                ("js_heap_mb", "MB", None),
            ):
                _validate_measurement(
                    metrics.get(metric_name),
                    f"{profile_location}.metrics.{metric_name}",
                    errors,
                    sample_count=sample_count,
                    unit=unit,
                    required_target=required_target,
                )
            yield_measurement = metrics.get("yield_count")
            if isinstance(yield_measurement, dict) and yield_measurement.get("samples") != [110] * sample_count:
                _error(errors, f"{profile_location}.metrics.yield_count", "every sample must record 110 bounded frame yields")
    missing = sorted(set(SCALE_COUNTS) - set(found))
    if missing:
        _error(errors, location, f"missing required profiles: {', '.join(missing)}")
    _cross_validate_release_contract(release_contract, found, errors)
    if payload.get("overall_status") != "pass":
        _error(errors, location, "overall_status must be pass for the hard gate")
    return errors


def _load(path: Path, allow_missing: bool, label: str) -> tuple[Any | None, list[str]]:
    if not path.is_file():
        if allow_missing:
            print(f"[museum-04-performance] SKIP {label}: {path} is absent (--allow-missing)")
            return None, []
        return None, [f"{label}: required evidence file is missing: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"{label}: cannot read valid JSON from {path}: {error}"]


def validate_files(current_path: Path, scale_path: Path, allow_missing: bool = False) -> list[str]:
    errors: list[str] = []
    current, load_errors = _load(current_path, allow_missing, "current_graph")
    errors.extend(load_errors)
    if current is not None:
        errors.extend(validate_current_graph(current))
    scale, load_errors = _load(scale_path, allow_missing, "scale")
    errors.extend(load_errors)
    if scale is not None:
        errors.extend(validate_scale(scale))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate committed MUSEUM-04 controlled-lab performance evidence")
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--scale", type=Path, default=DEFAULT_SCALE)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow absent evidence during preflight only; CI must invoke the command without this flag.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_files(args.current.resolve(), args.scale.resolve(), args.allow_missing)
    if errors:
        print("\n".join(f"[museum-04-performance] FAIL {error}" for error in errors))
        return 1
    print("[museum-04-performance] PASS current graph and 1k/10k/50k benchmark evidence contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
