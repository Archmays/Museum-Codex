#!/usr/bin/env python3
"""Build the internal MUSEUM-09B Batch 01 formal-candidate overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.formal_candidate import (
    DEFAULT_OUTPUT,
    DEFAULT_REFRESH_RECEIPT,
    build_formal_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_REFRESH_RECEIPT)
    parser.add_argument("--verify-deterministic", action="store_true")
    parser.add_argument("--no-promote-registry", action="store_true")
    args = parser.parse_args()
    result = build_formal_candidate(
        args.output.resolve(),
        receipt_path=args.receipt.resolve(),
        verify_deterministic=args.verify_deterministic,
        promote_registry=not args.no_promote_registry,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
