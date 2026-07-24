#!/usr/bin/env python3
"""Run or resume a plan-authorized museum expansion wave."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.expansion_wave_factory import (
    load_wave_plan,
    record_online_closeout,
    run_wave,
)

DEFAULT_PLAN = ROOT / "docs" / "05_roadmap" / "museum-09d-wave-01" / "release-plan.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-id")
    parser.add_argument("--batch-ids")
    parser.add_argument("--release-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--through", choices=("research", "media", "release"), default="release")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--from-batch")
    parser.add_argument("--from-stage", choices=("research", "media", "release"))
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--no-deploy", action="store_true")
    parser.add_argument("--record-closeout", type=Path)
    args = parser.parse_args()

    plan = load_wave_plan(args.release_plan)
    if args.phase_id and args.phase_id != plan.phase_id:
        parser.error("--phase-id does not match the approved release plan")
    if args.record_closeout:
        result = record_online_closeout(
            plan,
            json.loads(args.record_closeout.read_text(encoding="utf-8")),
        )
    else:
        if not args.phase_id or not args.batch_ids:
            parser.error("wave execution requires --phase-id and --batch-ids")
        batch_ids = [item.strip() for item in args.batch_ids.split(",") if item.strip()]
        result = run_wave(
            plan,
            batch_ids=batch_ids,
            through=args.through,
            journal_path=args.journal,
            dry_run=args.dry_run,
            resume=args.resume,
            from_batch=args.from_batch,
            from_stage=args.from_stage,
            no_deploy=args.no_deploy,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
