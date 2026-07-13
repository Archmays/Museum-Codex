from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from museum_pipeline.config import (
    ROOT,
    source_configuration,
    source_license_rules,
    source_registry_snapshot_hash,
)
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.validation.dispatch import validate_record


DEFAULT_SEED = ROOT / "research" / "art" / "museum-03b-identity-decisions.json"
DEFAULT_IDENTITY_BASIS = ROOT / "research" / "art" / "museum-03b-approved-identity-basis.json"
DEFAULT_SNAPSHOT_RECEIPTS = ROOT / "research" / "art" / "museum-03b-snapshot-receipts.json"
DEFAULT_APPLICATION = ROOT / "governance" / "decisions" / "museum-03b-selection-application.json"
DEFAULT_OUTPUT = ROOT / "data" / "reviewed" / "art" / "museum-03b" / "museum-03b-first-slate-v1"

SOURCE_RECORD_IDS = {
    "getty_ulan": "source:getty_ulan",
    "met_open_access": "source:met_open_access",
    "aic_api": "source:aic_api",
    "wikidata": "source:wikidata",
}

SOURCE_DETAILS = {
    "getty_ulan": {
        "name": "Getty Vocabularies / ULAN",
        "official_url": "https://vocab.getty.edu/ulan/",
        "host": "vocab.getty.edu",
        "source_type": "authority_file",
        "public_static_redistribution": "allowed",
        "risk": "Identity authority data does not independently prove artwork attribution or historical influence.",
    },
    "met_open_access": {
        "name": "The Metropolitan Museum of Art Open Access",
        "official_url": "https://collectionapi.metmuseum.org/public/collection/v1/",
        "host": "collectionapi.metmuseum.org",
        "source_type": "official_collection",
        "public_static_redistribution": "conditional",
        "risk": "Collection metadata is CC0; media permission remains object-level and is not inherited from image URLs.",
    },
    "aic_api": {
        "name": "Art Institute of Chicago API",
        "official_url": "https://api.artic.edu/docs/",
        "host": "api.artic.edu",
        "source_type": "official_collection",
        "public_static_redistribution": "conditional",
        "risk": "Artwork description is field-specific CC BY; this stage binds only the registered non-description data rule.",
    },
    "wikidata": {
        "name": "Wikidata",
        "official_url": "https://www.wikidata.org/wiki/Wikidata:Data_access",
        "host": "www.wikidata.org",
        "source_type": "open_encyclopedia",
        "public_static_redistribution": "allowed",
        "risk": "Tier 3 discovery source; it cannot independently establish death, authorship, or influence.",
    },
}


def build_identity_stage(
    *,
    seed_path: Path = DEFAULT_SEED,
    identity_basis_path: Path = DEFAULT_IDENTITY_BASIS,
    snapshot_receipts_path: Path = DEFAULT_SNAPSHOT_RECEIPTS,
    application_path: Path = DEFAULT_APPLICATION,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    if not output_dir.is_absolute():
        output_dir = (ROOT / output_dir).resolve()
    seed = _load_json(seed_path)
    identity_basis = _load_json(identity_basis_path)
    snapshot_receipts = _load_json(snapshot_receipts_path)
    application = _load_json(application_path)
    decisions = seed.get("artists", [])
    selected_ids = application.get("selected_candidate_ids", [])
    decision_ids = [item.get("approved_candidate_id") for item in decisions]
    if application.get("entity_type") != "selection_decision_application":
        raise PipelineError("selection_application_invalid", "Identity build requires the committed decision application")
    if application.get("replacement_count") != 0 or application.get("replacements"):
        raise PipelineError("auto_replacement_forbidden", "Identity build requires replacement_count=0")
    application_issues = validate_record(application)
    if application_issues:
        codes = ", ".join(sorted({issue.code for issue in application_issues}))
        raise PipelineError("selection_application_invalid", f"Committed decision application failed canonical validation: {codes}")
    basis_issues = validate_record(identity_basis)
    if basis_issues:
        codes = ", ".join(sorted({issue.code for issue in basis_issues}))
        raise PipelineError("approved_identity_basis_invalid", f"Approved identity basis failed canonical validation: {codes}")
    basis_failures = identity_basis_failures(seed, application, identity_basis)
    if basis_failures:
        raise PipelineError("approved_artist_identity_basis_mismatch", "; ".join(basis_failures))
    receipt_issues = validate_record(snapshot_receipts)
    if receipt_issues:
        codes = ", ".join(sorted({issue.code for issue in receipt_issues}))
        raise PipelineError("snapshot_receipt_ledger_invalid", f"Snapshot receipt ledger failed canonical validation: {codes}")
    expected_receipt_hash = canonical_sha256({key: value for key, value in snapshot_receipts.items() if key != "content_hash"})
    if snapshot_receipts.get("content_hash") != expected_receipt_hash:
        raise PipelineError("snapshot_receipt_ledger_hash_mismatch", "Snapshot receipt ledger content hash is invalid")
    snapshot_index = _snapshot_index(snapshot_receipts)
    if selected_ids != decision_ids or len(selected_ids) != 12 or len(set(selected_ids)) != 12:
        raise PipelineError("approved_artist_closure_mismatch", "Identity decisions must match the exact ordered approved slate")
    if application.get("resulting_batch_id") != seed.get("batch_id"):
        raise PipelineError("batch_id_mismatch", "Identity seed and decision application batch IDs differ")

    required_sources = {"getty_ulan", "met_open_access", "aic_api"}
    if any(item.get("external_ids", {}).get("wikidata") for item in decisions):
        required_sources.add("wikidata")
    sources = [_source_record(source_id) for source_id in sorted(required_sources)]
    artists: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    signoffs: list[dict[str, Any]] = []
    for decision in decisions:
        generated = _artist_records(seed, decision, snapshot_index)
        artists.append(generated["artist"])
        claims.extend(generated["claims"])
        evidence.extend(generated["evidence"])
        signoffs.extend(generated["signoffs"])

    outputs = {
        "artists.json": artists,
        "identity-claims.json": claims,
        "identity-evidence.json": evidence,
        "review-signoffs.json": signoffs,
        "sources.json": sources,
        "snapshot-receipts.json": snapshot_receipts,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-03b-identity-stage-", dir=output_dir.parent) as temporary:
        staging_dir = Path(temporary)
        for name, payload in outputs.items():
            _atomic_write_text(staging_dir / name, _pretty_json(payload))
        from museum_pipeline.art.validation import validate_identity_stage

        staged_result = validate_identity_stage(
            package_dir=staging_dir,
            application_path=application_path,
            seed_path=seed_path,
            identity_basis_path=identity_basis_path,
        )
        if not staged_result["ok"]:
            raise PipelineError(
                "identity_stage_validation_failed",
                "; ".join(staged_result["failures"]),
            )

    serialized_outputs = {name: _pretty_json(payload) for name, payload in outputs.items()}
    conflicts = [
        output_dir / name
        for name, serialized in serialized_outputs.items()
        if (output_dir / name).exists()
        and (output_dir / name).read_text(encoding="utf-8") != serialized
    ]
    if conflicts:
        raise PipelineError(
            "reviewed_identity_conflict",
            f"Refusing to overwrite different reviewed file: {conflicts[0]}",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    reused: list[str] = []
    for name, serialized in serialized_outputs.items():
        path = output_dir / name
        if path.exists():
            reused.append(name)
            continue
        _atomic_write_text(path, serialized)
        written.append(name)
    return {
        "ok": True,
        "output_dir": output_dir.relative_to(ROOT).as_posix() if output_dir.is_relative_to(ROOT) else str(output_dir),
        "artist_count": len(artists),
        "claim_count": len(claims),
        "evidence_count": len(evidence),
        "source_count": len(sources),
        "review_signoff_count": len(signoffs),
        "snapshot_receipt_count": len(snapshot_receipts["entries"]),
        "written": written,
        "reused": reused,
        "summary": "reviewed identity stage built without media or published promotion",
    }


def identity_basis_failures(
    seed: dict[str, Any],
    application: dict[str, Any],
    identity_basis: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    expected_content_hash = canonical_sha256({key: value for key, value in identity_basis.items() if key != "content_hash"})
    if identity_basis.get("content_hash") != expected_content_hash:
        failures.append("basis_content_hash_mismatch")
    if identity_basis.get("decision_application_id") != application.get("id"):
        failures.append("basis_application_id_mismatch")
    if identity_basis.get("application_basis_hash") != application.get("application_basis_hash"):
        failures.append("basis_application_hash_mismatch")
    if identity_basis.get("input_bundle_hash") != application.get("input_bundle_hash"):
        failures.append("basis_input_bundle_hash_mismatch")

    bindings = identity_basis.get("bindings", [])
    decisions = seed.get("artists", [])
    if len(bindings) != 12 or len(decisions) != 12:
        failures.append("basis_artist_count_mismatch")
        return failures
    application_labels = {
        item.get("candidate_id"): item.get("labels")
        for item in application.get("resolved_artists", [])
    }
    application_hashes = {
        item.get("candidate_id"): item.get("canonical_hash")
        for item in application.get("candidate_input_hashes", [])
    }
    for index, (binding, decision) in enumerate(zip(bindings, decisions, strict=True)):
        candidate_id = binding.get("approved_candidate_id")
        if candidate_id != decision.get("approved_candidate_id"):
            failures.append(f"basis_candidate_mismatch:{index}")
        if application_labels.get(candidate_id) != binding.get("approved_labels"):
            failures.append(f"basis_approved_labels_mismatch:{candidate_id}")
        if application_hashes.get(candidate_id) != binding.get("candidate_input_hash"):
            failures.append(f"basis_candidate_hash_mismatch:{candidate_id}")
        if decision.get("id") != binding.get("artist_id"):
            failures.append(f"basis_artist_id_mismatch:{candidate_id}")
        observed_labels = {key: decision.get("labels", {}).get(key) for key in ("en", "zh-Hans")}
        if observed_labels != binding.get("approved_labels"):
            failures.append(f"basis_seed_labels_mismatch:{candidate_id}")
        if decision.get("external_ids") != binding.get("external_ids"):
            failures.append(f"basis_external_ids_mismatch:{candidate_id}")
    return failures


def _snapshot_index(snapshot_receipts: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    seen_receipt_ids: set[str] = set()
    seen_snapshot_ids: set[str] = set()
    for entry in snapshot_receipts.get("entries", []):
        receipt_id = entry.get("receipt_id")
        snapshot_id = entry.get("snapshot_id")
        if receipt_id in seen_receipt_ids:
            raise PipelineError("snapshot_receipt_duplicate", f"Duplicate receipt ID: {receipt_id}")
        if snapshot_id in seen_snapshot_ids:
            raise PipelineError("snapshot_receipt_duplicate", f"Duplicate snapshot ID: {snapshot_id}")
        seen_receipt_ids.add(receipt_id)
        seen_snapshot_ids.add(snapshot_id)
        source_id = str(entry.get("source_id"))
        for source_object_id in entry.get("source_object_ids", []):
            key = (source_id, str(source_object_id))
            if key in result:
                raise PipelineError(
                    "snapshot_receipt_object_duplicate",
                    f"Multiple receipts bind {source_id}/{source_object_id}",
                )
            result[key] = entry
    return result


def _snapshot_for(
    snapshot_index: dict[tuple[str, str], dict[str, Any]],
    source_key: str,
    source_object_id: str,
    *,
    expected_sha256: str | None = None,
    expected_snapshot_id: str | None = None,
) -> dict[str, str]:
    entry = snapshot_index.get((source_key, str(source_object_id)))
    if entry is None:
        raise PipelineError(
            "snapshot_receipt_missing",
            f"No verified snapshot receipt for {source_key}/{source_object_id}",
        )
    if expected_sha256 is not None and entry.get("body_sha256") != expected_sha256:
        raise PipelineError(
            "snapshot_receipt_hash_mismatch",
            f"Snapshot hash differs for {source_key}/{source_object_id}",
        )
    if expected_snapshot_id is not None and entry.get("snapshot_id") != expected_snapshot_id:
        raise PipelineError(
            "snapshot_receipt_id_mismatch",
            f"Snapshot ID differs for {source_key}/{source_object_id}",
        )
    verification = entry.get("verification", {})
    if not all(verification.get(key) is True for key in ("body_present", "hash_match", "byte_count_match")):
        raise PipelineError(
            "snapshot_receipt_unverified",
            f"Snapshot receipt is not fully verified for {source_key}/{source_object_id}",
        )
    return {
        "snapshot_id": entry["snapshot_id"],
        "body_sha256": entry["body_sha256"],
    }


def _artist_records(
    seed: dict[str, Any],
    decision: dict[str, Any],
    snapshot_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    artist_id = decision["id"]
    slug = artist_id.split(":", 1)[1]
    timestamp = seed["reviewed_at"]
    reviewer = seed["reviewer_id"]
    getty_source_id = SOURCE_RECORD_IDS["getty_ulan"]
    collection_source_key = decision["collection_record"]["source_id"]
    collection = decision["collection_record"]
    external_ids = decision["external_ids"]
    getty_snapshot = _snapshot_for(
        snapshot_index,
        "getty_ulan",
        external_ids["ulan"],
        expected_sha256=decision["getty_snapshot"]["body_sha256"],
        expected_snapshot_id=decision["getty_snapshot"]["snapshot_id"],
    )
    collection_snapshot = _snapshot_for(
        snapshot_index,
        collection_source_key,
        str(collection["object_id"]),
        expected_sha256=collection["body_sha256"],
    )

    profile_claim_id = f"claim:{slug}-identity-profile"
    birth_claim_id = f"claim:{slug}-birth"
    death_claim_id = f"claim:{slug}-death"
    work_claim_id = f"claim:{slug}-official-record"
    activity_claim_id = f"claim:{slug}-activity-scope"
    period_claim_id = f"claim:{slug}-historical-period"
    tradition_claim_id = f"claim:{slug}-artistic-tradition"
    loc_claim_id = f"claim:{slug}-loc-crosswalk"
    wikidata_claim_id = f"claim:{slug}-wikidata-crosswalk"
    profile_evidence_id = f"evidence:{slug}-ulan-profile"
    birth_evidence_id = f"evidence:{slug}-ulan-birth"
    death_evidence_id = f"evidence:{slug}-ulan-death"
    work_evidence_id = f"evidence:{slug}-collection-record"
    context_evidence_id = f"evidence:{slug}-context-classification"
    loc_evidence_id = f"evidence:{slug}-loc-crosswalk"

    profile_evidence = _evidence_record(
        evidence_id=profile_evidence_id,
        claim_ids=[profile_claim_id],
        source_key="getty_ulan",
        source_object_id=external_ids["ulan"],
        snapshot=getty_snapshot,
        raw_locator="/identified_by",
        summary="The exact ULAN record supplies controlled names, roles, authority links, and identity context.",
        extracted_at=timestamp,
    )
    birth_evidence = _evidence_record(
        evidence_id=birth_evidence_id,
        claim_ids=[birth_claim_id],
        source_key="getty_ulan",
        source_object_id=external_ids["ulan"],
        snapshot=getty_snapshot,
        raw_locator="/born/timespan",
        summary="The exact ULAN record supplies the reviewed birth observation at the recorded precision.",
        extracted_at=timestamp,
    )
    death_evidence = _evidence_record(
        evidence_id=death_evidence_id,
        claim_ids=[death_claim_id],
        source_key="getty_ulan",
        source_object_id=external_ids["ulan"],
        snapshot=getty_snapshot,
        raw_locator="/died/timespan",
        summary="The exact ULAN record supplies the reviewed death observation and confirms the person is deceased.",
        extracted_at=timestamp,
    )
    work_evidence = _evidence_record(
        evidence_id=work_evidence_id,
        claim_ids=[work_claim_id],
        source_key=collection_source_key,
        source_object_id=collection["object_id"],
        snapshot=collection_snapshot,
        raw_locator="/artistDisplayName" if collection_source_key == "met_open_access" else "/data/artist_title",
        summary=f"The official collection record identifies {collection['title']} as a record associated with the approved artist identity; attribution is reviewed separately in the artwork wave.",
        extracted_at=timestamp,
        locator_url=collection["url"],
    )
    context_evidence = _curatorial_evidence_record(
        evidence_id=context_evidence_id,
        claim_ids=[activity_claim_id, period_claim_id, tradition_claim_id],
        source_refs=[
            {
                "source_key": "getty_ulan",
                "source_object_id": external_ids["ulan"],
                "snapshot": getty_snapshot,
                "raw_locators": ["/carried_out", "/classified_as"],
            },
            {
                "source_key": collection_source_key,
                "source_object_id": str(collection["object_id"]),
                "snapshot": collection_snapshot,
                "raw_locators": ["/medium", "/classification"] if collection_source_key == "met_open_access" else ["/data/medium_display"],
            },
        ],
        summary=(
            "Project-reviewed contextual classification based on the exact ULAN activity/role record and the exact "
            "official collection record. The activity, period, and tradition labels are synthesis fields, not verbatim source assertions."
        ),
        extracted_at=timestamp,
        stance="contextualizes",
    )
    loc_evidence = _evidence_record(
        evidence_id=loc_evidence_id,
        claim_ids=[loc_claim_id],
        source_key="getty_ulan",
        source_object_id=external_ids["ulan"],
        snapshot=getty_snapshot,
        raw_locator="/equivalent",
        summary=f"The exact ULAN authority record links the approved identity to Library of Congress name authority {external_ids['loc']}.",
        extracted_at=timestamp,
    )

    evidence_records = [profile_evidence, birth_evidence, death_evidence, work_evidence, context_evidence, loc_evidence]
    birth_counter_ids: list[str] = []
    if counter := decision.get("birth_counterevidence"):
        counter_id = f"evidence:{slug}-birth-counter"
        evidence_records.append(_counter_evidence(counter_id, birth_claim_id, counter, timestamp, snapshot_index))
        birth_counter_ids.append(counter_id)
    death_counter_ids: list[str] = []
    if counter := decision.get("death_counterevidence"):
        counter_id = f"evidence:{slug}-death-counter"
        evidence_records.append(_counter_evidence(counter_id, death_claim_id, counter, timestamp, snapshot_index))
        death_counter_ids.append(counter_id)

    profile_claim = _claim_record(
        claim_id=profile_claim_id,
        subject_id=artist_id,
        predicate="identity_profile",
        value=f"Resolved individual identity: {decision['labels']['en']}",
        datatype="string",
        precision="not_applicable",
        evidence_ids=[profile_evidence_id],
        counter_evidence_ids=[],
        claim_text={"en": f"{decision['labels']['en']} is the resolved individual represented by ULAN {decision['external_ids']['ulan']}.", "zh-Hans": f"{decision['labels']['zh-Hans']}对应已解析的个人身份。"},
        timestamp=timestamp,
        reviewer=reviewer,
    )
    birth_is_year = decision["birth"]["precision"] == "year" and decision["birth"]["display_value"].isdigit()
    birth_claim = _claim_record(
        claim_id=birth_claim_id,
        subject_id=artist_id,
        predicate="birth_year" if birth_is_year else "birth_period",
        value=decision["birth"]["display_value"],
        datatype="year" if birth_is_year else "string",
        precision="exact" if birth_is_year else "uncertain",
        evidence_ids=[birth_evidence_id],
        counter_evidence_ids=birth_counter_ids,
        claim_text={"en": f"Reviewed birth display: {decision['birth']['display_value']}.", "zh-Hans": f"审核采用的出生时间：{decision['birth']['display_value']}。"},
        timestamp=timestamp,
        reviewer=reviewer,
    )
    death_claim = _claim_record(
        claim_id=death_claim_id,
        subject_id=artist_id,
        predicate="death_year",
        value=decision["death"]["display_value"],
        datatype="year",
        precision="exact",
        evidence_ids=[death_evidence_id],
        counter_evidence_ids=death_counter_ids,
        claim_text={"en": f"Reviewed death year: {decision['death']['display_value']}.", "zh-Hans": f"审核采用的卒年：{decision['death']['display_value']}。"},
        timestamp=timestamp,
        reviewer=reviewer,
    )
    work_claim = _claim_record(
        claim_id=work_claim_id,
        subject_id=artist_id,
        predicate="has_verified_work_record",
        value=collection["url"],
        datatype="uri",
        precision="not_applicable",
        evidence_ids=[work_evidence_id],
        counter_evidence_ids=[],
        claim_text={"en": f"An official collection record exists for {collection['title']} under this artist identity.", "zh-Hans": f"正式馆藏中存在与该艺术家身份关联的《{collection['title']}》对象记录。"},
        timestamp=timestamp,
        reviewer=reviewer,
    )
    activity_value = f"{decision['activity_place']['label']} — {decision['activity_place']['historical_scope']}"
    activity_claim = _claim_record(
        claim_id=activity_claim_id,
        subject_id=artist_id,
        predicate="activity_scope",
        value=activity_value,
        datatype="string",
        precision="uncertain" if decision["activity_place"]["precision"] == "uncertain" else "not_applicable",
        evidence_ids=[context_evidence_id],
        counter_evidence_ids=[],
        claim_text={
            "en": f"Reviewed broad activity scope: {activity_value}.",
            "zh-Hans": f"审核采用的宽泛活动范围：{activity_value}。",
        },
        timestamp=timestamp,
        reviewer=reviewer,
    )
    period_claim = _claim_record(
        claim_id=period_claim_id,
        subject_id=artist_id,
        predicate="historical_period",
        value=decision["historical_period"],
        datatype="string",
        precision="not_applicable",
        evidence_ids=[context_evidence_id],
        counter_evidence_ids=[],
        claim_text={
            "en": f"Project-reviewed historical-period classification: {decision['historical_period']}.",
            "zh-Hans": f"项目审核的历史时期分类：{decision['historical_period']}。",
        },
        timestamp=timestamp,
        reviewer=reviewer,
    )
    tradition_claim = _claim_record(
        claim_id=tradition_claim_id,
        subject_id=artist_id,
        predicate="artistic_tradition",
        value=decision["artistic_tradition"],
        datatype="string",
        precision="not_applicable",
        evidence_ids=[context_evidence_id],
        counter_evidence_ids=[],
        claim_text={
            "en": f"Project-reviewed artistic-tradition classification: {decision['artistic_tradition']}.",
            "zh-Hans": f"项目审核的艺术传统分类：{decision['artistic_tradition']}。",
        },
        timestamp=timestamp,
        reviewer=reviewer,
    )
    loc_claim = _claim_record(
        claim_id=loc_claim_id,
        subject_id=artist_id,
        predicate="identity_same_as",
        value=f"https://id.loc.gov/authorities/names/{external_ids['loc']}",
        datatype="uri",
        precision="not_applicable",
        evidence_ids=[loc_evidence_id],
        counter_evidence_ids=[],
        claim_text={
            "en": f"The reviewed Library of Congress identity crosswalk is {external_ids['loc']}.",
            "zh-Hans": f"审核采用的美国国会图书馆身份对应项为 {external_ids['loc']}。",
        },
        timestamp=timestamp,
        reviewer=reviewer,
    )
    claim_records = [
        profile_claim,
        birth_claim,
        death_claim,
        work_claim,
        activity_claim,
        period_claim,
        tradition_claim,
        loc_claim,
    ]
    if resolution := decision.get("external_id_resolution"):
        support_id = f"evidence:{slug}-wikidata-crosswalk-support"
        counter_id = f"evidence:{slug}-wikidata-crosswalk-counter"
        getty_counter_id = f"evidence:{slug}-getty-wikidata-crosswalk-counter"
        profile_evidence["claim_ids"].append(wikidata_claim_id)
        evidence_records.extend([
            _evidence_record(
                evidence_id=support_id,
                claim_ids=[wikidata_claim_id],
                source_key="wikidata",
                source_object_id=resolution["accepted_wikidata"],
                snapshot=_snapshot_for(
                    snapshot_index,
                    "wikidata",
                    resolution["accepted_wikidata"],
                    expected_sha256=resolution["accepted_body_sha256"],
                    expected_snapshot_id=resolution["accepted_snapshot_id"],
                ),
                raw_locator="/entities/Q1374436/claims/P245",
                summary="The accepted Wikidata entity names Henry Ossawa Tanner and reciprocally asserts ULAN 500005351.",
                extracted_at=timestamp,
            ),
            _evidence_record(
                evidence_id=getty_counter_id,
                claim_ids=[wikidata_claim_id],
                source_key="getty_ulan",
                source_object_id=external_ids["ulan"],
                snapshot=getty_snapshot,
                raw_locator="/equivalent",
                summary="The ULAN record emits Q15487281 as an equivalent link; that assertion is preserved as rejected counter-evidence.",
                extracted_at=timestamp,
                stance="contradicts",
            ),
            _evidence_record(
                evidence_id=counter_id,
                claim_ids=[wikidata_claim_id],
                source_key="wikidata",
                source_object_id=resolution["quarantined_wikidata"],
                snapshot=_snapshot_for(
                    snapshot_index,
                    "wikidata",
                    resolution["quarantined_wikidata"],
                    expected_sha256=resolution["quarantined_body_sha256"],
                    expected_snapshot_id=resolution["quarantined_snapshot_id"],
                ),
                raw_locator="/entities/Q15487281/labels/en",
                summary="The quarantined QID resolves to Roger Brown, proving the ULAN same-as link is not Tanner.",
                extracted_at=timestamp,
                stance="contradicts",
            ),
        ])
        claim_records.append(_claim_record(
            claim_id=wikidata_claim_id,
            subject_id=artist_id,
            predicate="identity_same_as",
            value=f"https://www.wikidata.org/wiki/{resolution['accepted_wikidata']}",
            datatype="uri",
            precision="not_applicable",
            evidence_ids=[profile_evidence_id, support_id],
            counter_evidence_ids=[getty_counter_id, counter_id],
            claim_text={"en": "Q1374436 is the accepted Tanner crosswalk; Q15487281 is quarantined as a distinct person.", "zh-Hans": "采用 Q1374436 作为坦纳对应项；Q15487281 被隔离为不同人物。"},
            timestamp=timestamp,
            reviewer=reviewer,
        ))
    else:
        wikidata_evidence_id = f"evidence:{slug}-wikidata-crosswalk"
        wikidata_snapshot = _snapshot_for(snapshot_index, "wikidata", external_ids["wikidata"])
        evidence_records.append(_curatorial_evidence_record(
            evidence_id=wikidata_evidence_id,
            claim_ids=[wikidata_claim_id],
            source_refs=[
                {
                    "source_key": "getty_ulan",
                    "source_object_id": external_ids["ulan"],
                    "snapshot": getty_snapshot,
                    "raw_locator": "/equivalent",
                },
                {
                    "source_key": "wikidata",
                    "source_object_id": external_ids["wikidata"],
                    "snapshot": wikidata_snapshot,
                    "raw_locator": f"/entities/{external_ids['wikidata']}/claims/P245",
                },
            ],
            summary=(
                f"Reviewed identity crosswalk: ULAN {external_ids['ulan']} links to Wikidata {external_ids['wikidata']}, "
                "whose reciprocal P245 value identifies the same ULAN record. Wikidata is corroborating Tier 3 evidence only."
            ),
            extracted_at=timestamp,
        ))
        claim_records.append(_claim_record(
            claim_id=wikidata_claim_id,
            subject_id=artist_id,
            predicate="identity_same_as",
            value=f"https://www.wikidata.org/wiki/{external_ids['wikidata']}",
            datatype="uri",
            precision="not_applicable",
            evidence_ids=[wikidata_evidence_id],
            counter_evidence_ids=[],
            claim_text={
                "en": f"The reviewed Wikidata crosswalk is {external_ids['wikidata']}; it is not used as sole identity evidence.",
                "zh-Hans": f"审核采用的维基数据对应项为 {external_ids['wikidata']}；其不作为唯一身份依据。",
            },
            timestamp=timestamp,
            reviewer=reviewer,
        ))

    identity_signoff_id = f"review-signoff:{slug}-identity"
    history_signoff_id = f"review-signoff:{slug}-art-history"
    all_claim_ids = [
        profile_claim_id,
        birth_claim_id,
        death_claim_id,
        work_claim_id,
        activity_claim_id,
        period_claim_id,
        tradition_claim_id,
        loc_claim_id,
        wikidata_claim_id,
    ]
    signoffs = [
        _review_signoff(
            seed,
            identity_signoff_id,
            "identity_reviewer",
            [artist_id, profile_claim_id, birth_claim_id, death_claim_id, loc_claim_id, wikidata_claim_id],
            decision,
        ),
        _review_signoff(
            seed,
            history_signoff_id,
            "art_history_reviewer",
            [artist_id, death_claim_id, work_claim_id, activity_claim_id, period_claim_id, tradition_claim_id],
            decision,
        ),
    ]
    source_keys = ["getty_ulan", collection_source_key, "wikidata"]
    source_keys = list(dict.fromkeys(source_keys))
    aliases = [
        {**alias, "source_claim_id": profile_claim_id}
        for alias in decision["aliases"]
    ]
    name_records = [
        {
            "text": text,
            "language": language,
            "script": _script_for(language),
            "name_type": "preferred" if language == "en" else ("translated_display" if language == "zh-Hans" else "original"),
            "source_claim_id": profile_claim_id,
            "time_scope": None,
        }
        for language, text in decision["labels"].items()
    ]
    artist = {
        "schema_version": "1.1.0",
        "id": artist_id,
        "entity_type": "artist",
        "branch_id": "art",
        "labels": decision["labels"],
        "aliases": aliases,
        "external_ids": external_ids,
        "claim_ids": all_claim_ids,
        "source_ids": [SOURCE_RECORD_IDS[key] for key in source_keys],
        "source_license_bindings": [
            _binding(
                key,
                decision["external_ids"]["ulan"] if key == "getty_ulan"
                else collection["object_id"] if key == collection_source_key
                else external_ids["wikidata"],
            )
            for key in source_keys
        ],
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
        "created_at": timestamp,
        "updated_at": timestamp,
        "artist_kind": "individual",
        "deceased_status": "confirmed_deceased",
        "identity_status": "resolved",
        "life_dates": {
            "birth": {**decision["birth"], "claim_id": birth_claim_id},
            "death": {**decision["death"], "claim_id": death_claim_id},
        },
        "at_least_one_verified_work_or_record": True,
        "artwork_or_history_claim_ids": [work_claim_id],
        "review_status": "reviewed",
        "uncertainty_note": decision["uncertainty_note"],
        "branch_extensions": {
            "approved_candidate_id": decision["approved_candidate_id"],
            "name_records": name_records,
            "activity_places": [{**decision["activity_place"], "claim_id": activity_claim_id}],
            "historical_periods": [{"label": decision["historical_period"], "claim_id": period_claim_id}],
            "artistic_traditions": [{"label": decision["artistic_tradition"], "claim_id": tradition_claim_id}],
            "authority_source_ids": [getty_source_id],
            "source_independence_note": "Getty supplies the identity role; the named official collection source supplies a separate collection-record role. The latter is not counted as independent biographical confirmation.",
            "future_publishable_eligibility": "eligible_after_release_gates",
            "review_signoff_ids": [identity_signoff_id, history_signoff_id],
            "status_history": [
                {"from": None, "to": "candidate", "changed_at": timestamp, "changed_by": reviewer, "role": "identity collector", "reason": "Created from the exact approved candidate and fixed source records."},
                {"from": "candidate", "to": "sourced", "changed_at": timestamp, "changed_by": reviewer, "role": "identity reviewer", "reason": "Claim, evidence, source, and raw snapshot locators were closed."},
                {"from": "sourced", "to": "reviewed", "changed_at": timestamp, "changed_by": reviewer, "role": "art-history reviewer", "reason": "Identity, life precision, official-record role, and conflicts were reviewed without automated verification."},
            ],
        },
    }
    return {"artist": artist, "claims": claim_records, "evidence": evidence_records, "signoffs": signoffs}


def _source_record(source_id: str) -> dict[str, Any]:
    config = source_configuration(source_id)
    details = SOURCE_DETAILS[source_id]
    rules = source_license_rules(source_id)
    data_rule = next(rule for rule in rules if rule["content_class"] == "data" and (source_id != "aic_api" or rule["scope_match"]["field_policy"] == "exclude"))
    selected_rule_ids = [data_rule["rule_id"]]
    if source_id in {"met_open_access", "aic_api"}:
        media_rule = next(rule for rule in rules if rule["content_class"] == "media")
        selected_rule_ids.append(media_rule["rule_id"])
    return {
        "schema_version": "1.0.0",
        "id": SOURCE_RECORD_IDS[source_id],
        "entity_type": "source",
        "title": f"{details['name']} fixed source profile for MUSEUM-03B",
        "publisher": details["name"],
        "official_url": details["official_url"],
        "archived_url": None,
        "accessed_at": "2026-07-13",
        "published_or_updated_at": None,
        "source_version": config.get("adapter_name"),
        "tier": config["tier"],
        "source_type": details["source_type"],
        "access_method": config["adapter_name"],
        "api_key_required": "no",
        "access_limits": "Fixed registered endpoint and exact object IDs only; no arbitrary URL capture.",
        "rate_limit": config["rate_limit"],
        "registry_source_id": source_id,
        "registry_identity": {
            "canonical_name": details["name"],
            "canonical_official_host": details["host"],
            "snapshot_hash": source_registry_snapshot_hash(),
        },
        "license_rules": rules,
        "license_rules_snapshot_hash": canonical_sha256(rules),
        "selected_license_rule_ids": selected_rule_ids,
        "terms_url": config["terms_url"],
        "terms_version": "live-2026-07-13",
        "terms_snapshot_hash": None,
        "terms_verified_at": "2026-07-13",
        "reverify_by": "2027-07-13",
        "public_static_redistribution": details["public_static_redistribution"],
        "derivative_use": "allowed",
        "commercial_use": "allowed",
        "permission_status": "not_required",
        "permission_reference": None,
        "permission_scope": None,
        "permission_verified_at": "2026-07-13",
        "permission_expires_at": None,
        "permission_revoked_at": None,
        "risk_note": details["risk"],
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
    }


def _curatorial_evidence_record(
    *,
    evidence_id: str,
    claim_ids: list[str],
    source_refs: list[dict[str, Any]],
    summary: str,
    extracted_at: str,
    stance: str = "supports",
) -> dict[str, Any]:
    source_ids = [SOURCE_RECORD_IDS[ref["source_key"]] for ref in source_refs]
    if len(source_ids) != len(set(source_ids)):
        raise PipelineError("curatorial_source_duplicate", f"Duplicate source lineage in {evidence_id}")
    return {
        "schema_version": "1.1.0",
        "id": evidence_id,
        "entity_type": "evidence",
        "claim_ids": claim_ids,
        "stance": stance,
        "evidence_kind": "curatorial_assessment",
        "source_ids": source_ids,
        "source_license_bindings": [
            _binding(ref["source_key"], str(ref["source_object_id"]))
            for ref in source_refs
        ],
        "locator": {
            "record_id": " + ".join(str(ref["source_object_id"]) for ref in source_refs),
            "section": "project-reviewed synthesis from the exact raw locators listed in raw_snapshot_refs",
        },
        "summary": summary,
        "short_excerpt": None,
        "raw_snapshot_refs": [
            {
                "snapshot_id": ref["snapshot"]["snapshot_id"],
                "body_sha256": ref["snapshot"]["body_sha256"],
                "source_object_id": str(ref["source_object_id"]),
                "raw_locator": raw_locator,
            }
            for ref in source_refs
            for raw_locator in ref.get("raw_locators", [ref.get("raw_locator")])
        ],
        "original_language": "und",
        "extracted_at": extracted_at,
        "extraction_method": "manual",
        "reliability_note": (
            "This is a bounded project-reviewed synthesis. It does not promote broad context labels into direct historical influence, "
            "and each underlying source remains limited to its registered remit."
        ),
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
    }


def _claim_record(
    *,
    claim_id: str,
    subject_id: str,
    predicate: str,
    value: str,
    datatype: str,
    precision: str,
    evidence_ids: list[str],
    counter_evidence_ids: list[str],
    claim_text: dict[str, str],
    timestamp: str,
    reviewer: str,
) -> dict[str, Any]:
    disputed = bool(counter_evidence_ids)
    status = "disputed" if disputed else "reviewed"
    temporal = value if datatype == "year" and value.isdigit() else None
    return {
        "schema_version": "1.0.0",
        "id": claim_id,
        "entity_type": "claim",
        "subject_id": subject_id,
        "predicate": predicate,
        "object": {"value": value, "datatype": datatype, "precision": precision},
        "claim_text": claim_text,
        "temporal_scope": {
            "start": temporal,
            "end": temporal,
            "precision": "year" if temporal else "unknown",
            "uncertain": disputed or precision in {"circa", "uncertain"},
            "description": "Reviewed life date" if predicate in {"birth_year", "birth_period", "death_year", "death_period"} else "Not a temporal assertion",
        },
        "applicability_scope": "MUSEUM-03B internal reviewed identity record",
        "evidence_ids": evidence_ids,
        "counter_evidence_ids": counter_evidence_ids,
        "status": status,
        "status_history": [
            {"from": None, "to": "candidate", "changed_at": timestamp, "changed_by": reviewer, "role": "collector", "reason": "Created from fixed-source evidence."},
            {"from": "candidate", "to": "sourced", "changed_at": timestamp, "changed_by": reviewer, "role": "collector", "reason": "Exact evidence and source locators attached."},
            {"from": "sourced", "to": status, "changed_at": timestamp, "changed_by": reviewer, "role": "discipline reviewer", "reason": "Reviewed at source precision; competing evidence retained where present."},
        ],
        "disputed": disputed,
        "dispute_note": "Competing official-source observation retained; the artist record states the current reviewed projection." if disputed else None,
        "no_counter_evidence_reason": None,
        "dispute_display": "not_public" if disputed else "not_disputed",
        "review": {"reviewer": reviewer, "reviewed_at": timestamp[:10], "decision_note": "Accepted for internal reviewed use only; no automatic verified or public promotion."},
        "publish_status": "not_public",
        "supersedes": None,
        "data_version": "1.0.0",
    }


def _evidence_record(
    *,
    evidence_id: str,
    claim_ids: list[str],
    source_key: str,
    source_object_id: str,
    snapshot: dict[str, str],
    raw_locator: str,
    summary: str,
    extracted_at: str,
    locator_url: str | None = None,
    stance: str = "supports",
) -> dict[str, Any]:
    source_record_id = SOURCE_RECORD_IDS[source_key]
    rule = next(rule for rule in source_license_rules(source_key) if rule["content_class"] == "data" and (source_key != "aic_api" or rule["scope_match"]["field_policy"] == "exclude"))
    scope_locator, scope_fields = _scope_contract(source_key, source_object_id)
    return {
        "schema_version": "1.1.0",
        "id": evidence_id,
        "entity_type": "evidence",
        "claim_ids": claim_ids,
        "stance": stance,
        "evidence_kind": "dataset_record" if source_key in {"getty_ulan", "wikidata"} else "collection_record",
        "source_ids": [source_record_id],
        "source_license_bindings": [{
            "source_id": source_record_id,
            "rule_id": rule["rule_id"],
            "content_class": "data",
            "scope_locator": scope_locator,
            "scope_fields": scope_fields,
            "permission_resolution": "rule_direct",
        }],
        "locator": {
            "record_id": source_object_id,
            "section": scope_locator if source_key == "aic_api" else (locator_url or raw_locator),
        },
        "summary": summary,
        "short_excerpt": None,
        "raw_snapshot_refs": [{
            "snapshot_id": snapshot["snapshot_id"],
            "body_sha256": snapshot["body_sha256"],
            "source_object_id": source_object_id,
            "raw_locator": raw_locator,
        }],
        "original_language": "und",
        "extracted_at": extracted_at,
        "extraction_method": "api_field",
        "reliability_note": "The assertion is limited to the registered source's institutional or authority remit and is not generalized beyond that scope.",
        "lifecycle_status": "reviewed",
        "data_version": "1.0.0",
    }


def _counter_evidence(
    evidence_id: str,
    claim_id: str,
    counter: dict[str, Any],
    timestamp: str,
    snapshot_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    return _evidence_record(
        evidence_id=evidence_id,
        claim_ids=[claim_id],
        source_key=counter["source_id"],
        source_object_id=counter["object_id"],
        snapshot=_snapshot_for(
            snapshot_index,
            counter["source_id"],
            str(counter["object_id"]),
            expected_sha256=counter["body_sha256"],
        ),
        raw_locator=counter["raw_locator"],
        summary=f"The official collection record presents the competing display value {counter['display_value']}; it is preserved rather than overwritten.",
        extracted_at=timestamp,
        stance="contradicts",
    )


def _review_signoff(seed: dict[str, Any], signoff_id: str, role: str, record_ids: list[str], decision: dict[str, Any]) -> dict[str, Any]:
    session = seed["review_sessions"][role]
    return {
        "schema_version": "1.0.0",
        "id": signoff_id,
        "entity_type": "review_signoff",
        "record_ids": record_ids,
        "review_role": role,
        "reviewer_id": seed["reviewer_id"],
        "reviewer_kind": seed["reviewer_kind"],
        "single_operator_multi_role": True,
        "reviewed_at": session["reviewed_at"],
        "checklist": session["checklist"],
        "decision": session["decision"],
        "decision_note": f"{decision['labels']['en']}: {session['decision_note']}",
        "authority_basis": seed["authority_basis"],
        "data_version": "1.0.0",
    }


def _binding(source_key: str, source_object_id: str | None) -> dict[str, Any]:
    rule = next(rule for rule in source_license_rules(source_key) if rule["content_class"] == "data" and (source_key != "aic_api" or rule["scope_match"]["field_policy"] == "exclude"))
    scope_locator, scope_fields = _scope_contract(source_key, source_object_id)
    return {
        "source_id": SOURCE_RECORD_IDS[source_key],
        "rule_id": rule["rule_id"],
        "content_class": "data",
        "scope_locator": scope_locator,
        "scope_fields": scope_fields,
        "permission_resolution": "rule_direct",
    }


def _scope_contract(source_key: str, source_object_id: str | None) -> tuple[str, list[str]]:
    if source_key == "aic_api":
        if not source_object_id:
            raise PipelineError("aic_scope_object_missing", "AIC bindings require an exact object ID")
        fields = list(source_configuration("aic_api")["query_profiles"]["default"])
        query = urlencode({"fields": ",".join(fields)})
        return f"https://api.artic.edu/api/v1/artworks/{source_object_id}?{query}", fields
    scope_locators = {
        "getty_ulan": "ULAN N-Triples/SPARQL/per-record exports",
        "met_open_access": "Open Access collection API/CSV fields",
        "wikidata": "main/property/lexeme/entity-schema structured data",
    }
    try:
        return scope_locators[source_key], ["record"]
    except KeyError as error:
        raise PipelineError("source_scope_unknown", f"No exact source-rule scope for {source_key}") from error


def _script_for(language: str) -> str | None:
    if language.startswith("zh"):
        return "Hans" if language == "zh-Hans" else "Hant"
    if language == "ja":
        return "Jpan"
    if language == "ml":
        return "Mlym"
    return "Latn"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError("identity_input_invalid", f"Cannot read identity input: {path}") from error


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write_text(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
