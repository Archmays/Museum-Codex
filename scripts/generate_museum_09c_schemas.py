#!/usr/bin/env python3
"""Generate mechanically versioned MUSEUM-09C release schemas and manifest entries."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_ROOT = ROOT / "schemas" / "art" / "release"
RELEASE_ID = "release:art-expansion-batch-02-1.6.0"
DATA_VERSION = "1.6.0"

COPIES = {
    "art-expansion-public-record-v151.schema.json": "art-expansion-public-record-v160.schema.json",
    "art-expansion-source-v151.schema.json": "art-expansion-source-v160.schema.json",
    "art-expansion-media-asset-v151.schema.json": "art-expansion-media-asset-v160.schema.json",
    "artist-narrative.schema.json": "artist-narrative-v160.schema.json",
    "relationship-explorer-config.schema.json": "relationship-explorer-config-v160.schema.json",
}


def pretty_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def transform(value: object, source_name: str, target_name: str) -> object:
    if isinstance(value, list):
        return [transform(item, source_name, target_name) for item in value]
    if isinstance(value, dict):
        result = {key: transform(item, source_name, target_name) for key, item in value.items()}
        if "$id" in result:
            result["$id"] = str(result["$id"]).replace(source_name, target_name)
        if result.get("const") == "release:art-expansion-batch-01-1.5.1":
            result["const"] = RELEASE_ID
        if result.get("const") == "1.5.0":
            result["const"] = DATA_VERSION
        return result
    if isinstance(value, str):
        return value.replace("MUSEUM-09B-UX-01", "MUSEUM-09C")
    return value


def main() -> int:
    generated = []
    for source_name, target_name in COPIES.items():
        source = json.loads((SCHEMA_ROOT / source_name).read_text(encoding="utf-8"))
        target = transform(copy.deepcopy(source), source_name, target_name)
        if target_name == "artist-narrative-v160.schema.json":
            target["properties"]["narratives"]["minItems"] = 111
            target["properties"]["narratives"]["maxItems"] = 111
        (SCHEMA_ROOT / target_name).write_bytes(pretty_json_bytes(target))
        generated.append(target_name)
    manifest_path = ROOT / "schemas" / "schema-manifest.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    existing = {item["path"] for item in manifest["schemas"]}
    additions: list[dict[str, object]] = []
    for target_name in generated:
        path = f"schemas/art/release/{target_name}"
        if path not in existing:
            document = json.loads((SCHEMA_ROOT / target_name).read_text(encoding="utf-8"))
            additions.append(
                {
                    "path": path,
                    "id": document["$id"],
                    "version": "1.0.0",
                    "branch": "art",
                    "depends_on": [],
                }
            )
    if additions:
        marker = "\n  ]\n}\n"
        if marker not in manifest_text:
            raise ValueError("schema manifest closing marker drift")
        rendered = ",\n".join(
            "\n".join(
                [
                    "    {",
                    f'      "path": {json.dumps(item["path"])},',
                    f'      "id": {json.dumps(item["id"])},',
                    f'      "version": {json.dumps(item["version"])},',
                    f'      "branch": {json.dumps(item["branch"])},',
                    '      "depends_on": []',
                    "    }",
                ]
            )
            for item in additions
        )
        manifest_text = manifest_text.replace(marker, f",\n{rendered}{marker}", 1)
        manifest_path.write_text(manifest_text, encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "generated": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
