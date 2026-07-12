from __future__ import annotations

import uuid
from typing import Any

from museum_pipeline.config import source_configuration
from museum_pipeline.hashing import canonical_sha256


TRANSFORM_VERSION = "1.0.0"


def provisional_candidate_id(source_id: str, source_object_id: str) -> str:
    namespace = uuid.UUID(source_configuration(source_id)["adapter_namespace_uuid"])
    return f"candidate:{uuid.uuid5(namespace, source_object_id)}"


def provenance_entry(
    *,
    candidate_id: str,
    field_pointer: str,
    source_id: str,
    source_object_id: str,
    snapshot_id: str,
    raw_locator: str,
    raw_value: Any,
    normalized_value: Any,
    rule_id: str,
    content_class: str,
    observed_at: str,
    language: str | None = None,
    script: str | None = None,
    warnings: list[str] | None = None,
    inferred: bool = False,
    transform_id: str = "identity",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": f"field-provenance:{uuid.uuid5(uuid.NAMESPACE_URL, candidate_id + field_pointer + raw_locator)}",
        "entity_type": "field_provenance",
        "candidate_id": candidate_id,
        "field_pointer": field_pointer,
        "source_id": source_id,
        "source_object_id": source_object_id,
        "raw_snapshot_id": snapshot_id,
        "raw_locator": raw_locator,
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "transform_id": transform_id,
        "transform_version": TRANSFORM_VERSION,
        "transform_warnings": sorted(warnings or []),
        "source_tier": source_configuration(source_id)["tier"],
        "license_rule_id": rule_id,
        "content_class": content_class,
        "language": language,
        "script": script,
        "observed_at": observed_at,
        "inferred": inferred,
        "review_state": "candidate",
    }


def finalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(candidate)
    candidate["input_hash"] = canonical_sha256({key: value for key, value in candidate.items() if key != "input_hash"})
    return candidate
