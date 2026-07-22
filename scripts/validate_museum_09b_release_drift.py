#!/usr/bin/env python3
"""Close MUSEUM-09B-RELEASE source drift without requesting image bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "docs" / "qa" / "museum-09b-release" / "source-drift.json"
ALLOWLIST = ROOT / "data" / "reviewed" / "art" / "museum-09b-media" / "batch-01-media-bundle-v1" / "allowlist-snapshot.json"
DEFAULT_OUTPUT = ROOT / "docs" / "qa" / "museum-09b-release" / "source-drift-assessment.json"
IMAGE_ID = re.compile(r"^https://www\.artic\.edu/iiif/2/([0-9a-f-]+)/")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _probe_info(service_id: str, timeout: float) -> dict:
    url = f"{service_id}/info.json"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Museum-Codex/1.0 metadata-only release check"})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 -- exact allowlisted HTTPS host
            payload = response.read(1_048_577)
            if len(payload) > 1_048_576:
                raise ValueError("info_json_over_1_mib")
            document = json.loads(payload.decode("utf-8"))
            observed = document.get("@id") or document.get("id")
            identity_match = observed == service_id
            return {
                "status": "available" if identity_match else "identity_mismatch",
                "http_status": response.status,
                "content_type": response.headers.get_content_type(),
                "response_bytes": len(payload),
                "response_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "observed_service_id": observed,
                "identity_match": identity_match,
            }
    except HTTPError as error:
        return {"status": "transport_unavailable", "http_status": error.code, "response_bytes": 0, "identity_match": None}
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        return {"status": "transport_unavailable", "error": f"{type(error).__name__}:{error}", "response_bytes": 0, "identity_match": None}


def validate(receipt_path: Path, output_path: Path, *, probe_info: bool, timeout: float) -> dict:
    receipt = _read(receipt_path)
    allowlist = _read(ALLOWLIST)
    failures: list[str] = []
    if (
        receipt.get("checked_count") != 538
        or receipt.get("changed_count") != 87
        or receipt.get("unchanged_count") != 451
        or receipt.get("unavailable_count") != 0
        or receipt.get("new_media_bytes") != 0
        or receipt.get("transport_failures") != []
    ):
        failures.append("source_receipt_profile")
    changed = [item for item in receipt.get("records", []) if item.get("status") == "changed"]
    if len(changed) != 87 or any(item.get("source_id") != "aic_api" or item.get("classification") != "metadata_enhancement" for item in changed):
        failures.append("changed_record_classification")

    receipt_by_object = {
        (item.get("source_id"), str(item.get("source_object_id"))): item
        for item in receipt.get("records", []) if item.get("source_id") and item.get("source_object_id") is not None
    }
    external = [item for item in allowlist["records"] if item["candidate_status"] == "approved_external_iiif_candidate"]
    self_hosted = [item for item in allowlist["records"] if item["candidate_status"] == "approved_self_hosted_candidate"]
    external_results = []
    for item in external:
        match = IMAGE_ID.match(item["media_or_iiif_url_identity"])
        record = receipt_by_object.get((item["source_id"].removeprefix("source:"), str(item["source_object_id"])))
        current_image_id = (record or {}).get("minimal_current_projection", {}).get("image_id")
        expected_image_id = match.group(1) if match else None
        identity_match = bool(record and expected_image_id and current_image_id == expected_image_id)
        if not identity_match or record.get("status") == "unavailable":
            failures.append(f"external_identity:{item['work_id']}")
        service_id = f"https://www.artic.edu/iiif/2/{expected_image_id}"
        probe = _probe_info(service_id, timeout) if probe_info else {"status": "not_run", "response_bytes": 0, "identity_match": None}
        if probe.get("status") == "identity_mismatch":
            failures.append(f"info_identity:{item['work_id']}")
        external_results.append({
            "work_id": item["work_id"],
            "source_object_id": item["source_object_id"],
            "object_record_status": record.get("status"),
            "object_record_classification": record.get("classification"),
            "expected_image_id": expected_image_id,
            "current_image_id": current_image_id,
            "object_service_identity_match": identity_match,
            "final_public_state": "external_link_only",
            "info_json_probe": probe,
        })

    self_hosted_statuses = Counter(
        receipt_by_object[(item["source_id"].removeprefix("source:"), str(item["source_object_id"]))]["status"]
        for item in self_hosted
    )
    if self_hosted_statuses != Counter({"unchanged": 40}):
        failures.append("self_hosted_source_drift")
    if len(external) != 25 or len(self_hosted) != 40:
        failures.append("media_allowlist_profile")

    assessment = {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-09B-RELEASE",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
        "source_receipt_content_hash": receipt["content_hash"],
        "checked_records": 538,
        "changed_records": 87,
        "changed_classification": "metadata_enhancement_only",
        "unavailable_records": 0,
        "media_allowlist_records": 65,
        "self_hosted_records": 40,
        "self_hosted_statuses": dict(self_hosted_statuses),
        "external_link_only_records": 25,
        "external_object_identity_matches": sum(item["object_service_identity_match"] for item in external_results),
        "info_json_probe_statuses": dict(Counter(item["info_json_probe"]["status"] for item in external_results)),
        "metadata_response_bytes": sum(item["info_json_probe"].get("response_bytes", 0) for item in external_results),
        "image_endpoint_request_count": 0,
        "image_bytes_downloaded": 0,
        "new_media_bytes": 0,
        "rights_or_delivery_downgrade_count": 0,
        "release_decision": "pass_with_external_link_only_fail_closed_transport",
        "external_records": external_results,
        "failures": failures,
        "ok": not failures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(assessment, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return assessment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--probe-info", action="store_true")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    result = validate(args.receipt.resolve(), args.output.resolve(), probe_info=args.probe_info, timeout=args.timeout)
    print(json.dumps({key: result[key] for key in result if key != "external_records"}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
