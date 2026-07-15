#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.public_release import DEFAULT_OUTPUT, validate_museum_04_release


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the formal media-aware MUSEUM-04 public release")
    parser.add_argument("release_root", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-public",
        action="store_true",
        help="Require the immutable publishable/public release profile",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_museum_04_release(args.release_root, require_public=args.require_public)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        counts = result["counts"]
        profile = "formal public release"
        print(f"[PASS] MUSEUM-04 {profile}: artists={counts.get('artists')} contexts={counts.get('contexts')} relationships={counts.get('relationships')} media={counts.get('media')}")
    else:
        for failure in result["failures"]:
            print(f"[FAIL] {failure['code']}: {failure['message']} ({failure['path']})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
