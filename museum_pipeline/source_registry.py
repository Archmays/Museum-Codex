from __future__ import annotations

import ipaddress
import json
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from museum_pipeline.config import (
    ENDPOINT_REGISTRY_PATH,
    LICENSE_RULES_PATH,
    ROOT,
    SOURCE_MATRIX_PATH,
    endpoint_registry,
    license_rules_snapshot_hash,
    source_configuration,
    source_license_rules,
    source_matrix_ids,
    source_registry_snapshot_hash,
)
from museum_pipeline.hashing import sha256_file


REFERENCE_SOURCE_IDS = {"wikidata", "getty_ulan", "met_open_access", "aic_api"}


def verify_sources() -> dict[str, object]:
    issues: list[str] = []
    registry = endpoint_registry()
    if registry.get("network_default_enabled") is not False:
        issues.append("network_default_not_disabled")
    registered = {item.get("source_id") for item in registry.get("sources", []) if isinstance(item, dict)}
    if registered != REFERENCE_SOURCE_IDS:
        issues.append("reference_source_set_mismatch")
    matrix_ids = source_matrix_ids()
    for source_id in sorted(REFERENCE_SOURCE_IDS):
        if source_id not in matrix_ids:
            issues.append(f"source_matrix_missing:{source_id}")
            continue
        config = source_configuration(source_id)
        template = str(config.get("endpoint_template", ""))
        parsed = urlsplit(template.format(object_id="1" if source_id != "wikidata" else "Q1"))
        if parsed.scheme != "https" or parsed.hostname not in config.get("allowed_hosts", []):
            issues.append(f"endpoint_allowlist_mismatch:{source_id}")
        if set(config.get("allowed_redirect_hosts", [])) - set(config.get("allowed_hosts", [])):
            issues.append(f"redirect_allowlist_wider_than_endpoint:{source_id}")
        for host in config.get("allowed_hosts", []):
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                ip = None
            if host in {"localhost", "localhost.localdomain"} or ip and (ip.is_private or ip.is_loopback or ip.is_link_local):
                issues.append(f"private_host_registered:{source_id}")
        try:
            verified = date.fromisoformat(config["terms_verified_at"])
            if verified > date.today() or date.today() - verified > timedelta(days=366):
                issues.append(f"terms_verification_invalid:{source_id}")
        except (KeyError, ValueError):
            issues.append(f"terms_verification_invalid:{source_id}")
        rules = source_license_rules(source_id)
        if not rules or any(rule.get("no_inheritance") is not True for rule in rules):
            issues.append(f"license_rules_invalid:{source_id}")
    aic = source_configuration("aic_api").get("query_profiles", {})
    if "description" in aic.get("default", []) or "description" not in aic.get("description", []):
        issues.append("aic_profile_license_boundary_invalid")
    minimum = json.loads((ROOT / "research" / "source-registry" / "minimum-source-set.json").read_text(encoding="utf-8"))
    if minimum.get("license_rules_snapshot_hash") != license_rules_snapshot_hash():
        issues.append("canonical_license_rules_hash_mismatch")
    if minimum.get("source_matrix_snapshot_hash") != sha256_file(SOURCE_MATRIX_PATH):
        issues.append("canonical_source_matrix_hash_mismatch")
    return {
        "ok": not issues,
        "issues": sorted(issues),
        "reference_sources": sorted(REFERENCE_SOURCE_IDS),
        "endpoint_registry_path": ENDPOINT_REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "endpoint_registry_snapshot_hash": source_registry_snapshot_hash(),
        "license_rules_path": LICENSE_RULES_PATH.relative_to(ROOT).as_posix(),
        "license_rules_snapshot_hash": license_rules_snapshot_hash(),
    }
