from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.curation.bundle import build_selection_bundle, validate_selection_bundle
from museum_pipeline.curation.decision_application import apply_selection_decision
from museum_pipeline.hashing import sha256_file
from museum_pipeline.config import ROOT
from museum_pipeline.errors import PipelineError


EXIT_VALIDATION = 3


def register_curation_commands(subparsers: argparse._SubParsersAction) -> None:
    build = subparsers.add_parser("build-selection-pool", help="build an ignored MUSEUM-03A physical selection bundle from reviewed research input")
    build.add_argument("input", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--json", action="store_true")
    build.set_defaults(handler=_cmd_build)

    validate = subparsers.add_parser("validate-selection-bundle", help="validate MUSEUM-03A schemas, hashes, references, and private bundle boundaries")
    validate.add_argument("bundle", type=Path)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=_cmd_validate)

    compare = subparsers.add_parser("compare-scenarios", help="compare the three unapproved scenarios and recommended slate")
    compare.add_argument("bundle", type=Path)
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(handler=_cmd_compare)

    render = subparsers.add_parser("render-selection-handoff", help="return the governed user handoff and its SHA-256")
    render.add_argument("bundle", type=Path)
    render.add_argument("--json", action="store_true")
    render.set_defaults(handler=_cmd_render)

    explain = subparsers.add_parser("explain-candidate", help="explain one candidate's sources, rights, leads, and readiness without approval")
    explain.add_argument("candidate_id")
    explain.add_argument("--bundle", required=True, type=Path)
    explain.add_argument("--json", action="store_true")
    explain.set_defaults(handler=_cmd_explain)

    decision = subparsers.add_parser("selection-decision-template", help="return the pending user decision template; never applies a decision")
    decision.add_argument("bundle", type=Path)
    decision.add_argument("--output", type=Path)
    decision.add_argument("--json", action="store_true")
    decision.set_defaults(handler=_cmd_decision)

    apply_decision = subparsers.add_parser("apply-selection-decision", help="apply one validated submitted Recommended Slate decision exactly once")
    apply_decision.add_argument("bundle", type=Path)
    apply_decision.add_argument("decision", type=Path)
    apply_decision.add_argument("--output", required=True, type=Path)
    apply_decision.add_argument("--resulting-batch-id", required=True)
    apply_decision.add_argument("--applied-at")
    apply_decision.add_argument("--code-commit")
    apply_decision.add_argument("--json", action="store_true")
    apply_decision.set_defaults(handler=_cmd_apply_decision)


def _cmd_build(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    review_root = (ROOT / "data" / "review").resolve()
    for path, code in ((args.input.resolve(), "selection_input_not_ignored"), (args.output.resolve(), "selection_output_not_ignored")):
        try:
            path.relative_to(review_root)
        except ValueError as error:
            raise PipelineError(code, "Selection research inputs and outputs must remain under the ignored data/review root") from error
    document = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = build_selection_bundle(document, args.output)
    return {
        "ok": True, "summary": "private selection bundle built and validated",
        "bundle_relative_name": args.output.name, "bundle_hash": manifest["bundle_hash"],
        "candidate_pool_count": manifest["candidate_pool_count"],
        "qualified_candidate_count": manifest["qualified_candidate_count"],
        "user_confirmation_received": False,
    }, 0


def _cmd_validate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_selection_bundle(args.bundle)
    return {
        "ok": not issues, "summary": "selection bundle validation",
        "issues": [{"code": item.code, "message": item.message, "location": item.location} for item in issues],
    }, 0 if not issues else EXIT_VALIDATION


def _cmd_compare(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_selection_bundle(args.bundle)
    if issues:
        return _cmd_validate(args)
    names = ("scenario-a.json", "scenario-b.json", "scenario-c.json", "recommended-slate.json")
    scenarios = [json.loads((args.bundle / name).read_text(encoding="utf-8")) for name in names]
    comparison = [{
        "id": item["id"], "title": item["title"], "scenario_kind": item["scenario_kind"],
        "candidate_count": len(item["candidate_ids"]), "women_count": item["gender_underrepresentation_audit"]["women_count"],
        "tradition_count": len(item["region_tradition_counts"]), "period_count": len(item["time_coverage"]),
        "medium_count": len(item["media_coverage"]),
        "four_or_more_clear_paths": item["rights_readiness"]["candidates_with_four_or_more_clear_paths"],
        "lead_count": item["relationship_connectivity_potential"]["lead_count"], "user_approved": False,
    } for item in scenarios]
    return {"ok": True, "summary": "four unapproved slate comparisons", "scenarios": comparison}, 0


def _cmd_render(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_selection_bundle(args.bundle)
    if issues:
        return _cmd_validate(args)
    path = args.bundle / "selection-handoff.md"
    return {"ok": True, "summary": "selection handoff ready", "sha256": sha256_file(path), "bytes": path.stat().st_size, "content": path.read_text(encoding="utf-8")}, 0


def _cmd_explain(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_selection_bundle(args.bundle)
    if issues:
        return _cmd_validate(argparse.Namespace(bundle=args.bundle))
    candidates = json.loads((args.bundle / "candidate-pool.json").read_text(encoding="utf-8"))
    candidate = next((item for item in candidates if item["id"] == args.candidate_id), None)
    if candidate is None:
        return {"ok": False, "summary": "candidate not found", "issues": [{"code": "candidate_missing"}]}, EXIT_VALIDATION
    artworks = [item for item in json.loads((args.bundle / "artwork-rights-preflight.json").read_text(encoding="utf-8")) if item["candidate_id"] == args.candidate_id]
    leads = [item for item in json.loads((args.bundle / "relationship-leads.json").read_text(encoding="utf-8")) if args.candidate_id in {item["source_candidate_id"], item.get("target_candidate_id")}]
    return {"ok": True, "summary": "candidate preflight explanation", "candidate": candidate, "artwork_rights_preflight": artworks, "relationship_leads": leads, "formal_relationships_created": False}, 0


def _cmd_decision(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    issues = validate_selection_bundle(args.bundle)
    if issues:
        return _cmd_validate(args)
    template = json.loads((args.bundle / "selection-decision-template.json").read_text(encoding="utf-8"))
    if args.output:
        write_canonical_json(args.output, template)
    return {"ok": True, "summary": "pending user decision template", "template": template, "output_written": bool(args.output)}, 0


def _cmd_apply_decision(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    receipt, idempotent = apply_selection_decision(
        bundle_root=args.bundle,
        decision_path=args.decision,
        output_path=args.output,
        resulting_batch_id=args.resulting_batch_id,
        applied_at=args.applied_at,
        code_commit=args.code_commit,
    )
    return {
        "ok": True,
        "summary": "approved selection decision applied",
        "submitted_decision_id": receipt["submitted_decision_id"],
        "application_receipt_id": receipt["id"],
        "resulting_batch_id": receipt["resulting_batch_id"],
        "approved_artist_count": len(receipt["selected_candidate_ids"]),
        "application_basis_hash": receipt["application_basis_hash"],
        "idempotent": idempotent,
        "replacement_count": receipt["replacement_count"],
        "media_strategy": receipt["media_strategy"],
        "media_execution_default": receipt["media_execution_default"],
    }, 0
