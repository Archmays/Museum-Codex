from __future__ import annotations

import uuid
from typing import Any


def json_pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def candidate_claim(
    *,
    candidate_id: str,
    predicate: str,
    value: Any,
    source_id: str,
    source_object_id: str,
    snapshot_id: str,
    raw_locator: str,
    source_tier: int,
    license_rule_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = f"{candidate_id}|{predicate}|{raw_locator}"
    return {
        "id": f"candidate-claim:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
        "subject_candidate_id": candidate_id,
        "predicate": predicate,
        "value": value,
        "status": "candidate",
        "inferred": False,
        "algorithm_or_rule_version": None,
        "source_tier": source_tier,
        "license_rule_id": license_rule_id,
        "content_class": "data",
        "evidence": {
            "source_id": source_id,
            "source_object_id": source_object_id,
            "raw_snapshot_id": snapshot_id,
            "raw_locator": raw_locator,
            "stance": "supports",
        },
        "source_assertion_metadata": metadata or {},
    }


def nested_literals(value: Any, pointer: str) -> list[tuple[str, str, str | None]]:
    """Return (pointer, text, language) from common JSON-LD literal shapes."""
    if isinstance(value, str):
        return [(pointer, value, None)]
    if isinstance(value, list):
        result: list[tuple[str, str, str | None]] = []
        for index, item in enumerate(value):
            result.extend(nested_literals(item, f"{pointer}/{index}"))
        return result
    if isinstance(value, dict):
        text = value.get("@value", value.get("value"))
        if isinstance(text, str):
            language = value.get("@language", value.get("language"))
            return [(pointer, text, language if isinstance(language, str) else None)]
        identifier = value.get("@id")
        if isinstance(identifier, str):
            return [(pointer, identifier, None)]
    return []
