#!/usr/bin/env python3
"""Lightweight docs-only parser, front-matter, secret/path and evidence checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABSOLUTE_PATH = re.compile(r"(?i)(?:[A-Z]:\\(?:Users|ChatGPT-Codex-Projects)\\|/home/|/Users/)")
SECRET = re.compile(
    r"(?i)(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|(?:api[_-]?key|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,})"
)
HASH = re.compile(r"sha256:[a-f0-9]{64}")
LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
BINARY_EVIDENCE = {
    ".gif": (b"GIF87a", b"GIF89a"),
    ".jpeg": (b"\xff\xd8\xff",),
    ".jpg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


def _front_matter(text: str, path: Path) -> list[str]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return []
    lines = text.splitlines()
    try:
        closing = lines.index("---", 1)
    except ValueError:
        return [f"{path}: unterminated front matter"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, line in enumerate(lines[1:closing], 2):
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "-")):
            continue
        if ":" not in line:
            errors.append(f"{path}:{index}: invalid front matter entry")
            continue
        key = line.split(":", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            errors.append(f"{path}:{index}: invalid front matter key")
        if key in seen:
            errors.append(f"{path}:{index}: duplicate front matter key {key}")
        seen.add(key)
    return errors


def validate(path: Path) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    if not path.exists():
        return []
    errors: list[str] = []
    suffix = path.suffix.lower()
    if suffix in BINARY_EVIDENCE:
        data = path.read_bytes()
        signatures = BINARY_EVIDENCE[suffix]
        if not data:
            return [f"{relative}: empty binary evidence"]
        if not any(data.startswith(signature) for signature in signatures):
            return [f"{relative}: invalid {suffix} evidence signature"]
        if suffix == ".webp" and (len(data) < 12 or data[8:12] != b"WEBP"):
            return [f"{relative}: invalid WebP evidence signature"]
        return []
    if suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            return [f"{relative}: invalid JSON: {error}"]
    text = path.read_text(encoding="utf-8")
    if "\t" in text and suffix in {".yml", ".yaml"}:
        errors.append(f"{relative}: YAML contains a tab")
    if suffix == ".md":
        errors.extend(_front_matter(text, Path(relative)))
        for target in LOCAL_LINK.findall(text):
            clean = target.split("#", 1)[0].strip("<>")
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{relative}: broken local link {target}")
    if SECRET.search(text):
        errors.append(f"{relative}: possible secret")
    if ABSOLUTE_PATH.search(text):
        errors.append(f"{relative}: local absolute path")
    for value in re.findall(r"sha256:[A-Za-z0-9]+", text):
        if not HASH.fullmatch(value):
            errors.append(f"{relative}: malformed SHA-256 reference {value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--paths-file", type=Path)
    args = parser.parse_args()
    raw_paths = list(args.paths)
    if args.paths_file:
        raw_paths.extend(args.paths_file.read_text(encoding="utf-8").splitlines())
    paths = sorted(
        {
            (ROOT / value.strip().replace("\\", "/")).resolve()
            for value in raw_paths
            if value.strip() and not value.startswith("D\t")
        }
    )
    failures = [failure for path in paths for failure in validate(path)]
    result = {"ok": not failures, "checked": len(paths), "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
