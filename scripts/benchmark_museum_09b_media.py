#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.media_bundle import benchmark_bundle_builds


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark clean deterministic MUSEUM-09B-MEDIA builds")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    result = benchmark_bundle_builds(runs=args.runs)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["deterministic_package_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
