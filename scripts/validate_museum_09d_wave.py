#!/usr/bin/env python3
"""Validate the MUSEUM expansion wave, release chain, and deployment marker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.expansion_wave_factory import (
    CANONICAL_REGISTRY,
    load_wave_plan,
    validate_cross_batch,
)

DEFAULT_PLAN = ROOT / "docs" / "05_roadmap" / "museum-09d-wave-01" / "release-plan.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--registry", type=Path, default=CANONICAL_REGISTRY)
    parser.add_argument("--allow-predeployment-final", action="store_true")
    args = parser.parse_args()
    plan = load_wave_plan(args.plan)
    result = validate_cross_batch(plan, args.registry)
    failures = list(result["failures"])
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in registry["batches"]}
    for batch in plan.batches[:-1]:
        record = by_id[batch.batch_id]
        if (
            record.get("status") != "published"
            or record.get("is_current_release") is not False
            or record.get("deployment_count") != 0
        ):
            failures.append(f"{batch.batch_id}: intermediate release/deployment state mismatch")
    final = by_id[plan.batches[-1].batch_id]
    if args.allow_predeployment_final:
        if (
            final.get("status") != "media_bundle_ready"
            or final.get("candidate_release", {}).get("id") != plan.final_release_id
            or final.get("deployment_count") != 0
        ):
            failures.append("final batch is not in the expected predeployment state")
    elif (
        final.get("status") != "published"
        or final.get("current_release", {}).get("id") != plan.final_release_id
        or final.get("deployment_count") != 1
    ):
        failures.append("final batch online publication state mismatch")
    marker_path = plan.deployment_marker_path
    if not marker_path.is_file():
        failures.append("final deployment marker is missing")
    else:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if (
            marker.get("release_id") != plan.final_release_id
            or marker.get("deployment_eligible") is not True
            or marker.get("intermediate_deployment_count") != 0
            or any(item.get("deployment_eligible") is not False for item in marker.get("intermediate_releases", []))
        ):
            failures.append("final-only deployment marker contract mismatch")
    result["failures"] = failures
    result["status"] = "pass" if not failures else "fail"
    result["ok"] = not failures
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
