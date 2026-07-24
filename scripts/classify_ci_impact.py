#!/usr/bin/env python3
"""Classify a Git change into Museum-Codex's four CI execution levels.

The classifier intentionally uses only the Python standard library and Git.  A
changed-path file or repeated --changed-path values provide a deterministic
fixture interface without a third-party path-filter action.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance" / "ci-impact-contract.json"
ZERO_SHA = re.compile(r"^0+$")
E2E_IMPACT = (
    ("e2e/museum-04", "MUSEUM-04", "constellation"),
    ("e2e/museum-05a", "MUSEUM-05A", "gallery"),
    ("e2e/museum-05b", "MUSEUM-05B", "gallery"),
    ("e2e/museum-06", "MUSEUM-06", "paths"),
    ("e2e/museum-07", "MUSEUM-07", "map"),
    ("e2e/museum-08", "MUSEUM-08", "search"),
    ("e2e/museum-09b", "MUSEUM-09B-UX-01", "shell"),
    ("e2e/online", "MUSEUM-09B-UX-01", "online"),
)


@dataclass(frozen=True)
class Change:
    status: str
    path: str
    previous_path: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.path,) if self.previous_path is None else (self.previous_path, self.path)


def _normalize(path: str) -> str:
    value = path.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _parse_name_status(lines: Iterable[str]) -> list[Change]:
    changes: list[Change] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        kind = status[:1]
        if kind in {"R", "C"} and len(parts) >= 3:
            changes.append(Change(status=kind, previous_path=_normalize(parts[1]), path=_normalize(parts[2])))
        elif len(parts) >= 2:
            changes.append(Change(status=kind, path=_normalize(parts[1])))
        else:
            # Fixture shorthand: A:path, D:path, or a bare modified path.
            shorthand = line.split(":", 1)
            if len(shorthand) == 2 and shorthand[0] in {"A", "M", "D", "T", "U"}:
                changes.append(Change(status=shorthand[0], path=_normalize(shorthand[1])))
            else:
                changes.append(Change(status="M", path=_normalize(line)))
    return changes


def changed_paths_from_git(before: str, after: str) -> tuple[list[Change], bool]:
    empty_before = not before or bool(ZERO_SHA.fullmatch(before))
    if empty_before:
        output = _run_git(["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", "-M", after])
        return _parse_name_status(output.splitlines()), True
    output = _run_git(["diff", "--name-status", "-M", before, after])
    return _parse_name_status(output.splitlines()), False


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(path == pattern or path.startswith(pattern) for pattern in patterns)


def _is_docs_only_path(path: str, contract: dict[str, Any]) -> bool:
    exact = set(contract["docs_only_exact"])
    if any(path.startswith(item + "/") for item in exact):
        return False
    return path in exact or any(path.startswith(prefix) for prefix in contract["docs_only_prefixes"])


def _phase_for_release(contract: dict[str, Any], release_id: str) -> str:
    for item in [*contract["historical_releases"], contract["candidate_release"]]:
        if item["release_id"] == release_id:
            return item["phase"]
    raise KeyError(release_id)


def classify_changes(
    changes: list[Change],
    mode: str = "auto",
    *,
    first_push: bool = False,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    paths = sorted({path for change in changes for path in change.paths})
    statuses = sorted({change.status for change in changes})
    docs_only = bool(paths) and all(_is_docs_only_path(path, contract) for path in paths)
    closeout_docs = docs_only and all(
        path.startswith(("docs/phase-reports/", "docs/qa/")) for path in paths
    )
    workflow_changed = any(_matches(path, contract["workflow_prefixes"]) for path in paths)
    dependencies_changed = any(path in contract["dependency_paths"] for path in paths)
    classifier_changed = "scripts/classify_ci_impact.py" in paths
    shared_core_changed = classifier_changed or any(
        _matches(path, contract["shared_core_prefixes"]) for path in paths
    )
    security_rights_changed = any(_matches(path, contract["security_rights_prefixes"]) for path in paths)
    public_changed = any(path.startswith("public/") for path in paths)
    runtime_changed = any(_matches(path, contract["runtime_prefixes"]) for path in paths)
    deployment_binding_changed = any(
        _matches(path, contract.get("deployment_binding_paths", ())) for path in paths
    )

    affected_phases: set[str] = set()
    for phase, patterns in contract["phase_paths"].items():
        if any(_matches(path, patterns) for path in paths):
            affected_phases.add(phase)
    for prefix, phase, _suite in E2E_IMPACT:
        if any(path.startswith(prefix) for path in paths):
            affected_phases.add(phase)
    if any(path.startswith("src/") for path in paths):
        affected_phases.add(contract["candidate_release"]["phase"])
    if shared_core_changed or security_rights_changed:
        affected_phases.update(item["phase"] for item in contract["historical_releases"])
        affected_phases.add(contract["candidate_release"]["phase"])

    rebuild: set[str] = set()
    for item in [*contract["historical_releases"], contract["candidate_release"]]:
        phase_patterns = contract["phase_paths"][item["phase"]]
        release_affecting = [
            pattern
            for pattern in phase_patterns
            if (
                Path(pattern).name.startswith(("build_museum_", "validate_museum_"))
                or pattern.startswith("schemas/")
                or pattern.startswith("public/releases/")
                or pattern.startswith("museum_pipeline/")
            )
        ]
        if any(_matches(path, release_affecting) for path in paths):
            rebuild.add(item["release_id"])

    # Common schema and source/rights decisions are consumed by every release.
    if any(path.startswith("schemas/common/") for path in paths) or security_rights_changed:
        rebuild.update(item["release_id"] for item in contract["historical_releases"])
        rebuild.add(contract["candidate_release"]["release_id"])

    release_directories = [
        item["directory"] + "/"
        for item in [*contract["historical_releases"], contract["candidate_release"]]
    ]
    release_bundle_changed = any(
        path.startswith(directory) for path in paths for directory in release_directories
    )
    manual_full = mode == "full"
    full_required = any(
        (
            manual_full,
            first_push,
            workflow_changed,
            dependencies_changed,
            shared_core_changed,
            security_rights_changed,
            release_bundle_changed,
        )
    )
    if docs_only and not manual_full:
        full_required = False
        rebuild.clear()
        affected_phases.clear()
        runtime_changed = False
        public_changed = False

    historical_ids = [item["release_id"] for item in contract["historical_releases"]]
    hash_only = sorted(release_id for release_id in historical_ids if release_id not in rebuild)

    browser_suites = {
        suite
        for suite, patterns in contract["browser_suites"].items()
        if any(_matches(path, patterns) for path in paths)
    }
    for prefix, _phase, suite in E2E_IMPACT:
        if any(path.startswith(prefix) for path in paths):
            browser_suites.add(suite)
    if runtime_changed and not browser_suites:
        browser_suites.add("shell")
    browser_suites = sorted(browser_suites)
    deploy_required = bool(
        (runtime_changed or public_changed or deployment_binding_changed or manual_full)
        and not docs_only
        and not closeout_docs
    )

    reasons: list[str] = []
    if docs_only:
        reasons.append("closeout_docs_only" if closeout_docs else "docs_only")
    if first_push:
        reasons.append("first_push")
    if workflow_changed:
        reasons.append("workflow_changed")
    if dependencies_changed:
        reasons.append("dependencies_changed")
    if shared_core_changed:
        reasons.append("shared_core_changed")
    if security_rights_changed:
        reasons.append("security_or_rights_core_changed")
    if release_bundle_changed:
        reasons.append("release_bundle_changed")
    if manual_full:
        reasons.append("manual_full")
    elif mode == "targeted":
        reasons.append("manual_targeted")
    if runtime_changed:
        reasons.append("runtime_changed")
    if public_changed:
        reasons.append("public_changed")
    if deployment_binding_changed:
        reasons.append("deployment_binding_changed")
    if rebuild:
        reasons.append("release_closure_changed")
    if not reasons:
        reasons.append("no_effective_change" if not paths else "phase_scoped_change")

    level = (
        "docs-only"
        if docs_only
        else "final-full"
        if full_required
        else "shared-core"
        if shared_core_changed
        else "phase-scoped"
    )
    return {
        "schema_version": "1.0.0",
        "impact_level": level,
        "docs_only": docs_only,
        "runtime_changed": runtime_changed,
        "public_changed": public_changed,
        "full_required": full_required,
        "shared_core_changed": shared_core_changed,
        "dependencies_changed": dependencies_changed,
        "workflow_changed": workflow_changed,
        "affected_phases": sorted(affected_phases),
        "releases_to_rebuild": sorted(rebuild),
        "releases_hash_only": hash_only,
        "browser_suites": browser_suites,
        "deploy_required": deploy_required,
        "reason_codes": sorted(set(reasons)),
        "changed_paths": paths,
        "change_kinds": statuses,
        "first_push": first_push,
        "workflow_dispatch_mode": mode,
    }


def _github_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_github_outputs(result: dict[str, Any], destination: Path) -> None:
    keys = (
        "docs_only",
        "runtime_changed",
        "public_changed",
        "full_required",
        "shared_core_changed",
        "dependencies_changed",
        "workflow_changed",
        "affected_phases",
        "releases_to_rebuild",
        "releases_hash_only",
        "browser_suites",
        "deploy_required",
        "reason_codes",
        "impact_level",
    )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        for key in keys:
            handle.write(f"{key}={_github_value(result[key])}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", default=os.environ.get("GITHUB_EVENT_BEFORE", ""))
    parser.add_argument("--after", default=os.environ.get("GITHUB_SHA", "HEAD"))
    parser.add_argument("--mode", choices=("auto", "targeted", "full"), default="auto")
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--changed-paths-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    fixture_lines = list(args.changed_path)
    if args.changed_paths_file:
        fixture_lines.extend(args.changed_paths_file.read_text(encoding="utf-8").splitlines())
    if fixture_lines:
        changes = _parse_name_status(fixture_lines)
        first_push = not args.before or bool(ZERO_SHA.fullmatch(args.before))
    else:
        changes, first_push = changed_paths_from_git(args.before, args.after)

    result = classify_changes(changes, args.mode, first_push=first_push)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8", newline="\n")
    github_output = args.github_output or (
        Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None
    )
    if github_output:
        write_github_outputs(result, github_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
