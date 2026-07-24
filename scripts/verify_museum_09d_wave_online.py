#!/usr/bin/env python3
"""Verify deployed MUSEUM-09D-WAVE-01 identity, bytes, and runtime closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import verify_museum_09b_online as verifier

verifier.RELEASE_DIRECTORY = "art-expansion-batch-05-1.9.0"
verifier.RELEASE_ID = "release:art-expansion-batch-05-1.9.0"
verifier.PHASE_ID = "MUSEUM-09D-WAVE-01"
verifier.PROBE_LABEL = "museum09d_wave_01"
verifier.EXPECTED_COUNTS = {
    "artists": 258,
    "artworks": 2471,
    "contexts": 828,
    "claims": 3321,
    "evidence": 3207,
    "relationships": 60,
    "episodes": 400,
    "tours": 18,
    "new_media_originals": 0,
    "new_media_derivatives": 0,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verifier.verify_online(args.base_url, args.commit)
    report["phase_id"] = verifier.PHASE_ID
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
