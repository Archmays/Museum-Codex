#!/usr/bin/env python3
"""Build the tracked, non-public MUSEUM-09A global expansion candidate package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.global_expansion import DEFAULT_OUTPUT, build_global_expansion


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    result = build_global_expansion(
        args.output.resolve(),
        verify_deterministic=args.verify_deterministic,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
