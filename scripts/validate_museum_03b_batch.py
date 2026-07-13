#!/usr/bin/env python3
"""Validate the sealed, internal MUSEUM-03B reviewed art package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.batch_validation import DEFAULT_PACKAGE, validate_approved_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", nargs="?", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = validate_approved_batch(args.package_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result["ok"]:
        counts = result["counts"]
        print(
            "[PASS] MUSEUM-03B reviewed package: "
            f"artists={counts['artists']} artworks={counts['artworks']} "
            f"contexts={counts['contexts']} relationships={counts['relationships']}"
        )
    else:
        for failure in result["failures"]:
            print(
                f"[FAIL] {failure['code']} {failure['location']}: {failure['message']}",
                file=sys.stderr,
            )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

