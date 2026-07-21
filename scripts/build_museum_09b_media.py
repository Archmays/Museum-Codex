#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.media_bundle import (
    DEFAULT_BUNDLE_ROOT,
    acquire,
    build_bundle,
    update_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire and build the MUSEUM-09B-MEDIA Batch 01 internal bundle")
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--acquire", action="store_true", help="perform bounded official-source checks and eligible downloads")
    parser.add_argument("--force-network", action="store_true", help="ignore existing object review cache")
    parser.add_argument(
        "--force-source",
        action="append",
        default=[],
        choices=["aic_api", "cleveland_open_access"],
        help="ignore the review cache for one source only",
    )
    parser.add_argument("--force-derivatives", action="store_true", help="re-encode instead of reusing verified derivatives")
    parser.add_argument("--reuse-bundle", type=Path, help="reuse verified derivative bytes from an existing internal bundle")
    parser.add_argument("--update-registry", action="store_true", help="promote Batch 01 after package validation")
    args = parser.parse_args()

    result: dict[str, object] = {}
    if args.acquire:
        result["acquisition"] = acquire(
            force_network=args.force_network,
            force_sources=args.force_source,
        )["metrics"]
    result["build"] = build_bundle(
        args.output,
        force_derivatives=args.force_derivatives,
        reuse_bundle=args.reuse_bundle,
    )
    if args.update_registry:
        result["registry"] = update_registry(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
