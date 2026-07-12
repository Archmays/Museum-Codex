from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from museum_pipeline import __version__
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import RAW_ROOT, license_rules_snapshot_hash, source_registry_snapshot_hash
from museum_pipeline.errors import PipelineError, contains_unredacted_secret
from museum_pipeline.hashing import canonical_sha256, sha256_bytes
from museum_pipeline.paths import resolve_within, safe_relative_path


ALLOWED_RESPONSE_HEADERS = {
    "cache-control", "content-length", "content-type", "date", "etag", "expires",
    "last-modified", "location", "retry-after", "vary", "x-ratelimit-limit", "x-ratelimit-remaining",
}


def write_snapshot(
    *,
    adapter: SourceAdapter,
    request: RequestSpec,
    response: ResponseContract,
    source_object_ids: list[str],
    run_id: str,
    fetched_at: datetime | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    raw_root: Path = RAW_ROOT,
    previous_snapshot: Path | None = None,
) -> Path:
    timestamp = (fetched_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if timestamp.tzinfo is None:
        raise PipelineError("timestamp_timezone_missing", "Snapshot timestamp must be timezone-aware")
    body_hash = sha256_bytes(response.body)
    if response.status_code == 304:
        if previous_snapshot is None:
            raise PipelineError("not_modified_without_previous", "HTTP 304 requires a previous snapshot")
        previous_manifest = load_snapshot_manifest(previous_snapshot)
        body_hash = str(previous_manifest["body_sha256"])
    timestamp_slug = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    relative = f"{adapter.source_id}/{timestamp:%Y/%m/%d}/{timestamp_slug}-{body_hash[7:19]}"
    safe_relative_path(relative)
    raw_root.mkdir(parents=True, exist_ok=True)
    if raw_root.is_symlink():
        raise PipelineError("symlink_escape", "The governed raw root may not be a symbolic link")
    target = resolve_within(raw_root, relative)
    if target.exists():
        raise PipelineError("snapshot_overwrite", "Snapshot directory already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = _find_body_snapshot(raw_root / adapter.source_id, body_hash)
    event_type = "acquired"
    reused_snapshot_id: str | None = None
    body_path: str | None = "response.body"
    if response.status_code == 304:
        existing = previous_snapshot
        event_type = "not_modified"
    elif existing is not None:
        event_type = "duplicate_content"
    if existing is not None:
        reused_manifest = load_snapshot_manifest(existing)
        reused_snapshot_id = reused_manifest["snapshot_id"]
        body_path = None

    sanitized_request = adapter.redact_request(request)
    snapshot_id = f"snapshot:{adapter.source_id}:{timestamp_slug.lower()}:{body_hash[7:19]}"
    acquisition_request_id = f"acquisition-request:{canonical_sha256(sanitized_request)[7:23]}"
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "entity_type": "raw_snapshot_manifest",
        "source_id": adapter.source_id,
        "event_type": event_type,
        "acquisition_request_id": acquisition_request_id,
        "sanitized_request": sanitized_request,
        "http_method": request.method,
        "canonical_endpoint": sanitized_request["canonical_endpoint"],
        "query_profile": request.query_profile,
        "credential_alias": request.credential_alias,
        "fetched_at": timestamp.isoformat().replace("+00:00", "Z"),
        "adapter_name": adapter.adapter_name,
        "adapter_version": adapter.adapter_version,
        "contract_version": adapter.contract_version,
        "source_registry_snapshot_hash": source_registry_snapshot_hash(),
        "license_rules_snapshot_hash": license_rules_snapshot_hash(),
        "status_code": response.status_code,
        "response_headers": {
            name.lower(): value
            for name, value in sorted(response.headers.items(), key=lambda item: item[0].lower())
            if name.lower() in ALLOWED_RESPONSE_HEADERS
        },
        "redirect_chain": list(response.redirect_chain),
        "final_url": response.final_url,
        "content_type": response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
        "body_bytes": len(response.body) if body_path else _referenced_body_metadata(existing)[0],
        "body_sha256": body_hash if body_path else _referenced_body_metadata(existing)[1],
        "response_body_path": body_path,
        "reused_body_snapshot_id": reused_snapshot_id,
        "source_object_ids": sorted(set(source_object_ids)),
        "retry_count": response.retry_count,
        "warnings": sorted(set(warnings or [])),
        "errors": sorted(set(errors or [])),
        "terms_verified_at": adapter.configuration["terms_verified_at"],
        "run_id": run_id,
    }
    temporary = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=target.parent))
    try:
        if body_path:
            (temporary / body_path).write_bytes(response.body)
        (temporary / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def load_snapshot_manifest(snapshot_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError("snapshot_manifest_invalid", "Snapshot manifest is missing or invalid") from error


def validate_snapshot(snapshot_dir: Path, *, now: datetime | None = None, raw_root: Path | None = None) -> list[str]:
    manifest = load_snapshot_manifest(snapshot_dir)
    issues: list[str] = []
    from museum_pipeline.validation.dispatch import validate_record

    issues.extend(issue.code for issue in validate_record(manifest))
    try:
        fetched_at = datetime.fromisoformat(str(manifest.get("fetched_at", "")).replace("Z", "+00:00"))
        if fetched_at > (now or datetime.now(timezone.utc)) + timedelta(minutes=5):
            issues.append("future_fetched_at")
    except ValueError:
        issues.append("fetched_at_invalid")
    body_path = manifest.get("response_body_path")
    if body_path is not None:
        try:
            body_file = resolve_within(snapshot_dir, str(body_path), must_exist=True)
            body = body_file.read_bytes()
            if len(body) != manifest.get("body_bytes"):
                issues.append("body_bytes_mismatch")
            if sha256_bytes(body) != manifest.get("body_sha256"):
                issues.append("body_hash_mismatch")
        except PipelineError as error:
            issues.append(error.code)
    elif manifest.get("event_type") not in {"duplicate_content", "not_modified"} or not manifest.get("reused_body_snapshot_id"):
        issues.append("body_reference_invalid")
    else:
        governed_root = raw_root or _infer_raw_root(snapshot_dir, str(manifest.get("source_id", "")))
        reference = _find_snapshot_by_id(governed_root, str(manifest["reused_body_snapshot_id"])) if governed_root else None
        if reference is None:
            issues.append("snapshot_body_reference_missing")
        else:
            try:
                referenced_manifest = load_snapshot_manifest(reference)
                if referenced_manifest.get("source_id") != manifest.get("source_id"):
                    issues.append("body_reference_source_mismatch")
                body = snapshot_body_bytes(reference, raw_root=governed_root)
                if len(body) != manifest.get("body_bytes"):
                    issues.append("body_bytes_mismatch")
                if sha256_bytes(body) != manifest.get("body_sha256"):
                    issues.append("body_hash_mismatch")
            except PipelineError as error:
                issues.append(error.code)
    if manifest.get("source_registry_snapshot_hash") != source_registry_snapshot_hash():
        issues.append("source_registry_snapshot_hash_mismatch")
    if manifest.get("license_rules_snapshot_hash") != license_rules_snapshot_hash():
        issues.append("license_rules_snapshot_hash_mismatch")
    try:
        from museum_pipeline.adapters import get_adapter

        adapter = get_adapter(str(manifest.get("source_id")))
    except PipelineError as error:
        expected_adapter_version = None
        issues.append(error.code)
    else:
        expected_adapter_version = adapter.adapter_version
        try:
            for source_object_id in manifest.get("source_object_ids", []):
                adapter.validate_object_id(str(source_object_id))
            request_headers = manifest.get("sanitized_request", {}).get("headers", {})
            for url in [manifest.get("canonical_endpoint"), *manifest.get("redirect_chain", []), manifest.get("final_url")]:
                adapter.validate_request(RequestSpec(
                    str(manifest.get("http_method")), str(url), request_headers,
                    str(manifest.get("query_profile")), manifest.get("credential_alias"),
                ))
        except PipelineError as error:
            issues.append(error.code)
    if expected_adapter_version is None or manifest.get("adapter_version") != expected_adapter_version:
        issues.append("unknown_adapter_version")
    if contains_unredacted_secret(json.dumps(manifest.get("sanitized_request", {}), ensure_ascii=False)):
        issues.append("secret_not_redacted")
    sanitized = manifest.get("sanitized_request", {})
    for outer, inner in (
        ("canonical_endpoint", "canonical_endpoint"),
        ("http_method", "method"),
        ("query_profile", "query_profile"),
        ("credential_alias", "credential_alias"),
    ):
        if manifest.get(outer) != sanitized.get(inner):
            issues.append("sanitized_request_manifest_mismatch")
    redirects = manifest.get("redirect_chain", [])
    expected_final = redirects[-1] if redirects else manifest.get("canonical_endpoint")
    if manifest.get("final_url") != expected_final:
        issues.append("redirect_chain_final_url_mismatch")
    if set(manifest.get("response_headers", {})) - ALLOWED_RESPONSE_HEADERS:
        issues.append("response_header_not_allowlisted")
    if any("[REDACTED]" not in str(value) and name.lower() in {"authorization", "cookie", "token", "api_key"}
           for name, value in manifest.get("sanitized_request", {}).get("headers", {}).items()):
        issues.append("secret_not_redacted")
    expected_suffix = str(manifest.get("body_sha256", ""))[7:19]
    if expected_suffix and not str(manifest.get("snapshot_id", "")).endswith(f":{expected_suffix}"):
        issues.append("snapshot_id_body_hash_mismatch")
    return sorted(set(issues))


def snapshot_body_bytes(snapshot_dir: Path, *, raw_root: Path | None = None, _visited: set[str] | None = None) -> bytes:
    manifest = load_snapshot_manifest(snapshot_dir)
    governed_root = raw_root or _infer_raw_root(snapshot_dir, str(manifest.get("source_id", ""))) or RAW_ROOT
    visited = set(_visited or set())
    snapshot_id = str(manifest.get("snapshot_id", ""))
    if snapshot_id in visited:
        raise PipelineError("snapshot_body_reference_cycle", "Snapshot body references contain a cycle")
    visited.add(snapshot_id)
    body_path = manifest.get("response_body_path")
    if isinstance(body_path, str):
        return resolve_within(snapshot_dir, body_path, must_exist=True).read_bytes()
    reference = manifest.get("reused_body_snapshot_id")
    if not isinstance(reference, str):
        raise PipelineError("snapshot_body_missing", "Snapshot has no body or valid body reference")
    target = _find_snapshot_by_id(governed_root, reference)
    if target is None:
        raise PipelineError("snapshot_body_reference_missing", "Referenced snapshot body cannot be resolved")
    target_manifest = load_snapshot_manifest(target)
    if target_manifest.get("source_id") != manifest.get("source_id"):
        raise PipelineError("body_reference_source_mismatch", "Referenced snapshot belongs to a different source")
    return snapshot_body_bytes(target, raw_root=governed_root, _visited=visited)


def _find_body_snapshot(source_root: Path, body_hash: str) -> Path | None:
    if not source_root.exists():
        return None
    for manifest_path in sorted(source_root.rglob("manifest.json")):
        if manifest_path.is_symlink():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("body_sha256") == body_hash and isinstance(manifest.get("response_body_path"), str):
            try:
                body_path = resolve_within(manifest_path.parent, manifest["response_body_path"], must_exist=True)
                body = body_path.read_bytes()
            except (OSError, PipelineError):
                continue
            if len(body) == manifest.get("body_bytes") and sha256_bytes(body) == body_hash:
                return manifest_path.parent
    return None


def _find_snapshot_by_id(raw_root: Path, snapshot_id: str) -> Path | None:
    for manifest_path in sorted(raw_root.rglob("manifest.json")) if raw_root.exists() else []:
        if manifest_path.is_symlink():
            continue
        try:
            if json.loads(manifest_path.read_text(encoding="utf-8")).get("snapshot_id") == snapshot_id:
                return manifest_path.parent
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _referenced_body_metadata(snapshot_dir: Path | None) -> tuple[int, str]:
    if snapshot_dir is None:
        raise PipelineError("snapshot_body_reference_missing", "Referenced body snapshot is missing")
    manifest = load_snapshot_manifest(snapshot_dir)
    return int(manifest["body_bytes"]), str(manifest["body_sha256"])


def _infer_raw_root(snapshot_dir: Path, source_id: str) -> Path | None:
    try:
        resolved = snapshot_dir.resolve(strict=True)
    except OSError:
        return None
    if len(resolved.parents) >= 5 and resolved.parents[3].name == source_id:
        return resolved.parents[4]
    return None
