#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.pathways import DEFAULT_OUTPUT, validate_museum_06_release


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the immutable MUSEUM-06 artist pathway release")
    parser.add_argument("release_root", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-public", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.require_public and args.release_root.resolve() != DEFAULT_OUTPUT.resolve():
        parser.error(f"--require-public requires {DEFAULT_OUTPUT}")
    result = validate_museum_06_release(args.release_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if result["ok"] else "FAIL")
        for item in result["failures"]:
            print(f"[{item['code']}] {item['path']}: {item['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
