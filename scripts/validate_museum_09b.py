#!/usr/bin/env python3
"""Validate the internal MUSEUM-09B formal-candidate package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.formal_candidate import DEFAULT_OUTPUT, validate_formal_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--wave", type=int, choices=range(1, 6))
    args = parser.parse_args()
    package = args.package.resolve()
    result = validate_formal_candidate(package)
    if args.wave and result["ok"]:
        review = json.loads(
            (package / "batch-review-summary.json").read_text(encoding="utf-8")
        )
        wave = next(item for item in review["waves"] if item["wave"] == args.wave)
        if wave["artist_count"] != 10 or wave["validation_status"] != "pass":
            result = {
                **result,
                "ok": False,
                "failures": [{
                    "code": "wave_closure",
                    "message": f"wave {args.wave} does not close 10 artists",
                    "location": "batch-review-summary.json",
                }],
            }
        else:
            result["wave"] = wave
    if args.json or not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        counts = result["counts"]
        print(
            "[PASS] MUSEUM-09B formal candidate: "
            f"artists={counts['artists']} artworks={counts['artworks']} "
            f"media={counts['media_decisions']}"
            + (f" wave={args.wave}" if args.wave else "")
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
