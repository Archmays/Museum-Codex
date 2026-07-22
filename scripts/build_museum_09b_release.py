#!/usr/bin/env python3
"""Build the immutable MUSEUM-09B-RELEASE overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.release_expansion import DEFAULT_OUTPUT, build_museum_09b_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-update-ledger", action="store_true")
    args = parser.parse_args()
    result = build_museum_09b_release(args.output, update_ledger=not args.no_update_ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
