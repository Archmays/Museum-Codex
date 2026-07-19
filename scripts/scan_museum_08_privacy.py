#!/usr/bin/env python3
"""Fail closed on analytics, query-history, cookies, geolocation, and remote telemetry."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LOCAL_PREFERENCE_KEYS = {"museum-locale", "museum-low-bandwidth"}
SCANNED_SUFFIXES = {".cjs", ".html", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
SKIPPED_PARTS = {"coverage", "node_modules", "test-results", "tests"}

FORBIDDEN_APIS = {
    "cookie_api": re.compile(r"\b(?:document\s*\.\s*cookie|cookieStore)\b"),
    "geolocation_api": re.compile(r"\bnavigator\s*\.\s*geolocation\b"),
    "send_beacon": re.compile(r"\b(?:navigator\s*\.\s*)?sendBeacon\s*\("),
    "session_storage": re.compile(r"\bsessionStorage\s*\.\s*(?:getItem|setItem|removeItem|clear)\s*\("),
}
FORBIDDEN_DEPENDENCY_TOKENS = {
    "@amplitude",
    "@google-analytics",
    "@segment",
    "@sentry",
    "analytics",
    "fullstory",
    "matomo",
    "mixpanel",
    "plausible",
    "posthog",
    "telemetry",
}
STORAGE_CALL = re.compile(
    r"\b(?:window\s*\.\s*)?localStorage\s*\.\s*"
    r"(?P<operation>getItem|setItem|removeItem)\s*\(\s*(?P<argument>[A-Za-z_$][\w$]*|[\"'`][^\"'`]+[\"'`])"
)
STRING_CONSTANT = re.compile(
    r"(?:(?:const|let|var)\s+|(?<=[,;]))"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?P<quote>[\"'`])(?P<value>[^\"'`]+)(?P=quote)"
)


def _source_has_forbidden_api(code: str) -> bool:
    pattern = FORBIDDEN_APIS[code]
    return any(
        pattern.search(path.read_text(encoding="utf-8", errors="replace"))
        for path in _iter_files(ROOT / "src")
    )


def _allow_built_vendor_token(code: str, path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    if not relative.startswith("dist/assets/") or _source_has_forbidden_api(code):
        return False
    if code == "session_storage":
        return True
    if code == "geolocation_api" and path.name.startswith("maplibre-gl-"):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        return package.get("dependencies", {}).get("maplibre-gl") == "5.24.0"
    return False


def _iter_files(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
        return
    for path in sorted(target.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() in SCANNED_SUFFIXES
            and not any(part in SKIPPED_PARTS for part in path.parts)
        ):
            yield path


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _scan_dependencies() -> list[dict[str, str]]:
    package_path = ROOT / "package.json"
    if not package_path.exists():
        return []
    package = json.loads(package_path.read_text(encoding="utf-8"))
    failures: list[dict[str, str]] = []
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        for dependency in package.get(group, {}):
            normalized = dependency.lower()
            if any(token in normalized for token in FORBIDDEN_DEPENDENCY_TOKENS):
                failures.append(
                    {
                        "code": "telemetry_dependency",
                        "path": "package.json",
                        "detail": f"{group}:{dependency}",
                    }
                )
    return failures


def scan_privacy(target: Path, *, include_dependencies: bool = True) -> dict[str, object]:
    target = target.resolve()
    failures = _scan_dependencies() if include_dependencies else []
    observed_keys: set[str] = set()
    built_vendor_capability_tokens: list[dict[str, str]] = []
    checked_files = 0

    for path in _iter_files(target):
        checked_files += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = _display(path)
        constants = {match.group("name"): match.group("value") for match in STRING_CONSTANT.finditer(text)}

        for code, pattern in FORBIDDEN_APIS.items():
            if pattern.search(text):
                if _allow_built_vendor_token(code, path):
                    built_vendor_capability_tokens.append(
                        {
                            "code": code,
                            "path": relative,
                            "disposition": "vendored_token_only_source_and_browser_zero_use_required",
                        }
                    )
                else:
                    failures.append({"code": code, "path": relative, "detail": "forbidden browser API"})

        for match in STORAGE_CALL.finditer(text):
            argument = match.group("argument")
            if argument[0] in "\"'`":
                key = argument[1:-1]
            else:
                key = constants.get(argument)
            if key is None:
                failures.append(
                    {
                        "code": "dynamic_local_storage_key",
                        "path": relative,
                        "detail": f"{match.group('operation')}:{argument}",
                    }
                )
                continue
            observed_keys.add(key)
            if key not in ALLOWED_LOCAL_PREFERENCE_KEYS:
                failures.append(
                    {
                        "code": "forbidden_local_storage_key",
                        "path": relative,
                        "detail": f"{match.group('operation')}:{key}",
                    }
                )

    result: dict[str, object] = {
        "ok": not failures,
        "target": _display(target),
        "checked_files": checked_files,
        "allowed_local_preference_keys": sorted(ALLOWED_LOCAL_PREFERENCE_KEYS),
        "observed_local_storage_keys": sorted(observed_keys),
        "built_vendor_capability_tokens": built_vendor_capability_tokens,
        "analytics_used": False if not failures else None,
        "query_history_stored": False if not failures else None,
        "user_geolocation_used": False if not failures else None,
        "failures": failures,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=ROOT / "src")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan_privacy(args.target)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
