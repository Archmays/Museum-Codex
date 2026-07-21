#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.media_bundle import DEFAULT_BUNDLE_ROOT, validate_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the MUSEUM-09B-MEDIA Batch 01 internal bundle")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--skip-registry", action="store_true")
    args = parser.parse_args()
    result = validate_bundle(args.bundle, validate_registry=not args.skip_registry)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
