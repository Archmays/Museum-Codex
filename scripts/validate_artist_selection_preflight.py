#!/usr/bin/env python3
"""Validate MUSEUM-03A public contracts without reading live or private candidate data."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.curation.fixtures import evaluate_curation_invalid_fixture
from museum_pipeline.curation.decision_application import validate_committed_selection_application
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.scan_public_artifact_for_candidate_data import scan_public_artifact
from scripts.validate_governance_foundation import schema_manifest_entries


VALID = ROOT / "fixtures" / "curation" / "valid"
INVALID = ROOT / "fixtures" / "curation" / "invalid"


def validate_artist_selection_preflight(*, verbose: bool = True) -> dict:
    failures: list[str] = []
    environment = load_schema_environment()
    manifest_paths = {item["path"] for item in schema_manifest_entries(ROOT)}
    schema_paths = {path.relative_to(ROOT).as_posix() for path in (ROOT / "schemas").rglob("*.schema.json")}
    if manifest_paths != schema_paths:
        failures.append("schema_manifest_set_mismatch")
    curation_schemas = sorted(path for path in environment.by_path if path.startswith("schemas/curation/"))
    if len(curation_schemas) != 8:
        failures.append(f"curation_schema_count:{len(curation_schemas)}")

    valid_count = 0
    for path in sorted(VALID.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        issues = validate_record(record, environment=environment)
        if issues:
            failures.append(f"valid:{path.name}:{','.join(item.code for item in issues)}")
        else:
            valid_count += 1
            if verbose:
                print(f"[PASS] {path.relative_to(ROOT).as_posix()}")
    invalid_count = 0
    for path in sorted(INVALID.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        codes = evaluate_curation_invalid_fixture(case)
        if case["expected_error"] not in codes:
            failures.append(f"invalid:{path.name}:expected={case['expected_error']}:actual={','.join(sorted(codes))}")
        else:
            invalid_count += 1
            if verbose:
                print(f"[PASS] {path.relative_to(ROOT).as_posix()} (expected {case['expected_error']})")

    public_findings = scan_public_artifact(ROOT / "public")
    if public_findings:
        failures.extend(f"public:{item['code']}:{item['path']}" for item in public_findings)
    tracked = _tracked_private_paths()
    if tracked:
        failures.extend(f"tracked_private_selection_path:{path}" for path in tracked)
    workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
    if "--live" in workflow or "build-selection-pool" in workflow:
        failures.append("live_or_private_selection_in_ci")
    decision_path = ROOT / "governance" / "decisions" / "museum-03b-selection-decision.json"
    application_path = ROOT / "governance" / "decisions" / "museum-03b-selection-application.json"
    if decision_path.exists() != application_path.exists():
        failures.append("museum_03b_selection_records_incomplete")
    elif decision_path.exists():
        failures.extend(
            f"museum_03b_selection:{issue}"
            for issue in validate_committed_selection_application(decision_path, application_path)
        )

    return {
        "ok": not failures, "schemas": len(environment.by_path), "curation_schemas": len(curation_schemas),
        "valid_fixtures": valid_count, "invalid_fixtures": invalid_count, "failures": sorted(failures),
    }


def _tracked_private_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "data/raw", "data/intermediate", "data/review", "data/staging"],
        cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8",
    )
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = validate_artist_selection_preflight(verbose=not args.json)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result["ok"]:
        print(f"[PASS] MUSEUM-03A preflight: schemas={result['schemas']} curation={result['curation_schemas']} valid={result['valid_fixtures']} invalid={result['invalid_fixtures']}")
    else:
        for failure in result["failures"]:
            print(f"[FAIL] {failure}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
