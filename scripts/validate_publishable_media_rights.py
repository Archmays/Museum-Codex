#!/usr/bin/env python3
"""Block media that is not cleared for a public static release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_governance_foundation import ROOT, ValidationIssue, media_publish_issues


def resolve_inputs(paths: Iterable[Path]) -> tuple[list[Path], list[tuple[Path, str, ValidationIssue]]]:
    files: set[Path] = set()
    failures: list[tuple[Path, str, ValidationIssue]] = []
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        if not resolved.exists():
            failures.append((resolved, "<path>", ValidationIssue("path_missing", "Input path does not exist")))
        elif resolved.is_dir():
            directory_files = set(resolved.rglob("*.json"))
            if not directory_files:
                failures.append((resolved, "<path>", ValidationIssue("no_json_files", "Input directory contains no JSON files")))
            files.update(directory_files)
        elif resolved.is_file() and resolved.suffix.lower() == ".json":
            files.add(resolved)
        else:
            failures.append((resolved, "<path>", ValidationIssue("unsupported_input", "Input must be a JSON file or directory")))
    return sorted(files), failures


def media_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("entity_type") == "media_asset":
            yield value
            return
        for child in value.values():
            yield from media_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from media_objects(child)


def scan(paths: Iterable[Path], allow_empty: bool = False) -> tuple[list[tuple[Path, str, ValidationIssue]], int, int]:
    files, failures = resolve_inputs(paths)
    file_count = 0
    media_count = 0
    for path in files:
        file_count += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append((path, "<file>", ValidationIssue("invalid_json", str(exc))))
            continue
        for media in media_objects(payload):
            media_count += 1
            media_id = str(media.get("id", "<missing-id>"))
            for issue in media_publish_issues(media, f"{path}:{media_id}"):
                failures.append((path, media_id, issue))
    if media_count == 0 and not allow_empty:
        failures.append((ROOT, "<none>", ValidationIssue("no_media", "No media records were found; publish validation is fail-closed")))
    return failures, file_count, media_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("fixtures/governance/valid")])
    parser.add_argument("--allow-empty", action="store_true", help="Diagnostic-only: allow an input set with no media records")
    args = parser.parse_args()
    failures, file_count, media_count = scan(args.paths, allow_empty=args.allow_empty)
    if failures:
        for path, media_id, issue in failures:
            try:
                display_path = path.relative_to(ROOT).as_posix()
            except ValueError:
                display_path = str(path)
            print(f"[BLOCK] {display_path} {media_id}: {issue.code} - {issue.message}")
        print(f"[FAIL] media rights: {len(failures)} blocker(s); {media_count} media record(s) in {file_count} file(s)")
        return 1
    print(f"[PASS] media rights: {media_count} media record(s) in {file_count} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
