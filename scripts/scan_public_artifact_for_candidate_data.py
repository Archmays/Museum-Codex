#!/usr/bin/env python3
"""Fail closed when non-public data, media, or operational arms content reaches a public artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".txt", ".xml"}
THIRD_PARTY_MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".mp3", ".mp4", ".wav", ".webm"}
FORBIDDEN_PATH_PARTS = {"raw", "intermediate", "review", "recorded", "pipeline"}
FORBIDDEN_CONTENT = {
    "candidate_id": re.compile(r"candidate:[0-9a-f-]{36}", re.IGNORECASE),
    "snapshot_id": re.compile(r"snapshot:[a-z][a-z0-9_]*:", re.IGNORECASE),
    "identity_proposal": re.compile(r"identity-proposal:", re.IGNORECASE),
    "review_bundle": re.compile(r"review-bundle:", re.IGNORECASE),
    "source_object_record": re.compile(r'"(?:source_object_id|raw_snapshot_id|candidate_claims|field_provenance)"'),
    "wikidata_qid": re.compile(r"(?<![A-Za-z0-9])Q[1-9][0-9]{0,11}(?![A-Za-z0-9])|(?:www\.)?wikidata\.org/(?:wiki|entity)/Q[1-9][0-9]*", re.IGNORECASE),
    "ulan_id": re.compile(r"vocab\.getty\.edu/(?:page/)?ulan/[0-9]{9}|\bULAN\s*[:#-]?\s*[0-9]{9}\b", re.IGNORECASE),
    "technical_probe_data": re.compile(
        r"\b500115493\b|\b27992\b|Douglas Adams|Dürer,? Albrecht|One-dollar Liberty Head Coin|"
        r"A Sunday on La Grande Jatte|James Barton Longacre|Georges Seurat",
        re.IGNORECASE,
    ),
    "operational_arms_content": re.compile(
        r"制造(?:武器|弹药|爆炸物)|(?:武器|弹药)(?:改装|装填|发射|瞄准|拆装|采购|购买)(?:教程|指南|步骤|方法)?|"
        r"how\s+to\s+(?:build|manufacture|modify|load|fire|aim|buy)\s+(?:a\s+)?(?:weapon|firearm|ammunition)|"
        r"(?:weapon|firearm|ammunition)\s+(?:build|manufacturing|modification|loading|firing|aiming|purchase)\s+(?:steps|instructions|guide)",
        re.IGNORECASE,
    ),
}


def scan_public_artifact(root: Path) -> list[dict[str, str]]:
    if not root.exists() or not root.is_dir():
        return [{"code": "public_artifact_missing", "path": root.name}]
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        return [{"code": "public_artifact_empty", "path": root.name}]
    findings: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if set(part.lower() for part in path.relative_to(root).parts) & FORBIDDEN_PATH_PARTS:
            findings.append({"code": "candidate_zone_in_public_artifact", "path": relative})
        if path.suffix.lower() in THIRD_PARTY_MEDIA_SUFFIXES:
            findings.append({"code": "third_party_media_in_public_artifact", "path": relative})
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append({"code": "public_text_not_utf8", "path": relative})
            continue
        for code, pattern in FORBIDDEN_CONTENT.items():
            if pattern.search(text):
                public_code = code if code in {"wikidata_qid", "ulan_id", "operational_arms_content"} else "candidate_data_publicly_exposed"
                findings.append({"code": public_code, "path": relative})
    unique = {(item["code"], item["path"]): item for item in findings}
    return [unique[key] for key in sorted(unique)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT / "dist")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    findings = scan_public_artifact(args.root)
    payload = {"ok": not findings, "root": args.root.name, "findings": findings}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif findings:
        for finding in findings:
            print(f"[public-artifact-scan] {finding['code']}: {finding['path']}", file=sys.stderr)
    else:
        print(f"[public-artifact-scan] PASS files={sum(path.is_file() for path in args.root.rglob('*'))}")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
