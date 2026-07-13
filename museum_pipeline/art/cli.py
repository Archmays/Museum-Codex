from __future__ import annotations

import argparse
import json
from pathlib import Path

from museum_pipeline.art.batch import build_approved_batch
from museum_pipeline.art.batch_validation import DEFAULT_PACKAGE, validate_approved_batch
from museum_pipeline.art.identity import (
    DEFAULT_APPLICATION,
    DEFAULT_IDENTITY_BASIS,
    DEFAULT_OUTPUT,
    DEFAULT_SEED,
    DEFAULT_SNAPSHOT_RECEIPTS,
    build_identity_stage,
)
from museum_pipeline.art.validation import validate_identity_stage
from museum_pipeline.errors import PipelineError
from museum_pipeline.validation.dispatch import canonical_schema_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MUSEUM-03B reviewed art-batch tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    identity_build = subparsers.add_parser("build-identity-stage", help="build the exact approved internal identity stage")
    identity_build.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    identity_build.add_argument("--identity-basis", type=Path, default=DEFAULT_IDENTITY_BASIS)
    identity_build.add_argument("--snapshot-receipts", type=Path, default=DEFAULT_SNAPSHOT_RECEIPTS)
    identity_build.add_argument("--application", type=Path, default=DEFAULT_APPLICATION)
    identity_build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    identity_build.add_argument("--json", action="store_true")
    identity_validate = subparsers.add_parser("validate-identity-stage", help="validate the exact 12-person identity gate")
    identity_validate.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    identity_validate.add_argument("--identity-basis", type=Path, default=DEFAULT_IDENTITY_BASIS)
    identity_validate.add_argument("--verify-raw", action="store_true", help="also re-hash ignored local raw receipt files")
    identity_validate.add_argument("--application", type=Path, default=DEFAULT_APPLICATION)
    identity_validate.add_argument("--package-dir", type=Path, default=DEFAULT_OUTPUT)
    identity_validate.add_argument("--json", action="store_true")

    batch_build = subparsers.add_parser("build-approved-batch", help="atomically build the sealed internal MUSEUM-03B package")
    batch_build.add_argument("--code-commit", required=True, help="exact 40-character implementation commit")
    batch_build.add_argument("--output-dir", type=Path, default=DEFAULT_PACKAGE)
    batch_build.add_argument("--json", action="store_true")
    batch_validate = subparsers.add_parser("validate-approved-batch", help="validate physical and semantic package closure")
    batch_validate.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    batch_validate.add_argument("--json", action="store_true")
    graph_build = subparsers.add_parser(
        "build-graph-input",
        help="build or reuse the sealed batch and report its non-public graph input",
    )
    graph_build.add_argument("--code-commit", required=True, help="exact 40-character implementation commit")
    graph_build.add_argument("--output-dir", type=Path, default=DEFAULT_PACKAGE)
    graph_build.add_argument("--json", action="store_true")
    explain = subparsers.add_parser("explain-record", help="explain a packaged record's provenance, rights, and review state")
    explain.add_argument("record_id")
    explain.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    explain.add_argument("--json", action="store_true")
    coverage = subparsers.add_parser("report-coverage", help="report reviewed-batch coverage without network access")
    coverage.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    coverage.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build-identity-stage":
            result = build_identity_stage(
                seed_path=args.seed,
                identity_basis_path=args.identity_basis,
                snapshot_receipts_path=args.snapshot_receipts,
                application_path=args.application,
                output_dir=args.output_dir,
            )
        elif args.command == "validate-identity-stage":
            result = validate_identity_stage(
                package_dir=args.package_dir,
                application_path=args.application,
                seed_path=args.seed,
                identity_basis_path=args.identity_basis,
                verify_raw_files=args.verify_raw,
            )
        elif args.command == "build-approved-batch":
            result = build_approved_batch(code_commit=args.code_commit, output_dir=args.output_dir)
        elif args.command == "validate-approved-batch":
            result = validate_approved_batch(args.package_dir)
        elif args.command == "build-graph-input":
            result = build_approved_batch(code_commit=args.code_commit, output_dir=args.output_dir)
            if result.get("ok"):
                graph = _read_packaged_record(args.output_dir, "graph-input:museum-03b-first-slate-v1")
                result = {
                    **result,
                    "graph_input_path": str((args.output_dir / "graph-input.json").resolve()),
                    "graph_input_hash": graph.get("content_hash"),
                    "graph_primary_artist_count": len(graph.get("primary_nodes", [])),
                    "graph_relationship_count": len(graph.get("edges", [])),
                }
        elif args.command == "explain-record":
            validation = validate_approved_batch(args.package_dir)
            if not validation.get("ok"):
                result = validation
            else:
                result = _explain_record(args.package_dir, args.record_id)
        else:
            validation = validate_approved_batch(args.package_dir)
            if not validation.get("ok"):
                result = validation
            else:
                manifest = _read_json(args.package_dir / "package-manifest.json")
                result = {
                    "ok": True,
                    "phase_id": "MUSEUM-03B",
                    "package_dir": str(args.package_dir.resolve()),
                    "package_content_hash": manifest.get("content_hash"),
                    "counts": validation.get("counts", {}),
                    "formal_public_release_created": False,
                    "media_bytes_downloaded": False,
                    "summary": "reviewed batch coverage is closed; package remains internal, static, and no-media",
                }
    except PipelineError as error:
        result = {"ok": False, "error": {"code": error.code, "message": str(error)}}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result.get("ok"):
        print(f"[PASS] {args.command}: {result.get('summary') or result.get('counts') or result}")
    else:
        print(f"[FAIL] {args.command}: {result}")
    return 0 if result.get("ok") else 1


def _explain_record(package_dir: Path, record_id: str) -> dict[str, object]:
    record = _read_packaged_record(package_dir, record_id)
    explanation: dict[str, object] = {
        "ok": True,
        "record_id": record_id,
        "entity_type": record.get("entity_type"),
        "canonical_schema": canonical_schema_path(record),
        "lifecycle_status": record.get("lifecycle_status"),
        "review_status": record.get("review_status"),
        "source_ids": record.get("source_ids", []),
        "claim_ids": record.get("claim_ids", []),
        "evidence_ids": record.get("evidence_ids", []),
        "review_signoff_ids": record.get("review_signoff_ids", record.get("reviewer_signoff_ids", [])),
        "summary": f"resolved {record_id} through the sealed package without live access",
    }
    if record.get("entity_type") == "artwork":
        explanation["official_object_record"] = record.get("official_object_record")
        explanation["media_eligibility_assessment_id"] = record.get("media_eligibility_assessment_id")
        explanation["rights_preflight_id"] = record.get("rights_preflight_id")
        explanation["media_asset_ids"] = record.get("media_asset_ids", [])
    elif record.get("entity_type") == "media_eligibility_assessment":
        explanation["rights"] = {
            "outcome": record.get("outcome"),
            "metadata_license": record.get("metadata_license"),
            "media_license": record.get("media_license"),
            "media_rights_status": record.get("media_rights_status"),
            "media_rights_basis": record.get("media_rights_basis"),
            "rights_statement_url": record.get("rights_statement_url"),
            "rights_holder": record.get("rights_holder"),
            "attribution": record.get("attribution"),
            "permissions": record.get("permissions"),
            "license_scope": record.get("license_scope"),
            "permission_status": record.get("permission_status"),
            "withdrawal_or_revocation": record.get("withdrawal_or_revocation"),
            "technical_delivery": record.get("technical_delivery"),
            "rights_evidence": record.get("rights_evidence"),
            "evidence_hash": record.get("evidence_hash"),
            "risk": record.get("risk"),
            "block_reasons": record.get("block_reasons"),
            "future_public_media_eligible": record.get("future_public_media_eligible"),
            "self_hosted_open_media_eligible": record.get("self_hosted_open_media_eligible"),
            "development_only": record.get("development_only"),
            "metadata_inherited_as_media_rights": record.get("metadata_inherited_as_media_rights"),
            "bytes_downloaded": record.get("bytes_downloaded"),
            "media_bytes_present": record.get("media_bytes_present"),
            "verified_at": record.get("verified_at"),
            "reverify_by": record.get("reverify_by"),
        }
    elif record.get("entity_type") == "relationship":
        explanation["relationship"] = {
            "relationship_type": record.get("relationship_type"),
            "evidence_level": record.get("evidence_level"),
            "historical_relationship_strength": record.get("historical_relationship_strength"),
            "evidence_confidence": record.get("evidence_confidence"),
            "computational_similarity": record.get("computational_similarity"),
            "curatorial_relevance": record.get("curatorial_relevance"),
            "context_entity_ids": record.get("context_entity_ids", []),
            "is_algorithmic": record.get("is_algorithmic"),
        }
    return explanation


def _read_packaged_record(package_dir: Path, record_id: str) -> dict[str, object]:
    manifest = _read_json(package_dir / "package-manifest.json")
    for entry in manifest.get("files", []):
        if record_id not in entry.get("record_ids", []):
            continue
        document = _read_json(package_dir / entry["path"])
        records = document if isinstance(document, list) else [document]
        for record in records:
            if isinstance(record, dict) and record.get("id") == record_id:
                return record
    if manifest.get("id") == record_id:
        return manifest
    raise PipelineError("packaged_record_missing", f"Record is absent from the sealed package: {record_id}")


def _read_json(path: Path) -> dict[str, object] | list[object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PipelineError("package_json_invalid", f"Cannot read package JSON {path}: {error}") from error
