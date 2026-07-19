#!/usr/bin/env python3
"""Ensure scale-only synthetic IDs never enter public or production build bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = b"synthetic-scale:"
TEXT_SUFFIXES = {
    ".css",
    ".geojson",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def scan(paths: list[Path]) -> dict[str, object]:
    failures: list[str] = []
    checked = 0
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            checked += 1
            if MARKER in path.read_bytes():
                try:
                    relative = path.relative_to(ROOT).as_posix()
                except ValueError:
                    relative = path.as_posix()
                failures.append(relative)
    return {"ok": not failures, "checked_files": checked, "marker": MARKER.decode(), "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    targets = args.paths or [ROOT / "public", ROOT / "dist"]
    result = scan(targets)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
