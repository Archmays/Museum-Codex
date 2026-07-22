#!/usr/bin/env python3
"""Materialize reviewed Batch 01 derivatives into a production artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.release_expansion import materialize_museum_09b_media


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--verbose", action="store_true", help="Include the per-file materialization records in stdout.")
    args = parser.parse_args()
    result = materialize_museum_09b_media(args.output.resolve())
    output = result if args.verbose else {key: value for key, value in result.items() if key != "records"}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
