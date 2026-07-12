from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT_REGISTRY_PATH = ROOT / "research" / "source-registry" / "pipeline-endpoint-registry.json"
SOURCE_MATRIX_PATH = ROOT / "research" / "source-registry" / "source-comparison-matrix.csv"
LICENSE_RULES_PATH = ROOT / "research" / "source-registry" / "source-license-rules.json"
RAW_ROOT = ROOT / "data" / "raw"
INTERMEDIATE_ROOT = ROOT / "data" / "intermediate"
USER_AGENT = "Museum-Codex-Pipeline/0.1 (+https://github.com/Archmays/Museum-Codex)"


@lru_cache(maxsize=1)
def endpoint_registry() -> dict[str, Any]:
    if not ENDPOINT_REGISTRY_PATH.exists():
        raise PipelineError("endpoint_registry_missing", "Pipeline endpoint registry is missing")
    return json.loads(ENDPOINT_REGISTRY_PATH.read_text(encoding="utf-8"))


def source_configuration(source_id: str) -> dict[str, Any]:
    for source in endpoint_registry().get("sources", []):
        if source.get("source_id") == source_id:
            return source
    raise PipelineError("source_not_registered", f"Source is not registered: {source_id}")


@lru_cache(maxsize=1)
def license_rule_registry() -> dict[str, list[dict[str, Any]]]:
    document = json.loads(LICENSE_RULES_PATH.read_text(encoding="utf-8"))
    return {item["source_id"]: item["rules"] for item in document["sources"]}


def source_license_rules(source_id: str) -> list[dict[str, Any]]:
    try:
        return license_rule_registry()[source_id]
    except KeyError as error:
        raise PipelineError("source_rules_missing", f"No canonical rules for source: {source_id}") from error


def source_matrix_ids() -> set[str]:
    with SOURCE_MATRIX_PATH.open("r", encoding="utf-8", newline="") as stream:
        return {row["source_id"] for row in csv.DictReader(stream)}


def source_registry_snapshot_hash() -> str:
    return canonical_sha256(endpoint_registry())


def license_rules_snapshot_hash() -> str:
    return sha256_file(LICENSE_RULES_PATH)
