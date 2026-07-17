#!/usr/bin/env python3
"""Validate schemas, governance fixtures, and fail-closed release bundles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "governance"
RELEASE_FIXTURE_ROOT = ROOT / "fixtures" / "release-bundles" / "valid"
SOURCE_RULES_PATH = ROOT / "research" / "source-registry" / "source-license-rules.json"
SOURCE_MATRIX_PATH = ROOT / "research" / "source-registry" / "source-comparison-matrix.csv"
SOURCE_REGISTRY_CONFIG_PATH = ROOT / "research" / "source-registry" / "minimum-source-set.json"
LICENSE_DECISIONS_PATH = ROOT / "governance" / "license-decisions.json"
MAX_GOVERNANCE_REVIEW_AGE_DAYS = 366
RELEASE_SOURCE_MATRIX_SNAPSHOT_HASHES = {
    "release:art-constellation-1.0.0": "sha256:1df4788f3d3779bd0d126486eec7e96c2c07ff2ce040ce74cf9f8448fe61ac21",
    "release:art-gallery-interactions-1.1.0": "sha256:1df4788f3d3779bd0d126486eec7e96c2c07ff2ce040ce74cf9f8448fe61ac21",
    "release:art-pathways-1.2.0": "sha256:1df4788f3d3779bd0d126486eec7e96c2c07ff2ce040ce74cf9f8448fe61ac21",
}

ALLOWED_CLAIM_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"candidate"},
    "candidate": {"sourced", "withdrawn"},
    "sourced": {"reviewed", "disputed", "withdrawn"},
    "reviewed": {"verified", "disputed", "withdrawn"},
    "verified": {"publishable", "disputed", "withdrawn"},
    "publishable": {"published", "withdrawn"},
    "published": {"deprecated", "withdrawn"},
    "disputed": {"reviewed", "deprecated", "withdrawn"},
    "deprecated": set(),
    "withdrawn": set(),
}

DIRECT_HISTORICAL_TYPES = {
    "student_of", "teacher_of", "worked_in_studio_of", "collaborated_with",
    "explicitly_influenced_by", "explicitly_influenced", "referenced_or_quoted",
}

HIGH_RISK_PREDICATES = {
    "birth_date", "birth_year", "birth_period", "death_date", "death_year", "death_period", "identity_same_as",
    "creator_attribution", "attributed_to", "student_of", "teacher_of",
    "worked_in_studio_of", "collaborated_with", "explicitly_influenced_by",
    "explicitly_influenced", "referenced_or_quoted",
}

COMPUTATIONAL_PREDICATES = {"computationally_similar_to", "computational_similarity"}

RELEASE_LISTS = {
    "entity": "included_entity_ids",
    "relationship": "included_relationship_ids",
    "claim": "included_claim_ids",
    "evidence": "included_evidence_ids",
    "source": "included_source_ids",
    "media": "included_media_asset_ids",
}

TARGET_SCHEMA_BY_ENTITY_TYPE = {
    "claim": "schemas/common/claim.schema.json",
    "evidence": "schemas/common/evidence.schema.json",
    "source": "schemas/common/source.schema.json",
    "media_asset": "schemas/common/media-asset.schema.json",
    "media_retry_record": "schemas/art/media/media-retry.schema.json",
    "dataset_release": "schemas/common/dataset-release.schema.json",
    "art_gallery_interaction_index": "schemas/art/release/art-gallery-interaction-index.schema.json",
    "art_path_result": "schemas/art/release/path-result.schema.json",
    **{
        entity_type: "schemas/art/release/art-pathways-artifact.schema.json"
        for entity_type in (
            "art_path_algorithm_contract", "art_path_graph_input", "art_path_index",
            "art_path_explanation_collection", "art_path_ab_review_summary",
            "art_path_performance_contract", "art_path_route_config",
        )
    },
    "artist": "schemas/art/artist.schema.json",
    "artwork": "schemas/art/artwork.schema.json",
    "review_signoff": "schemas/art/batch/review-signoff.schema.json",
    "approved_identity_basis": "schemas/art/batch/approved-identity-basis.schema.json",
    "snapshot_receipt_ledger": "schemas/art/batch/snapshot-receipt-ledger.schema.json",
    "artwork_selection_basis": "schemas/art/batch/artwork-selection-basis.schema.json",
    "manual_evidence_capture": "schemas/art/batch/manual-evidence-capture.schema.json",
    "relationship_research_disposition": "schemas/art/batch/relationship-research-disposition.schema.json",
    "media_eligibility_assessment": "schemas/art/batch/media-eligibility-assessment.schema.json",
    "formal_art_batch_manifest": "schemas/art/batch/formal-art-batch-manifest.schema.json",
    "reviewed_package_manifest": "schemas/art/batch/reviewed-package-manifest.schema.json",
    "graph_input": "schemas/art/batch/graph-input.schema.json",
    "replacement_review_request": "schemas/art/batch/replacement-review-request.schema.json",
    "public_leakage_label_set": "schemas/art/batch/public-leakage-label-set.schema.json",
    **{
        entity_type: "schemas/art/context/art-context.schema.json"
        for entity_type in (
            "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
            "exhibition_event", "material", "technique", "subject", "time_period", "person",
        )
    },
    "taxon": "schemas/biology/taxon.schema.json",
    "species": "schemas/biology/taxon.schema.json",
    **{
        entity_type: "schemas/art/release/public-constellation-record.schema.json"
        for entity_type in (
            "art_constellation_artist", "art_constellation_context", "art_constellation_artwork",
            "art_constellation_relationship", "art_constellation_claim", "art_constellation_evidence",
        )
    },
}

ART_CONTEXT_ENTITY_TYPES = {
    "art_movement", "art_group", "museum_institution", "organization", "place", "exhibition",
    "exhibition_event", "material", "technique", "subject", "time_period", "person",
}

PUBLIC_CONSTELLATION_ENTITY_TYPES = {
    "art_constellation_artist", "art_constellation_context", "art_constellation_artwork",
    "art_constellation_relationship", "art_constellation_claim", "art_constellation_evidence",
}

ARTIFACT_SCHEMAS = {
    "source_registry": "schemas/common/source-rules-snapshot.schema.json",
    "license_decisions": "schemas/common/license-decision-registry.schema.json",
    "third_party_notices": "schemas/common/third-party-notices.schema.json",
    "attributions": "schemas/common/attribution-manifest.schema.json",
}

ART_RELATION_TARGET_TYPES = {
    "member_of": {"art_group", "organization"},
    "associated_with_movement": {"art_movement"},
}

ART_RELATION_CONTEXT_TYPES = {
    "participated_in_same_exhibition": {"exhibition", "exhibition_event"},
    "shared_patron": {"person", "organization"},
    "shared_institution": {"museum_institution", "organization"},
    "shared_subject": {"subject"},
    "shared_technique": {"technique"},
    "shared_material": {"material"},
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    location: str = "$"


@dataclass
class SchemaEnvironment:
    by_path: dict[str, dict[str, Any]]
    registry: Registry


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_source_rules() -> dict[str, list[dict[str, Any]]]:
    document = load_json(SOURCE_RULES_PATH)
    return {
        item["source_id"]: item["rules"]
        for item in document.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("source_id"), str) and isinstance(item.get("rules"), list)
    }


def canonical_source_identities() -> dict[str, dict[str, str]]:
    with SOURCE_MATRIX_PATH.open("r", encoding="utf-8", newline="") as handle:
        return {
            row["source_id"]: {
                "canonical_name": row["name"],
                "canonical_official_host": (urlparse(row["official_url"]).hostname or "").lower(),
            }
            for row in csv.DictReader(handle)
        }


def license_decision_registry() -> dict[str, dict[str, Any]]:
    document = load_json(LICENSE_DECISIONS_PATH)
    return {
        item["decision_id"]: item
        for item in document.get("decisions", [])
        if isinstance(item, dict) and isinstance(item.get("decision_id"), str)
    }


def schema_manifest_versions() -> dict[str, str]:
    return {
        item["path"]: item["version"]
        for item in schema_manifest_entries(ROOT)
        if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("version"), str)
    }


def schema_manifest_entries(root: Path) -> list[dict[str, Any]]:
    manifest_paths = sorted((root / "schemas").rglob("schema-manifest.json"))
    if root / "schemas" / "schema-manifest.json" not in manifest_paths:
        raise ValueError("Missing schemas/schema-manifest.json")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest_path in manifest_paths:
        manifest = load_json(manifest_path)
        document_entries = manifest.get("schemas")
        if (
            manifest.get("dialect") != "https://json-schema.org/draft/2020-12/schema"
            or not isinstance(document_entries, list)
        ):
            relative = manifest_path.relative_to(root).as_posix()
            raise ValueError(f"Schema manifest has an invalid dialect or schemas list: {relative}")
        for entry in document_entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError(f"Schema manifest contains an invalid entry: {manifest_path}")
            if entry["path"] in seen:
                raise ValueError(f"Schema manifest path is declared more than once: {entry['path']}")
            seen.add(entry["path"])
            entries.append(entry)
    return entries


def schema_version_key(path: str) -> str:
    prefix = "schemas/"
    suffix = ".schema.json"
    return path[len(prefix):-len(suffix)] if path.startswith(prefix) and path.endswith(suffix) else path


def expected_target_schema(data: dict[str, Any]) -> str | None:
    if data.get("branch_id") == "arms":
        return None
    entity_type = data.get("entity_type")
    if entity_type in ART_CONTEXT_ENTITY_TYPES:
        if data.get("branch_id") == "art":
            return "schemas/art/context/art-context.schema.json"
        return "schemas/common/entity.schema.json"
    if entity_type == "relationship":
        record_id = str(data.get("id", ""))
        branch = data.get("branch_id")
        if record_id.startswith("art-rel:") or branch == "art":
            return "schemas/art/artist-relationship.schema.json"
        if record_id.startswith("bio-rel:") or branch == "biology":
            return "schemas/biology/ecosystem-interaction.schema.json"
        return "schemas/common/relationship.schema.json"
    return TARGET_SCHEMA_BY_ENTITY_TYPE.get(str(entity_type), "schemas/common/entity.schema.json")


def target_schema_binding_issues(target_schema: str, data: dict[str, Any], prefix: str) -> list[ValidationIssue]:
    expected = expected_target_schema(data)
    if expected is None:
        return [
            ValidationIssue(
                "arms_branch_schema_not_implemented",
                "Branch 'arms' has no concrete entity schema; fallback to the common entity schema is forbidden until MUSEUM-ARMS-00 implements the branch contract",
                f"{prefix}.target_schema",
            )
        ]
    if target_schema == expected:
        return []
    return [
        ValidationIssue(
            "schema_target_mismatch",
            f"Record type {data.get('entity_type')!r}, branch {data.get('branch_id')!r}, and ID {data.get('id')!r} require {expected}, not {target_schema}",
            f"{prefix}.target_schema",
        )
    ]


def record_identity_issues(data: dict[str, Any], prefix: str) -> list[ValidationIssue]:
    record_id = data.get("id")
    entity_type = data.get("entity_type")
    if not isinstance(record_id, str) or ":" not in record_id or not isinstance(entity_type, str):
        return [ValidationIssue("record_id_invalid", "Record needs a stable string ID and entity_type", f"{prefix}.id")]
    id_prefix = record_id.split(":", 1)[0]
    expected_types = {
        "artist": {"artist", "art_constellation_artist"},
        "artwork": {"artwork", "art_constellation_artwork"},
        "claim": {"claim", "art_constellation_claim"},
        "evidence": {"evidence", "art_constellation_evidence"},
        "art-rel": {"relationship", "art_constellation_relationship"},
        "bio-rel": {"relationship"},
        "rel": {"relationship"},
        "media": {"media_asset"},
        "release": {"dataset_release"},
        "review-signoff": {"review_signoff"},
        "approved-identity-basis": {"approved_identity_basis"},
        "snapshot-receipt-ledger": {"snapshot_receipt_ledger"},
        "artwork-selection-basis": {"artwork_selection_basis"},
        "manual-evidence-capture": {"manual_evidence_capture"},
        "relationship-disposition": {"relationship_research_disposition"},
        "media-assessment": {"media_eligibility_assessment"},
        "art-batch-manifest": {"formal_art_batch_manifest"},
        "reviewed-package-manifest": {"reviewed_package_manifest"},
        "graph-input": {"graph_input"},
        "replacement-review-request": {"replacement_review_request"},
        "public-leakage-label-set": {"public_leakage_label_set"},
        "selection-decision": {"selection_decision"},
        "selection-decision-application": {"selection_decision_application"},
        "taxon": {"taxon", "species"},
        "material": {"material", "art_constellation_context"},
        "technique": {"technique", "art_constellation_context"},
        "subject": {"subject", "art_constellation_context"},
        "museum_institution": {"museum_institution", "art_constellation_context"},
        "place": {"place", "art_constellation_context"},
    }.get(id_prefix, {id_prefix})
    if entity_type in expected_types:
        return []
    return [
        ValidationIssue(
            "record_id_entity_type_mismatch",
            f"ID prefix {id_prefix!r} is incompatible with entity_type {entity_type!r}",
            f"{prefix}.id",
        )
    ]


def governed_date_issues(value: Any, field: str, prefix: str, *, stale: bool = False) -> list[ValidationIssue]:
    parsed = parse_date(value)
    if parsed is None:
        return []
    if parsed > date.today():
        return [ValidationIssue("governance_date_in_future", f"{field} cannot be in the future", f"{prefix}.{field}")]
    if stale and date.today() - parsed > timedelta(days=MAX_GOVERNANCE_REVIEW_AGE_DAYS):
        return [ValidationIssue("governance_review_stale", f"{field} is older than {MAX_GOVERNANCE_REVIEW_AGE_DAYS} days", f"{prefix}.{field}")]
    return []


def claim_temporal_sort_key(claim_object: dict[str, Any]) -> tuple[int, int, int] | None:
    value = str(claim_object.get("value", ""))
    datatype = claim_object.get("datatype")
    if datatype == "year" and re.fullmatch(r"-?[0-9]{1,6}", value):
        return int(value), 1, 1
    if datatype == "date":
        match = re.fullmatch(r"([0-9]{4,6})-([0-9]{2})-([0-9]{2})", value)
        if match:
            return tuple(int(part) for part in match.groups())
    return None


def source_rule_scope_matches(rule: dict[str, Any], locator: str, scope_fields: list[str]) -> bool:
    contract = rule.get("scope_match") if isinstance(rule.get("scope_match"), dict) else {}
    normalized = locator
    parsed = urlparse(locator)
    if contract.get("normalization") == "url_path_decode":
        if parsed.scheme or parsed.netloc:
            allowed_schemes = {str(item).lower() for item in contract.get("allowed_schemes", [])}
            allowed_hosts = {str(item).lower() for item in contract.get("allowed_hosts", [])}
            if parsed.scheme.lower() not in allowed_schemes or (parsed.hostname or "").lower() not in allowed_hosts:
                return False
        elif contract.get("allow_relative_path") is not True:
            return False
        normalized = parsed.path if parsed.scheme or parsed.netloc else locator.split("?", 1)[0].split("#", 1)[0]
        for _ in range(4):
            decoded = unquote(normalized)
            if decoded == normalized:
                break
            normalized = decoded
    try:
        if re.fullmatch(str(contract.get("pattern", "")), normalized) is None:
            return False
    except re.error:
        return False
    observed_fields = set(scope_fields)
    if contract.get("require_explicit_query_fields") is True:
        raw_values = parse_qs(parsed.query, keep_blank_values=True).get("fields", [])
        if not raw_values:
            return False
        query_fields: set[str] = set()
        for raw_value in raw_values:
            decoded = raw_value
            for _ in range(4):
                next_value = unquote(decoded)
                if next_value == decoded:
                    break
                decoded = next_value
            query_fields.update(part.strip() for part in decoded.split(",") if part.strip())
        if not query_fields or query_fields != observed_fields:
            return False
    policy_fields = set(contract.get("fields", []))
    if contract.get("field_policy") == "include" and not policy_fields.issubset(observed_fields):
        return False
    if contract.get("field_policy") == "exclude" and policy_fields & observed_fields:
        return False
    return True


def validate_schema_manifest(root: Path, by_path: dict[str, dict[str, Any]]) -> None:
    by_manifest_path = {entry["path"]: entry for entry in schema_manifest_entries(root)}
    if set(by_manifest_path) != set(by_path):
        missing = sorted(set(by_path) - set(by_manifest_path))
        extra = sorted(set(by_manifest_path) - set(by_path))
        raise ValueError(f"Schema manifest path mismatch; missing={missing}, extra={extra}")
    for path, entry in by_manifest_path.items():
        if entry.get("id") != by_path[path].get("$id"):
            raise ValueError(f"Schema manifest $id mismatch for {path}")
        if not isinstance(entry.get("version"), str) or not entry["version"]:
            raise ValueError(f"Schema manifest version missing for {path}")
        dependencies = entry.get("depends_on")
        if not isinstance(dependencies, list) or any(item not in by_path for item in dependencies):
            raise ValueError(f"Schema manifest dependency is invalid for {path}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(path: str) -> None:
        if path in visiting:
            raise ValueError(f"Schema dependency cycle detected at {path}")
        if path in visited:
            return
        visiting.add(path)
        for dependency in by_manifest_path[path]["depends_on"]:
            visit(dependency)
        visiting.remove(path)
        visited.add(path)

    for path in by_manifest_path:
        visit(path)


def load_schema_environment(root: Path = ROOT) -> SchemaEnvironment:
    by_path: dict[str, dict[str, Any]] = {}
    registry: Registry = Registry()
    for path in sorted((root / "schemas").rglob("*.schema.json")):
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        relative = path.relative_to(root).as_posix()
        by_path[relative] = schema
        schema_id = schema.get("$id")
        if not schema_id:
            raise ValueError(f"Schema has no $id: {relative}")
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    if not by_path:
        raise ValueError("No schemas found")
    validate_schema_manifest(root, by_path)
    return SchemaEnvironment(by_path=by_path, registry=registry)


def json_path(error_path: Iterable[Any]) -> str:
    parts = ["$"]
    for part in error_path:
        parts.append(f"[{part}]" if isinstance(part, int) else f".{part}")
    return "".join(parts)


def schema_issues(
    target_schema: str,
    data: dict[str, Any],
    environment: SchemaEnvironment,
    prefix: str = "$",
) -> list[ValidationIssue]:
    schema = environment.by_path.get(target_schema)
    if schema is None:
        return [ValidationIssue("schema_target_missing", f"Unknown target schema: {target_schema}", prefix)]
    validator = Draft202012Validator(schema, registry=environment.registry, format_checker=FormatChecker())
    issues: list[ValidationIssue] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        suffix = json_path(error.absolute_path)
        location = prefix if suffix == "$" else f"{prefix}{suffix[1:]}"
        issues.append(ValidationIssue("schema", error.message, location))
    return issues


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def claim_transition_issues(data: dict[str, Any], prefix: str) -> list[ValidationIssue]:
    if data.get("entity_type") != "claim":
        return []
    issues: list[ValidationIssue] = []
    history = data.get("status_history", [])
    previous: str | None = None
    for index, event in enumerate(history):
        source = event.get("from")
        target = event.get("to")
        if source != previous or target not in ALLOWED_CLAIM_TRANSITIONS.get(source, set()):
            issues.append(
                ValidationIssue(
                    "invalid_claim_transition",
                    f"Transition {source!r} -> {target!r} is not allowed or is not contiguous",
                    f"{prefix}.status_history[{index}]",
                )
            )
        previous = target
    if history and previous != data.get("status"):
        issues.append(
            ValidationIssue(
                "claim_status_history_mismatch",
                f"Last history status {previous!r} does not match current status {data.get('status')!r}",
                f"{prefix}.status",
            )
        )
    return issues


def source_publish_issues(
    data: dict[str, Any],
    prefix: str,
    release_public_until: str | None = None,
    source_registry_snapshot_hash: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if data.get("public_static_redistribution") != "allowed":
        issues.append(ValidationIssue("source_redistribution_not_approved", "Source terms do not allow public static redistribution", f"{prefix}.public_static_redistribution"))
    if data.get("permission_status") not in {"approved", "not_required"}:
        issues.append(ValidationIssue("source_permission_not_approved", "Source permission is not approved", f"{prefix}.permission_status"))
    if data.get("permission_revoked_at") is not None:
        issues.append(ValidationIssue("source_permission_revoked", "A revoked source permission cannot support a public release", f"{prefix}.permission_revoked_at"))
    if data.get("lifecycle_status") not in {"publishable", "published"}:
        issues.append(ValidationIssue("source_status_not_publishable", "Source record is not in a publishable lifecycle state", f"{prefix}.lifecycle_status"))
    if data.get("tier") == 4:
        issues.append(ValidationIssue("tier_4_source_not_publishable", "Tier 4 sources are discovery-only and cannot enter a public release", f"{prefix}.tier"))
    if not data.get("terms_snapshot_hash"):
        issues.append(ValidationIssue("source_terms_snapshot_missing", "Publishable source requires a hashed terms snapshot or equivalent signed record", f"{prefix}.terms_snapshot_hash"))

    rules = [rule for rule in data.get("license_rules", []) if isinstance(rule, dict)]
    rules_by_id = {rule.get("rule_id"): rule for rule in rules if isinstance(rule.get("rule_id"), str)}
    if len(rules_by_id) != len(rules):
        issues.append(ValidationIssue("source_license_rule_id_duplicate", "Source license rule IDs must be present and unique", f"{prefix}.license_rules"))
    if stable_json_hash(rules) != data.get("license_rules_snapshot_hash"):
        issues.append(ValidationIssue("source_license_snapshot_hash_mismatch", "Source rule snapshot hash does not match license_rules", f"{prefix}.license_rules_snapshot_hash"))
    selected_ids = data.get("selected_license_rule_ids", [])
    if not selected_ids:
        issues.append(ValidationIssue("source_license_rule_selection_missing", "Publishable source requires at least one stable selected rule ID", f"{prefix}.selected_license_rule_ids"))
    for rule_id in selected_ids:
        if rule_id not in rules_by_id:
            issues.append(ValidationIssue("source_license_rule_unresolved", f"Selected license rule {rule_id!r} does not exist", f"{prefix}.selected_license_rule_ids"))

    registry_id = data.get("registry_source_id")
    canonical = canonical_source_rules()
    identities = canonical_source_identities()
    registry_config = load_json(SOURCE_REGISTRY_CONFIG_PATH)
    identity = data.get("registry_identity") if isinstance(data.get("registry_identity"), dict) else {}
    if registry_id == "synthetic_fixture":
        host = (urlparse(str(data.get("official_url", ""))).hostname or "").lower()
        if host != "example.org" or "fixture" not in str(data.get("id", "")):
            issues.append(ValidationIssue("synthetic_source_scope_invalid", "synthetic_fixture is limited to fixture IDs on example.org", f"{prefix}.registry_source_id"))
        expected_identity_base = {"canonical_name": data.get("publisher"), "canonical_official_host": host}
        expected_identity = {**expected_identity_base, "snapshot_hash": stable_json_hash(expected_identity_base)}
        if identity != expected_identity:
            issues.append(ValidationIssue("source_registry_identity_mismatch", "Synthetic fixture identity snapshot does not match publisher and official host", f"{prefix}.registry_identity"))
    elif registry_id not in canonical:
        issues.append(ValidationIssue("source_registry_unknown", f"Source registry ID {registry_id!r} is not in the verified canonical registry", f"{prefix}.registry_source_id"))
    else:
        expected_id = f"source:{registry_id}"
        if data.get("id") != expected_id:
            issues.append(ValidationIssue("source_registry_id_mismatch", f"Canonical registry source {registry_id!r} must use ID {expected_id}", f"{prefix}.id"))
        expected_rules = canonical[registry_id]
        selected_id_set = {
            rule_id for rule_id in selected_ids if isinstance(rule_id, str)
        }
        if set(rules_by_id) == selected_id_set:
            expected_snapshot_rules = [
                rule for rule in expected_rules if rule.get("rule_id") in selected_id_set
            ]
        else:
            expected_snapshot_rules = expected_rules
        expected_snapshot_hash = stable_json_hash(expected_snapshot_rules)
        if (
            len(expected_snapshot_rules) != len(rules)
            or expected_snapshot_hash != data.get("license_rules_snapshot_hash")
            or expected_snapshot_hash != stable_json_hash(rules)
        ):
            issues.append(ValidationIssue("canonical_source_rules_mismatch", "Release source rules do not match the verified canonical registry snapshot", f"{prefix}.license_rules_snapshot_hash"))
        if registry_id == "iucn_red_list":
            issues.append(ValidationIssue("iucn_public_redistribution_blocked", "Canonical IUCN rules prohibit static public redistribution; a future separately governed permission override is required", f"{prefix}.registry_source_id"))
        expected_identity_base = identities.get(str(registry_id), {})
        expected_identity = {
            **expected_identity_base,
            "snapshot_hash": source_registry_snapshot_hash or registry_config.get("source_matrix_snapshot_hash"),
        }
        official_host = (urlparse(str(data.get("official_url", ""))).hostname or "").lower()
        if (
            identity != expected_identity
            or data.get("publisher") != expected_identity_base.get("canonical_name")
            or official_host != expected_identity_base.get("canonical_official_host")
        ):
            issues.append(ValidationIssue("source_registry_identity_mismatch", "Source publisher/official host does not match the hashed canonical source identity registry", f"{prefix}.registry_identity"))

    terms_verified = parse_date(data.get("terms_verified_at"))
    reverify_by = parse_date(data.get("reverify_by"))
    issues.extend(governed_date_issues(data.get("accessed_at"), "accessed_at", prefix))
    issues.extend(governed_date_issues(data.get("terms_verified_at"), "terms_verified_at", prefix, stale=True))
    issues.extend(governed_date_issues(data.get("permission_verified_at"), "permission_verified_at", prefix, stale=data.get("permission_status") == "approved"))
    if reverify_by and reverify_by < date.today():
        issues.append(ValidationIssue("source_terms_stale", f"Source terms required reverification by {reverify_by.isoformat()}", f"{prefix}.reverify_by"))
    if terms_verified and reverify_by and (reverify_by - terms_verified).days > MAX_GOVERNANCE_REVIEW_AGE_DAYS:
        issues.append(ValidationIssue("source_reverification_window_too_long", f"Source reverification window exceeds {MAX_GOVERNANCE_REVIEW_AGE_DAYS} days", f"{prefix}.reverify_by"))

    expiry = parse_date(data.get("permission_expires_at"))
    if expiry and expiry < date.today():
        issues.append(ValidationIssue("source_permission_expired", f"Source permission expired on {expiry.isoformat()}", f"{prefix}.permission_expires_at"))
    if data.get("permission_status") == "approved":
        scope = data.get("permission_scope") or {}
        starts = parse_date(scope.get("starts_at"))
        if starts is None:
            issues.append(ValidationIssue("source_permission_start_missing", "Approved permission requires an effective date", f"{prefix}.permission_scope.starts_at"))
        elif starts > date.today():
            issues.append(ValidationIssue("source_permission_not_started", "Source permission has not started", f"{prefix}.permission_scope.starts_at"))
        if "github_pages" not in scope.get("platforms", []):
            issues.append(ValidationIssue("source_scope_missing_platform", "Permission does not cover GitHub Pages", f"{prefix}.permission_scope.platforms"))
        if "public_education" not in scope.get("purposes", []):
            issues.append(ValidationIssue("source_scope_missing_purpose", "Permission does not cover public education", f"{prefix}.permission_scope.purposes"))
        if "worldwide" not in scope.get("territories", []):
            issues.append(ValidationIssue("source_scope_missing_territory", "Permission does not cover worldwide public access", f"{prefix}.permission_scope.territories"))
        public_until = parse_date(release_public_until)
        if expiry and (public_until is None or public_until > expiry):
            issues.append(ValidationIssue("release_outlives_source_permission", "Release lifetime exceeds the source permission term", f"{prefix}.permission_expires_at"))
    return issues


def canonical_media_license_issues(data: dict[str, Any], prefix: str) -> list[ValidationIssue]:
    status = data.get("rights_status")
    descriptor = data.get("media_license") if isinstance(data.get("media_license"), dict) else {}
    identifier = str(descriptor.get("identifier", "")).upper()
    version = descriptor.get("version")
    url = str(descriptor.get("url", "")).rstrip("/")
    issues: list[ValidationIssue] = []
    patterns = {
        "cc0": (r"CC0-(1\.0)", "https://creativecommons.org/publicdomain/zero/{version}"),
        "cc_by": (r"CC-BY-(1\.0|2\.0|2\.5|3\.0|4\.0)", "https://creativecommons.org/licenses/by/{version}"),
        "cc_by_sa": (r"CC-BY-SA-(1\.0|2\.0|2\.5|3\.0|4\.0)", "https://creativecommons.org/licenses/by-sa/{version}"),
        "public_domain": (r"PDM-(1\.0)", "https://creativecommons.org/publicdomain/mark/{version}"),
    }
    specification = patterns.get(status)
    if specification:
        match = re.fullmatch(specification[0], identifier)
        if not match or version != match.group(1):
            issues.append(ValidationIssue("media_license_not_canonical", f"License identifier/version {identifier!r}/{version!r} is not a supported canonical pair", f"{prefix}.media_license"))
        else:
            expected_url = specification[1].format(version=version)
            if url != expected_url:
                issues.append(ValidationIssue("media_license_url_mismatch", f"License URL must be {expected_url}", f"{prefix}.media_license.url"))
    return issues


def media_publish_issues(
    data: dict[str, Any],
    prefix: str,
    release_public_until: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if data.get("rights_status") == "unknown":
        issues.append(ValidationIssue("unknown_rights_publish", "Media rights are unknown", f"{prefix}.rights_status"))
    if data.get("development_only") is True:
        issues.append(ValidationIssue("development_only_publish", "Development-only media cannot be published", f"{prefix}.development_only"))
    if data.get("allow_redistribution") is not True:
        issues.append(ValidationIssue("redistribution_not_allowed", "Media is not cleared for redistribution", f"{prefix}.allow_redistribution"))
    if data.get("rights_status") in {"restricted", "research_or_education_only"}:
        issues.append(ValidationIssue("rights_status_not_publishable", f"Rights status {data.get('rights_status')!r} is blocked by default", f"{prefix}.rights_status"))
    if data.get("review_status") != "verified":
        issues.append(ValidationIssue("media_not_verified", "Publishable media requires verified rights review", f"{prefix}.review_status"))
    if data.get("publish_status") not in {"publishable", "published"}:
        issues.append(ValidationIssue("media_publish_status_invalid", "Media publish_status is not publishable or published", f"{prefix}.publish_status"))
    if data.get("lifecycle_status") not in {"publishable", "published"}:
        issues.append(ValidationIssue("media_lifecycle_not_publishable", "Media lifecycle is not publishable or published", f"{prefix}.lifecycle_status"))
    if data.get("delivery_mode") == "self_hosted" and not data.get("content_hash"):
        issues.append(ValidationIssue("self_hosted_media_hash_missing", "Self-hosted media requires a content hash", f"{prefix}.content_hash"))
    if data.get("delivery_mode") == "self_hosted" and not data.get("storage_path"):
        issues.append(ValidationIssue("self_hosted_media_path_missing", "Self-hosted media requires a release-relative storage_path", f"{prefix}.storage_path"))
    if data.get("delivery_mode") in {"external_link", "iiif_external"} and data.get("cache_bytes") is not False:
        issues.append(ValidationIssue("external_media_cached", "External-link delivery cannot cache media bytes", f"{prefix}.cache_bytes"))
    if data.get("delivery_mode") in {"external_link", "iiif_external"} and data.get("storage_path") is not None:
        issues.append(ValidationIssue("external_media_storage_path", "External media cannot claim a local storage path", f"{prefix}.storage_path"))

    media_license = data.get("media_license")
    if not isinstance(media_license, dict):
        media_license = {}
    status = data.get("rights_status")
    identifier = str(media_license.get("identifier", "")).upper()
    expected_prefixes = {
        "public_domain": ("PDM-", "PUBLIC-DOMAIN"),
        "cc0": ("CC0-",),
        "cc_by": ("CC-BY-",),
        "cc_by_sa": ("CC-BY-SA-",),
    }
    prefixes = expected_prefixes.get(status)
    if prefixes and not identifier.startswith(prefixes):
        issues.append(ValidationIssue("media_license_mismatch", f"License {identifier!r} does not match rights_status {status!r}", f"{prefix}.media_license.identifier"))
    if status == "cc_by" and identifier.startswith("CC-BY-SA-"):
        issues.append(ValidationIssue("media_license_mismatch", "CC BY status cannot use a CC BY-SA identifier", f"{prefix}.media_license.identifier"))
    issues.extend(canonical_media_license_issues(data, prefix))
    permission_fields = {
        "allow_redistribution": "redistribution_allowed",
        "allow_modification": "modification_allowed",
        "allow_commercial_use": "commercial_use_allowed",
    }
    for outer, inner in permission_fields.items():
        if isinstance(media_license, dict) and data.get(outer) != media_license.get(inner):
            issues.append(ValidationIssue("media_license_permission_mismatch", f"{outer} disagrees with media_license.{inner}", f"{prefix}.{outer}"))
    if status in {"public_domain", "cc0", "cc_by", "cc_by_sa"} and not data.get("rights_statement_url"):
        issues.append(ValidationIssue("rights_statement_missing", "Open/public-domain media requires an object-level rights statement URL", f"{prefix}.rights_statement_url"))
    if not (data.get("rights_evidence") or {}).get("statement_snapshot_hash"):
        issues.append(ValidationIssue("rights_evidence_snapshot_missing", "Publishable media requires a hashed object-level rights-evidence snapshot", f"{prefix}.rights_evidence.statement_snapshot_hash"))
    issues.extend(governed_date_issues(data.get("reviewed_at"), "reviewed_at", prefix, stale=True))
    issues.extend(governed_date_issues((data.get("rights_evidence") or {}).get("verified_at"), "rights_evidence.verified_at", prefix, stale=True))

    scope = data.get("license_scope") or {}
    if status == "licensed":
        if scope.get("permission_status") != "approved":
            issues.append(ValidationIssue("license_scope_not_approved", "Licensed media permission is not approved", f"{prefix}.license_scope.permission_status"))
        if "github_pages" not in scope.get("platforms", []):
            issues.append(ValidationIssue("license_scope_missing_platform", "License does not cover GitHub Pages", f"{prefix}.license_scope.platforms"))
        if "public_education" not in scope.get("purposes", []):
            issues.append(ValidationIssue("license_scope_missing_purpose", "License does not cover public education", f"{prefix}.license_scope.purposes"))
        if "worldwide" not in scope.get("territories", []):
            issues.append(ValidationIssue("license_scope_missing_territory", "License does not cover worldwide access", f"{prefix}.license_scope.territories"))
        starts = parse_date(scope.get("starts_at"))
        if starts is None:
            issues.append(ValidationIssue("license_start_missing", "Licensed media requires an explicit effective date", f"{prefix}.license_scope.starts_at"))
        elif starts > date.today():
            issues.append(ValidationIssue("license_not_started", f"License starts on {starts.isoformat()}", f"{prefix}.license_scope.starts_at"))
        if scope.get("revoked_at") is not None:
            issues.append(ValidationIssue("license_revoked", "Licensed media has a revocation date", f"{prefix}.license_scope.revoked_at"))
        expiry = parse_date(scope.get("expires_at"))
        if expiry and expiry < date.today():
            issues.append(ValidationIssue("license_expired", f"Media license expired on {expiry.isoformat()}", f"{prefix}.license_scope.expires_at"))
        public_until = parse_date(release_public_until)
        if expiry and (public_until is None or public_until > expiry):
            issues.append(ValidationIssue("release_outlives_license", "Release lifetime exceeds the licensed media term", f"{prefix}.license_scope.expires_at"))

    if data.get("reuse_mode") == "adaptation":
        derivation = data.get("derivation") or {}
        if derivation.get("output_content_hash") != data.get("content_hash"):
            issues.append(ValidationIssue("derivation_hash_mismatch", "Derived output hash does not match the asset content hash", f"{prefix}.derivation.output_content_hash"))
        if status == "cc_by_sa" and (
            not re.fullmatch(r"CC-BY-SA-(1\.0|2\.0|2\.5|3\.0|4\.0)", str(derivation.get("output_license_identifier", "")).upper())
            or derivation.get("share_alike_compatibility_decision") != "compatible"
        ):
            issues.append(ValidationIssue("share_alike_not_satisfied", "Adapted CC BY-SA media must retain a compatible CC BY-SA output license", f"{prefix}.derivation"))
    return issues


def policy_issues(
    data: dict[str, Any],
    mode: str,
    prefix: str,
    source_registry_snapshot_hash: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    entity_type = data.get("entity_type")
    if entity_type == "artist" and data.get("lifecycle_status") in {"publishable", "published"}:
        if data.get("deceased_status") != "confirmed_deceased":
            issues.append(ValidationIssue("artist_not_confirmed_deceased", "A publishable artist must be confirmed deceased", f"{prefix}.deceased_status"))
    if entity_type == "relationship":
        if data.get("is_algorithmic") and data.get("relationship_type") in DIRECT_HISTORICAL_TYPES:
            issues.append(ValidationIssue("algorithmic_influence", "An algorithmic result cannot be stored as a direct historical relationship", f"{prefix}.relationship_type"))
        if data.get("public_display") and data.get("review_status") not in {"reviewed", "verified", "publishable", "published"}:
            issues.append(ValidationIssue("unreviewed_public_relationship", "A public relationship must be reviewed or beyond", f"{prefix}.review_status"))
        if data.get("branch_id") == "art" and data.get("source_entity_id") == data.get("target_entity_id"):
            issues.append(ValidationIssue("artist_self_relationship", "An artist relationship cannot connect an artist to itself", f"{prefix}.target_entity_id"))
        if mode == "publish":
            issues.extend(governed_date_issues(data.get("reviewed_at"), "reviewed_at", prefix, stale=True))
    if entity_type == "claim" and data.get("counter_evidence_ids") and (
        data.get("disputed") is not True or data.get("status") != "disputed"
    ):
        issues.append(ValidationIssue("counter_evidence_requires_disputed_status", "A claim with counter-evidence must enter the disputed workflow", f"{prefix}.counter_evidence_ids"))
    issues.extend(claim_transition_issues(data, prefix))
    if entity_type == "media_asset" and mode == "publish":
        issues.extend(media_publish_issues(data, prefix))
    if entity_type == "source" and mode == "publish":
        issues.extend(source_publish_issues(
            data,
            prefix,
            source_registry_snapshot_hash=source_registry_snapshot_hash,
        ))
    if data.get("public_animation_candidate") is True:
        animation = data.get("behavior_animation") or {}
        if not animation.get("animation_evidence_ids") or not animation.get("simplification_notes"):
            issues.append(ValidationIssue("biology_animation_evidence_missing", "A public behavior animation needs evidence IDs and simplification notes", f"{prefix}.behavior_animation"))
    return issues


def record_category(data: dict[str, Any]) -> str:
    entity_type = data.get("entity_type")
    if entity_type in {"relationship", "art_constellation_relationship"}:
        return "relationship"
    if entity_type in {"claim", "art_constellation_claim"}:
        return "claim"
    if entity_type in {"evidence", "art_constellation_evidence"}:
        return "evidence"
    if entity_type == "source":
        return "source"
    if entity_type == "media_asset":
        return "media"
    if entity_type == "dataset_release":
        return "release"
    return "entity"


def index_records(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
    indexed: dict[str, dict[str, Any]] = {}
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        data = record.get("data", {})
        record_id = data.get("id")
        if not isinstance(record_id, str):
            issues.append(ValidationIssue("record_id_missing", "Record ID must be a string", f"$.records[{index}].data.id"))
            continue
        if record_id in indexed:
            issues.append(ValidationIssue("duplicate_record_id", f"Duplicate record ID {record_id}", f"$.records[{index}].data.id"))
        else:
            indexed[record_id] = data
    return indexed, issues


def source_license_binding_issues(
    data: dict[str, Any],
    indexed: dict[str, dict[str, Any]],
    prefix: str,
) -> list[ValidationIssue]:
    entity_type = data.get("entity_type")
    if entity_type in {
        "source",
        "claim",
        "dataset_release",
        "formal_art_batch_manifest",
        "graph_input",
    }:
        return []
    is_media_contract = entity_type in {"media_asset", "media_eligibility_assessment"}
    expected_source_ids = [data.get("source_id")] if is_media_contract else list(data.get("source_ids", []))
    expected_source_ids = [item for item in expected_source_ids if isinstance(item, str)]
    bindings = [item for item in data.get("source_license_bindings", []) if isinstance(item, dict)]
    bound_source_ids = {item.get("source_id") for item in bindings}
    issues: list[ValidationIssue] = []
    if set(expected_source_ids) != bound_source_ids:
        issues.append(
            ValidationIssue(
                "source_license_binding_set_mismatch",
                f"License bindings must cover exactly the record sources; expected={sorted(expected_source_ids)}, actual={sorted(str(item) for item in bound_source_ids)}",
                f"{prefix}.source_license_bindings",
            )
        )
    for binding_index, binding in enumerate(bindings):
        binding_prefix = f"{prefix}.source_license_bindings[{binding_index}]"
        source = indexed.get(binding.get("source_id"), {})
        rules = {
            rule.get("rule_id"): rule
            for rule in source.get("license_rules", [])
            if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str)
        }
        rule = rules.get(binding.get("rule_id"))
        if source.get("entity_type") != "source":
            issues.append(ValidationIssue("source_license_binding_source_missing", "Binding source is absent", f"{binding_prefix}.source_id"))
            continue
        if rule is None:
            issues.append(ValidationIssue("source_license_binding_rule_missing", "Binding rule ID is absent from the source snapshot", f"{binding_prefix}.rule_id"))
            continue
        if binding.get("rule_id") not in source.get("selected_license_rule_ids", []):
            issues.append(ValidationIssue("source_license_binding_rule_not_selected", "Binding rule was not selected for this release source", f"{binding_prefix}.rule_id"))
        if binding.get("content_class") != rule.get("content_class"):
            issues.append(ValidationIssue("source_license_binding_class_mismatch", "Binding content_class does not match the selected rule", f"{binding_prefix}.content_class"))
        scope_locator = str(binding.get("scope_locator", ""))
        scope_fields = [str(item) for item in binding.get("scope_fields", [])]
        observed_scopes = [scope_locator]
        if (rule.get("scope_match") or {}).get("normalization") == "url_path_decode" and isinstance(data.get("locator"), dict):
            observed_scopes.extend(
                str(value)
                for value in data["locator"].values()
                if isinstance(value, str) and (value.startswith("/") or value.startswith("http://") or value.startswith("https://"))
            )
        if not observed_scopes or any(not source_rule_scope_matches(rule, item, scope_fields) for item in observed_scopes):
            issues.append(ValidationIssue("source_license_scope_mismatch", "Binding and machine-readable record locators must match the selected rule's executable scope contract", f"{binding_prefix}.scope_locator"))
        if is_media_contract:
            if binding.get("content_class") != "media":
                issues.append(ValidationIssue("media_source_rule_wrong_class", "Media must bind an object/media rule", f"{binding_prefix}.content_class"))
            if rule.get("redistribution") == "prohibited" or rule.get("rights_status") in {"restricted", "unknown", "not_applicable"}:
                issues.append(ValidationIssue("media_source_rule_not_publishable", "Bound media source rule blocks redistribution", f"{binding_prefix}.rule_id"))
            if rule.get("rights_status") != "mixed" and (
                rule.get("rights_status") != data.get("rights_status")
                or rule.get("identifier") != (data.get("media_license") or {}).get("identifier")
            ):
                issues.append(ValidationIssue("media_source_rule_license_mismatch", "Media rights/license must match the bound source media rule unless the rule is explicitly object-specific", f"{binding_prefix}.rule_id"))
            resolution = binding.get("permission_resolution")
            if resolution == "object_level":
                if rule.get("rights_status") != "mixed" or "conditional" not in {
                    rule.get("redistribution"), rule.get("modification"), rule.get("commercial_use")
                }:
                    issues.append(ValidationIssue("media_object_level_resolution_invalid", "object_level resolution is only valid for an explicitly mixed/conditional source rule", f"{binding_prefix}.permission_resolution"))
                permission_values = data.get("permissions", {}) if entity_type == "media_eligibility_assessment" else data
                for outer_field, rule_field in {
                    ("redistribution" if entity_type == "media_eligibility_assessment" else "allow_redistribution"): "redistribution",
                    ("modification" if entity_type == "media_eligibility_assessment" else "allow_modification"): "modification",
                    ("commercial_use" if entity_type == "media_eligibility_assessment" else "allow_commercial_use"): "commercial_use",
                }.items():
                    allowed = permission_values.get(outer_field) == ("allowed" if entity_type == "media_eligibility_assessment" else True)
                    if allowed and rule.get(rule_field) in {"prohibited", "unknown"}:
                        issues.append(ValidationIssue("media_source_rule_permission_mismatch", f"Object-level resolution cannot override {rule_field}={rule.get(rule_field)!r}", f"{binding_prefix}.rule_id"))
            else:
                if rule.get("rights_status") == "mixed":
                    issues.append(ValidationIssue("media_mixed_rule_requires_object_resolution", "A mixed media rule requires explicit object_level permission resolution", f"{binding_prefix}.permission_resolution"))
                permission_values = data.get("permissions", {}) if entity_type == "media_eligibility_assessment" else data
                for outer_field, rule_field in {
                    ("redistribution" if entity_type == "media_eligibility_assessment" else "allow_redistribution"): "redistribution",
                    ("modification" if entity_type == "media_eligibility_assessment" else "allow_modification"): "modification",
                    ("commercial_use" if entity_type == "media_eligibility_assessment" else "allow_commercial_use"): "commercial_use",
                }.items():
                    allowed = permission_values.get(outer_field) == ("allowed" if entity_type == "media_eligibility_assessment" else True)
                    if allowed and rule.get(rule_field) != "allowed":
                        issues.append(ValidationIssue("media_source_rule_permission_mismatch", f"{outer_field} exceeds bound rule permission {rule_field}={rule.get(rule_field)!r}", f"{binding_prefix}.rule_id"))
        else:
            if binding.get("permission_resolution") != "rule_direct":
                issues.append(ValidationIssue("factual_object_level_resolution_invalid", "Factual metadata/data bindings require direct rule permission", f"{binding_prefix}.permission_resolution"))
            if binding.get("content_class") not in {"metadata", "data"}:
                issues.append(ValidationIssue("factual_source_rule_wrong_class", "Factual records must bind metadata/data rules", f"{binding_prefix}.content_class"))
            if rule.get("redistribution") != "allowed" or rule.get("rights_status") in {"restricted", "unknown", "mixed", "not_applicable"}:
                issues.append(ValidationIssue("factual_source_rule_not_publishable", "Bound factual source rule does not unambiguously allow redistribution", f"{binding_prefix}.rule_id"))
    return issues


def require_reference_type(
    indexed: dict[str, dict[str, Any]],
    record_id: Any,
    expected_types: set[str],
    code: str,
    location: str,
) -> list[ValidationIssue]:
    target = indexed.get(record_id) if isinstance(record_id, str) else None
    if target is None:
        return [ValidationIssue(code, f"Referenced record {record_id!r} is absent", location)]
    if target.get("entity_type") not in expected_types:
        return [
            ValidationIssue(
                f"{code}_type",
                f"Referenced record {record_id!r} has type {target.get('entity_type')!r}; expected {sorted(expected_types)}",
                location,
            )
        ]
    return []


def reference_graph_issues(records: list[dict[str, Any]]) -> list[ValidationIssue]:
    indexed, issues = index_records(records)
    for index, record in enumerate(records):
        data = record.get("data", {})
        record_id = data.get("id")
        prefix = f"$.records[{index}].data"
        entity_type = data.get("entity_type")
        issues.extend(record_identity_issues(data, prefix))
        issues.extend(source_license_binding_issues(data, indexed, prefix))
        if entity_type in PUBLIC_CONSTELLATION_ENTITY_TYPES:
            # Public projection records have a purpose-built, fail-closed schema and
            # MUSEUM-04 semantic closure validator; common-entity fields are not inferred.
            continue
        if entity_type == "claim":
            support_ids = data.get("evidence_ids", [])
            counter_ids = data.get("counter_evidence_ids", [])
            for evidence_id in support_ids:
                evidence = indexed.get(evidence_id)
                if not evidence or evidence.get("entity_type") != "evidence":
                    issues.append(ValidationIssue("missing_evidence_reference", f"Claim references absent evidence {evidence_id}", f"{prefix}.evidence_ids"))
                    continue
                if record_id not in evidence.get("claim_ids", []):
                    issues.append(ValidationIssue("evidence_claim_backlink_missing", f"Evidence {evidence_id} does not link back to {record_id}", f"{prefix}.evidence_ids"))
                if evidence.get("stance") == "contradicts":
                    issues.append(ValidationIssue("evidence_stance_mismatch", f"Contradicting evidence {evidence_id} is in evidence_ids", f"{prefix}.evidence_ids"))
            for evidence_id in counter_ids:
                evidence = indexed.get(evidence_id)
                if not evidence or evidence.get("entity_type") != "evidence":
                    issues.append(ValidationIssue("missing_counter_evidence_reference", f"Claim references absent counter-evidence {evidence_id}", f"{prefix}.counter_evidence_ids"))
                    continue
                if record_id not in evidence.get("claim_ids", []):
                    issues.append(ValidationIssue("evidence_claim_backlink_missing", f"Counter-evidence {evidence_id} does not link back to {record_id}", f"{prefix}.counter_evidence_ids"))
                if evidence.get("stance") != "contradicts":
                    issues.append(ValidationIssue("counter_evidence_stance_mismatch", f"Counter-evidence {evidence_id} must contradict", f"{prefix}.counter_evidence_ids"))

            support_sources: list[dict[str, Any]] = []
            for evidence_id in support_ids:
                evidence = indexed.get(evidence_id, {})
                if evidence.get("stance") != "supports":
                    continue
                for source_id in evidence.get("source_ids", []):
                    source = indexed.get(source_id)
                    if source and source.get("entity_type") == "source":
                        support_sources.append(source)
            if data.get("status") in {"publishable", "published", "disputed"} and not any(
                indexed.get(evidence_id, {}).get("stance") == "supports" for evidence_id in support_ids
            ):
                issues.append(ValidationIssue("publishable_claim_requires_support", "A public claim needs at least one supporting Evidence record", f"{prefix}.evidence_ids"))
            if data.get("predicate") in HIGH_RISK_PREDICATES and not any(source.get("tier") in {1, 2} for source in support_sources):
                issues.append(ValidationIssue("high_risk_claim_requires_tier_1_or_2", "High-risk claim lacks Tier 1/2 supporting evidence", f"{prefix}.predicate"))
            if data.get("predicate") in COMPUTATIONAL_PREDICATES and not any(
                indexed.get(evidence_id, {}).get("evidence_kind") == "computational_result"
                for evidence_id in support_ids
                if indexed.get(evidence_id, {}).get("stance") == "supports"
            ):
                issues.append(ValidationIssue("computational_claim_requires_computation", "Computational similarity claims require supporting computational_result Evidence", f"{prefix}.evidence_ids"))

        if entity_type == "evidence":
            for claim_id in data.get("claim_ids", []):
                claim = indexed.get(claim_id)
                if not claim or claim.get("entity_type") != "claim":
                    issues.append(ValidationIssue("missing_claim_reference", f"Evidence references absent claim {claim_id}", f"{prefix}.claim_ids"))
                    continue
                expected_list = "counter_evidence_ids" if data.get("stance") == "contradicts" else "evidence_ids"
                if record_id not in claim.get(expected_list, []):
                    issues.append(ValidationIssue("claim_evidence_forward_link_missing", f"Claim {claim_id} does not reference evidence {record_id} in {expected_list}", f"{prefix}.claim_ids"))
                if data.get("evidence_kind") == "computational_result" and claim.get("predicate") not in COMPUTATIONAL_PREDICATES:
                    issues.append(ValidationIssue("computational_evidence_wrong_predicate", "Computational evidence may only support computational-similarity claims", f"{prefix}.evidence_kind"))
            for source_id in data.get("source_ids", []):
                if indexed.get(source_id, {}).get("entity_type") != "source":
                    issues.append(ValidationIssue("missing_source_reference", f"Evidence references absent source {source_id}", f"{prefix}.source_ids"))

        if entity_type == "relationship":
            for endpoint in ("source_entity_id", "target_entity_id"):
                if data.get(endpoint) not in indexed:
                    issues.append(ValidationIssue("missing_relationship_endpoint", f"Relationship endpoint {data.get(endpoint)} is absent", f"{prefix}.{endpoint}"))
            for context_id in data.get("context_entity_ids", []):
                if context_id not in indexed:
                    issues.append(ValidationIssue("missing_relationship_context", f"Relationship context {context_id} is absent", f"{prefix}.context_entity_ids"))
            for place_id in (data.get("place_scope") or {}).get("place_ids", []):
                issues.extend(require_reference_type(indexed, place_id, {"place"}, "missing_relationship_place", f"{prefix}.place_scope.place_ids"))
            if data.get("branch_id") == "art":
                issues.extend(require_reference_type(indexed, data.get("source_entity_id"), {"artist"}, "artist_relationship_source_invalid", f"{prefix}.source_entity_id"))
                relationship_type = data.get("relationship_type")
                target_types = ART_RELATION_TARGET_TYPES.get(str(relationship_type), {"artist"})
                issues.extend(require_reference_type(indexed, data.get("target_entity_id"), target_types, "artist_relationship_target_invalid", f"{prefix}.target_entity_id"))
                context_types = ART_RELATION_CONTEXT_TYPES.get(str(relationship_type))
                if context_types:
                    for context_id in data.get("context_entity_ids", []):
                        issues.extend(require_reference_type(indexed, context_id, context_types, "artist_relationship_context_invalid", f"{prefix}.context_entity_ids"))
            matching_relationship_claim = False
            for claim_id in data.get("claim_ids", []):
                if indexed.get(claim_id, {}).get("entity_type") != "claim":
                    issues.append(ValidationIssue("missing_relationship_claim", f"Relationship claim {claim_id} is absent", f"{prefix}.claim_ids"))
                    continue
                claim = indexed[claim_id]
                if (
                    claim.get("predicate") == data.get("relationship_type")
                    and claim.get("subject_id") == data.get("source_entity_id")
                    and (claim.get("object") or {}).get("entity_id") == data.get("target_entity_id")
                ):
                    matching_relationship_claim = True
            if data.get("claim_ids") and not matching_relationship_claim:
                issues.append(ValidationIssue("relationship_claim_semantics_mismatch", "No linked claim matches the relationship predicate and endpoints", f"{prefix}.claim_ids"))
            for source_id in data.get("source_ids", []):
                if indexed.get(source_id, {}).get("entity_type") != "source":
                    issues.append(ValidationIssue("missing_relationship_source", f"Relationship source {source_id} is absent", f"{prefix}.source_ids"))
            animation = data.get("behavior_animation") if isinstance(data.get("behavior_animation"), dict) else None
            if animation:
                for evidence_id in animation.get("animation_evidence_ids", []):
                    issues.extend(require_reference_type(indexed, evidence_id, {"evidence"}, "biology_animation_evidence_missing", f"{prefix}.behavior_animation.animation_evidence_ids"))

        if entity_type == "media_asset":
            if indexed.get(data.get("source_id"), {}).get("entity_type") != "source":
                issues.append(ValidationIssue("missing_media_source", f"Media source {data.get('source_id')} is absent", f"{prefix}.source_id"))
            derivation = data.get("derivation") if isinstance(data.get("derivation"), dict) else None
            if derivation:
                parent_id = derivation.get("derived_from_media_id")
                parent = indexed.get(parent_id, {})
                if parent.get("entity_type") != "media_asset":
                    issues.append(ValidationIssue("media_derivation_parent_missing", f"Derived media parent {parent_id!r} is absent", f"{prefix}.derivation.derived_from_media_id"))
                else:
                    if parent_id == record_id:
                        issues.append(ValidationIssue("media_derivation_self_reference", "A media asset cannot derive from itself", f"{prefix}.derivation.derived_from_media_id"))
                    if derivation.get("source_content_hash") != parent.get("content_hash"):
                        issues.append(ValidationIssue("media_derivation_source_hash_mismatch", "Derivation source hash does not match the parent asset", f"{prefix}.derivation.source_content_hash"))
                    if parent.get("allow_modification") is not True:
                        issues.append(ValidationIssue("media_derivation_parent_modification_blocked", "Parent media rights do not allow modification", f"{prefix}.derivation.derived_from_media_id"))
                    if parent.get("rights_status") == "cc_by_sa":
                        parent_identifier = (parent.get("media_license") or {}).get("identifier")
                        child_identifier = (data.get("media_license") or {}).get("identifier")
                        if derivation.get("output_license_identifier") != parent_identifier or child_identifier != parent_identifier:
                            issues.append(ValidationIssue("share_alike_version_mismatch", "CC BY-SA adaptation must retain the validated parent license version unless a future compatibility record explicitly permits another license", f"{prefix}.derivation.output_license_identifier"))

        if entity_type not in {"claim", "evidence", "source", "relationship", "media_asset", "dataset_release"}:
            for alias in data.get("aliases", []):
                claim_id = alias.get("source_claim_id") if isinstance(alias, dict) else None
                issues.extend(require_reference_type(indexed, claim_id, {"claim"}, "entity_alias_claim_missing", f"{prefix}.aliases"))
            for claim_id in data.get("claim_ids", []):
                if indexed.get(claim_id, {}).get("entity_type") != "claim":
                    issues.append(ValidationIssue("missing_entity_claim", f"Entity claim {claim_id} is absent", f"{prefix}.claim_ids"))
            for source_id in data.get("source_ids", []):
                if indexed.get(source_id, {}).get("entity_type") != "source":
                    issues.append(ValidationIssue("missing_entity_source", f"Entity source {source_id} is absent", f"{prefix}.source_ids"))
            if entity_type == "artist":
                life_dates = data.get("life_dates", {})
                required_claims = {
                    life_dates.get("birth", {}).get("claim_id"),
                    life_dates.get("death", {}).get("claim_id"),
                    *data.get("artwork_or_history_claim_ids", []),
                }
                if not (required_claims - {None}).issubset(set(data.get("claim_ids", []))):
                    issues.append(ValidationIssue("artist_required_claim_not_listed", "Life/work claims must also appear in artist.claim_ids", f"{prefix}.claim_ids"))
                for claim_id in required_claims - {None}:
                    if indexed.get(claim_id, {}).get("entity_type") != "claim":
                        issues.append(ValidationIssue("artist_life_or_work_claim_missing", f"Artist required claim {claim_id} is absent", prefix))
                life_sort_keys: dict[str, tuple[int, int, int]] = {}
                for life_field, predicates in {
                    "birth": {"birth_date", "birth_year", "birth_period"},
                    "death": {"death_date", "death_year", "death_period"},
                }.items():
                    life_value = life_dates.get(life_field, {})
                    claim = indexed.get(life_value.get("claim_id"), {})
                    claim_object = claim.get("object") if isinstance(claim.get("object"), dict) else {}
                    predicate = claim.get("predicate")
                    expected_datatype = (
                        "date" if predicate and predicate.endswith("_date")
                        else "string" if predicate and predicate.endswith("_period")
                        else "year"
                    )
                    sort_key = claim_temporal_sort_key(claim_object)
                    if sort_key is not None:
                        life_sort_keys[life_field] = sort_key
                    if (
                        claim.get("entity_type") != "claim"
                        or claim.get("subject_id") != record_id
                        or predicate not in predicates
                        or str(claim_object.get("value")) != str(life_value.get("display_value"))
                        or claim_object.get("datatype") != expected_datatype
                    ):
                        issues.append(
                            ValidationIssue(
                                "artist_life_claim_semantics_mismatch",
                                f"Artist {life_field} claim must match subject, controlled predicate, displayed value, and datatype",
                                f"{prefix}.life_dates.{life_field}",
                            )
                        )
                if {"birth", "death"}.issubset(life_sort_keys) and life_sort_keys["birth"] >= life_sort_keys["death"]:
                    issues.append(ValidationIssue("artist_life_dates_not_chronological", "Artist birth must be earlier than death", f"{prefix}.life_dates"))
                if life_sort_keys.get("death") and life_sort_keys["death"] > (date.today().year, date.today().month, date.today().day):
                    issues.append(ValidationIssue("artist_death_in_future", "A confirmed-deceased artist cannot have a future death date", f"{prefix}.life_dates.death"))
                allowed_work_predicates = {"has_verified_work_record", "documented_in_art_historical_record", "creator_of"}
                for claim_id in data.get("artwork_or_history_claim_ids", []):
                    claim = indexed.get(claim_id, {})
                    if claim.get("subject_id") != record_id or claim.get("predicate") not in allowed_work_predicates:
                        issues.append(ValidationIssue("artist_work_claim_semantics_mismatch", "Artist inclusion claim must describe a verified work or formal art-historical record for that artist", f"{prefix}.artwork_or_history_claim_ids"))
                        continue
                    support_sources = {
                        source_id
                        for evidence_id in claim.get("evidence_ids", [])
                        if indexed.get(evidence_id, {}).get("stance") == "supports"
                        for source_id in indexed.get(evidence_id, {}).get("source_ids", [])
                        if indexed.get(source_id, {}).get("tier") in {1, 2}
                    }
                    if not support_sources:
                        issues.append(ValidationIssue("artist_work_claim_requires_tier_1_or_2", "Artist inclusion work/history claim requires supporting Tier 1/2 evidence", f"{prefix}.artwork_or_history_claim_ids"))
            if entity_type == "artwork":
                for attribution in data.get("creator_attributions", []):
                    claim_id = attribution.get("claim_id")
                    claim = indexed.get(claim_id, {})
                    creator_id = attribution.get("creator_entity_id")
                    claim_object = claim.get("object") if isinstance(claim.get("object"), dict) else {}
                    attribution_type = attribution.get("attribution_type")
                    semantics_match = (
                        claim.get("entity_type") == "claim"
                        and claim.get("predicate") == "creator_attribution"
                        and claim.get("subject_id") == record_id
                    )
                    if creator_id is None:
                        semantics_match = semantics_match and claim_object.get("datatype") == "string" and claim_object.get("value") == attribution_type
                    else:
                        semantics_match = semantics_match and claim_object.get("entity_id") == creator_id
                    if not semantics_match:
                        issues.append(ValidationIssue("artwork_attribution_claim_invalid", f"Attribution claim {claim_id} does not match the artwork, creator, or controlled anonymous literal", f"{prefix}.creator_attributions"))
                    if creator_id is not None:
                        expected_creator_types = {"art_group", "organization"} if attribution_type == "collective" else {"artist"}
                        issues.extend(require_reference_type(indexed, creator_id, expected_creator_types, "artwork_creator_missing", f"{prefix}.creator_attributions"))
                issues.extend(require_reference_type(indexed, data.get("holding_institution_id"), {"museum_institution"}, "artwork_holding_institution_missing", f"{prefix}.holding_institution_id"))
                for material_id in data.get("material_ids", []):
                    issues.extend(require_reference_type(indexed, material_id, {"material"}, "artwork_material_missing", f"{prefix}.material_ids"))
                for technique_id in data.get("technique_ids", []):
                    issues.extend(require_reference_type(indexed, technique_id, {"technique"}, "artwork_technique_missing", f"{prefix}.technique_ids"))
                for media_id in data.get("media_asset_ids", []):
                    issues.extend(require_reference_type(indexed, media_id, {"media_asset"}, "artwork_media_missing", f"{prefix}.media_asset_ids"))
            if entity_type in {"taxon", "species"}:
                taxon_source_ids = {data.get("taxonomy_source_id")}
                issues.extend(require_reference_type(indexed, data.get("taxonomy_source_id"), {"source"}, "taxon_source_missing", f"{prefix}.taxonomy_source_id"))
                for assessment in data.get("conservation_assessments", []):
                    source_id = assessment.get("source_id") if isinstance(assessment, dict) else None
                    taxon_source_ids.add(source_id)
                    issues.extend(require_reference_type(indexed, source_id, {"source"}, "taxon_assessment_source_missing", f"{prefix}.conservation_assessments"))
                taxon_source_ids.discard(None)
                if not taxon_source_ids.issubset(set(data.get("source_ids", []))):
                    issues.append(ValidationIssue("taxon_source_binding_missing", "Taxonomy and conservation sources must appear in source_ids and therefore receive rule bindings", f"{prefix}.source_ids"))
    for media_id, media in indexed.items():
        if media.get("entity_type") != "media_asset":
            continue
        seen = {media_id}
        current = media
        while isinstance(current.get("derivation"), dict):
            parent_id = current["derivation"].get("derived_from_media_id")
            if parent_id in seen:
                issues.append(ValidationIssue("media_derivation_cycle", f"Media derivation cycle detected at {parent_id}", f"$.records[{media_id}].data.derivation"))
                break
            seen.add(parent_id)
            parent = indexed.get(parent_id)
            if not isinstance(parent, dict) or parent.get("entity_type") != "media_asset":
                break
            current = parent
    return issues


def record_is_publishable(data: dict[str, Any]) -> bool:
    category = record_category(data)
    if category == "claim":
        if data.get("status") in {"publishable", "published"} and data.get("publish_status") in {"publishable", "published"}:
            return True
        return data.get("status") == "disputed" and data.get("dispute_display") == "public_with_notice" and data.get("publish_status") == "disputed_public"
    if category == "relationship":
        return data.get("lifecycle_status") in {"publishable", "published"} and data.get("review_status") in {"publishable", "published"}
    if category == "evidence":
        return data.get("lifecycle_status") in {"publishable", "published"}
    if category == "source":
        return data.get("lifecycle_status") in {"publishable", "published"}
    if category == "media":
        return data.get("lifecycle_status") in {"publishable", "published"} and data.get("publish_status") in {"publishable", "published"} and data.get("review_status") == "verified"
    if data.get("review_status") is not None:
        return data.get("lifecycle_status") in {"publishable", "published"} and data.get("review_status") in {"publishable", "published"}
    return data.get("lifecycle_status") in {"publishable", "published"}


def release_bundle_issues(
    records: list[dict[str, Any]],
    release: dict[str, Any],
    *,
    require_publishable: bool = True,
    source_registry_snapshot_hash: str | None = None,
) -> list[ValidationIssue]:
    indexed, issues = index_records(records)
    target_schema_by_id: dict[str, str] = {}
    for index, record in enumerate(records):
        data = record.get("data", {})
        target_schema = record.get("target_schema")
        if isinstance(data, dict) and isinstance(target_schema, str):
            issues.extend(target_schema_binding_issues(target_schema, data, f"$.records[{index}]"))
            if isinstance(data.get("id"), str):
                target_schema_by_id[data["id"]] = target_schema
    issues.extend(reference_graph_issues(records))

    expected_by_category = {
        category: set(release.get(field, [])) for category, field in RELEASE_LISTS.items()
    }
    included_ids = set().union(*expected_by_category.values())
    withdrawal_ids = {item.get("id") for item in release.get("withdrawals", [])}
    deprecation_ids = {item.get("id") for item in release.get("deprecations", [])}
    for label, overlap in {
        "included/withdrawn": included_ids & withdrawal_ids,
        "included/deprecated": included_ids & deprecation_ids,
        "withdrawn/deprecated": withdrawal_ids & deprecation_ids,
    }.items():
        if overlap:
            issues.append(ValidationIssue("release_sets_not_disjoint", f"Release sets {label} overlap: {sorted(overlap)}", "$.data"))

    actual_ids = {record_id for record_id, data in indexed.items() if data.get("entity_type") != "dataset_release"}
    if actual_ids != included_ids:
        missing = sorted(included_ids - actual_ids)
        extra = sorted(actual_ids - included_ids)
        issues.append(ValidationIssue("release_record_set_mismatch", f"Release records do not exactly match included IDs; missing={missing}, extra={extra}", "$.data"))

    for category, expected_ids in expected_by_category.items():
        for record_id in expected_ids:
            data = indexed.get(record_id)
            if data is None:
                issues.append(ValidationIssue("release_record_missing", f"Included record {record_id} does not exist", f"$.data.{RELEASE_LISTS[category]}"))
                continue
            if record_category(data) != category:
                issues.append(ValidationIssue("release_record_type_mismatch", f"Record {record_id} belongs to {record_category(data)}, not {category}", f"$.data.{RELEASE_LISTS[category]}"))
            if require_publishable and not record_is_publishable(data):
                issues.append(ValidationIssue("release_record_not_publishable", f"Record {record_id} is not in an allowed publish state", f"$.data.{RELEASE_LISTS[category]}"))

    for claim_id in expected_by_category["claim"]:
        claim = indexed.get(claim_id, {})
        subject_id = claim.get("subject_id")
        if subject_id not in indexed:
            issues.append(ValidationIssue("claim_subject_missing", f"Claim {claim_id} subject {subject_id} is absent", f"$.records[{claim_id}].subject_id"))
        object_entity_id = (claim.get("object") or {}).get("entity_id") if isinstance(claim.get("object"), dict) else None
        if object_entity_id is not None and object_entity_id not in indexed:
            issues.append(ValidationIssue("claim_object_missing", f"Claim {claim_id} object {object_entity_id} is absent", f"$.records[{claim_id}].object.entity_id"))

    release_public_until = release.get("public_until")
    for source_id in expected_by_category["source"]:
        source = indexed.get(source_id)
        if source:
            issues.extend(source_publish_issues(
                source,
                f"$.records[{source_id}]",
                release_public_until,
                source_registry_snapshot_hash,
            ))
    for media_id in expected_by_category["media"]:
        media = indexed.get(media_id)
        if media:
            issues.extend(media_publish_issues(media, f"$.records[{media_id}]", release_public_until))

    data_manifest_ids: set[str] = set()
    media_manifest_ids: set[str] = set()
    manifest_by_path: dict[str, dict[str, Any]] = {}
    for manifest_file in release.get("manifest_files", []):
        path = manifest_file.get("path", "")
        if path in manifest_by_path:
            issues.append(ValidationIssue("duplicate_manifest_path", f"Manifest path {path!r} appears more than once", "$.data.manifest_files"))
        manifest_by_path[path] = manifest_file
        if manifest_file.get("record_type") == "data":
            record_ids = set(manifest_file.get("record_ids", []))
            data_manifest_ids.update(record_ids)
            schemas = {target_schema_by_id[item] for item in record_ids if item in target_schema_by_id}
            expected_schema_path = next(iter(schemas)) if len(schemas) == 1 else None
            if manifest_file.get("schema_path") != expected_schema_path:
                issues.append(ValidationIssue("manifest_schema_path_mismatch", f"Data file schema_path must be {expected_schema_path!r} for its record set", "$.data.manifest_files"))
        elif manifest_file.get("record_type") == "media":
            media_manifest_ids.update(manifest_file.get("record_ids", []))
            if not isinstance(manifest_file.get("bytes"), int) or manifest_file.get("bytes", 0) < 1:
                issues.append(ValidationIssue("self_hosted_media_empty", "A self-hosted media manifest must declare at least one byte", "$.data.manifest_files"))
        expected_artifact_schema = ARTIFACT_SCHEMAS.get(str(manifest_file.get("record_type")))
        if expected_artifact_schema and manifest_file.get("schema_path") != expected_artifact_schema:
            issues.append(ValidationIssue("artifact_schema_path_mismatch", f"{manifest_file.get('record_type')} must declare schema_path {expected_artifact_schema}", "$.data.manifest_files"))
    if data_manifest_ids != included_ids:
        issues.append(ValidationIssue("manifest_record_ids_mismatch", f"Data manifest record IDs do not equal release included IDs; missing={sorted(included_ids - data_manifest_ids)}, extra={sorted(data_manifest_ids - included_ids)}", "$.data.manifest_files"))

    self_hosted_media_ids = {
        media_id
        for media_id in expected_by_category["media"]
        if indexed.get(media_id, {}).get("delivery_mode") == "self_hosted"
    }
    if media_manifest_ids != self_hosted_media_ids:
        issues.append(ValidationIssue("media_manifest_ids_mismatch", f"Media byte manifests must equal self-hosted media IDs; expected={sorted(self_hosted_media_ids)}, actual={sorted(media_manifest_ids)}", "$.data.manifest_files"))
    for media_id in self_hosted_media_ids:
        matching = [item for item in release.get("manifest_files", []) if item.get("record_type") == "media" and media_id in item.get("record_ids", [])]
        if (
            len(matching) != 1
            or matching[0].get("path") != indexed.get(media_id, {}).get("storage_path")
            or matching[0].get("record_ids") != [media_id]
        ):
            issues.append(ValidationIssue("self_hosted_media_manifest_missing", f"Self-hosted media {media_id} must map exactly once to its storage_path", "$.data.manifest_files"))

    artifact_contracts = [
        ("source_registry_manifest", release.get("source_registry_manifest", {}), "source_registry"),
        ("license_decisions", {"path": release.get("license_decisions", {}).get("registry_path"), "sha256": release.get("license_decisions", {}).get("registry_sha256")}, "license_decisions"),
        ("third_party_notices_manifest", release.get("third_party_notices_manifest", {}), "third_party_notices"),
        ("attribution_manifest", release.get("attribution_manifest", {}), "attributions"),
    ]
    for field, artifact, expected_type in artifact_contracts:
        manifest_file = manifest_by_path.get(artifact.get("path"))
        if not manifest_file or manifest_file.get("sha256") != artifact.get("sha256") or manifest_file.get("record_type") != expected_type:
            issues.append(ValidationIssue("release_artifact_manifest_mismatch", f"{field} does not match a {expected_type} manifest file", f"$.data.{field}"))
    if set(release.get("attribution_manifest", {}).get("asset_ids", [])) != expected_by_category["media"]:
        issues.append(ValidationIssue("attribution_manifest_incomplete", "Attribution manifest asset IDs must equal included media IDs", "$.data.attribution_manifest.asset_ids"))

    required_notice_ids = expected_by_category["source"] | expected_by_category["media"]
    expected_artifact_ids = {
        "source_registry": expected_by_category["source"],
        "third_party_notices": required_notice_ids,
        "attributions": expected_by_category["media"],
    }
    decision_fields = release.get("license_decisions", {})
    referenced_decision_ids = {
        decision_fields.get("code_license_decision_id"),
        decision_fields.get("original_content_license_decision_id"),
    } - {None}
    expected_artifact_ids["license_decisions"] = referenced_decision_ids
    for record_type, expected_ids in expected_artifact_ids.items():
        matching = [item for item in release.get("manifest_files", []) if item.get("record_type") == record_type]
        actual_ids = set().union(*(set(item.get("record_ids", [])) for item in matching)) if matching else set()
        if actual_ids != expected_ids:
            issues.append(ValidationIssue("artifact_record_ids_mismatch", f"{record_type} manifest IDs must be {sorted(expected_ids)}, got {sorted(actual_ids)}", "$.data.manifest_files"))

    decisions = license_decision_registry()
    for subject, id_field, status_field in (
        ("code", "code_license_decision_id", "code_license_status"),
        ("original_content", "original_content_license_decision_id", "original_content_license_status"),
    ):
        decision_id = decision_fields.get(id_field)
        decision = decisions.get(decision_id)
        if not decision:
            issues.append(ValidationIssue("license_decision_unresolved", f"License decision {decision_id!r} is absent from the machine registry", f"$.data.license_decisions.{id_field}"))
            continue
        if decision.get("subject") != subject or decision.get("status") != decision_fields.get(status_field):
            issues.append(ValidationIssue("license_decision_mismatch", f"License decision {decision_id!r} does not match declared subject/status", f"$.data.license_decisions.{id_field}"))
        constraint = decision.get("scope_constraint") or {}
        pattern = constraint.get("release_id_pattern")
        if not isinstance(pattern, str) or re.fullmatch(pattern, str(release.get("id", ""))) is None:
            issues.append(ValidationIssue("license_decision_scope_mismatch", f"License decision {decision_id!r} does not cover release {release.get('id')!r}", f"$.data.license_decisions.{id_field}"))
        if constraint.get("release_kind") == "synthetic_fixture":
            non_fixture_ids = sorted(item for item in included_ids if "fixture" not in item)
            non_fixture_sources = sorted(
                source_id
                for source_id in expected_by_category["source"]
                if indexed.get(source_id, {}).get("registry_source_id") != "synthetic_fixture"
            )
            if "fixture" not in str(release.get("build_version", "")).lower() or non_fixture_ids or non_fixture_sources:
                issues.append(ValidationIssue("synthetic_license_decision_out_of_scope", f"Synthetic fixture decision cannot cover non-fixture build/records; record_ids={non_fixture_ids}, sources={non_fixture_sources}", f"$.data.license_decisions.{id_field}"))
        if release.get("public_release") and decision.get("status") not in {"decided", "not_applicable"}:
            issues.append(ValidationIssue("license_decision_not_closed", f"Public release cannot use {decision.get('status')!r} license decision {decision_id}", f"$.data.license_decisions.{id_field}"))

    manifest_versions = schema_manifest_versions()
    used_schema_paths = set(target_schema_by_id.values())
    used_schema_paths.update(
        item.get("schema_path")
        for item in release.get("manifest_files", [])
        if isinstance(item.get("schema_path"), str)
    )
    expected_schema_versions = {
        schema_version_key(path): manifest_versions[path]
        for path in used_schema_paths
        if path in manifest_versions
    }
    if release.get("schema_versions") != expected_schema_versions:
        issues.append(
            ValidationIssue(
                "release_schema_versions_mismatch",
                f"schema_versions must exactly match consumed schemas; expected={expected_schema_versions}, actual={release.get('schema_versions')}",
                "$.data.schema_versions",
            )
        )
    return issues


def fixture_paths(root: Path = FIXTURE_ROOT) -> list[Path]:
    return sorted(root.rglob("*.json"))


def validate_fixture(path: Path, environment: SchemaEnvironment) -> list[ValidationIssue]:
    fixture = load_json(path)
    mode = fixture.get("mode", "foundation")
    context = fixture.get("context", {})
    records = fixture.get("records")
    if records is None:
        records = [{"target_schema": fixture.get("target_schema"), "data": fixture.get("data")}]

    issues: list[ValidationIssue] = []
    releases: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        data = record.get("data")
        target_schema = record.get("target_schema")
        prefix = "$.data" if "records" not in fixture else f"$.records[{index}].data"
        if not isinstance(data, dict) or not isinstance(target_schema, str):
            issues.append(ValidationIssue("fixture_shape", "Each fixture record needs target_schema and object data", prefix))
            continue
        issues.extend(target_schema_binding_issues(target_schema, data, prefix))
        issues.extend(record_identity_issues(data, prefix))
        issues.extend(schema_issues(target_schema, data, environment, prefix))
        issues.extend(policy_issues(data, mode, prefix))
        if data.get("entity_type") == "dataset_release" and data.get("status") in {"publishable", "published"}:
            releases.append(data)

    if context.get("require_local_references"):
        issues.extend(reference_graph_issues(records))
    for release in releases:
        issues.extend(release_bundle_issues(records, release))
    return issues


def canonical_release_path(release_root: Path, relative: str) -> tuple[Path | None, str | None]:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        return None, "Path must be a non-empty POSIX relative path without backslashes or a drive/URI scheme"
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        return None, "Path must stay within the release root and contain no dot segments"
    root_resolved = release_root.resolve()
    candidate = (root_resolved / Path(*posix.parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None, "Resolved path escapes the release root"
    return candidate, None


def release_content_hash(manifest_files: list[dict[str, Any]]) -> str:
    lines = [f"{item['path']}\0{item['sha256']}\0{item['bytes']}\n" for item in sorted(manifest_files, key=lambda item: item["path"])]
    return "sha256:" + hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_release_directory(release_root: Path, environment: SchemaEnvironment) -> list[ValidationIssue]:
    release_root = release_root.resolve()
    manifest_path = release_root / "manifest.json"
    if not manifest_path.is_file():
        return [ValidationIssue("release_manifest_missing", f"Missing release manifest: {manifest_path}")]
    try:
        release = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [ValidationIssue("release_manifest_invalid", str(exc), str(manifest_path))]

    source_registry_snapshot_hash = RELEASE_SOURCE_MATRIX_SNAPSHOT_HASHES.get(release.get("id"))
    issues = schema_issues("schemas/common/dataset-release.schema.json", release, environment, "$.manifest")
    issues.extend(record_identity_issues(release, "$.manifest"))
    records: list[dict[str, Any]] = [{"target_schema": "schemas/common/dataset-release.schema.json", "data": release}]
    declared_paths = {
        item.get("path") for item in release.get("manifest_files", []) if isinstance(item.get("path"), str)
    }
    actual_paths = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    }
    expected_paths = {"manifest.json"} | declared_paths
    if actual_paths != expected_paths:
        issues.append(
            ValidationIssue(
                "release_file_set_mismatch",
                f"Release files must exactly match the manifest; missing={sorted(expected_paths - actual_paths)}, extra={sorted(actual_paths - expected_paths)}",
                str(release_root),
            )
        )

    parsed_artifacts: dict[str, Any] = {}
    for index, item in enumerate(release.get("manifest_files", [])):
        relative = item.get("path")
        path, error = canonical_release_path(release_root, relative)
        if error or path is None:
            issues.append(ValidationIssue("manifest_path_unsafe", error or "Unsafe path", f"$.manifest.manifest_files[{index}].path"))
            continue
        if not path.is_file():
            issues.append(ValidationIssue("manifest_file_missing", f"Manifest file does not exist: {relative}", f"$.manifest.manifest_files[{index}].path"))
            continue
        payload = path.read_bytes()
        actual_sha = hashlib.sha256(payload).hexdigest()
        if item.get("record_type") == "media" and not payload:
            issues.append(ValidationIssue("self_hosted_media_empty", "A self-hosted media file cannot be empty", f"$.manifest.manifest_files[{index}].path"))
        if len(payload) != item.get("bytes"):
            issues.append(ValidationIssue("manifest_size_mismatch", f"Expected {item.get('bytes')} bytes, got {len(payload)}", f"$.manifest.manifest_files[{index}].bytes"))
        if actual_sha != item.get("sha256"):
            issues.append(ValidationIssue("manifest_hash_mismatch", f"Expected {item.get('sha256')}, got {actual_sha}", f"$.manifest.manifest_files[{index}].sha256"))
        record_type = item.get("record_type")
        if record_type == "data":
            try:
                data_file = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                issues.append(ValidationIssue("release_data_invalid_json", str(exc), str(path)))
                continue
            file_records = data_file.get("records") if isinstance(data_file, dict) else None
            if not isinstance(file_records, list):
                issues.append(ValidationIssue("release_data_shape", "Data file must contain a records array", str(path)))
                continue
            actual_ids: set[str] = set()
            for record_index, record in enumerate(file_records):
                if not isinstance(record, dict) or not isinstance(record.get("target_schema"), str) or not isinstance(record.get("data"), dict):
                    issues.append(ValidationIssue("release_data_shape", "Each release record needs target_schema and object data", f"{path}:records[{record_index}]"))
                    continue
                record_id = record["data"].get("id")
                if not isinstance(record_id, str):
                    issues.append(ValidationIssue("release_record_id_invalid", "Physical release record ID must be a string", f"{path}:records[{record_index}].data.id"))
                else:
                    actual_ids.add(record_id)
                issues.extend(target_schema_binding_issues(record["target_schema"], record["data"], f"{path}:records[{record_index}]"))
                issues.extend(record_identity_issues(record["data"], f"{path}:records[{record_index}].data"))
                issues.extend(schema_issues(record["target_schema"], record["data"], environment, f"{path}:records[{record_index}].data"))
                issues.extend(policy_issues(
                    record["data"],
                    "publish",
                    f"{path}:records[{record_index}].data",
                    source_registry_snapshot_hash,
                ))
                records.append(record)
            if actual_ids != set(item.get("record_ids", [])):
                issues.append(ValidationIssue("manifest_file_record_ids_mismatch", f"Manifest IDs {sorted(item.get('record_ids', []))} do not match file IDs {sorted(actual_ids)}", f"$.manifest.manifest_files[{index}].record_ids"))
        elif record_type in ARTIFACT_SCHEMAS:
            try:
                artifact = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                issues.append(ValidationIssue("release_artifact_invalid_json", str(exc), str(path)))
                continue
            parsed_artifacts[str(relative)] = artifact
            expected_schema = ARTIFACT_SCHEMAS[record_type]
            if item.get("schema_path") != expected_schema:
                issues.append(ValidationIssue("artifact_schema_path_mismatch", f"{record_type} requires schema_path {expected_schema}", f"$.manifest.manifest_files[{index}].schema_path"))
            issues.extend(schema_issues(expected_schema, artifact, environment, str(path)))
            if record_type == "source_registry":
                artifact_ids = [entry.get("source_id") for entry in artifact.get("sources", []) if isinstance(entry, dict) and isinstance(entry.get("source_id"), str)]
            elif record_type == "license_decisions":
                artifact_ids = [entry.get("decision_id") for entry in artifact.get("decisions", []) if isinstance(entry, dict) and isinstance(entry.get("decision_id"), str)]
            elif record_type == "third_party_notices":
                artifact_ids = [entry.get("record_id") for entry in artifact.get("notices", []) if isinstance(entry, dict) and isinstance(entry.get("record_id"), str)]
            else:
                artifact_ids = [entry.get("asset_id") for entry in artifact.get("assets", []) if isinstance(entry, dict) and isinstance(entry.get("asset_id"), str)]
            actual_ids = set(artifact_ids)
            if len(artifact_ids) != len(actual_ids):
                issues.append(ValidationIssue("artifact_duplicate_record_id", f"{record_type} contains duplicate record IDs", str(path)))
            if actual_ids != set(item.get("record_ids", [])):
                issues.append(ValidationIssue("artifact_file_record_ids_mismatch", f"Manifest IDs {sorted(item.get('record_ids', []))} do not match artifact IDs {sorted(actual_ids)}", f"$.manifest.manifest_files[{index}].record_ids"))

    if release.get("content_hash") != release_content_hash(release.get("manifest_files", [])):
        issues.append(ValidationIssue("release_content_hash_mismatch", "Release content_hash does not match the manifest file set", "$.manifest.content_hash"))
    require_publishable = (
        release.get("status") in {"publishable", "published"}
        or release.get("public_release") is True
    )
    issues.extend(release_bundle_issues(
        records,
        release,
        require_publishable=require_publishable,
        source_registry_snapshot_hash=source_registry_snapshot_hash,
    ))

    indexed, _ = index_records(records)
    manifest_by_path = {item.get("path"): item for item in release.get("manifest_files", [])}
    for media_id in release.get("included_media_asset_ids", []):
        media = indexed.get(media_id, {})
        if media.get("delivery_mode") != "self_hosted":
            continue
        storage_path = media.get("storage_path")
        manifest_item = manifest_by_path.get(storage_path)
        if not manifest_item or manifest_item.get("record_type") != "media" or manifest_item.get("record_ids") != [media_id]:
            issues.append(ValidationIssue("self_hosted_media_file_unbound", f"Self-hosted media {media_id} has no exclusive physical manifest file", f"$.records[{media_id}].storage_path"))
        elif f"sha256:{manifest_item.get('sha256')}" != media.get("content_hash"):
            issues.append(ValidationIssue("self_hosted_media_content_hash_mismatch", f"Self-hosted media {media_id} content_hash does not match its physical file", f"$.records[{media_id}].content_hash"))

    source_ref = release.get("source_registry_manifest", {})
    source_snapshot = parsed_artifacts.get(source_ref.get("path"))
    if isinstance(source_snapshot, dict):
        snapshot_by_id = {item.get("source_id"): item for item in source_snapshot.get("sources", []) if isinstance(item, dict)}
        if set(snapshot_by_id) != set(release.get("included_source_ids", [])):
            issues.append(ValidationIssue("source_snapshot_set_mismatch", "Source snapshot must cover exactly all included sources", f"$.manifest.source_registry_manifest"))
        for source_id in release.get("included_source_ids", []):
            source = indexed.get(source_id, {})
            snapshot = snapshot_by_id.get(source_id, {})
            if (
                snapshot.get("registry_source_id") != source.get("registry_source_id")
                or snapshot.get("registry_identity") != source.get("registry_identity")
                or snapshot.get("license_rules_snapshot_hash") != source.get("license_rules_snapshot_hash")
                or stable_json_hash(snapshot.get("license_rules", [])) != source.get("license_rules_snapshot_hash")
            ):
                issues.append(ValidationIssue("source_snapshot_record_mismatch", f"Source snapshot does not close rules for {source_id}", f"$.manifest.source_registry_manifest"))

    decision_path = release.get("license_decisions", {}).get("registry_path")
    local_decisions = parsed_artifacts.get(decision_path)
    if isinstance(local_decisions, dict):
        local_by_id = {item.get("decision_id"): item for item in local_decisions.get("decisions", []) if isinstance(item, dict)}
        global_decisions = license_decision_registry()
        referenced = {
            release.get("license_decisions", {}).get("code_license_decision_id"),
            release.get("license_decisions", {}).get("original_content_license_decision_id"),
        } - {None}
        if set(local_by_id) != referenced:
            issues.append(ValidationIssue("license_decision_file_set_mismatch", "Physical decision registry must contain exactly the referenced decisions", str(decision_path)))
        for decision_id in referenced:
            if local_by_id.get(decision_id) != global_decisions.get(decision_id):
                issues.append(ValidationIssue("license_decision_file_mismatch", f"Physical decision {decision_id} differs from the governed registry", str(decision_path)))

    notice_ref = release.get("third_party_notices_manifest", {})
    notices = parsed_artifacts.get(notice_ref.get("path"))
    if isinstance(notices, dict):
        notice_by_id = {item.get("record_id"): item for item in notices.get("notices", []) if isinstance(item, dict)}
        used_rule_ids_by_source: dict[str, set[str]] = {}
        for record in indexed.values():
            for binding in record.get("source_license_bindings", []):
                if isinstance(binding, dict) and isinstance(binding.get("source_id"), str) and isinstance(binding.get("rule_id"), str):
                    used_rule_ids_by_source.setdefault(binding["source_id"], set()).add(binding["rule_id"])
        expected_notice_ids = set(release.get("included_source_ids", [])) | set(release.get("included_media_asset_ids", []))
        if set(notice_by_id) != expected_notice_ids:
            issues.append(ValidationIssue("third_party_notices_incomplete", "Notices must cover exactly all included Source and Media records", str(notice_ref.get("path"))))
        for record_id, notice in notice_by_id.items():
            record = indexed.get(record_id, {})
            if record.get("entity_type") == "media_asset":
                media_license = record.get("media_license") or {}
                expected_rule_ids = {binding.get("rule_id") for binding in record.get("source_license_bindings", []) if isinstance(binding, dict)}
                expected_attribution_texts = {record.get("attribution")} if media_license.get("attribution_required") else set()
                if (
                    notice.get("source_url") != record.get("source_object_url")
                    or set(notice.get("license_rule_ids", [])) != expected_rule_ids
                    or set(notice.get("license_identifiers", [])) != {media_license.get("identifier")}
                    or set(notice.get("attribution_texts", [])) != expected_attribution_texts
                    or notice.get("rights_holder") != record.get("rights_holder")
                ):
                    issues.append(ValidationIssue("third_party_notice_media_mismatch", f"Notice does not match media {record_id}", str(notice_ref.get("path"))))
            if record.get("entity_type") == "source":
                rules_by_id = {rule.get("rule_id"): rule for rule in record.get("license_rules", []) if isinstance(rule, dict)}
                used_rule_ids = used_rule_ids_by_source.get(record_id, set())
                used_identifiers = {rules_by_id[rule_id].get("identifier") for rule_id in used_rule_ids if rule_id in rules_by_id}
                attribution_texts = {rules_by_id[rule_id].get("attribution_template") for rule_id in used_rule_ids if rule_id in rules_by_id and rules_by_id[rule_id].get("attribution_template")}
                if (
                    notice.get("source_url") != record.get("official_url")
                    or not used_rule_ids
                    or set(notice.get("license_rule_ids", [])) != used_rule_ids
                    or set(notice.get("license_identifiers", [])) != used_identifiers
                    or set(notice.get("attribution_texts", [])) != attribution_texts
                    or notice.get("rights_holder") != record.get("publisher")
                ):
                    issues.append(ValidationIssue("third_party_notice_source_mismatch", f"Notice does not match source {record_id}", str(notice_ref.get("path"))))

    attribution_ref = release.get("attribution_manifest", {})
    attributions = parsed_artifacts.get(attribution_ref.get("path"))
    if isinstance(attributions, dict):
        attribution_by_id = {item.get("asset_id"): item for item in attributions.get("assets", []) if isinstance(item, dict)}
        expected_media_ids = set(release.get("included_media_asset_ids", []))
        if set(attribution_by_id) != expected_media_ids:
            issues.append(ValidationIssue("attribution_file_incomplete", "Attribution file must cover exactly all included media", str(attribution_ref.get("path"))))
        for media_id, attribution in attribution_by_id.items():
            media = indexed.get(media_id, {})
            media_license = media.get("media_license") or {}
            expected_changes = None if media.get("reuse_mode") == "verbatim" else (media.get("derivation") or {}).get("transform_recipe")
            if (
                attribution.get("attribution") != media.get("attribution")
                or attribution.get("license_identifier") != media_license.get("identifier")
                or attribution.get("license_url") != media_license.get("url")
                or attribution.get("source_url") != media.get("source_object_url")
                or attribution.get("changes_statement") != expected_changes
            ):
                issues.append(ValidationIssue("attribution_record_mismatch", f"Attribution does not match media {media_id}", str(attribution_ref.get("path"))))
    return issues


def run(root: Path = ROOT, verbose: bool = True) -> tuple[bool, dict[str, Any]]:
    try:
        environment = load_schema_environment(root)
    except Exception as exc:
        if verbose:
            print(f"[FAIL] schema bootstrap: {exc}")
        return False, {"schema_error": str(exc)}

    summary: dict[str, Any] = {
        "schemas": len(environment.by_path),
        "governance_registries": 0,
        "fixtures": 0,
        "expected_valid": 0,
        "expected_invalid": 0,
        "release_bundles": 0,
        "failures": [],
    }
    all_passed = True
    try:
        decision_document = load_json(root / "governance" / "license-decisions.json")
        decision_issues = schema_issues(
            "schemas/common/license-decision-registry.schema.json",
            decision_document,
            environment,
            "$.license_decisions",
        )
        decision_ids = [item.get("decision_id") for item in decision_document.get("decisions", []) if isinstance(item, dict)]
        if len(decision_ids) != len(set(decision_ids)):
            decision_issues.append(ValidationIssue("duplicate_license_decision_id", "License decision IDs must be unique", "$.license_decisions.decisions"))
    except (OSError, json.JSONDecodeError) as exc:
        decision_issues = [ValidationIssue("license_decision_registry_invalid", str(exc), "$.license_decisions")]
    summary["governance_registries"] = 1
    if decision_issues:
        all_passed = False
        summary["failures"].append({"registry": "governance/license-decisions.json", "issues": [issue.__dict__ for issue in decision_issues]})
        if verbose:
            for issue in decision_issues:
                print(f"[FAIL] governance/license-decisions.json {issue.code} {issue.location}: {issue.message}")
    elif verbose:
        print("[PASS] governance/license-decisions.json (machine decision registry)")
    fixture_root = root / "fixtures" / "governance"
    for path in fixture_paths(fixture_root):
        summary["fixtures"] += 1
        fixture = load_json(path)
        expected_valid = fixture.get("expected_valid") is True
        issues = validate_fixture(path, environment)
        actual_valid = not issues
        relative = path.relative_to(root).as_posix()
        expected_codes = set(fixture.get("expected_error_codes", []))
        actual_codes = {issue.code for issue in issues}
        passed = actual_valid == expected_valid and (expected_valid or expected_codes.issubset(actual_codes))
        all_passed &= passed
        summary["expected_valid" if expected_valid else "expected_invalid"] += 1
        if verbose:
            if passed:
                detail = "valid" if expected_valid else f"expected invalid: {', '.join(sorted(actual_codes))}"
                print(f"[PASS] {relative} ({detail})")
            else:
                print(f"[FAIL] {relative}: expected_valid={expected_valid}, actual_valid={actual_valid}")
                for issue in issues:
                    print(f"       {issue.code} {issue.location}: {issue.message}")
        if not passed:
            summary["failures"].append({"fixture": relative, "issues": [issue.__dict__ for issue in issues]})

    release_fixture_root = root / "fixtures" / "release-bundles" / "valid"
    if release_fixture_root.exists():
        for manifest in sorted(release_fixture_root.glob("*/manifest.json")):
            summary["release_bundles"] += 1
            issues = validate_release_directory(manifest.parent, environment)
            passed = not issues
            all_passed &= passed
            relative = manifest.parent.relative_to(root).as_posix()
            if verbose:
                print(f"[{'PASS' if passed else 'FAIL'}] {relative} (physical release bundle)")
                for issue in issues:
                    print(f"       {issue.code} {issue.location}: {issue.message}")
            if issues:
                summary["failures"].append({"release_bundle": relative, "issues": [issue.__dict__ for issue in issues]})

    if verbose:
        state = "PASS" if all_passed else "FAIL"
        print(
            f"[{state}] governance foundation: {summary['schemas']} schemas; "
            f"{summary['expected_valid']} valid fixtures; {summary['expected_invalid']} invalid fixtures; "
            f"{summary['release_bundles']} physical release bundle(s)"
        )
    return all_passed, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary")
    parser.add_argument("--release-root", action="append", type=Path, default=[], help="Additionally validate a physical release directory")
    args = parser.parse_args()
    passed, summary = run(verbose=not args.json)
    environment = load_schema_environment(ROOT)
    explicit_release_results: list[dict[str, Any]] = []
    for release_root in args.release_root:
        resolved = release_root if release_root.is_absolute() else ROOT / release_root
        issues = validate_release_directory(resolved, environment)
        passed &= not issues
        explicit_release_results.append({"path": str(resolved), "issues": [issue.__dict__ for issue in issues]})
        if not args.json:
            print(f"[{'PASS' if not issues else 'FAIL'}] explicit release {resolved}")
            for issue in issues:
                print(f"       {issue.code} {issue.location}: {issue.message}")
    if args.json:
        print(json.dumps({"status": "pass" if passed else "fail", **summary, "explicit_releases": explicit_release_results}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
