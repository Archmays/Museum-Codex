from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_bytes
from museum_pipeline.media.constants import (
    COMMONS_SEARCH_HOST,
    MAX_DECODE_PIXELS,
    MAX_MEDIA_BYTES,
    MAX_METADATA_BYTES,
    MEDIA_VAULT,
    PHASE_ID,
    PIPELINE_EXECUTOR,
    SOURCE_POLICIES,
    artwork_slug,
    artwork_vault,
)
from museum_pipeline.media.discovery import (
    build_discovery_record,
    commons_search_url,
    metadata_request_url,
    parse_commons_search,
    rijks_object_pid,
    rijks_resolver_url,
    validate_rijks_chain_step,
)
from museum_pipeline.media.image_processing import (
    ImageProcessingError,
    compare_preview_visual_match,
    inspect_image_bytes,
)
from museum_pipeline.media.inputs import load_media_inputs
from museum_pipeline.media.state import load_json, replace_generated, utc_now, write_bytes_once, write_once
from museum_pipeline.media.transport import (
    MediaAcquisitionEvidence,
    MediaDownloadRequest,
    MediaDownloadResult,
    MediaTransport,
    MediaTransportPolicy,
    MetadataFetchRequest,
    MetadataFetchResult,
)


_EVENT_HEADERS = {"content-type", "content-length", "etag", "last-modified", "retry-after", "location"}
_COMMONS_PROFILE = {
    "source_id": "source:wikimedia_commons",
    "role": "supplementary_discovery_only",
    "canonical_host": COMMONS_SEARCH_HOST,
    "endpoint": "/w/api.php",
    "license_gate": "permanent_revision_file_level_license_no_fair_use_no_dispute_official_object_corroboration_visual_match",
    "auto_promotion": False,
    "version": "1.0.0",
}
_RIJKS_METADATA_FILES = {
    "object": (
        "official-metadata-response.json",
        "official-metadata-headers.json",
        "metadata-acquisition-event.json",
        "metadata",
    ),
    "visual_item": (
        "official-metadata-visual-item-response.json",
        "official-metadata-visual-item-headers.json",
        "metadata-visual-item-acquisition-event.json",
        "metadata-visual-item",
    ),
    "digital_object": (
        "official-metadata-digital-object-response.json",
        "official-metadata-digital-object-headers.json",
        "metadata-digital-object-acquisition-event.json",
        "metadata-digital-object",
    ),
}


def media_transport() -> MediaTransport:
    return MediaTransport(
        policy=MediaTransportPolicy(
            total_timeout_seconds=180.0,
            max_bytes=MAX_MEDIA_BYTES,
            max_metadata_bytes=MAX_METADATA_BYTES,
            max_redirects=3,
            max_retries=3,
            source_min_interval_seconds={
                "source:aic_api": 1.0,
                "source:cleveland_open_access": 1.0,
                "source:met_open_access": 0.25,
                "source:rijksmuseum": 1.0,
                "source:wikimedia_commons": 1.0,
            },
        )
    )


def discover_all(*, live: bool, transport: MediaTransport | None = None) -> dict[str, Any]:
    if not live:
        raise PipelineError("media_network_disabled", "Media discovery is offline unless --live is explicit", exit_code=4)
    inputs = load_media_inputs()
    client = transport or media_transport()
    discovered = reused = failed = alternatives = 0
    failures: list[dict[str, str]] = []
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        directory = artwork_vault(artwork["id"])
        discovery_path = directory / "discovery.json"
        if discovery_path.exists():
            reused += 1
            continue
        request = load_json(directory / "acquisition-request.json")
        url = metadata_request_url(request["source_id"], request["source_object_id"])
        try:
            metadata_chain: list[dict[str, Any]] | None = None
            if request["source_id"] == "source:rijksmuseum":
                resolved = _resolve_rijks_metadata_chain(
                    client,
                    request,
                    persist_step=lambda step: _persist_rijks_metadata_step(directory, step),
                )
                response_body = resolved["body"]
                response_sha256 = resolved["response_sha256"]
                event = resolved["steps"][0]["event"]
                metadata_hops = [
                    hop
                    for step in resolved["steps"]
                    for hop in step["hop_evidence"]
                ]
                metadata_chain = [
                    {
                        "role": step["role"],
                        "request_url": step["request_url"],
                        "final_url": step["event"]["final_url"],
                        "response_sha256": step["response_sha256"],
                        "event_id": step["event"]["id"],
                        "response_file": step["response_file"],
                        "headers_file": step["headers_file"],
                        "event_file": step["event_file"],
                        "network_hops": step["hop_evidence"],
                    }
                    for step in resolved["steps"]
                ]
                write_bytes_once(directory / "official-metadata-envelope.json", response_body)
            else:
                result = client.fetch_metadata(
                    MetadataFetchRequest(
                        url=url,
                        source_id=request["source_id"],
                        trusted_hosts=frozenset({SOURCE_POLICIES[request["source_id"]]["metadata_host"]}),
                    )
                )
                if result.status_code != 200:
                    raise PipelineError("media_metadata_status", "Official metadata endpoint did not return HTTP 200", exit_code=5)
                observed_at = utc_now()
                write_bytes_once(directory / "official-metadata-response.json", result.body)
                write_once(directory / "official-metadata-headers.json", dict(result.response_headers))
                event = _metadata_event(request, result, observed_at)
                write_once(directory / "metadata-acquisition-event.json", event)
                response_body = result.body
                response_sha256 = sha256_bytes(result.body)
                metadata_hops = [asdict(hop) for hop in result.hop_evidence]

            observed_at = utc_now()
            discovery = build_discovery_record(
                request,
                response_body,
                response_sha256=response_sha256,
            )
            discovery.update(
                {
                    "metadata_event_id": event["id"],
                    "discovered_at": observed_at,
                    "metadata_hops": metadata_hops,
                }
            )
            if metadata_chain is not None:
                discovery["metadata_chain"] = metadata_chain
            if not discovery["media"]["source_url"]:
                alternative = _search_alternative(client, request, discovery, directory, observed_at)
                discovery["alternative_source_search_id"] = alternative["id"]
                alternatives += 1
            else:
                discovery["alternative_source_search_id"] = None
            write_once(discovery_path, discovery)
            discovered += 1
        except (PipelineError, OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            failure = _failure_record(request, "discovery", error)
            _persist_failure(directory / "discovery-failure.json", failure)
            failures.append({"artwork_id": artwork["id"], "code": failure["error_code"]})
            failed += 1
    return {
        "ok": failed == 0,
        "summary": "official metadata discovery completed",
        "total": len(inputs.artworks),
        "discovered": discovered,
        "reused": reused,
        "failed": failed,
        "alternative_searches": alternatives,
        "failures": failures,
    }


def acquire_all(
    *,
    live: bool,
    download_media: bool,
    transport: MediaTransport | None = None,
) -> dict[str, Any]:
    if not live or not download_media:
        raise PipelineError(
            "media_live_flags_required",
            "Media acquisition requires both --live and --download-media",
            exit_code=4,
        )
    inputs = load_media_inputs()
    client = transport or media_transport()
    downloaded = reused = unavailable = failed = 0
    original_bytes = 0
    failures: list[dict[str, str]] = []
    dedupe_candidates: list[Path] = []
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        directory = artwork_vault(artwork["id"])
        byte_path = directory / "byte-record.json"
        if byte_path.exists():
            request = load_json(directory / "acquisition-request.json")
            discovery = load_json(directory / "discovery.json")
            record = load_json(byte_path)
            source_url = discovery["media"]["source_url"]
            original = directory / "original.jpg"
            persisted = _load_acquisition_evidence(
                directory / "original-acquisition-event.json",
                request=request,
                source_url=source_url,
                kind="original",
            )
            if persisted is None:
                raise PipelineError(
                    "media_resume_evidence_missing",
                    "Existing byte record has no trusted original acquisition evidence",
                    exit_code=5,
                )
            record_hash = record.get("sha256")
            if not isinstance(record_hash, str):
                raise PipelineError(
                    "media_resume_evidence_mismatch",
                    "Existing byte record has no evidence-bound SHA-256",
                    exit_code=5,
                )
            event, evidence = persisted
            result = client.download(
                MediaDownloadRequest(
                    url=source_url,
                    source_id=request["source_id"],
                    trusted_hosts=frozenset(discovery["media"]["trusted_hosts"]),
                    destination=original,
                    expected_sha256=record_hash,
                    resume_evidence=evidence,
                )
            )
            _validate_existing_byte_record(record, request, event, result, original)
            reused += 1
            original_bytes += result.file_size
            dedupe_candidates.append(original)
            continue
        discovery_path = directory / "discovery.json"
        if not discovery_path.exists():
            unavailable += 1
            continue
        discovery = load_json(discovery_path)
        source_url = discovery["media"]["source_url"]
        if not source_url:
            unavailable += 1
            continue
        request = load_json(directory / "acquisition-request.json")
        destination = directory / "original.jpg"
        try:
            persisted = _load_acquisition_evidence(
                directory / "original-acquisition-event.json",
                request=request,
                source_url=source_url,
                kind="original",
            )
            expected = persisted[1].sha256 if persisted is not None else None
            result = client.download(
                MediaDownloadRequest(
                    url=source_url,
                    source_id=request["source_id"],
                    trusted_hosts=frozenset(discovery["media"]["trusted_hosts"]),
                    destination=destination,
                    expected_sha256=expected,
                    resume_evidence=persisted[1] if persisted is not None else None,
                    dedupe_candidates=tuple(dedupe_candidates),
                )
            )
            payload = destination.read_bytes()
            inspected = inspect_image_bytes(payload, result.content_type, max_pixels=MAX_DECODE_PIXELS)
            if inspected["quality"]["flags"]["placeholder_suspected"] or inspected["quality"]["flags"]["tracking_pixel"]:
                raise ImageProcessingError("placeholder_detected", "Official media bytes appear to be a placeholder or tracking pixel")
            if result.reused_existing:
                if persisted is None:
                    raise PipelineError(
                        "media_resume_evidence_missing",
                        "Existing original was reused without persisted acquisition evidence",
                        exit_code=5,
                    )
                event = persisted[0]
                acquired_at = event["occurred_at"]
            else:
                acquired_at = utc_now()
                event = _download_event(request, result, acquired_at, "original")
                event["request_url"] = source_url
                write_once(directory / "original-acquisition-event.json", event)
            visual_match = _acquire_preview(client, request, discovery, directory, payload, result.content_type)
            technical = {"inspection": inspected, "official_preview_match": visual_match}
            write_once(directory / "technical-inspection.json", technical)
            byte_record = _byte_record(request, result, inspected, event, acquired_at)
            write_once(byte_path, byte_record)
            downloaded += int(not result.reused_existing)
            reused += int(result.reused_existing)
            original_bytes += result.file_size
            dedupe_candidates.append(destination)
        except (PipelineError, ImageProcessingError, OSError, ValueError) as error:
            failure = _failure_record(request, "acquisition", error)
            _persist_failure(directory / "acquisition-failure.json", failure)
            failures.append({"artwork_id": artwork["id"], "code": failure["error_code"]})
            failed += 1
    return {
        "ok": True,
        "summary": "eligible official media acquisition attempts completed",
        "total_artworks": len(inputs.artworks),
        "downloaded": downloaded,
        "reused": reused,
        "no_approved_locator": unavailable,
        "failed": failed,
        "original_bytes": original_bytes,
        "failures": failures,
    }


def _load_acquisition_evidence(
    path: Path,
    *,
    request: Mapping[str, Any],
    source_url: Any,
    kind: str,
) -> tuple[dict[str, Any], MediaAcquisitionEvidence] | None:
    if not path.exists():
        return None
    event = load_json(path)
    expected_bindings = {
        "schema_version": "1.0.0",
        "id": f"media-event:{artwork_slug(request['artwork_id'])}-{kind}",
        "entity_type": "media_acquisition_event",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "request_id": request["id"],
        "artwork_id": request["artwork_id"],
        "event_type": "download_completed",
        "request_url": source_url,
        "status_code": 200,
        "error_code": None,
        "terminal": True,
        "data_version": "1.0.0",
    }
    if not isinstance(event, dict) or any(event.get(key) != value for key, value in expected_bindings.items()):
        raise PipelineError(
            "media_resume_evidence_mismatch",
            "Persisted acquisition evidence is not bound to the exact original request",
            exit_code=5,
        )
    final_url = event.get("final_url")
    redirects = event.get("redirect_chain")
    headers = event.get("response_headers")
    resolved_ips = event.get("resolved_public_ips")
    peer_ip = event.get("connected_peer_ip")
    digest = event.get("body_sha256")
    byte_count = event.get("bytes_received")
    occurred_at = event.get("occurred_at")
    if (
        not isinstance(source_url, str)
        or not isinstance(final_url, str)
        or not isinstance(redirects, list)
        or any(not isinstance(value, str) for value in redirects)
        or not isinstance(headers, dict)
        or not isinstance(resolved_ips, list)
        or not resolved_ips
        or any(not isinstance(value, str) for value in resolved_ips)
        or not isinstance(peer_ip, str)
        or not isinstance(digest, str)
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count <= 0
        or not isinstance(occurred_at, str)
        or not occurred_at
    ):
        raise PipelineError(
            "media_resume_evidence_invalid",
            "Persisted acquisition evidence does not close bytes and HTTP hop evidence",
            exit_code=5,
        )
    evidence = MediaAcquisitionEvidence(
        request_url=source_url,
        final_url=final_url,
        redirect_chain=tuple(redirects),
        status_code=event["status_code"],
        response_headers=headers,
        resolved_public_ips=tuple(resolved_ips),
        connected_peer_ip=peer_ip,
        sha256=digest,
        file_size=byte_count,
    )
    return event, evidence


def _validate_existing_byte_record(
    record: Mapping[str, Any],
    request: Mapping[str, Any],
    event: Mapping[str, Any],
    result: MediaDownloadResult,
    original: Path,
) -> None:
    expected_relative = original.resolve().relative_to(MEDIA_VAULT.parents[3].resolve()).as_posix()
    expected_bindings = {
        "request_id": request["id"],
        "event_id": event["id"],
        "artwork_id": request["artwork_id"],
        "source_id": request["source_id"],
        "source_url": event["request_url"],
        "final_url": result.final_url,
        "status_code": result.status_code,
        "mime_declared": result.content_type,
        "magic_mime": result.content_type,
        "byte_length": result.file_size,
        "sha256": result.sha256,
        "vault_relative_path": expected_relative,
    }
    if not isinstance(record, Mapping) or any(record.get(key) != value for key, value in expected_bindings.items()):
        raise PipelineError(
            "media_resume_evidence_mismatch",
            "Existing byte record is not bound to its exact acquisition evidence and local bytes",
            exit_code=5,
        )


def _resolve_rijks_metadata_chain(
    client: MediaTransport,
    request: dict[str, Any],
    *,
    persist_step: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if request.get("source_id") != "source:rijksmuseum":
        raise ValueError("Rijksmuseum metadata resolver received a different source")

    policy = SOURCE_POLICIES["source:rijksmuseum"]
    trusted_hosts = frozenset({policy["metadata_host"]})
    expected_pid = rijks_object_pid(request["source_object_id"])
    request_url = metadata_request_url(request["source_id"], request["source_object_id"])
    documents: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []

    for role in ("object", "visual_item", "digital_object"):
        response_file, headers_file, event_file, event_suffix = _RIJKS_METADATA_FILES[role]
        result = client.fetch_metadata(
            MetadataFetchRequest(
                url=request_url,
                source_id=request["source_id"],
                trusted_hosts=trusted_hosts,
            )
        )
        if result.status_code != 200:
            raise PipelineError(
                "media_metadata_status",
                "Rijksmuseum resolver did not return HTTP 200",
                exit_code=5,
            )

        event = _metadata_event_for_url(
            request,
            result,
            utc_now(),
            request_url=request_url,
            event_suffix=event_suffix,
        )
        step = {
            "role": role,
            "request_url": request_url,
            "response_body": result.body,
            "response_sha256": sha256_bytes(result.body),
            "response_headers": dict(result.response_headers),
            "hop_evidence": [asdict(hop) for hop in result.hop_evidence],
            "event": event,
            "response_file": response_file,
            "headers_file": headers_file,
            "event_file": event_file,
        }
        if persist_step is not None:
            persist_step(step)

        if result.final_url != request_url or result.redirect_chain:
            raise PipelineError(
                "rijks_metadata_endpoint_mismatch",
                "Rijksmuseum resolver changed the exact governed PID endpoint",
                exit_code=5,
            )
        document, next_pid = validate_rijks_chain_step(
            result.body,
            role=role,
            expected_pid=expected_pid,
        )
        documents[role] = document
        steps.append(step)
        if next_pid is not None:
            expected_pid = next_pid
            request_url = rijks_resolver_url(next_pid)

    body = canonical_json_bytes(documents)
    return {
        "body": body,
        "response_sha256": sha256_bytes(body),
        "steps": steps,
    }


def _persist_rijks_metadata_step(directory: Path, step: Mapping[str, Any]) -> None:
    write_bytes_once(directory / str(step["response_file"]), step["response_body"])
    write_once(directory / str(step["headers_file"]), step["response_headers"])
    write_once(directory / str(step["event_file"]), step["event"])


def _metadata_event(request: dict[str, Any], result: MetadataFetchResult, occurred_at: str) -> dict[str, Any]:
    return _metadata_event_for_url(
        request,
        result,
        occurred_at,
        request_url=metadata_request_url(request["source_id"], request["source_object_id"]),
        event_suffix="metadata",
    )


def _metadata_event_for_url(
    request: dict[str, Any],
    result: MetadataFetchResult,
    occurred_at: str,
    *,
    request_url: str,
    event_suffix: str,
) -> dict[str, Any]:
    return _event(
        request,
        event_id=f"media-event:{artwork_slug(request['artwork_id'])}-{event_suffix}",
        event_type="download_completed",
        occurred_at=occurred_at,
        request_url=request_url,
        final_url=result.final_url,
        redirects=result.redirect_chain,
        ips=result.resolved_public_ips,
        peer=result.connected_peer_ip,
        status=result.status_code,
        headers=result.response_headers,
        byte_count=len(result.body),
        digest=sha256_bytes(result.body),
    )


def _download_event(
    request: dict[str, Any],
    result: MediaDownloadResult,
    occurred_at: str,
    kind: str,
) -> dict[str, Any]:
    event_type = "reused_existing_bytes" if result.reused_existing else "not_modified" if result.not_modified else "download_completed"
    return _event(
        request,
        event_id=f"media-event:{artwork_slug(request['artwork_id'])}-{kind}",
        event_type=event_type,
        occurred_at=occurred_at,
        request_url=result.final_url if result.reused_existing else (request.get("candidate_media_url") or result.final_url),
        final_url=result.final_url,
        redirects=result.redirect_chain,
        ips=result.resolved_public_ips,
        peer=result.connected_peer_ip,
        status=result.status_code,
        headers=result.response_headers,
        byte_count=result.file_size,
        digest=result.sha256,
    )


def _event(
    request: dict[str, Any],
    *,
    event_id: str,
    event_type: str,
    occurred_at: str,
    request_url: str,
    final_url: str | None,
    redirects: Iterable[str],
    ips: Iterable[str],
    peer: str | None,
    status: int | None,
    headers: Mapping[str, str],
    byte_count: int,
    digest: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": event_id,
        "entity_type": "media_acquisition_event",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "request_id": request["id"],
        "artwork_id": request["artwork_id"],
        "event_type": event_type,
        "occurred_at": occurred_at,
        "request_url": request_url,
        "final_url": final_url,
        "redirect_chain": list(redirects),
        "resolved_public_ips": sorted(set(ips)),
        "connected_peer_ip": peer,
        "status_code": status,
        "response_headers": {key: value for key, value in headers.items() if key in _EVENT_HEADERS},
        "bytes_received": byte_count,
        "body_sha256": digest,
        "error_code": None,
        "terminal": True,
        "data_version": "1.0.0",
    }


def _byte_record(
    request: dict[str, Any],
    result: MediaDownloadResult,
    inspected: dict[str, Any],
    event: dict[str, Any],
    acquired_at: str,
) -> dict[str, Any]:
    if result.status_code != 200:
        raise PipelineError(
            "media_acquisition_status_invalid",
            "A byte record requires evidence of the original HTTP 200 response",
            exit_code=5,
        )
    relative = result.destination.resolve().relative_to(MEDIA_VAULT.parents[3].resolve()).as_posix()
    phash = inspected["phash"]["value"].replace("phash64:", "phash:")
    flags = inspected["quality"]["flags"]
    return {
        "schema_version": "1.0.0",
        "id": f"media-byte:{artwork_slug(request['artwork_id'])}",
        "entity_type": "media_byte_record",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "request_id": request["id"],
        "event_id": event["id"],
        "artwork_id": request["artwork_id"],
        "source_id": request["source_id"],
        "source_url": (load_json(artwork_vault(request["artwork_id"]) / "discovery.json"))["media"]["source_url"],
        "final_url": result.final_url,
        "status_code": result.status_code,
        "mime_declared": result.content_type,
        "magic_mime": inspected["mime"],
        "byte_length": result.file_size,
        "sha256": result.sha256,
        "phash": phash,
        "width": inspected["display_width"],
        "height": inspected["display_height"],
        "pixels": inspected["display_width"] * inspected["display_height"],
        "decode_passed": True,
        "html_error": False,
        "placeholder": bool(flags["placeholder_suspected"]),
        "tracking_pixel": bool(flags["tracking_pixel"]),
        "immutable": True,
        "vault_relative_path": relative,
        "acquired_at": acquired_at,
        "data_version": "1.0.0",
    }


def _acquire_preview(
    client: MediaTransport,
    request: dict[str, Any],
    discovery: dict[str, Any],
    directory: Path,
    original: bytes,
    original_mime: str,
) -> dict[str, Any] | None:
    preview_url = discovery["media"].get("preview_url")
    if not preview_url or preview_url == discovery["media"].get("source_url"):
        return None
    destination = directory / "official-preview.jpg"
    persisted = _load_acquisition_evidence(
        directory / "preview-acquisition-event.json",
        request=request,
        source_url=preview_url,
        kind="preview",
    )
    expected = persisted[1].sha256 if persisted is not None else None
    result = client.download(
        MediaDownloadRequest(
            url=preview_url,
            source_id=request["source_id"],
            trusted_hosts=frozenset(discovery["media"]["trusted_hosts"]),
            destination=destination,
            expected_sha256=expected,
            resume_evidence=persisted[1] if persisted is not None else None,
        )
    )
    if not result.reused_existing:
        occurred_at = utc_now()
        event = _download_event(request, result, occurred_at, "preview")
        event["request_url"] = preview_url
        write_once(directory / "preview-acquisition-event.json", event)
    return compare_preview_visual_match(
        original,
        original_mime,
        destination.read_bytes(),
        result.content_type,
        max_pixels=MAX_DECODE_PIXELS,
    )


def _search_alternative(
    client: MediaTransport,
    request: dict[str, Any],
    discovery: dict[str, Any],
    directory: Path,
    searched_at: str,
) -> dict[str, Any]:
    expected = request["expected_identity"]
    search_url = commons_search_url(expected["title"], expected["artist"])
    candidates: list[dict[str, Any]] = []
    result_code = "not_found"
    rights_result = "not_evaluated"
    candidate_id = candidate_url = None
    try:
        result = client.fetch_metadata(
            MetadataFetchRequest(
                url=search_url,
                source_id="source:wikimedia_commons",
                trusted_hosts=frozenset({COMMONS_SEARCH_HOST}),
            )
        )
        write_bytes_once(directory / "commons-search-response.json", result.body)
        write_once(directory / "commons-search-headers.json", dict(result.response_headers))
        candidates = parse_commons_search(result.body)
        if candidates:
            result_code = "conflict"
            candidate_id = str(candidates[0].get("page_id"))
            candidate_url = candidates[0].get("description_url")
            rights_result = "unknown"
    except (PipelineError, OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        result_code = "source_unavailable"
    write_once(directory / "commons-search-candidates.json", candidates)
    rights_conflict = discovery["rights"]["conflict"]
    record = {
        "schema_version": "1.0.0",
        "id": f"alternative-search:{artwork_slug(request['artwork_id'])}",
        "entity_type": "media_alternative_source_search",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "artwork_id": request["artwork_id"],
        "original_source_id": request["source_id"],
        "query_basis": {
            "artist": expected["artist"],
            "title": expected["title"],
            "date": expected["date"],
            "institution": expected["institution"],
            "accession": expected["accession"],
            "identity_hash": canonical_sha256(expected),
        },
        "sources_attempted": [
            {
                "source_id": "source:wikimedia_commons",
                "source_class": "registered_official_source",
                "registry_profile_hash": canonical_sha256(_COMMONS_PROFILE),
                "official_endpoint": search_url,
                "identity_result": result_code,
                "rights_result": rights_result,
                "candidate_media_id": candidate_id,
                "candidate_media_url": candidate_url,
                "attempted_at": searched_at,
            }
        ],
        "search_status": "source_unavailable" if result_code == "source_unavailable" else "no_approved_alternative",
        "selected_source_id": None,
        "selected_media_id": None,
        "selected_media_url": None,
        "recommended_terminal_decision": "blocked_rights_conflict" if rights_conflict else "metadata_only_after_automated_review",
        "searched_at": searched_at,
        "data_version": "1.0.0",
    }
    write_once(directory / "alternative-source-search.json", record)
    return record


def commons_profile() -> dict[str, Any]:
    return {**_COMMONS_PROFILE, "content_hash": canonical_sha256(_COMMONS_PROFILE)}


def _failure_record(request: dict[str, Any], step: str, error: Exception) -> dict[str, Any]:
    code = error.code if isinstance(error, PipelineError) else getattr(error, "code", "media_unexpected_failure")
    message = error.public_message if isinstance(error, PipelineError) else str(error)
    return {
        "artwork_id": request["artwork_id"],
        "request_id": request["id"],
        "step": step,
        "error_code": code,
        "message": message,
        "failed_at": utc_now(),
        "terminal_for_artwork": True,
    }


def _persist_failure(path: Path, failure: dict[str, Any]) -> dict[str, Any]:
    """Keep the first identical failure stable and archive changed terminal evidence."""

    if not path.exists():
        write_once(path, failure)
        return failure
    existing = load_json(path)
    stable_fields = ("artwork_id", "request_id", "step", "error_code", "message", "terminal_for_artwork")
    if all(existing.get(field) == failure.get(field) for field in stable_fields):
        return existing
    archive_hash = canonical_sha256(existing).removeprefix("sha256:")[:16]
    archive = path.with_name(f"{path.stem}-{archive_hash}.json")
    write_once(archive, existing)
    replace_generated(path, failure)
    return failure
