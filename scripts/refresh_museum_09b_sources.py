#!/usr/bin/env python3
"""Run the bounded metadata-only MUSEUM-09B source refresh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.formal_candidate import (
    DEFAULT_REFRESH_RECEIPT,
    refresh_source_records,
    reuse_sealed_source_receipt,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_REFRESH_RECEIPT)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--reuse-sealed",
        type=Path,
        help="last complete source-drift manifest to reuse after the current receipt records a bounded transport failure",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.reuse_sealed:
        result = reuse_sealed_source_receipt(
            args.reuse_sealed.resolve(),
            output,
            output,
        )
    else:
        result = refresh_source_records(output, timeout_seconds=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
