#!/usr/bin/env python3
"""Materialize the current art release's sealed media graph into a site artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.expansion_batch_factory import materialize_current_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--release-root",
        type=Path,
        default=ROOT / "public" / "releases" / "art-expansion-batch-05-1.9.0",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    result = materialize_current_release(args.output.resolve(), args.release_root.resolve())
    output = result if args.verbose else {key: value for key, value in result.items() if key != "records"}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
