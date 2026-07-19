#!/usr/bin/env python3
"""Generate and benchmark the fixed-seed, non-public MUSEUM-08 scale fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.scale_fixture import DEFAULT_OUTPUT, generate_scale_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs" / "qa" / "museum-08" / "scale-readiness.json")
    args = parser.parse_args()
    evidence = generate_scale_evidence(args.output)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_bytes(
        (json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
