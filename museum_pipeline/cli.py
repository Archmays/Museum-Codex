from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from museum_pipeline.acquisition import acquire
from museum_pipeline.adapters import adapters_by_source, get_adapter
from museum_pipeline.adapters.base import ResponseContract
from museum_pipeline.canonical_json import canonical_json_text, write_canonical_json
from museum_pipeline.config import INTERMEDIATE_ROOT, ROOT
from museum_pipeline.errors import PipelineError
from museum_pipeline.identity.proposals import propose_identities
from museum_pipeline.review.bundles import build_review_bundle, load_records
from museum_pipeline.review.decisions import apply_decisions
from museum_pipeline.runs import artifact_ref, create_run_manifest, update_run_inputs, update_run_outputs, utc_now
from museum_pipeline.snapshots import load_snapshot_manifest, snapshot_body_bytes, validate_snapshot
from museum_pipeline.source_registry import verify_sources
from museum_pipeline.validation.dispatch import ValidationIssue, validate_record
from museum_pipeline.validation.physical import validate_review_bundle_file, validate_run_directory
from museum_pipeline.curation.cli import register_curation_commands


EXIT_VALIDATION = 3
EXIT_NETWORK_DISABLED = 4
EXIT_TRANSPORT = 5
EXIT_IO = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m museum_pipeline", description="Offline-first Museum-Codex build-time data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-sources", help="verify endpoint, source, and license registries without network access")
    _json_flag(verify)
    verify.set_defaults(handler=_cmd_verify_sources)

    listing = subparsers.add_parser("list-adapters", help="list the four implemented reference adapters")
    _json_flag(listing)
    listing.set_defaults(handler=_cmd_list_adapters)

    acquisition = subparsers.add_parser("acquire", help="acquire one explicit source object; network is disabled unless --live is present")
    acquisition.add_argument("--source", required=True, choices=sorted(adapters_by_source()))
    acquisition.add_argument("--object-id", required=True)
    acquisition.add_argument("--query-profile", default="default")
    acquisition.add_argument("--live", action="store_true", help="explicitly permit one real HTTPS request sequence")
    _json_flag(acquisition)
    acquisition.set_defaults(handler=_cmd_acquire)

    snapshot = subparsers.add_parser("validate-snapshot", help="validate an immutable raw snapshot directory")
    snapshot.add_argument("snapshot_dir", type=Path)
    _json_flag(snapshot)
    snapshot.set_defaults(handler=_cmd_validate_snapshot)

    normalize = subparsers.add_parser("normalize", help="normalize one raw snapshot into a deterministic candidate run")
    normalize.add_argument("snapshot_dir", type=Path)
    normalize.add_argument("--output-dir", type=Path)
    _json_flag(normalize)
    normalize.set_defaults(handler=_cmd_normalize)

    proposals = subparsers.add_parser("propose-identities", help="create review-only same/distinct/uncertain proposals")
    proposals.add_argument("normalized_dir", type=Path)
    proposals.add_argument("--output", type=Path)
    _json_flag(proposals)
    proposals.set_defaults(handler=_cmd_propose_identities)

    bundle = subparsers.add_parser("build-review-bundle", help="build a local versionable review bundle from a pipeline run")
    bundle.add_argument("pipeline_run_dir", type=Path)
    bundle.add_argument("--output", type=Path)
    _json_flag(bundle)
    bundle.set_defaults(handler=_cmd_build_review_bundle)

    validate_bundle = subparsers.add_parser("validate-review-bundle", help="validate review bundle schema and stale-input hashes")
    validate_bundle.add_argument("bundle", type=Path)
    _json_flag(validate_bundle)
    validate_bundle.set_defaults(handler=_cmd_validate_review_bundle)

    decisions = subparsers.add_parser("apply-decisions", help="apply non-stale local decisions without creating publishable data")
    decisions.add_argument("bundle", type=Path)
    decisions.add_argument("decisions", type=Path)
    decisions.add_argument("--output", type=Path)
    _json_flag(decisions)
    decisions.set_defaults(handler=_cmd_apply_decisions)

    explain = subparsers.add_parser("explain-field", help="trace one candidate field back to raw locators and license rules")
    explain.add_argument("candidate_id")
    explain.add_argument("json_pointer")
    explain.add_argument("--root", type=Path, default=INTERMEDIATE_ROOT)
    _json_flag(explain)
    explain.set_defaults(handler=_cmd_explain_field)

    run = subparsers.add_parser("validate-run", help="validate a physical pipeline run and exact output closure")
    run.add_argument("pipeline_run_dir", type=Path)
    _json_flag(run)
    run.set_defaults(handler=_cmd_validate_run)
    register_curation_commands(subparsers)
    return parser


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit deterministic machine-readable JSON")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, exit_code = args.handler(args)
    except PipelineError as error:
        _emit({"ok": False, "error": {"code": error.code, "message": error.public_message}}, True)
        return error.exit_code
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        _emit({"ok": False, "error": {"code": "io_or_json_failure", "message": "A governed local file could not be read or written"}}, True)
        return EXIT_IO
    _emit(payload, args.json)
    return exit_code


def _emit(payload: dict[str, Any], machine: bool) -> None:
    if machine:
        print(canonical_json_text(payload))
        return
    if payload.get("ok"):
        print(f"PASS: {payload.get('summary', 'command completed')}")
    else:
        print(f"FAIL: {payload.get('summary', 'command failed')}", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str))


def _issues_payload(issues: list[ValidationIssue] | list[str], summary: str) -> tuple[dict[str, Any], int]:
    normalized = [
        {"code": item.code, "message": item.message, "location": item.location}
        if isinstance(item, ValidationIssue) else {"code": item}
        for item in issues
    ]
    return {"ok": not normalized, "summary": summary, "issues": normalized}, 0 if not normalized else EXIT_VALIDATION


def _cmd_verify_sources(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = verify_sources()
    contracts = []
    issues = list(result["issues"])
    for adapter in adapters_by_source().values():
        contract = adapter.contract_record()
        schema_issues = validate_record(contract)
        issues.extend(f"adapter_contract:{adapter.source_id}:{issue.code}" for issue in schema_issues)
        contracts.append(contract)
    result.update({"ok": not issues, "issues": sorted(issues), "adapter_contracts": contracts, "summary": "source and adapter registries verified"})
    return result, 0 if not issues else EXIT_VALIDATION


def _cmd_list_adapters(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    records = [adapter.contract_record() for adapter in adapters_by_source().values()]
    issues = [issue for record in records for issue in validate_record(record)]
    return {"ok": not issues, "summary": f"{len(records)} adapters", "adapters": records}, 0 if not issues else EXIT_VALIDATION


def _cmd_acquire(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = acquire(adapter=get_adapter(args.source), object_id=args.object_id, live=args.live, query_profile=args.query_profile)
    snapshot_path = result.pop("snapshot_path")
    result["snapshot_relative_path"] = _safe_display_path(snapshot_path)
    return {"ok": True, "summary": "live acquisition recorded", **result}, 0


def _cmd_validate_snapshot(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_snapshot(args.snapshot_dir)
    manifest = load_snapshot_manifest(args.snapshot_dir)
    payload, code = _issues_payload(issues, "raw snapshot validation")
    payload["snapshot_id"] = manifest.get("snapshot_id")
    return payload, code


def _cmd_normalize(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    snapshot_issues = validate_snapshot(args.snapshot_dir)
    if snapshot_issues:
        return _issues_payload(snapshot_issues, "raw snapshot failed before normalization")
    manifest = load_snapshot_manifest(args.snapshot_dir)
    adapter = get_adapter(manifest["source_id"])
    response = ResponseContract(
        manifest["status_code"], manifest["response_headers"], snapshot_body_bytes(args.snapshot_dir),
        manifest["final_url"], tuple(manifest["redirect_chain"]), manifest["retry_count"],
    )
    document = adapter.validate_response_contract(response)
    candidate = adapter.normalize(document, snapshot_id=manifest["snapshot_id"], observed_at=manifest["fetched_at"])
    if candidate["contract_drift"]:
        return {
            "ok": False,
            "summary": "adapter contract drift blocked normalization",
            "issues": [
                {"code": "adapter_contract_drift", "location": item.get("raw_locator", "$"), "detail": item.get("code")}
                for item in candidate["contract_drift"]
            ],
            "candidate_written": False,
        }, EXIT_VALIDATION
    issues = validate_record(candidate)
    if issues:
        return _issues_payload(issues, "normalized candidate validation")
    run_token = str(uuid.uuid4())
    run_dir = args.output_dir or (INTERMEDIATE_ROOT / "runs" / run_token)
    if run_dir.exists():
        raise PipelineError("run_output_exists", "Pipeline run output directory already exists")
    run_dir.mkdir(parents=True)
    candidate_path = run_dir / "candidate.json"
    write_canonical_json(candidate_path, candidate)
    started = utc_now()
    snapshot_manifest_path = args.snapshot_dir / "manifest.json"
    inputs = [artifact_ref(snapshot_manifest_path, relative_to=ROOT, record_ids=[manifest["snapshot_id"]])]
    output = artifact_ref(candidate_path, relative_to=run_dir, record_ids=[candidate["id"]])
    run_manifest = create_run_manifest(
        started_at=started, status="completed", network_mode="offline",
        adapter_runs=[{
            "source_id": adapter.source_id, "adapter_version": adapter.adapter_version,
            "contract_version": adapter.contract_version, "snapshot_ids": [manifest["snapshot_id"]],
            "status": "drift" if candidate["contract_drift"] else "pass",
        }],
        inputs=inputs, outputs=[output], commands=["normalize"],
    )
    write_canonical_json(run_dir / "pipeline-run.json", run_manifest)
    return {
        "ok": True, "summary": "snapshot normalized into a candidate-only run",
        "run_id": run_manifest["id"], "run_relative_path": _safe_display_path(run_dir),
        "candidate_id": candidate["id"], "candidate_input_hash": candidate["input_hash"],
        "contract_drift_count": len(candidate["contract_drift"]), "publishable": False,
    }, 0


def _cmd_propose_identities(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if (args.normalized_dir / "pipeline-run.json").exists():
        run_issues = validate_run_directory(args.normalized_dir)
        if run_issues:
            return _issues_payload(run_issues, "identity input run validation")
    candidates = load_records(args.normalized_dir, "normalized_candidate")
    if len(candidates) < 2:
        raise PipelineError("identity_inputs_insufficient", "At least two normalized candidates are required")
    candidate_issues = [issue for candidate in candidates for issue in validate_record(candidate)]
    if candidate_issues:
        return _issues_payload(candidate_issues, "identity candidate validation")
    proposals = propose_identities(candidates)
    issues = [issue for proposal in proposals for issue in validate_record(proposal)]
    if issues:
        return _issues_payload(issues, "identity proposal validation")
    output = args.output or (args.normalized_dir / "identity-proposals.json")
    _require_new_output(output)
    write_canonical_json(output, proposals)
    if (args.normalized_dir / "pipeline-run.json").exists():
        update_run_outputs(args.normalized_dir, [(output, [proposal["id"] for proposal in proposals])], "propose-identities")
    counts = {status: sum(item["proposed_status"] == status for item in proposals) for status in ("same", "distinct", "uncertain")}
    return {"ok": True, "summary": f"{len(proposals)} identity proposals", "counts": counts, "auto_merges": 0}, 0


def _cmd_build_review_bundle(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_issues = validate_run_directory(args.pipeline_run_dir)
    if run_issues:
        return _issues_payload(run_issues, "review input run validation")
    bundle = build_review_bundle(args.pipeline_run_dir)
    issues = validate_record(bundle)
    if issues:
        return _issues_payload(issues, "review bundle validation")
    output = args.output or (args.pipeline_run_dir / "review-bundle.json")
    _require_new_output(output)
    write_canonical_json(output, bundle)
    update_run_outputs(args.pipeline_run_dir, [(output, [bundle["id"]])], "build-review-bundle")
    return {
        "ok": True, "summary": "local review bundle built", "bundle_id": bundle["id"],
        "candidate_count": len(bundle["candidate_records"]), "proposal_count": len(bundle["identity_proposals"]),
        "rights_warning_count": len(bundle["rights_warnings"]), "candidate_data_publicly_exposed": False,
    }, 0


def _cmd_validate_review_bundle(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return _issues_payload(validate_review_bundle_file(args.bundle), "review bundle validation")


def _cmd_apply_decisions(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    bundle_issues = validate_review_bundle_file(args.bundle)
    if bundle_issues:
        return _issues_payload(bundle_issues, "review bundle validation")
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    document = json.loads(args.decisions.read_text(encoding="utf-8"))
    decisions = document.get("decisions") if isinstance(document, dict) else document
    if not isinstance(decisions, list):
        raise PipelineError("decisions_document_invalid", "Decisions document must be an array or contain a decisions array")
    issues = [issue for decision in decisions for issue in validate_record(decision)]
    if issues:
        return _issues_payload(issues, "review decision validation")
    result = apply_decisions(bundle, decisions)
    output = args.output or (args.bundle.parent / "decision-results.json")
    _require_new_output(output)
    write_canonical_json(output, result)
    if (args.bundle.parent / "pipeline-run.json").exists():
        decision_ids = [decision["id"] for decision in decisions]
        update_run_inputs(args.bundle.parent, [(args.decisions, decision_ids)])
        merge_ids = [record["id"] for record in result["merge_records"]]
        update_run_outputs(args.bundle.parent, [(output, [*decision_ids, *merge_ids])], "apply-decisions")
    stale = sum(not item["applied"] for item in result["results"])
    return {"ok": True, "summary": "local decisions evaluated", "applied": len(result["results"]) - stale, "stale": stale, "merge_records": len(result["merge_records"]), "publishable_records_created": False}, 0


def _cmd_explain_field(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    for candidate in load_records(args.root, "normalized_candidate"):
        if candidate["id"] != args.candidate_id:
            continue
        candidate_issues = validate_record(candidate)
        if candidate_issues:
            return _issues_payload(candidate_issues, "candidate validation before field explanation")
        entries = [entry for entry in candidate["field_provenance"] if entry["field_pointer"] == args.json_pointer]
        if not entries:
            raise PipelineError("field_provenance_missing", "Candidate field has no provenance entry")
        return {"ok": True, "summary": "field provenance resolved", "candidate_id": args.candidate_id, "field_pointer": args.json_pointer, "provenance": entries}, 0
    raise PipelineError("candidate_not_found", "Candidate ID was not found in the selected local root")


def _cmd_validate_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return _issues_payload(validate_run_directory(args.pipeline_run_dir), "pipeline run physical validation")


def _safe_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _require_new_output(path: Path) -> None:
    if path.exists():
        raise PipelineError("run_output_exists", "Pipeline output already exists; create a new run or output path")


if __name__ == "__main__":
    raise SystemExit(main())
