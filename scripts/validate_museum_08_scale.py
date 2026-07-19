#!/usr/bin/env python3
"""Validate committed MUSEUM-08 scale evidence and optional generated fixture closure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.scale_fixture import validate_scale_fixture


def validate_evidence(path: Path, fixture: Path | None = None) -> dict[str, object]:
    failures: list[str] = []
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return {"ok": False, "failures": [f"evidence:{error}"]}
    expected = {
        "scale_architecture_ready": True,
        "synthetic_scale_validated": True,
        "real_content_expansion_started": False,
        "museum_09_entered": False,
        "synthetic_artist_count": 500,
        "synthetic_artwork_count": 5000,
        "synthetic_search_record_count": 20000,
        "synthetic_relationship_count": 10000,
        "synthetic_path_index_record_count": 50000,
        "public_synthetic_leakage_count": 0,
        "status": "pass",
    }
    for key, expected_value in expected.items():
        if evidence.get(key) != expected_value:
            failures.append(f"{key}:{evidence.get(key)!r}")
    if evidence.get("byte_identical_repeat") is not True:
        failures.append("determinism")
    if evidence.get("partial_rebuild", {}).get("unrelated_bytes_unchanged") is not True:
        failures.append("partial_rebuild")
    search = evidence.get("search", {})
    if search.get("all_search_record_count") != 20000:
        failures.append("search_count")
    if not isinstance(search.get("query_p95_ms"), (int, float)) or search["query_p95_ms"] > 120:
        failures.append("query_p95")
    if search.get("first_result_found") is not True:
        failures.append("first_result")
    if fixture is not None:
        fixture_result = validate_scale_fixture(fixture)
        if not fixture_result["ok"]:
            failures.extend(f"fixture:{item}" for item in fixture_result["failures"])
    return {"ok": not failures, "failures": failures, "evidence": evidence}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs" / "qa" / "museum-08" / "scale-readiness.json")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = validate_evidence(args.evidence, args.fixture)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
