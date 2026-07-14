#!/usr/bin/env python3
"""Exercise the MUSEUM-04 valid zero-media and expected-invalid release fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.public_release import DEFAULT_OUTPUT, _release_content_hash, validate_museum_04_release
from museum_pipeline.canonical_json import canonical_json_bytes


FIXTURE_ROOT = ROOT / "fixtures" / "museum-04-release"


def run(base_release: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    base_release = base_release.resolve() if base_release.is_absolute() else (ROOT / base_release).resolve()
    results: list[dict[str, Any]] = []
    for fixture_path in sorted(FIXTURE_ROOT.rglob("*.json")):
        fixture = _load_json(fixture_path)
        mutation = fixture["mutation"]
        if mutation == "none":
            validation = validate_museum_04_release(base_release)
        else:
            with tempfile.TemporaryDirectory(prefix="museum-04-fixture-") as temporary:
                release_root = Path(temporary) / "art-constellation-0.1.0"
                shutil.copytree(base_release, release_root)
                _apply_mutation(release_root, mutation)
                validation = validate_museum_04_release(release_root)
        expected_valid = fixture["expected_valid"] is True
        expected_codes = set(fixture.get("expected_error_codes", []))
        expected_counts = fixture.get("expected_counts", {})
        observed_codes = set(validation["codes"])
        counts_match = all(
            validation.get("counts", {}).get(key) == value
            for key, value in expected_counts.items()
        )
        passed = validation["ok"] is expected_valid and expected_codes <= observed_codes and counts_match
        results.append({
            "fixture_id": fixture["fixture_id"],
            "passed": passed,
            "expected_valid": expected_valid,
            "expected_error_codes": sorted(expected_codes),
            "expected_counts": expected_counts,
            "observed_error_codes": sorted(observed_codes),
        })
    return {"ok": all(item["passed"] for item in results), "count": len(results), "results": results}


def _apply_mutation(release_root: Path, mutation: str) -> None:
    if mutation == "causal_wording":
        document = _load_json(release_root / "relationships.json")
        document["relationships"][0]["short_explanation"]["en"] = "One artist was directly influenced by the other."
        _write_artifact(release_root, "relationships.json", document)
    elif mutation == "causal_title":
        document = _load_json(release_root / "relationships.json")
        document["relationships"][0]["title"]["en"] = "One artist directly influenced the other"
        _write_artifact(release_root, "relationships.json", document)
    elif mutation == "media_byte":
        media_path = release_root / "media" / "unexpected.jpg"
        media_path.parent.mkdir()
        media_path.write_bytes(b"not-an-image")
    elif mutation == "private_path":
        document = _load_json(release_root / "artists.json")
        document["artists"][0]["summary"]["en"] += " C:\\private\\notes.txt"
        _write_artifact(release_root, "artists.json", document)
    elif mutation == "manifest_private_path":
        document = _load_json(release_root / "manifest.json")
        document["release_notes"] = "file://C:/private/release-notes.txt"
        (release_root / "manifest.json").write_bytes(canonical_json_bytes(document))
    elif mutation == "media_url":
        document = _load_json(release_root / "artworks.json")
        document["artworks"][0]["official_object_url"] = "https://example.org/assets/artwork.jpg"
        _write_artifact(release_root, "artworks.json", document)
    elif mutation == "extensionless_media_url":
        document = _load_json(release_root / "artworks.json")
        document["artworks"][0]["official_object_url"] = "https://images.example.org/assets/12345"
        _write_artifact(release_root, "artworks.json", document)
    elif mutation == "external_qid":
        document = _load_json(release_root / "manifest.json")
        document["release_notes"] = "Unexpected external authority identifier Q42424242."
        (release_root / "manifest.json").write_bytes(canonical_json_bytes(document))
    elif mutation == "source_media_rule":
        document = _load_json(release_root / "source-rules-snapshot.json")
        canonical = _load_json(ROOT / "research" / "source-registry" / "source-license-rules.json")
        canonical_source = next(item for item in canonical["sources"] if item["source_id"] == "aic_api")
        media_rule = next(item for item in canonical_source["rules"] if item["content_class"] == "media")
        source_snapshot = next(item for item in document["sources"] if item["source_id"] == "source:aic_api")
        source_snapshot["license_rules"].append(media_rule)
        source_snapshot["license_rules_snapshot_hash"] = "sha256:" + hashlib.sha256(
            canonical_json_bytes(source_snapshot["license_rules"])
        ).hexdigest()
        _write_artifact(release_root, "source-rules-snapshot.json", document)
    elif mutation == "missing_notice":
        document = _load_json(release_root / "third-party-notices.json")
        document["notices"].pop()
        _write_artifact(release_root, "third-party-notices.json", document)
    elif mutation == "human_review_overclaim":
        document = _load_json(release_root / "release-signoff.json")
        document["human_reviewer_claimed"] = True
        _write_artifact(release_root, "release-signoff.json", document)
    elif mutation == "signoff_fabrication":
        document = _load_json(release_root / "release-signoff.json")
        document["checks"] = [f"fabricated-check-{index}" for index in range(14)]
        document["limitations"] = "Human review by Mays completed."
        _write_artifact(release_root, "release-signoff.json", document)
    elif mutation == "rights_open_license":
        document = _load_json(release_root / "rights.json")
        statement = {
            "zh-Hans": "CC0 unrestricted use statement.",
            "en": "Released under CC0 for unrestricted use.",
        }
        document["code_rights"]["statement"] = statement
        document["original_content_rights"]["statement"] = statement
        _write_artifact(release_root, "rights.json", document)
    elif mutation == "performance_drift":
        document = _load_json(release_root / "performance-contract.json")
        document["budgets"]["mobile_visible_vertices_max"] = 1
        document["budgets"]["desktop_visible_edges_max"] = 999999
        document["scale_boundaries"]["one_k"]["vertices"] = 2000
        _write_artifact(release_root, "performance-contract.json", document)
    elif mutation == "claim_closure":
        document = _load_json(release_root / "relationships.json")
        document["relationships"][0]["claim_ids"] = ["claim:missing-public-claim"]
        _write_artifact(release_root, "relationships.json", document)
    elif mutation == "missing_evidence":
        document = _load_json(release_root / "claims.json")
        claim = document["claims"][0]
        claim["evidence_ids"].append("evidence:missing-public-evidence")
        envelope = next(item for item in document["records"] if item["data"]["id"] == claim["id"])
        envelope["data"]["evidence_ids"].append("evidence:missing-public-evidence")
        _write_artifact(release_root, "claims.json", document)
    elif mutation == "evidence_long_summary":
        document = _load_json(release_root / "evidence.json")
        document["evidence"][0]["summary"]["en"] = "Repeated source passage. " * 1000
        _write_artifact(release_root, "evidence.json", document)
    elif mutation == "manifest_hash":
        path = release_root / "graph-summary.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "withdrawal_contract":
        manifest = _load_json(release_root / "manifest.json")
        manifest["predecessor"] = "release:art-constellation-0.0.9"
        (release_root / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    else:
        raise ValueError(f"Unknown MUSEUM-04 fixture mutation: {mutation}")


def _write_artifact(release_root: Path, name: str, document: dict[str, Any]) -> None:
    payload = canonical_json_bytes(document)
    (release_root / name).write_bytes(payload)
    manifest = _load_json(release_root / "manifest.json")
    entry = next(item for item in manifest["manifest_files"] if item["path"] == name)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    entry["bytes"] = len(payload)
    manifest["content_hash"] = _release_content_hash(manifest["manifest_files"])
    (release_root / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.release_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["results"]:
            print(f"[{'PASS' if item['passed'] else 'FAIL'}] {item['fixture_id']}: {', '.join(item['observed_error_codes']) or 'valid'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
