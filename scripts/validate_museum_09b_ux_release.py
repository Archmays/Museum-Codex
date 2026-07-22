#!/usr/bin/env python3
"""Validate the immutable MUSEUM-09B-UX-01 successor release and copy audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.ux_release import DEFAULT_OUTPUT, validate_museum_09b_ux_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_root", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    result = validate_museum_09b_ux_release(args.release_root)
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(result.get("audit", {}), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    public_result = {key: value for key, value in result.items() if key != "audit"}
    print(json.dumps(public_result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
