#!/usr/bin/env python3
"""Validate source coverage, scoped license rules, dates, and permission summaries."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "research" / "source-registry"
MATRIX = REGISTRY_DIR / "source-comparison-matrix.csv"
CONFIG_PATH = REGISTRY_DIR / "minimum-source-set.json"
RULES_PATH = REGISTRY_DIR / "source-license-rules.json"

REQUIRED_COLUMNS = [
    "branch", "source_id", "name", "official_url", "data_types", "access_method",
    "api_key", "access_limits", "rate_limit",
    "metadata_license", "metadata_redistribution", "metadata_modification",
    "metadata_attribution", "metadata_commercial_use",
    "data_license", "data_redistribution", "data_modification", "data_attribution", "data_commercial_use",
    "media_license", "media_redistribution", "media_modification", "media_attribution", "media_commercial_use",
    "public_static_redistribution", "permission_status", "license_rules_ref",
    "static_pages_fit", "tier", "risks", "verified_at", "reverify_by",
    "terms_url", "terms_version", "terms_snapshot_status",
]

CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
REQUIRED_SOURCE_IDS = set(CONFIG.get("minimum_source_ids", []))
PERMISSION_COLUMNS = [
    f"{content}_{permission}"
    for content in ("metadata", "data", "media")
    for permission in ("redistribution", "modification", "attribution", "commercial_use")
]


@dataclass(frozen=True)
class RegistryIssue:
    row: int
    column: str
    message: str


def https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def load_rules() -> tuple[dict[str, list[dict[str, object]]], list[RegistryIssue]]:
    issues: list[RegistryIssue] = []
    if not RULES_PATH.exists():
        return {}, [RegistryIssue(0, "source-license-rules.json", "License rules file is missing")]
    try:
        raw = RULES_PATH.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [RegistryIssue(0, "source-license-rules.json", str(exc))]
    expected_snapshot_hash = CONFIG.get("license_rules_snapshot_hash")
    actual_snapshot_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    if expected_snapshot_hash != actual_snapshot_hash:
        issues.append(RegistryIssue(0, "license_rules_snapshot_hash", f"Expected {expected_snapshot_hash}, got {actual_snapshot_hash}"))
    result: dict[str, list[dict[str, object]]] = {}
    seen_rule_ids: set[str] = set()
    for index, entry in enumerate(payload.get("sources", []), start=1):
        source_id = entry.get("source_id")
        rules = entry.get("rules")
        if not isinstance(source_id, str) or not isinstance(rules, list):
            issues.append(RegistryIssue(index, "license_rules", "Each source needs source_id and rules"))
            continue
        if source_id in result:
            issues.append(RegistryIssue(index, "license_rules", f"Duplicate rule source {source_id}"))
        result[source_id] = rules
        classes = {rule.get("content_class") for rule in rules if isinstance(rule, dict)}
        if not {"metadata", "data", "media"}.issubset(classes):
            issues.append(RegistryIssue(index, "license_rules", f"{source_id} must explicitly cover metadata, data, and media"))
        for rule_index, rule in enumerate(rules):
            location = f"{source_id}.rules[{rule_index}]"
            required = {
                "rule_id", "content_class", "applies_to", "scope_match", "rights_status", "identifier", "version", "url",
                "attribution_template", "redistribution", "modification", "commercial_use",
                "share_alike", "scope_note", "no_inheritance",
            }
            if not isinstance(rule, dict) or not required.issubset(rule):
                issues.append(RegistryIssue(index, location, "License rule fields are incomplete"))
                continue
            rule_id = rule.get("rule_id")
            selector_hash = hashlib.sha256(str(rule.get("applies_to", "")).encode("utf-8")).hexdigest()[:12]
            expected_rule_id = f"{source_id}:{rule.get('content_class')}:{selector_hash}"
            if rule_id != expected_rule_id:
                issues.append(RegistryIssue(index, location, f"Stable rule_id must be {expected_rule_id}"))
            if rule_id in seen_rule_ids:
                issues.append(RegistryIssue(index, location, f"Duplicate rule_id {rule_id}"))
            if isinstance(rule_id, str):
                seen_rule_ids.add(rule_id)
            if rule.get("no_inheritance") is not True:
                issues.append(RegistryIssue(index, location, "License rules must be fail-closed with no_inheritance=true"))
            if not str(rule.get("applies_to", "")).strip():
                issues.append(RegistryIssue(index, location, "applies_to selector is blank"))
            scope_match = rule.get("scope_match") if isinstance(rule.get("scope_match"), dict) else {}
            if (
                scope_match.get("normalization") not in {"none", "url_path_decode"}
                or not str(scope_match.get("pattern", ""))
                or not isinstance(scope_match.get("allowed_schemes"), list)
                or not isinstance(scope_match.get("allowed_hosts"), list)
                or not isinstance(scope_match.get("allow_relative_path"), bool)
                or scope_match.get("field_policy") not in {"any", "include", "exclude"}
                or not isinstance(scope_match.get("fields"), list)
                or not isinstance(scope_match.get("require_explicit_query_fields"), bool)
            ):
                issues.append(RegistryIssue(index, location, "scope_match needs an executable normalization and regex pattern"))
            else:
                try:
                    re.compile(str(scope_match["pattern"]))
                except re.error as exc:
                    issues.append(RegistryIssue(index, location, f"scope_match regex is invalid: {exc}"))
            for field in ("redistribution", "modification", "commercial_use"):
                if rule.get(field) not in {"allowed", "conditional", "prohibited", "unknown"}:
                    issues.append(RegistryIssue(index, location, f"Invalid {field} value"))
            rights_status = rule.get("rights_status")
            identifier = str(rule.get("identifier", "")).upper()
            expected = {
                "cc0": "CC0-", "cc_by": "CC-BY-", "cc_by_sa": "CC-BY-SA-", "odc_by": "ODC-BY-"
            }.get(rights_status)
            if expected and not identifier.startswith(expected):
                issues.append(RegistryIssue(index, location, f"Identifier {identifier!r} conflicts with {rights_status}"))
            if rights_status == "cc_by" and identifier.startswith("CC-BY-SA-"):
                issues.append(RegistryIssue(index, location, "CC BY rule cannot use a CC BY-SA identifier"))
            if rights_status in {"cc0", "cc_by", "cc_by_sa", "odc_by"} and not https_url(str(rule.get("url") or "")):
                issues.append(RegistryIssue(index, location, "Standard open license requires an HTTPS license URL"))
            if rights_status in {"cc_by", "cc_by_sa", "odc_by"} and not str(rule.get("attribution_template") or "").strip():
                issues.append(RegistryIssue(index, location, "Attribution license requires an attribution template"))

    aic_rules = result.get("aic_api", [])
    if not any(rule.get("content_class") == "data" and "/description" in str(rule.get("applies_to")) and rule.get("rights_status") == "cc_by" for rule in aic_rules):
        issues.append(RegistryIssue(0, "aic_api", "AIC description field needs a dedicated CC BY rule"))
    iucn_rules = result.get("iucn_red_list", [])
    if not iucn_rules or any(rule.get("redistribution") != "prohibited" for rule in iucn_rules):
        issues.append(RegistryIssue(0, "iucn_red_list", "IUCN rules must block redistribution until written permission is recorded"))
    return result, issues


def validate(path: Path = MATRIX) -> tuple[list[RegistryIssue], list[dict[str, str]]]:
    issues: list[RegistryIssue] = []
    rules_by_source, rule_issues = load_rules()
    issues.extend(rule_issues)
    if not path.exists():
        return issues + [RegistryIssue(0, "file", f"Missing registry: {path}")], []

    actual_matrix_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if CONFIG.get("source_matrix_snapshot_hash") != actual_matrix_hash:
        issues.append(RegistryIssue(0, "source_matrix_snapshot_hash", f"Expected {CONFIG.get('source_matrix_snapshot_hash')}, got {actual_matrix_hash}"))

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if headers != REQUIRED_COLUMNS:
            issues.append(RegistryIssue(1, "header", f"Expected columns {REQUIRED_COLUMNS}; got {headers}"))
        rows = list(reader)

    seen: set[str] = set()
    max_age = int(CONFIG.get("maximum_verification_age_days", 366))
    for index, row in enumerate(rows, start=2):
        for column in REQUIRED_COLUMNS:
            if not (row.get(column) or "").strip():
                issues.append(RegistryIssue(index, column, "Required value is blank"))
        source_id = row.get("source_id", "")
        if source_id in seen:
            issues.append(RegistryIssue(index, "source_id", "Duplicate source_id"))
        seen.add(source_id)
        if row.get("branch") not in {"art", "biology"}:
            issues.append(RegistryIssue(index, "branch", "Must be art or biology"))
        if row.get("api_key") not in {"yes", "no", "conditional"}:
            issues.append(RegistryIssue(index, "api_key", "Must be yes, no, or conditional"))
        for column in PERMISSION_COLUMNS:
            if row.get(column) not in {"yes", "no", "conditional", "not_applicable"}:
                issues.append(RegistryIssue(index, column, "Must be yes, no, conditional, or not_applicable"))
        if row.get("public_static_redistribution") not in {"allowed", "conditional", "prohibited", "unknown"}:
            issues.append(RegistryIssue(index, "public_static_redistribution", "Invalid permission value"))
        if row.get("permission_status") not in {"approved", "not_required", "pending", "denied", "revoked"}:
            issues.append(RegistryIssue(index, "permission_status", "Invalid permission status"))
        if row.get("static_pages_fit") not in {"high", "medium", "conditional", "low"}:
            issues.append(RegistryIssue(index, "static_pages_fit", "Unexpected fit value"))
        if row.get("tier") not in {"1", "2", "3", "4"}:
            issues.append(RegistryIssue(index, "tier", "Tier must be 1, 2, 3, or 4"))
        for column in ("official_url", "terms_url"):
            if not https_url(row.get(column, "")):
                issues.append(RegistryIssue(index, column, "Must be an absolute HTTPS URL"))
        try:
            verified = date.fromisoformat(row.get("verified_at", ""))
            reverify = date.fromisoformat(row.get("reverify_by", ""))
            age = (reverify - verified).days
            if verified > date.today():
                issues.append(RegistryIssue(index, "verified_at", "Verification date is in the future"))
            if reverify < date.today():
                issues.append(RegistryIssue(index, "reverify_by", "Source verification is stale"))
            if age < 1 or age > max_age:
                issues.append(RegistryIssue(index, "reverify_by", f"Reverification window must be 1..{max_age} days"))
        except ValueError:
            issues.append(RegistryIssue(index, "verified_at/reverify_by", "Must be ISO dates"))
        expected_ref = f"source-license-rules.json#{source_id}"
        if row.get("license_rules_ref") != expected_ref:
            issues.append(RegistryIssue(index, "license_rules_ref", f"Expected {expected_ref}"))
        if source_id not in rules_by_source:
            issues.append(RegistryIssue(index, "license_rules_ref", "No scoped license rules found"))
        if source_id == "iucn_red_list" and not (
            row.get("public_static_redistribution") == "prohibited" and row.get("permission_status") == "pending"
        ):
            issues.append(RegistryIssue(index, "iucn_red_list", "IUCN must remain blocked pending written permission"))

    missing = REQUIRED_SOURCE_IDS - seen
    if missing:
        issues.append(RegistryIssue(0, "source_id", f"Missing minimum sources: {', '.join(sorted(missing))}"))
    extra_rule_sources = set(rules_by_source) - seen
    if extra_rule_sources:
        issues.append(RegistryIssue(0, "license_rules", f"Rules exist for absent registry sources: {', '.join(sorted(extra_rule_sources))}"))

    for filename in ("art-source-registry.md", "biology-source-registry.md", "source-verification-notes.md"):
        if not (REGISTRY_DIR / filename).is_file():
            issues.append(RegistryIssue(0, filename, "Required registry document is missing"))
    return issues, rows


def main() -> int:
    issues, rows = validate()
    if issues:
        for issue in issues:
            print(f"[FAIL] row {issue.row} column {issue.column}: {issue.message}")
        print(f"[FAIL] source registry: {len(issues)} issue(s), {len(rows)} row(s)")
        return 1
    art = sum(row["branch"] == "art" for row in rows)
    biology = sum(row["branch"] == "biology" for row in rows)
    print(f"[PASS] source registry: {len(rows)} sources ({art} art, {biology} biology); structural and scoped-license semantics checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
