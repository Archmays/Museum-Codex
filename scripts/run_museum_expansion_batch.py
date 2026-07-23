#!/usr/bin/env python3
"""Run one registry-driven museum expansion transaction stage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.expansion_batch_factory import (
    load_batch_inputs,
    record_online_closeout,
    repair_batch_01_registry,
    run_media,
    run_release,
    run_research,
)


def _version_from_release_id(release_id: str) -> str:
    value = release_id.rsplit("-", 1)[-1]
    if value.count(".") != 2:
        raise ValueError("release id must end in a semantic version")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id")
    parser.add_argument("--stage", choices=("research", "media", "release"))
    parser.add_argument("--through", choices=("research", "media", "release"))
    parser.add_argument("--release-id")
    parser.add_argument("--predecessor")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repair-batch-01", action="store_true")
    parser.add_argument("--record-closeout", type=Path)
    args = parser.parse_args()
    if args.repair_batch_01:
        repair_batch_01_registry()
        print(json.dumps({"ok": True, "action": "repair-batch-01"}, indent=2))
        return 0
    if args.record_closeout:
        if not args.batch_id:
            parser.error("--record-closeout requires --batch-id")
        record_online_closeout(args.batch_id, json.loads(args.record_closeout.read_text(encoding="utf-8")))
        print(json.dumps({"ok": True, "action": "record-closeout", "batch_id": args.batch_id}, indent=2))
        return 0
    if not args.batch_id or not args.release_id:
        parser.error("transaction stages require --batch-id and --release-id")
    final_stage = args.through or args.stage
    if not final_stage:
        parser.error("choose --stage or --through")
    version = _version_from_release_id(args.release_id)
    inputs = load_batch_inputs(args.batch_id)
    order = ("research", "media", "release")
    results = []
    for stage in order[: order.index(final_stage) + 1] if args.through else (final_stage,):
        if stage == "research":
            results.append(run_research(inputs, release_id=args.release_id, version=version))
        elif stage == "media":
            results.append(run_media(inputs))
        else:
            if not args.predecessor:
                parser.error("release stage requires --predecessor")
            output = args.output or ROOT / "public" / "releases" / args.release_id.removeprefix("release:")
            results.append(
                run_release(
                    inputs,
                    release_id=args.release_id,
                    predecessor_id=args.predecessor,
                    version=version,
                    output_dir=output,
                )
            )
    print(json.dumps({"ok": True, "batch_id": args.batch_id, "stages": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
