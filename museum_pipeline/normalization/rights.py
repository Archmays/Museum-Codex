from __future__ import annotations

from typing import Any


def media_candidate(
    *,
    source_id: str,
    source_object_id: str,
    source_locator: str,
    url_or_identifier: str,
    hints: dict[str, Any],
    license_rule_id: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_object_id": source_object_id,
        "source_locator": source_locator,
        "url_or_identifier": url_or_identifier,
        "rights_hints": hints,
        "license_rule_id": license_rule_id,
        "content_class": "media",
        "rights_status": "unknown",
        "development_only": True,
        "publish_status": "blocked",
        "bytes_downloaded": False,
    }


def media_candidate_issues(candidate: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if candidate.get("rights_status") != "unknown" or candidate.get("development_only") is not True:
        hints = candidate.get("rights_hints", {})
        if hints.get("iiif_access_is_license") is True or hints.get("iiif_url"):
            issues.append("iiif_not_rights_proof")
        if hints.get("primary_image_is_rights_proof") is True or hints.get("primaryImage"):
            issues.append("met_image_not_rights_proof")
        if not issues:
            issues.append("media_candidate_rights_escalation")
    if candidate.get("bytes_downloaded") is not False:
        issues.append("media_bytes_downloaded")
    return sorted(set(issues))
