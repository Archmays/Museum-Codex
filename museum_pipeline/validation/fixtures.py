from __future__ import annotations

import io
import json
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from museum_pipeline.adapters import get_adapter
from museum_pipeline.adapters.base import RequestSpec, ResponseContract
from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.config import source_license_rules
from museum_pipeline.errors import PipelineError, contains_unredacted_secret
from museum_pipeline.identity.signals import special_identity_mapping_issues
from museum_pipeline.normalization.rights import media_candidate_issues
from museum_pipeline.paths import resolve_within, safe_relative_path
from museum_pipeline.review.decisions import decision_is_stale
from museum_pipeline.snapshots import load_snapshot_manifest, validate_snapshot, write_snapshot
from museum_pipeline.transport import HttpTransport, TransportPolicy
from museum_pipeline.validation.dispatch import validate_record


def evaluate_invalid_fixture(case: dict) -> set[str]:
    operation = case["operation"]
    codes: set[str] = set()
    try:
        if operation == "validate_request":
            adapter = get_adapter(case["source_id"])
            adapter.validate_request(RequestSpec("GET", case["url"], adapter.default_headers(), "default"))
        elif operation == "redaction":
            value = case.get("text", f"{case.get('header')}={case.get('value')}")
            if contains_unredacted_secret(value):
                codes.add("secret_not_redacted")
        elif operation == "safe_path":
            safe_relative_path(case["path"])
        elif operation == "symlink_path":
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "link").mkdir()
                original = Path.is_symlink
                with patch.object(Path, "is_symlink", lambda self: self.name == "link" or original(self)):
                    resolve_within(root, case["path"])
        elif operation in {"snapshot_mutation", "snapshot_overwrite"}:
            codes.update(_snapshot_case(case))
        elif operation == "license_rule":
            if case["rule_id"] not in {rule["rule_id"] for rule in source_license_rules(case["source_id"])}:
                codes.add("source_rule_missing")
        elif operation == "aic_fields":
            get_adapter("aic_api").map_license_rules(case["fields"])
        elif operation == "aic_wrong_rule":
            actual = get_adapter("aic_api").map_license_rules(get_adapter("aic_api").profile_fields("description"))[case["field"]]
            if actual != case["rule_id"]:
                codes.add("aic_license_rule_mismatch")
        elif operation == "media_rights":
            hints = {case["hint"]: True}
            candidate = {"rights_status": case["rights_status"], "development_only": False, "rights_hints": hints, "bytes_downloaded": False}
            codes.update(media_candidate_issues(candidate))
        elif operation == "tier3_claim":
            record = {"entity_type": "normalized_candidate", "candidate_claims": [{"source_tier": 3, "status": case["status"]}]}
            codes.update(issue.code for issue in validate_record(record))
        elif operation == "identity_proposal":
            record = {"entity_type": "identity_proposal", "proposed_status": case["proposed_status"], "signals": case["signals"], "hard_conflicts": case["hard_conflicts"]}
            codes.update(issue.code for issue in validate_record(record))
        elif operation == "special_identity":
            codes.update(special_identity_mapping_issues(case["source_kind"], case["normalized_kind"]))
        elif operation == "stale_decision":
            bundle = {"exact_input_hashes": {"candidate.json": case["bundle_hash"]}}
            decision = {"input_hashes": {"candidate.json": case["decision_hash"]}}
            if decision_is_stale(bundle, decision):
                codes.add("stale_input_hashes")
        elif operation == "merge_record":
            record = {
                "entity_type": "merge_record", "survivor_candidate_id": "candidate:survivor",
                "loser_candidate_ids": case["loser_ids"], "alias_mappings": case["alias_mappings"],
                "loser_ids_retained": True,
            }
            codes.update(issue.code for issue in validate_record(record))
        elif operation == "contract_drift":
            if not case.get("quarantine"):
                codes.add("unknown_field_not_quarantined")
        elif operation == "public_leak":
            from scripts.scan_public_artifact_for_candidate_data import scan_public_artifact

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "dist"
                target = root / Path(case["path"]).relative_to("dist")
                target.parent.mkdir(parents=True)
                target.write_text(case["content"], encoding="utf-8")
                codes.update(item["code"] for item in scan_public_artifact(root))
        elif operation == "recorded_notice":
            if case.get("notice_present") is not True:
                codes.add("recorded_fixture_notice_missing")
        elif operation == "retry_limit":
            adapter = get_adapter("wikidata")
            request = adapter.build_request("Q42")
            responses = [ResponseContract(status, {"content-type": "application/json"}, b"{}", request.url) for status in case["statuses"]]
            transport = _SequenceTransport(responses)
            result = transport.fetch(adapter, request)
            if result.retry_count == transport.policy.max_retries and transport.remaining:
                codes.add("retry_limit_exceeded")
        elif operation == "redirect":
            adapter = get_adapter(case["source_id"])
            request = adapter.build_request("Q42")
            transport = _SequenceTransport([ResponseContract(302, {"location": case["location"]}, b"", request.url)])
            transport.fetch(adapter, request)
        else:
            codes.add("fixture_operation_unknown")
    except PipelineError as error:
        codes.add(error.code)
    return codes


def validate_recorded_fixture_directory(directory: Path) -> list[str]:
    issues: list[str] = []
    manifest_path = directory / "fixture-manifest.json"
    body_path = directory / "response.body"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["recorded_fixture_manifest_invalid"]
    required = {
        "schema_version", "source_id", "adapter_version", "contract_version", "captured_at",
        "official_endpoint", "sanitized_request", "content_type", "body_bytes", "body_sha256",
        "fixture_projection", "projection_note", "original_live_snapshot_id", "original_live_body_bytes",
        "original_live_body_sha256", "source_license_rule_ids", "terms_url", "documentation_url",
        "third_party_notice_path", "media_bytes_included", "curatorial_selection",
    }
    if required - set(manifest):
        issues.append("recorded_fixture_manifest_incomplete")
    try:
        notice = resolve_within(directory, str(manifest.get("third_party_notice_path", "")), must_exist=True)
    except PipelineError:
        notice = None
    if notice is None or not notice.read_text(encoding="utf-8").strip():
        issues.append("recorded_fixture_notice_missing")
    if not body_path.exists():
        issues.append("recorded_fixture_body_missing")
        return issues
    from museum_pipeline.hashing import sha256_bytes

    body = body_path.read_bytes()
    if len(body) != manifest.get("body_bytes"):
        issues.append("recorded_fixture_bytes_mismatch")
    if sha256_bytes(body) != manifest.get("body_sha256"):
        issues.append("recorded_fixture_hash_mismatch")
    if manifest.get("media_bytes_included") is not False:
        issues.append("recorded_fixture_media_bytes_forbidden")
    if manifest.get("curatorial_selection") is not False:
        issues.append("recorded_fixture_curatorial_boundary_invalid")
    if manifest.get("fixture_projection") is not True or not str(manifest.get("projection_note", "")).strip():
        issues.append("recorded_fixture_projection_undocumented")
    if not isinstance(manifest.get("original_live_body_bytes"), int) or manifest.get("original_live_body_bytes", 0) < len(body):
        issues.append("recorded_fixture_live_bytes_invalid")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", str(manifest.get("original_live_body_sha256", ""))):
        issues.append("recorded_fixture_live_hash_invalid")
    try:
        adapter = get_adapter(manifest["source_id"])
        if directory.name != adapter.source_id:
            issues.append("recorded_fixture_source_directory_mismatch")
        if manifest.get("adapter_version") != adapter.adapter_version or manifest.get("contract_version") != adapter.contract_version:
            issues.append("recorded_fixture_adapter_version_mismatch")
        request = manifest.get("sanitized_request", {})
        if contains_unredacted_secret(json.dumps(request, ensure_ascii=False)):
            issues.append("recorded_fixture_secret_not_redacted")
        if request.get("canonical_endpoint") != manifest.get("official_endpoint"):
            issues.append("recorded_fixture_endpoint_mismatch")
        adapter.validate_request(RequestSpec(
            request.get("method"), request.get("canonical_endpoint"), request.get("headers", {}),
            request.get("query_profile"), request.get("credential_alias"),
        ))
        response = ResponseContract(200, {"content-type": manifest["content_type"]}, body, manifest["official_endpoint"])
        document = adapter.validate_response_contract(response)
        candidate = adapter.normalize(
            document,
            snapshot_id=str(manifest["original_live_snapshot_id"]),
            observed_at=str(manifest["captured_at"]),
        )
        if validate_record(candidate):
            issues.append("recorded_fixture_normalization_invalid")
        used_rule_ids = {
            item["license_rule_id"]
            for collection in (candidate["field_provenance"], candidate["candidate_claims"], candidate["media_candidates"])
            for item in collection
        }
        if not used_rule_ids <= set(manifest.get("source_license_rule_ids", [])):
            issues.append("recorded_fixture_rule_binding_missing")
        rule_ids = {rule["rule_id"] for rule in source_license_rules(adapter.source_id)}
        if not set(manifest.get("source_license_rule_ids", [])) <= rule_ids:
            issues.append("recorded_fixture_rule_missing")
    except (KeyError, PipelineError):
        issues.append("recorded_fixture_contract_invalid")
    return sorted(set(issues))


def _snapshot_case(case: dict) -> set[str]:
    adapter = get_adapter("aic_api")
    request = adapter.build_request("27992")
    response = ResponseContract(200, {"content-type": "application/json"}, b'{"fixture":true}\r\n', request.url)
    timestamp = datetime(2026, 7, 12, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as temporary:
        raw_root = Path(temporary) / "raw"
        snapshot = write_snapshot(
            adapter=adapter, request=request, response=response, source_object_ids=["27992"],
            run_id="pipeline-run:77777777-7777-5777-8777-777777777777", fetched_at=timestamp,
            raw_root=raw_root,
        )
        if case["operation"] == "snapshot_overwrite":
            try:
                write_snapshot(
                    adapter=adapter, request=request, response=response, source_object_ids=["27992"],
                    run_id="pipeline-run:77777777-7777-5777-8777-777777777777", fetched_at=timestamp,
                    raw_root=raw_root,
                )
            except PipelineError as error:
                return {error.code}
            return set()
        manifest = load_snapshot_manifest(snapshot)
        manifest[case["field"]] = case["value"]
        write_canonical_json(snapshot / "manifest.json", manifest)
        return set(validate_snapshot(snapshot))


class _SequenceTransport(HttpTransport):
    def __init__(self, responses: list[ResponseContract]) -> None:
        super().__init__(
            policy=TransportPolicy(total_timeout_seconds=30, max_retries=3),
            sleeper=lambda _delay: None,
            random_value=lambda: 0,
            resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
        )
        self.remaining = list(responses)

    def _one_request(self, request: RequestSpec, timeout: float) -> ResponseContract:
        if not self.remaining:
            raise PipelineError("fixture_response_empty", "No fixture response remains")
        return self.remaining.pop(0)
