#!/usr/bin/env python3
"""Fail closed when non-public data, media, or operational arms content reaches a public artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TEXT_SUFFIXES = {
    ".cjs", ".css", ".csv", ".htm", ".html", ".js", ".json", ".jsx", ".map", ".md", ".mjs",
    ".svg", ".ts", ".tsv", ".tsx", ".txt", ".webmanifest", ".xhtml", ".xml", ".yaml", ".yml",
}
MAX_SCANNABLE_TEXT_BYTES = 5 * 1024 * 1024
THIRD_PARTY_MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".mp3", ".mp4", ".wav", ".webm"}
MUSEUM_04_RELEASE_DIR = Path("releases") / "art-constellation-1.0.0"
MUSEUM_05B_RELEASE_DIR = Path("releases") / "art-gallery-interactions-1.1.0"
MUSEUM_06_RELEASE_DIR = Path("releases") / "art-pathways-1.2.0"
MUSEUM_07_RELEASE_DIR = Path("releases") / "art-time-place-1.3.0"
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
        r"\b500115493\b|\b27992\b|Douglas Adams|One-dollar Liberty Head Coin|"
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


def scan_public_artifact(
    root: Path,
    *,
    private_candidate_terms: set[str] | None = None,
    formal_art_terms: list[dict[str, str]] | None = None,
    formal_art_exempt_roots: set[Path] | None = None,
) -> list[dict[str, str]]:
    if not root.exists() or not root.is_dir():
        return [{"code": "public_artifact_missing", "path": root.name}]
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        return [{"code": "public_artifact_empty", "path": root.name}]
    findings: list[dict[str, str]] = []
    resolved_exempt_roots = {path.resolve() for path in formal_art_exempt_roots or set()}
    for path in files:
        relative = path.relative_to(root).as_posix()
        formal_exempt = _path_is_within_any(path, resolved_exempt_roots)
        authority_id_exempt = any(
            exempt_root.name == MUSEUM_07_RELEASE_DIR.name and path.resolve().is_relative_to(exempt_root)
            for exempt_root in resolved_exempt_roots
        )
        if set(part.lower() for part in path.relative_to(root).parts) & FORBIDDEN_PATH_PARTS:
            findings.append({"code": "candidate_zone_in_public_artifact", "path": relative})
        if path.suffix.lower() in THIRD_PARTY_MEDIA_SUFFIXES and not formal_exempt:
            findings.append({"code": "third_party_media_in_public_artifact", "path": relative})
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_SCANNABLE_TEXT_BYTES:
            findings.append({"code": "public_text_too_large_to_scan", "path": relative})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append({"code": "public_text_not_utf8", "path": relative})
            continue
        for code, pattern in FORBIDDEN_CONTENT.items():
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            if authority_id_exempt and code in {"ulan_id", "wikidata_qid"}:
                continue
            if code == "technical_probe_data" and formal_exempt and all(
                _match_is_declared_formal_label(match.group(0), formal_art_terms or [])
                for match in matches
            ):
                continue
            if matches:
                public_code = code if code in {"wikidata_qid", "ulan_id", "operational_arms_content"} else "candidate_data_publicly_exposed"
                findings.append({"code": public_code, "path": relative})
        for term in sorted(private_candidate_terms or set(), key=str.casefold):
            if len(term) >= 4 and term.casefold() in text.casefold():
                findings.append({"code": "candidate_name_publicly_exposed", "path": relative})
        if not formal_exempt:
            for term in formal_art_terms or []:
                value = term["value"]
                if _term_matches(text, value, term["match_mode"]):
                    findings.append({"code": "formal_art_data_publicly_exposed", "path": relative})
    unique = {(item["code"], item["path"]): item for item in findings}
    return [unique[key] for key in sorted(unique)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT / "dist")
    parser.add_argument("--selection-bundle", type=Path, help="optional ignored bundle whose labels must not appear in the public artifact")
    parser.add_argument("--label-set", type=Path, help="tracked MUSEUM-03B leakage-label set for approved formal data")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    terms = candidate_terms_from_bundle(args.selection_bundle) if args.selection_bundle else set()
    formal_terms, label_error = formal_art_terms_from_label_set(args.label_set) if args.label_set else ([], None)
    exempt_roots, release_findings = validated_formal_art_exempt_roots(args.root) if formal_terms else (set(), [])
    findings = scan_public_artifact(
        args.root,
        private_candidate_terms=terms,
        formal_art_terms=formal_terms,
        formal_art_exempt_roots=exempt_roots,
    )
    findings.extend(release_findings)
    if label_error:
        findings.append({"code": "public_label_set_invalid", "path": args.label_set.name})
    payload = {"ok": not findings, "root": args.root.name, "findings": findings}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif findings:
        for finding in findings:
            print(f"[public-artifact-scan] {finding['code']}: {finding['path']}", file=sys.stderr)
    else:
        print(f"[public-artifact-scan] PASS files={sum(path.is_file() for path in args.root.rglob('*'))}")
    return 0 if not findings else 1


def candidate_terms_from_bundle(bundle: Path) -> set[str]:
    try:
        candidates = json.loads((bundle / "candidate-pool.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return set()
    return {
        item["text"]
        for candidate in candidates if isinstance(candidate, dict)
        for item in candidate.get("preferred_labels", []) + candidate.get("aliases", [])
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    }


def formal_art_terms_from_label_set(path: Path) -> tuple[list[dict[str, str]], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return [], "unreadable"
    values = payload.get("terms") if isinstance(payload, dict) else None
    if not isinstance(values, list) or not values:
        return [], "terms_missing"
    result: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            return [], "term_invalid"
        value = item.get("value")
        match_mode = item.get("match_mode")
        if not isinstance(value, str) or len(value.strip()) < 2 or match_mode not in {"casefold_substring", "exact_token", "serialized_string"}:
            return [], "term_invalid"
        result.append({"value": value.strip(), "match_mode": match_mode})
    return result, None


def _term_matches(text: str, value: str, match_mode: str) -> bool:
    if match_mode == "casefold_substring":
        return value.casefold() in text.casefold()
    if match_mode == "serialized_string":
        return re.search(rf"(?P<quote>[\"'`])\s*{re.escape(value)}\s*(?P=quote)", text) is not None
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def validated_museum_04_exempt_roots(root: Path) -> tuple[set[Path], list[dict[str, str]]]:
    release_root = _release_root_for_scan(root, MUSEUM_04_RELEASE_DIR)
    if not release_root.is_dir():
        return set(), []
    from museum_pipeline.art.public_release import validate_museum_04_release

    result = validate_museum_04_release(release_root)
    if result["ok"]:
        return {release_root.resolve()}, []
    return set(), [{"code": "museum_04_release_invalid", "path": release_root.relative_to(root).as_posix() if release_root != root else root.name}]


def validated_formal_art_exempt_roots(root: Path) -> tuple[set[Path], list[dict[str, str]]]:
    """Allow only exact, physically validated formal release directories."""
    timeplace_root = _release_root_for_scan(root, MUSEUM_07_RELEASE_DIR)
    if timeplace_root.is_dir():
        from museum_pipeline.art.timeplace import validate_museum_07_release

        result = validate_museum_07_release(timeplace_root)
        if not result["ok"]:
            return set(), [{
                "code": "museum_07_release_invalid",
                "path": timeplace_root.relative_to(root).as_posix() if timeplace_root != root else root.name,
            }]
        release_roots = {
            _release_root_for_scan(root, release_dir).resolve()
            for release_dir in (MUSEUM_04_RELEASE_DIR, MUSEUM_05B_RELEASE_DIR, MUSEUM_06_RELEASE_DIR, MUSEUM_07_RELEASE_DIR)
            if _release_root_for_scan(root, release_dir).is_dir()
        }
        return release_roots, []
    exempt_roots, findings = validated_museum_04_exempt_roots(root)
    release_root = _release_root_for_scan(root, MUSEUM_05B_RELEASE_DIR)
    if release_root.is_dir():
        from museum_pipeline.art.interactions import validate_museum_05b_release

        result = validate_museum_05b_release(release_root)
        if result["ok"]:
            exempt_roots.add(release_root.resolve())
        else:
            findings.append({
                "code": "museum_05b_release_invalid",
                "path": release_root.relative_to(root).as_posix() if release_root != root else root.name,
            })
    pathway_root = _release_root_for_scan(root, MUSEUM_06_RELEASE_DIR)
    if pathway_root.is_dir():
        from museum_pipeline.art.pathways import validate_museum_06_release

        result = validate_museum_06_release(pathway_root)
        if result["ok"]:
            exempt_roots.add(pathway_root.resolve())
        else:
            findings.append({
                "code": "museum_06_release_invalid",
                "path": pathway_root.relative_to(root).as_posix() if pathway_root != root else root.name,
            })
    return exempt_roots, findings


def _release_root_for_scan(root: Path, release_dir: Path) -> Path:
    if root.name == release_dir.name and root.parent.name == "releases":
        return root
    return root / release_dir


def _path_is_within_any(path: Path, roots: set[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root) for root in roots)


def _match_is_declared_formal_label(value: str, formal_terms: list[dict[str, str]]) -> bool:
    folded = value.casefold().strip()
    return any(term["value"].casefold().strip() == folded for term in formal_terms)


if __name__ == "__main__":
    raise SystemExit(main())
