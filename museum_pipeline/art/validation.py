from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from museum_pipeline.art.identity import (
    DEFAULT_APPLICATION,
    DEFAULT_IDENTITY_BASIS,
    DEFAULT_OUTPUT,
    DEFAULT_SEED,
    SOURCE_RECORD_IDS,
    identity_basis_failures,
)
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import (
    canonical_source_rules,
    policy_issues,
    reference_graph_issues,
    stable_json_hash,
)


ARRAY_FILES = {
    "artists.json": "schemas/art/artist.schema.json",
    "identity-claims.json": "schemas/common/claim.schema.json",
    "identity-evidence.json": "schemas/common/evidence.schema.json",
    "review-signoffs.json": "schemas/art/batch/review-signoff.schema.json",
    "sources.json": "schemas/common/source.schema.json",
}


def validate_identity_stage(
    *,
    package_dir: Path = DEFAULT_OUTPUT,
    application_path: Path = DEFAULT_APPLICATION,
    seed_path: Path = DEFAULT_SEED,
    identity_basis_path: Path = DEFAULT_IDENTITY_BASIS,
    verify_raw_files: bool = False,
) -> dict[str, Any]:
    package_dir = _resolve_path(package_dir)
    application_path = _resolve_path(application_path)
    seed_path = _resolve_path(seed_path)
    identity_basis_path = _resolve_path(identity_basis_path)
    failures: list[str] = []
    records: dict[str, list[dict[str, Any]]] = {}
    environment = load_schema_environment()

    for filename, schema_path in ARRAY_FILES.items():
        values = _read_json(package_dir / filename, f"identity_file_json_invalid:{filename}", failures)
        if values is None:
            failures.append(f"identity_file_missing:{filename}")
            records[filename] = []
            continue
        if not isinstance(values, list):
            failures.append(f"identity_file_not_array:{filename}")
            records[filename] = []
            continue
        records[filename] = values
        validator = Draft202012Validator(
            environment.by_path[schema_path],
            registry=environment.registry,
            format_checker=FormatChecker(),
        )
        for index, value in enumerate(values):
            for error in validator.iter_errors(value):
                location = ".".join(str(part) for part in error.absolute_path)
                failures.append(f"schema:{filename}:{index}:{location}:{error.message}")

    application = _read_object(application_path, "selection_application_unreadable", failures)
    seed = _read_object(seed_path, "identity_seed_unreadable", failures)
    identity_basis = _read_object(identity_basis_path, "approved_identity_basis_unreadable", failures)
    snapshot_receipts = _read_object(
        package_dir / "snapshot-receipts.json",
        "snapshot_receipt_ledger_unreadable",
        failures,
    )

    if application.get("replacement_count") != 0 or application.get("replacements"):
        failures.append("auto_replacement_present")
    for issue in validate_record(application, environment=environment):
        failures.append(f"selection_application:{issue.code}:{issue.location}")
    for issue in validate_record(identity_basis, environment=environment):
        failures.append(f"approved_identity_basis:{issue.code}:{issue.location}")
    for issue in validate_record(snapshot_receipts, environment=environment):
        failures.append(f"snapshot_receipt_ledger:{issue.code}:{issue.location}")
    for failure in identity_basis_failures(seed, application, identity_basis):
        failures.append(f"approved_artist_identity_basis_mismatch:{failure}")

    expected_receipt_hash = canonical_sha256(
        {key: value for key, value in snapshot_receipts.items() if key != "content_hash"}
    )
    if snapshot_receipts.get("content_hash") != expected_receipt_hash:
        failures.append("snapshot_receipt_ledger_hash_mismatch")
    if snapshot_receipts.get("batch_id") != application.get("resulting_batch_id"):
        failures.append("snapshot_receipt_batch_mismatch")
    snapshot_by_id, snapshot_by_object = _validate_snapshot_receipts(
        snapshot_receipts,
        failures,
        verify_raw_files=verify_raw_files,
    )

    artists = records.get("artists.json", [])
    claims = records.get("identity-claims.json", [])
    evidence = records.get("identity-evidence.json", [])
    sources = records.get("sources.json", [])
    signoffs = records.get("review-signoffs.json", [])
    artist_by_id = _unique_index(artists, "artist", failures)
    claim_by_id = _unique_index(claims, "claim", failures)
    evidence_by_id = _unique_index(evidence, "evidence", failures)
    source_by_id = _unique_index(sources, "source", failures)
    signoff_by_id = _unique_index(signoffs, "review_signoff", failures)

    approved_ids = application.get("selected_candidate_ids", [])
    observed_approved = [
        item.get("branch_extensions", {}).get("approved_candidate_id")
        for item in artists
    ]
    if approved_ids != observed_approved or len(artists) != 12 or len(set(observed_approved)) != 12:
        failures.append("approved_artist_exact_order_mismatch")
    if len(signoffs) != 24:
        failures.append("review_signoff_count_mismatch")

    basis_by_artist = {
        item.get("artist_id"): item
        for item in identity_basis.get("bindings", [])
        if isinstance(item, dict)
    }
    seed_by_artist = {
        item.get("id"): item
        for item in seed.get("artists", [])
        if isinstance(item, dict)
    }

    canonical_rules = canonical_source_rules()
    registry_lineages: dict[str, list[str]] = {}
    for source in sources:
        source_id = str(source.get("id", "unknown"))
        registry_id = str(source.get("registry_source_id"))
        registry_lineages.setdefault(registry_id, []).append(source_id)
        expected_rules = canonical_rules.get(registry_id)
        if expected_rules is None or source.get("license_rules") != expected_rules:
            failures.append(f"source_canonical_rules_mismatch:{source_id}")
        if stable_json_hash(source.get("license_rules", [])) != source.get("license_rules_snapshot_hash"):
            failures.append(f"source_license_snapshot_hash_mismatch:{source_id}")
    for registry_id, source_ids in registry_lineages.items():
        if len(source_ids) > 1:
            failures.append(f"source_registry_lineage_duplicate:{registry_id}")

    signoff_owner: dict[str, str] = {}
    for artist in artists:
        artist_id = str(artist.get("id", "unknown"))
        branch = artist.get("branch_extensions", {})
        if artist.get("artist_kind") != "individual" or artist.get("identity_status") != "resolved":
            failures.append(f"artist_identity_unresolved:{artist_id}")
        if artist.get("deceased_status") != "confirmed_deceased":
            failures.append(f"artist_death_unresolved:{artist_id}")
        if artist.get("review_status") not in {"reviewed", "verified"}:
            failures.append(f"artist_not_reviewed:{artist_id}")
        if artist.get("review_status") in {"publishable", "published"} or artist.get("lifecycle_status") in {"publishable", "published"}:
            failures.append(f"artist_public_state_forbidden:{artist_id}")

        binding = basis_by_artist.get(artist_id)
        if binding is None:
            failures.append(f"approved_artist_identity_basis_mismatch:artist_missing:{artist_id}")
        else:
            observed_labels = {key: artist.get("labels", {}).get(key) for key in ("en", "zh-Hans")}
            if observed_labels != binding.get("approved_labels"):
                failures.append(f"approved_artist_identity_basis_mismatch:labels:{artist_id}")
            if artist.get("external_ids") != binding.get("external_ids"):
                failures.append(f"approved_artist_identity_basis_mismatch:external_ids:{artist_id}")
            if branch.get("approved_candidate_id") != binding.get("approved_candidate_id"):
                failures.append(f"approved_artist_identity_basis_mismatch:candidate:{artist_id}")

        artist_source_ids = artist.get("source_ids", [])
        if len(artist_source_ids) < 2:
            failures.append(f"artist_source_roles_missing:{artist_id}")
        artist_registry_ids: list[str] = []
        for source_id in artist_source_ids:
            source = source_by_id.get(source_id)
            if source is None:
                failures.append(f"artist_source_missing:{artist_id}:{source_id}")
            else:
                artist_registry_ids.append(str(source.get("registry_source_id")))
        if len(artist_registry_ids) != len(set(artist_registry_ids)):
            failures.append(f"artist_source_lineage_duplicate:{artist_id}")
        if len(set(artist_registry_ids)) < 2:
            failures.append(f"artist_source_independence_missing:{artist_id}")

        authority_ids = branch.get("authority_source_ids", [])
        if not authority_ids:
            failures.append(f"artist_authority_source_missing:{artist_id}")
        for source_id in authority_ids:
            source = source_by_id.get(source_id)
            if source is None:
                failures.append(f"artist_authority_source_missing:{artist_id}:{source_id}")
            elif source.get("source_type") != "authority_file":
                failures.append(f"artist_authority_source_role_invalid:{artist_id}:{source_id}")
            if source_id not in artist_source_ids:
                failures.append(f"artist_authority_source_not_bound:{artist_id}:{source_id}")

        artist_claim_ids = artist.get("claim_ids", [])
        for claim_id in artist_claim_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None:
                failures.append(f"artist_claim_missing:{artist_id}:{claim_id}")
            elif claim.get("subject_id") != artist_id:
                failures.append(f"artist_claim_scope_mismatch:{artist_id}:{claim_id}")
        work_ids = artist.get("artwork_or_history_claim_ids", [])
        if not work_ids:
            failures.append(f"artist_work_history_missing:{artist_id}")
        for claim_id in work_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None or claim.get("subject_id") != artist_id or claim.get("predicate") != "has_verified_work_record":
                failures.append(f"artist_work_history_missing:{artist_id}:{claim_id}")
        if artist.get("at_least_one_verified_work_or_record") is not True:
            failures.append(f"artist_verified_work_flag_missing:{artist_id}")

        nested_claim_ids = _validate_nested_artist_claims(artist, claim_by_id, failures)
        external_claim_ids = _validate_external_id_claims(artist, claim_by_id, failures)
        required_by_role = {
            "identity_reviewer": {
                artist_id,
                artist.get("life_dates", {}).get("birth", {}).get("claim_id"),
                artist.get("life_dates", {}).get("death", {}).get("claim_id"),
                *nested_claim_ids["name"],
                *external_claim_ids,
            },
            "art_history_reviewer": {
                artist_id,
                artist.get("life_dates", {}).get("death", {}).get("claim_id"),
                *work_ids,
                *nested_claim_ids["activity"],
                *nested_claim_ids["period"],
                *nested_claim_ids["tradition"],
            },
        }
        required_by_role = {
            role: {record_id for record_id in record_ids if isinstance(record_id, str)}
            for role, record_ids in required_by_role.items()
        }

        roles: dict[str, dict[str, Any]] = {}
        linked_signoffs: list[dict[str, Any]] = []
        linked_ids = branch.get("review_signoff_ids", [])
        if len(linked_ids) != 2:
            failures.append(f"artist_review_signoff_set_invalid:{artist_id}")
        for signoff_id in linked_ids:
            signoff = signoff_by_id.get(signoff_id)
            if signoff is None:
                failures.append(f"artist_signoff_missing:{artist_id}:{signoff_id}")
                continue
            prior_owner = signoff_owner.setdefault(signoff_id, artist_id)
            if prior_owner != artist_id:
                failures.append(f"artist_signoff_scope_mismatch:{artist_id}:{signoff_id}")
            linked_signoffs.append(signoff)
            role = str(signoff.get("review_role"))
            roles[role] = signoff
            record_ids = set(signoff.get("record_ids", []))
            if artist_id not in record_ids:
                failures.append(f"artist_signoff_scope_mismatch:{artist_id}:{signoff_id}")
            for record_id in record_ids:
                claim = claim_by_id.get(record_id)
                if claim is not None and claim.get("subject_id") != artist_id:
                    failures.append(f"artist_signoff_scope_mismatch:{artist_id}:{signoff_id}:{record_id}")
            expected_scope = required_by_role.get(role)
            if expected_scope is None or not expected_scope <= record_ids:
                failures.append(f"artist_signoff_required_scope_missing:{artist_id}:{role}")
            accepted = signoff.get("decision") in {"accepted_reviewed", "accepted_verified"}
            failure_free = not any(item.get("result") == "fail" for item in signoff.get("checklist", []))
            if not accepted or not failure_free:
                failures.append(f"artist_signoff_not_accepted:{artist_id}:{signoff_id}")
        if set(roles) != {"identity_reviewer", "art_history_reviewer"}:
            failures.append(f"artist_review_roles_missing:{artist_id}")
        elif (
            roles["identity_reviewer"].get("reviewed_at") == roles["art_history_reviewer"].get("reviewed_at")
            or roles["identity_reviewer"].get("checklist") == roles["art_history_reviewer"].get("checklist")
        ):
            failures.append(f"artist_review_roles_not_separated:{artist_id}")
        if artist.get("review_status") == "verified" and not any(
            signoff.get("reviewer_kind") == "human" and signoff.get("decision") == "accepted_verified"
            for signoff in linked_signoffs
        ):
            failures.append(f"artist_verified_without_human_signoff:{artist_id}")

        _validate_seed_conflicts(
            artist,
            seed_by_artist.get(artist_id, {}),
            claim_by_id,
            failures,
        )

    for claim in claims:
        claim_id = str(claim.get("id", "unknown"))
        if claim.get("subject_id") not in artist_by_id:
            failures.append(f"claim_subject_missing:{claim_id}")
        for evidence_id in [*claim.get("evidence_ids", []), *claim.get("counter_evidence_ids", [])]:
            if evidence_id not in evidence_by_id:
                failures.append(f"claim_evidence_missing:{claim_id}:{evidence_id}")
        if claim.get("status") in {"publishable", "published"} or claim.get("publish_status") not in {"not_public", "blocked"}:
            failures.append(f"claim_public_state_forbidden:{claim_id}")

    for item in evidence:
        evidence_id = str(item.get("id", "unknown"))
        for claim_id in item.get("claim_ids", []):
            claim = claim_by_id.get(claim_id)
            if claim is None:
                failures.append(f"evidence_claim_missing:{evidence_id}:{claim_id}")
            elif item.get("stance") == "contradicts" and evidence_id not in claim.get("counter_evidence_ids", []):
                failures.append(f"evidence_counter_backlink_missing:{evidence_id}:{claim_id}")
            elif item.get("stance") != "contradicts" and evidence_id not in claim.get("evidence_ids", []):
                failures.append(f"evidence_support_backlink_missing:{evidence_id}:{claim_id}")
        for source_id in item.get("source_ids", []):
            if source_id not in source_by_id:
                failures.append(f"evidence_source_missing:{evidence_id}:{source_id}")
        binding_source_ids = {binding.get("source_id") for binding in item.get("source_license_bindings", [])}
        if binding_source_ids != set(item.get("source_ids", [])):
            failures.append(f"evidence_source_binding_mismatch:{evidence_id}")
        raw_refs = item.get("raw_snapshot_refs", [])
        if not raw_refs:
            failures.append(f"evidence_raw_locator_missing:{evidence_id}")
        for raw_ref in raw_refs:
            snapshot_id = raw_ref.get("snapshot_id")
            entry = snapshot_by_id.get(snapshot_id)
            if entry is None:
                failures.append(f"evidence_snapshot_missing:{evidence_id}:{snapshot_id}")
                continue
            if raw_ref.get("body_sha256") != entry.get("body_sha256"):
                failures.append(f"evidence_snapshot_hash_mismatch:{evidence_id}:{snapshot_id}")
            source_object_id = str(raw_ref.get("source_object_id"))
            if source_object_id not in entry.get("source_object_ids", []):
                failures.append(f"evidence_snapshot_object_mismatch:{evidence_id}:{snapshot_id}")
            expected_source_record = SOURCE_RECORD_IDS.get(str(entry.get("source_id")))
            if expected_source_record not in item.get("source_ids", []):
                failures.append(f"evidence_snapshot_source_mismatch:{evidence_id}:{snapshot_id}")
            if snapshot_by_object.get((str(entry.get("source_id")), source_object_id)) is not entry:
                failures.append(f"evidence_snapshot_object_index_mismatch:{evidence_id}:{snapshot_id}")
        if item.get("lifecycle_status") in {"publishable", "published"}:
            failures.append(f"evidence_public_state_forbidden:{evidence_id}")

    known_record_ids = set(artist_by_id) | set(claim_by_id) | set(evidence_by_id) | set(source_by_id) | set(signoff_by_id)
    for signoff in signoffs:
        signoff_id = str(signoff.get("id", "unknown"))
        if signoff.get("reviewer_kind") != "human" and signoff.get("decision") == "accepted_verified":
            failures.append(f"ai_signoff_cannot_verify:{signoff_id}")
        if signoff.get("decision") not in {"accepted_reviewed", "accepted_verified"}:
            failures.append(f"signoff_not_accepted:{signoff_id}")
        if any(item.get("result") == "fail" for item in signoff.get("checklist", [])):
            failures.append(f"signoff_check_failed:{signoff_id}")
        for record_id in signoff.get("record_ids", []):
            if record_id not in known_record_ids:
                failures.append(f"signoff_record_missing:{signoff_id}:{record_id}")

    wrapped_records = [
        {"data": record}
        for collection in records.values()
        for record in collection
    ]
    for issue in reference_graph_issues(wrapped_records):
        failures.append(f"governance:{issue.code}:{issue.location}")
    for index, wrapper in enumerate(wrapped_records):
        for issue in policy_issues(wrapper["data"], "review", f"$.records[{index}].data"):
            failures.append(f"governance:{issue.code}:{issue.location}")

    return {
        "ok": not failures,
        "artist_count": len(artists),
        "claim_count": len(claims),
        "evidence_count": len(evidence),
        "source_count": len(sources),
        "review_signoff_count": len(signoffs),
        "snapshot_receipt_count": len(snapshot_receipts.get("entries", [])),
        "failures": sorted(set(failures)),
        "package_dir": package_dir.relative_to(ROOT).as_posix() if package_dir.is_relative_to(ROOT) else str(package_dir),
    }


def _validate_snapshot_receipts(
    ledger: dict[str, Any],
    failures: list[str],
    *,
    verify_raw_files: bool,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    by_snapshot: dict[str, dict[str, Any]] = {}
    by_object: dict[tuple[str, str], dict[str, Any]] = {}
    receipt_ids: set[str] = set()
    for entry in ledger.get("entries", []):
        receipt_id = entry.get("receipt_id")
        snapshot_id = entry.get("snapshot_id")
        if receipt_id in receipt_ids:
            failures.append(f"snapshot_receipt_duplicate:{receipt_id}")
        receipt_ids.add(receipt_id)
        if snapshot_id in by_snapshot:
            failures.append(f"snapshot_id_duplicate:{snapshot_id}")
        else:
            by_snapshot[snapshot_id] = entry
        source_id = str(entry.get("source_id"))
        for source_object_id in entry.get("source_object_ids", []):
            key = (source_id, str(source_object_id))
            if key in by_object:
                failures.append(f"snapshot_object_duplicate:{source_id}:{source_object_id}")
            else:
                by_object[key] = entry
        if verify_raw_files:
            _verify_tracked_raw_file(entry, failures)
    return by_snapshot, by_object


def _verify_tracked_raw_file(entry: dict[str, Any], failures: list[str]) -> None:
    snapshot_id = str(entry.get("snapshot_id", "unknown"))
    for field in ("raw_receipt_path", "raw_body_path"):
        value = entry.get(field)
        if not isinstance(value, str):
            failures.append(f"snapshot_raw_path_invalid:{snapshot_id}:{field}")
            continue
        path = (ROOT / value).resolve()
        if not path.is_relative_to(ROOT) or path.is_symlink() or not path.is_file():
            failures.append(f"snapshot_raw_file_missing:{snapshot_id}:{field}")
    body_value = entry.get("raw_body_path")
    if not isinstance(body_value, str):
        return
    body_path = (ROOT / body_value).resolve()
    if not body_path.is_relative_to(ROOT) or not body_path.is_file() or body_path.is_symlink():
        return
    body = body_path.read_bytes()
    observed_hash = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if observed_hash != entry.get("body_sha256"):
        failures.append(f"snapshot_raw_hash_mismatch:{snapshot_id}")
    if len(body) != entry.get("body_bytes"):
        failures.append(f"snapshot_raw_bytes_mismatch:{snapshot_id}")


def _validate_nested_artist_claims(
    artist: dict[str, Any],
    claim_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> dict[str, set[str]]:
    artist_id = str(artist.get("id", "unknown"))
    branch = artist.get("branch_extensions", {})
    groups = {
        "name": (branch.get("name_records", []), "source_claim_id", "identity_profile"),
        "activity": (branch.get("activity_places", []), "claim_id", "activity_scope"),
        "period": (branch.get("historical_periods", []), "claim_id", "historical_period"),
        "tradition": (branch.get("artistic_traditions", []), "claim_id", "artistic_tradition"),
    }
    result: dict[str, set[str]] = {key: set() for key in groups}
    for group, (values, key, predicate) in groups.items():
        for value in values:
            claim_id = value.get(key)
            if isinstance(claim_id, str):
                result[group].add(claim_id)
            claim = claim_by_id.get(claim_id)
            if claim is None:
                failures.append(f"artist_nested_claim_missing:{artist_id}:{group}:{claim_id}")
            elif claim.get("subject_id") != artist_id or claim.get("predicate") != predicate:
                failures.append(f"artist_nested_claim_semantics_invalid:{artist_id}:{group}:{claim_id}")
            if claim_id not in artist.get("claim_ids", []):
                failures.append(f"artist_nested_claim_not_bound:{artist_id}:{group}:{claim_id}")
    return result


def _validate_external_id_claims(
    artist: dict[str, Any],
    claim_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> set[str]:
    artist_id = str(artist.get("id", "unknown"))
    external_ids = artist.get("external_ids", {})
    expected_values = {
        f"https://id.loc.gov/authorities/names/{external_ids.get('loc')}",
        f"https://www.wikidata.org/wiki/{external_ids.get('wikidata')}",
    }
    found: set[str] = set()
    for claim_id in artist.get("claim_ids", []):
        claim = claim_by_id.get(claim_id, {})
        if claim.get("predicate") == "identity_same_as" and claim.get("object", {}).get("value") in expected_values:
            found.add(claim_id)
    found_values = {
        claim_by_id[claim_id].get("object", {}).get("value")
        for claim_id in found
    }
    for value in expected_values - found_values:
        failures.append(f"artist_external_id_claim_missing:{artist_id}:{value}")
    return found


def _validate_seed_conflicts(
    artist: dict[str, Any],
    decision: dict[str, Any],
    claim_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    artist_id = str(artist.get("id", "unknown"))
    if not decision:
        failures.append(f"identity_seed_artist_missing:{artist_id}")
        return
    for field in ("birth", "death"):
        projected = artist.get("life_dates", {}).get(field, {})
        expected = decision.get(field, {})
        if projected.get("display_value") != expected.get("display_value") or projected.get("precision") != expected.get("precision"):
            failures.append(f"identity_life_projection_mismatch:{artist_id}:{field}")
        claim_id = projected.get("claim_id")
        claim = claim_by_id.get(claim_id, {})
        if expected.get("precision") == "uncertain" and claim.get("object", {}).get("precision") != "uncertain":
            failures.append(f"identity_approximate_precision_inflated:{artist_id}:{field}")
        if decision.get(f"{field}_counterevidence"):
            if claim.get("status") != "disputed" or not claim.get("counter_evidence_ids"):
                failures.append(f"identity_competing_claim_missing:{artist_id}:{field}")
    resolution = decision.get("external_id_resolution")
    if resolution:
        accepted = resolution.get("accepted_wikidata")
        if artist.get("external_ids", {}).get("wikidata") != accepted:
            failures.append(f"identity_external_resolution_mismatch:{artist_id}")
        expected_uri = f"https://www.wikidata.org/wiki/{accepted}"
        crosswalk = next(
            (
                claim
                for claim in claim_by_id.values()
                if claim.get("subject_id") == artist_id
                and claim.get("predicate") == "identity_same_as"
                and claim.get("object", {}).get("value") == expected_uri
            ),
            {},
        )
        if crosswalk.get("status") != "disputed" or not crosswalk.get("counter_evidence_ids"):
            failures.append(f"identity_external_conflict_not_quarantined:{artist_id}")


def _read_json(path: Path, invalid_code: str, failures: list[str]) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        failures.append(invalid_code)
        return None


def _read_object(path: Path, invalid_code: str, failures: list[str]) -> dict[str, Any]:
    value = _read_json(path, invalid_code, failures)
    if not isinstance(value, dict):
        if value is not None:
            failures.append(invalid_code)
        return {}
    return value


def _resolve_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _unique_index(records: list[dict[str, Any]], label: str, failures: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            failures.append(f"{label}_id_missing")
        elif record_id in result:
            failures.append(f"{label}_id_duplicate:{record_id}")
        else:
            result[record_id] = record
    return result
