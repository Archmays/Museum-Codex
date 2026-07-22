#!/usr/bin/env python3
"""Build the immutable MUSEUM-09B-UX-01 successor release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.ux_release import DEFAULT_OUTPUT, build_museum_09b_ux_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-update-ledger", action="store_true")
    args = parser.parse_args()
    result = build_museum_09b_ux_release(args.output, update_ledger=not args.no_update_ledger)
    summary = {key: value for key, value in result.items() if key != "audit"}
    summary["narrative_audit"] = {
        "status": result["audit"]["status"],
        "artist_count": result["audit"]["artist_count"],
        "banned_primary_hits": result["audit"]["banned_primary_hits"],
        "duplicate_full_intro_count": result["audit"]["duplicate_full_intro_count"],
        "template_signature_count": result["audit"]["template_signature_count"],
        "max_pair_similarity": result["audit"]["max_pair_similarity"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
