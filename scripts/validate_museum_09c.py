#!/usr/bin/env python3
"""Validate a registry-driven MUSEUM-09C release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.expansion_batch_factory import (
    load_batch_inputs,
    validate_registry_lifecycle,
    validate_release,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_root", type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--predecessor", required=True)
    args = parser.parse_args()
    inputs = load_batch_inputs(args.batch_id)
    predecessor_root = ROOT / "public" / "releases" / args.predecessor.removeprefix("release:")
    predecessor_artists = len(json.loads((predecessor_root / "artists.json").read_text(encoding="utf-8"))["artists"])
    predecessor_artworks = len(json.loads((predecessor_root / "artworks.json").read_text(encoding="utf-8"))["artworks"])
    result = validate_release(
        args.release_root.resolve(),
        release_id=args.release_id,
        predecessor_id=args.predecessor,
        expected_artists=predecessor_artists + inputs.batch["artist_count"],
        expected_artworks=predecessor_artworks + inputs.batch["work_count"],
    )
    registry = json.loads(
        (ROOT / "governance" / "museum-09-batch-registry.json").read_text(encoding="utf-8")
    )
    result["failures"].extend(validate_registry_lifecycle(registry))
    result["ok"] = not result["failures"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
