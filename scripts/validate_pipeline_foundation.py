#!/usr/bin/env python3
"""Validate MUSEUM-02 schemas, adapters, fixtures, and recorded contract responses offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.adapters import get_adapter
from museum_pipeline.adapters.base import ResponseContract
from museum_pipeline.source_registry import REFERENCE_SOURCE_IDS, verify_sources
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from museum_pipeline.validation.fixtures import evaluate_invalid_fixture, validate_recorded_fixture_directory


VALID = ROOT / "fixtures" / "pipeline" / "valid"
INVALID = ROOT / "fixtures" / "pipeline" / "invalid"
RECORDED = ROOT / "fixtures" / "pipeline" / "recorded"
ADAPTER_FIXTURES = {
    "adapter-wikidata-response.json": "wikidata",
    "adapter-getty-ulan-response.json": "getty_ulan",
    "adapter-met-response.json": "met_open_access",
    "adapter-aic-response.json": "aic_api",
}


def validate_pipeline_foundation(*, allow_missing_recorded: bool = False, verbose: bool = True) -> dict[str, object]:
    failures: list[str] = []
    environment = load_schema_environment()
    source_result = verify_sources()
    failures.extend(f"source:{issue}" for issue in source_result["issues"])

    valid_count = 0
    for path in sorted(VALID.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if path.name in ADAPTER_FIXTURES:
            source_id = ADAPTER_FIXTURES[path.name]
            adapter = get_adapter(source_id)
            body = path.read_bytes()
            response = ResponseContract(200, {"content-type": "application/json"}, body, adapter.build_request("Q42" if source_id == "wikidata" else "500115493" if source_id == "getty_ulan" else "1" if source_id == "met_open_access" else "27992").url)
            try:
                parsed = adapter.validate_response_contract(response)
                candidate = adapter.normalize(parsed, snapshot_id=f"snapshot:{source_id}:fixture", observed_at="2026-07-12T00:00:00Z")
                issues = validate_record(candidate, environment=environment)
            except Exception as error:  # surfaced as a fixture failure below
                failures.append(f"valid:{path.name}:{type(error).__name__}")
                continue
            if issues:
                failures.append(f"valid:{path.name}:{','.join(sorted({item.code for item in issues}))}")
                continue
        else:
            issues = validate_record(document, environment=environment)
            if issues:
                failures.append(f"valid:{path.name}:{','.join(sorted({item.code for item in issues}))}")
                continue
        valid_count += 1
        if verbose:
            print(f"[PASS] {path.relative_to(ROOT).as_posix()}")

    invalid_count = 0
    for path in sorted(INVALID.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        codes = evaluate_invalid_fixture(case)
        if case["expected_error"] not in codes:
            failures.append(f"invalid:{path.name}:expected={case['expected_error']}:actual={sorted(codes)}")
            continue
        invalid_count += 1
        if verbose:
            print(f"[PASS] {path.relative_to(ROOT).as_posix()} (expected {case['expected_error']})")

    recorded_count = 0
    recorded_dirs = sorted(path for path in RECORDED.iterdir() if path.is_dir()) if RECORDED.exists() else []
    if not recorded_dirs and not allow_missing_recorded:
        failures.append("recorded:missing")
    for directory in recorded_dirs:
        issues = validate_recorded_fixture_directory(directory)
        if issues:
            failures.append(f"recorded:{directory.name}:{','.join(issues)}")
            continue
        recorded_count += 1
        if verbose:
            print(f"[PASS] {directory.relative_to(ROOT).as_posix()}")
    if recorded_dirs and {path.name for path in recorded_dirs} != REFERENCE_SOURCE_IDS:
        failures.append("recorded:source_set_mismatch")

    result = {
        "ok": not failures,
        "schemas": len(environment.by_path),
        "valid_fixtures": valid_count,
        "invalid_fixtures": invalid_count,
        "recorded_fixtures": recorded_count,
        "adapter_contracts": len(REFERENCE_SOURCE_IDS),
        "failures": sorted(failures),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing-recorded", action="store_true", help="bootstrap-only: validate synthetic contracts before the first controlled live probes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = validate_pipeline_foundation(allow_missing_recorded=args.allow_missing_recorded, verbose=not args.json)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result["ok"]:
        print(f"[PASS] pipeline foundation: schemas={result['schemas']} valid={result['valid_fixtures']} invalid={result['invalid_fixtures']} recorded={result['recorded_fixtures']} adapters={result['adapter_contracts']}")
    else:
        for failure in result["failures"]:
            print(f"[FAIL] {failure}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
