#!/usr/bin/env python3
"""Generate version-bound expansion schemas from an approved release plan."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.canonical_json import canonical_json_bytes

DEFAULT_PLAN = ROOT / "docs" / "05_roadmap" / "museum-09d-wave-01" / "release-plan.json"
RELEASE_SCHEMA_ROOT = ROOT / "schemas" / "art" / "release"
TEMPLATES = {
    "art-expansion-public-record": "art-expansion-public-record-v160.schema.json",
    "art-expansion-source": "art-expansion-source-v160.schema.json",
    "art-expansion-media-asset": "art-expansion-media-asset-v160.schema.json",
    "artist-narrative": "artist-narrative-v160.schema.json",
    "relationship-explorer-config": "relationship-explorer-config-v160.schema.json",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _suffix(version: str) -> str:
    return "v" + "".join(character for character in version if character.isdigit())


def _replace(value: Any, *, release_id: str, version: str, suffix: str, count: int, phase_id: str) -> Any:
    if isinstance(value, list):
        return [
            _replace(item, release_id=release_id, version=version, suffix=suffix, count=count, phase_id=phase_id)
            for item in value
        ]
    if not isinstance(value, dict):
        if value == "release:art-expansion-batch-02-1.6.0":
            return release_id
        if value == "1.6.0":
            return version
        if isinstance(value, str):
            return (
                value.replace("v160.schema.json", f"{suffix}.schema.json")
                .replace("MUSEUM-09C", phase_id)
            )
        return value
    result = {
        key: _replace(item, release_id=release_id, version=version, suffix=suffix, count=count, phase_id=phase_id)
        for key, item in value.items()
    }
    narratives = result.get("properties", {}).get("narratives")
    if isinstance(narratives, dict):
        narratives["minItems"] = count
        narratives["maxItems"] = count
    return result


def _manifest_entry(path: str, schema: dict[str, Any], template_name: str) -> dict[str, Any]:
    return {
        "path": path,
        "id": schema["$id"],
        "version": "1.0.0",
        "branch": "art",
        "depends_on": (
            ["schemas/common/source.schema.json"]
            if template_name == "art-expansion-source"
            else []
        ),
    }


def _manifest_base_text(path: Path, generated_paths: set[str]) -> str:
    relative = path.relative_to(ROOT).as_posix()
    tracked = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    current = path.read_text(encoding="utf-8")
    if tracked.returncode == 0 and not generated_paths.intersection(
        {item["path"] for item in json.loads(tracked.stdout)["schemas"]}
    ):
        return tracked.stdout
    return current


def _append_manifest_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    generated_paths = {item["path"] for item in entries}
    text = _manifest_base_text(path, generated_paths)
    existing = {item["path"] for item in json.loads(text)["schemas"]}
    additions = [item for item in entries if item["path"] not in existing]
    if not additions:
        path.write_text(text, encoding="utf-8", newline="\n")
        return
    marker = "\n  ]\n}\n"
    if marker not in text:
        raise ValueError(f"schema manifest closing marker drift: {path}")
    rendered_records = []
    for item in additions:
        depends_on = json.dumps(item["depends_on"], ensure_ascii=False)
        rendered_records.append(
            "\n".join(
                [
                    "    {",
                    f'      "path": {json.dumps(item["path"])},',
                    f'      "id": {json.dumps(item["id"])},',
                    f'      "version": {json.dumps(item["version"])},',
                    f'      "branch": {json.dumps(item["branch"])},',
                    f'      "depends_on": {depends_on}',
                    "    }",
                ]
            )
        )
    text = text.replace(marker, ",\n" + ",\n".join(rendered_records) + marker, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def build(plan_path: Path) -> list[str]:
    plan = _read(plan_path)
    generated: list[str] = []
    manifest_entries: list[dict[str, Any]] = []
    for batch in plan["batches"]:
        suffix = _suffix(batch["version"])
        for name, template in TEMPLATES.items():
            schema = _replace(
                copy.deepcopy(_read(RELEASE_SCHEMA_ROOT / template)),
                release_id=batch["release_id"],
                version=batch["version"],
                suffix=suffix,
                count=batch["cumulative_artist_count"],
                phase_id=plan["phase_id"],
            )
            relative = f"schemas/art/release/{name}-{suffix}.schema.json"
            _write(ROOT / relative, schema)
            generated.append(relative)
            manifest_entries.append(_manifest_entry(relative, schema, name))
    _append_manifest_entries(
        ROOT / "schemas" / "art" / "release" / "schema-manifest.json",
        [],
    )
    _append_manifest_entries(
        ROOT / "schemas" / "schema-manifest.json",
        copy.deepcopy(manifest_entries),
    )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = args.plan.resolve()
    if args.check:
        before = {
            path: path.read_bytes()
            for path in [
                ROOT / "schemas" / "art" / "release" / "schema-manifest.json",
                ROOT / "schemas" / "schema-manifest.json",
                *(
                    ROOT
                    / "schemas"
                    / "art"
                    / "release"
                    / f"{name}-{_suffix(batch['version'])}.schema.json"
                    for batch in _read(plan)["batches"]
                    for name in TEMPLATES
                ),
            ]
            if path.is_file()
        }
        generated = build(plan)
        after = {path: path.read_bytes() for path in before}
        if before != after:
            print(json.dumps({"ok": False, "reason": "generated_schema_drift"}, indent=2))
            return 1
    else:
        generated = build(plan)
    print(json.dumps({"ok": True, "generated": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
