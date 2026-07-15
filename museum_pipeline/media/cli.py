from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from museum_pipeline.errors import PipelineError
from museum_pipeline.media.pipeline import (
    acquire_media,
    assess_rights,
    build_derivatives_and_bundle,
    cross_check_media,
    discover_media,
    explain_artwork,
    plan_media,
    report_coverage,
    validate_media_bundle,
)


EXIT_VALIDATION = 3
EXIT_NETWORK_DISABLED = 4
EXIT_IO = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m museum_pipeline.media", description="Offline-first MUSEUM-03C media pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _command(subparsers, "plan", "create 44 governed acquisition requests", lambda _: plan_media())
    discover = _command(subparsers, "discover", "refresh official object metadata and alternative-source searches", lambda args: discover_media(live=args.live))
    discover.add_argument("--live", action="store_true")
    acquire = _command(subparsers, "acquire", "download approved official media bytes", lambda args: acquire_media(live=args.live, download_media=args.download_media))
    acquire.add_argument("--live", action="store_true")
    acquire.add_argument("--download-media", action="store_true")
    _command(subparsers, "cross-check", "evaluate mandatory identity, rights, byte and quality closure", lambda _: cross_check_media())
    _command(subparsers, "assess-rights", "record one terminal automated decision for every artwork", lambda _: assess_rights())
    _command(subparsers, "build-derivatives", "build approved Web derivatives, ledger and media bundle", lambda _: build_derivatives_and_bundle())
    _command(subparsers, "validate-bundle", "validate exact physical M03C bundle closure", lambda _: validate_media_bundle())
    explain = _command(subparsers, "explain", "show governed evidence for one artwork", lambda args: explain_artwork(args.artwork_id))
    explain.add_argument("--artwork-id", required=True)
    _command(subparsers, "report-coverage", "report 44-work and per-artist media coverage", lambda _: report_coverage())
    return parser


def _command(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    handler: Callable[[argparse.Namespace], dict[str, Any]],
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
        code = 0 if payload.get("ok") else EXIT_VALIDATION
    except PipelineError as error:
        payload = {"ok": False, "error": {"code": error.code, "message": error.public_message}}
        code = error.exit_code
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        payload = {"ok": False, "error": {"code": "media_pipeline_failure", "message": str(error)}}
        code = EXIT_IO
    _emit(payload, bool(args.json))
    return code


def _emit(payload: dict[str, Any], machine: bool) -> None:
    if machine:
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return
    stream = sys.stdout if payload.get("ok") else sys.stderr
    summary = str(payload.get("summary") or payload.get("error", {}).get("message", "command failed"))
    ascii_summary = json.dumps(summary, ensure_ascii=True)[1:-1]
    print(("PASS" if payload.get("ok") else "FAIL") + ": " + ascii_summary, file=stream)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False), file=stream)


if __name__ == "__main__":
    raise SystemExit(main())
