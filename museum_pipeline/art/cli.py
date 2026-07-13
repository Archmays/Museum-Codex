from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MUSEUM-03B reviewed art-batch tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-identity-stage", help="build the exact approved internal identity stage")
    build.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    build.add_argument("--identity-basis", type=Path, default=DEFAULT_IDENTITY_BASIS)
    build.add_argument("--snapshot-receipts", type=Path, default=DEFAULT_SNAPSHOT_RECEIPTS)
    build.add_argument("--application", type=Path, default=DEFAULT_APPLICATION)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--json", action="store_true")
    validate = subparsers.add_parser("validate-identity-stage", help="validate the exact 12-person identity gate")
    validate.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    validate.add_argument("--identity-basis", type=Path, default=DEFAULT_IDENTITY_BASIS)
    validate.add_argument("--application", type=Path, default=DEFAULT_APPLICATION)
    validate.add_argument("--package-dir", type=Path, default=DEFAULT_OUTPUT)
    validate.add_argument("--json", action="store_true")
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
        else:
            result = validate_identity_stage(
                package_dir=args.package_dir,
                application_path=args.application,
                seed_path=args.seed,
                identity_basis_path=args.identity_basis,
            )
    except PipelineError as error:
        result = {"ok": False, "error": {"code": error.code, "message": str(error)}}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif result.get("ok"):
        print(f"[PASS] {args.command}: {result}")
    else:
        print(f"[FAIL] {args.command}: {result}")
    return 0 if result.get("ok") else 1
