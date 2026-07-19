#!/usr/bin/env python3
"""Block current-release entity counts from shared runtime and governance code."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CURRENT_COUNTS = {
    "artist": {12},
    "artwork": {44},
    "context": {31},
    "media": {31},
    "no_image": {13},
    "observation": {44},
    "relationship": {36},
    "tour": {18},
    "path": {198},
    "place": {23},
    "episode": {36},
}
ENTITY_TOKEN = (
    r"artist(?:s|Count|_count)?|artwork(?:s|Count|_count)?|context(?:s|Count|_count)?|"
    r"media(?:Count|_count)?|no[_ -]?image(?:Count|_count)?|observation(?:s|Count|_count)?|"
    r"relationship(?:s|Count|_count)?|tour(?:s|Count|_count)?|path(?:s|Count|_count)?|"
    r"place(?:s|Count|_count)?|episode(?:s|Count|_count)?"
)
ALL_VALUES = "|".join(str(value) for values in CURRENT_COUNTS.values() for value in sorted(values))
SEMANTIC_PATTERNS = (
    re.compile(
        rf"(?i)\b(?:{ENTITY_TOKEN})\b[^\n]{{0,36}}"
        rf"(?:===?|!==?|<=?|>=?|:)\s*(?:as\s+const\s*)?(?:{ALL_VALUES})\b"
    ),
    re.compile(rf"(?i)\b(?:{ALL_VALUES})\s+(?:{ENTITY_TOKEN})\b"),
    re.compile(r"\b(?:12|十二)\s*位?艺术家\b"),
    re.compile(r"\b(?:44|四十四)\s*件?作品\b"),
    re.compile(r"(?i)\b(?:12|twelve)\s+artists?\b"),
    re.compile(r"(?i)\b(?:44|forty[- ]?four)\s+artworks?\b"),
    re.compile(r"(?i)\b(?:31|thirty[- ]?one)\s+(?:contexts?|media|places?)\b"),
    re.compile(r"(?i)\b(?:36|thirty[- ]?six)\s+(?:relationships?|episodes?)\b"),
    re.compile(r"(?i)\b(?:18|eighteen)\s+tours?\b"),
    re.compile(r"(?i)\b(?:198|one hundred (?:and )?ninety[- ]?eight)\s+paths?\b"),
)
SCANNED_SUFFIXES = {".js", ".jsx", ".json", ".mjs", ".py", ".ts", ".tsx"}


def _shared_roots() -> tuple[Path, ...]:
    return (
        ROOT / "src",
        ROOT / "schemas" / "common",
        ROOT / "museum_pipeline" / "validation",
        ROOT / "scripts" / "validate_governance_foundation.py",
    )


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        if root.is_file():
            yield root
            continue
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            try:
                relative = path.relative_to(ROOT).as_posix()
            except ValueError:
                relative = path.as_posix()
            if "/tests/" in f"/{relative}/" or relative.startswith("src/tests/"):
                continue
            yield path


def scan_hardcoded_counts(paths: Iterable[Path] | None = None) -> dict[str, object]:
    roots = tuple(paths) if paths is not None else _shared_roots()
    failures: list[dict[str, object]] = []
    checked_files = 0
    for path in _iter_files(roots):
        checked_files += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        for line_number, line in enumerate(text.splitlines(), 1):
            for pattern in SEMANTIC_PATTERNS:
                match = pattern.search(line)
                if match:
                    failures.append(
                        {
                            "code": "shared_current_release_count",
                            "path": relative,
                            "line": line_number,
                            "excerpt": match.group(0)[:160],
                        }
                    )
                    break
    return {
        "ok": not failures,
        "checked_files": checked_files,
        "candidate_invariants_allowed_only_in": [
            "public/releases/art-v1-candidate-1.4.0",
            "schemas/art/candidate",
            "phase reports",
            "exact regression fixtures",
        ],
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan_hardcoded_counts(args.paths or None)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
