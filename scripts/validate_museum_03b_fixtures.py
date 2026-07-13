#!/usr/bin/env python3
"""Validate the complete synthetic MUSEUM-03B art-batch fixture matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.fixtures import validate_fixture_matrix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result")
    args = parser.parse_args(argv)
    result = validate_fixture_matrix(ROOT)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result["ok"]:
        print(
            "[PASS] MUSEUM-03B synthetic fixtures: "
            f"valid={result['valid_fixtures']} invalid={result['invalid_fixtures']} "
            f"behaviors={result['numbered_behaviors']}"
        )
    else:
        for failure in result["failures"]:
            print(f"[FAIL] {failure}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
