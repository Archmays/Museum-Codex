from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from museum_pipeline.adapters.base import ResponseContract
from museum_pipeline.errors import PipelineError
from museum_pipeline.snapshots import load_snapshot_manifest, write_snapshot
from museum_pipeline.transport import HttpTransport


def acquire(
    *,
    adapter,
    object_id: str,
    live: bool,
    query_profile: str = "default",
    transport: HttpTransport | None = None,
    raw_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if live is not True:
        raise PipelineError("network_disabled", "Network is disabled; pass --live explicitly for acquisition", exit_code=4)
    request = adapter.build_request(object_id, query_profile=query_profile)
    response: ResponseContract = (transport or HttpTransport()).fetch(adapter, request)
    source_object_ids: list[str] = []
    drift: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    document = None
    try:
        document = adapter.validate_response_contract(response)
        source_object_ids = adapter.extract_source_object_ids(document)
        drift = adapter.detect_contract_drift(document)
        warnings.extend(item.get("code", "contract_drift") for item in drift)
    except PipelineError as error:
        errors.append(error.code)
    run_id = f"pipeline-run:{uuid.uuid4()}"
    kwargs = {
        "adapter": adapter, "request": request, "response": response,
        "source_object_ids": source_object_ids, "run_id": run_id,
        "fetched_at": now or datetime.now(timezone.utc), "warnings": warnings, "errors": errors,
    }
    if raw_root is not None:
        kwargs["raw_root"] = raw_root
    snapshot_dir = write_snapshot(**kwargs)
    if errors:
        raise PipelineError(errors[0], "Live response failed its adapter contract after the raw event was recorded", exit_code=5)
    manifest = load_snapshot_manifest(snapshot_dir)
    return {
        "run_id": run_id,
        "source_id": adapter.source_id,
        "adapter_version": adapter.adapter_version,
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_path": snapshot_dir,
        "status_code": response.status_code,
        "content_type": manifest["content_type"],
        "body_bytes": manifest["body_bytes"],
        "body_sha256": manifest["body_sha256"],
        "source_object_ids": source_object_ids,
        "contract_drift": drift,
    }
