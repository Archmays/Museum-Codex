#!/usr/bin/env python3
"""Verify deployed MUSEUM-09C identity, bytes, and bounded runtime closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import verify_museum_09b_online as verifier

verifier.RELEASE_DIRECTORY = "art-expansion-batch-02-1.6.0"
verifier.RELEASE_ID = "release:art-expansion-batch-02-1.6.0"
verifier.EXPECTED_COUNTS = {
    "artists": 111,
    "artworks": 1017,
    "contexts": 352,
    "claims": 1573,
    "evidence": 1459,
    "relationships": 60,
    "episodes": 183,
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
    report["phase_id"] = "MUSEUM-09C"
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
