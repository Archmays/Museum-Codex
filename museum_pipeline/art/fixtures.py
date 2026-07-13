from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from museum_pipeline.art.contract_validation import validate_art_batch_contract


ROOT = Path(__file__).resolve().parents[2]
VALID_ROOT = ROOT / "fixtures" / "art-batch" / "valid"
INVALID_ROOT = ROOT / "fixtures" / "art-batch" / "invalid"

def build_synthetic_batch() -> dict[str, Any]:
    """Build an entirely synthetic, internally closed MUSEUM-03B test batch."""

    artist_ids = [f"artist:synthetic-{index:02d}" for index in range(1, 13)]
    candidate_ids = [f"artist-candidate:synthetic-{index:02d}" for index in range(1, 13)]
    artists = [
        {
            "id": artist_id,
            "candidate_id": candidate_id,
            "labels": {"en": f"Synthetic Artist {index:02d}"},
            "aliases": [f"Synthetic Alias {index:02d}"],
            "artist_kind": "individual",
            "deceased_status": "confirmed_deceased",
            "identity_conflict": False,
            "source_lineages": [
                {"id": f"synthetic-authority-{index:02d}", "tier": 1, "role": "authority"},
                {"id": f"synthetic-museum-{index:02d}", "tier": 1, "role": "museum"},
            ],
            "death_date": {
                "value": f"19{index:02d}-01-01",
                "precision": "exact",
                "source_precision": "exact",
            },
            "verified_work_history": True,
            "auto_replacement": False,
            "state": "reviewed",
        }
        for index, (artist_id, candidate_id) in enumerate(zip(artist_ids, candidate_ids), 1)
    ]

    work_counts = (4, 4, 4, 4, 2, 4, 4, 4, 4, 2, 4, 4)
    artworks: list[dict[str, Any]] = []
    for artist_index, (artist_id, count) in enumerate(zip(artist_ids, work_counts), 1):
        for work_index in range(1, count + 1):
            serial = len(artworks) + 1
            artwork_id = f"artwork:synthetic-{serial:02d}"
            artworks.append(
                {
                    "id": artwork_id,
                    "artist_id": artist_id,
                    "official_object_url": f"https://fixtures.invalid/object/{serial:02d}",
                    "attribution": {
                        "statement": f"Synthetic attribution {artist_index:02d}-{work_index:02d}",
                        "preserved": True,
                    },
                    "creation_date": {"value": f"18{serial:02d}", "precision": "exact"},
                    "institution_id": "institution:synthetic-museum",
                    "accession_number": f"SYN-{serial:04d}",
                    "metadata_rights_basis": "synthetic_fixture_metadata_rule",
                    "media_rights_basis": "synthetic_fixture_media_rule",
                    "rights_separation": True,
                    "rights_evidence": [{"kind": "reviewed_claim", "id": f"claim:rights-{serial:02d}"}],
                    "description": "Short project-authored synthetic fixture description.",
                    "description_origin": "project_authored",
                    "state": "reviewed",
                }
            )

    contexts = [
        _context("place:synthetic-city", "place", "Synthetic City", requires_historical_scope=True),
        _context("movement:synthetic-movement", "movement", "Synthetic Movement"),
        _context("group:synthetic-circle", "group", "Synthetic Circle"),
        _context("institution:synthetic-museum", "institution", "Synthetic Museum"),
        _context("material:synthetic-paper", "material", "Synthetic Paper"),
        _context("technique:synthetic-print", "technique", "Synthetic Printing"),
        _context("subject:synthetic-observation", "subject", "Synthetic Observation"),
        _context("exhibition:synthetic-show", "exhibition", "Synthetic Exhibition"),
    ]

    relationships: list[dict[str, Any]] = []
    for offset in (1, 2, 3):
        for source_index, source_id in enumerate(artist_ids):
            target_id = artist_ids[(source_index + offset) % len(artist_ids)]
            serial = len(relationships) + 1
            relationships.append(
                {
                    "id": f"art-rel:synthetic-{serial:02d}",
                    "source_entity_id": source_id,
                    "target_entity_id": target_id,
                    "relationship_type": "shared_context",
                    "relationship_semantics": "historical_context",
                    "evidence_level": "B",
                    "specific_context_ids": ["subject:synthetic-observation"],
                    "place_context_id": "place:synthetic-city",
                    "time_scope": {"start": "1800", "end": "1950", "precision": "range"},
                    "direct_evidence": False,
                    "is_algorithmic": False,
                    "generated_method": "human_review",
                    "public_display": False,
                    "claim_reviewed": True,
                }
            )

    media = [
        {
            "artwork_id": artwork["id"],
            "eligibility": "self_hosted_open_media_eligible",
            "rights_status": "clear",
            "development_only": False,
            "counted_clear": True,
            "external_iiif_cache_bytes": False,
            "self_hosted_bytes_present": False,
            "license_id": "CC0-1.0",
            "attribution": "Not required for this synthetic CC0 fixture.",
            "revoked_or_expired": False,
            "rule_scope": "media",
            "forced_image_quota": False,
        }
        for artwork in artworks
    ]

    bundle_hash = "sha256:" + "b" * 64
    decision_hash = "sha256:" + "d" * 64
    application_input_hash = "sha256:" + "a" * 64
    application_output_hash = "sha256:" + "e" * 64
    package_files = [
        {
            "path": "records.json",
            "declared_bytes": 100,
            "actual_bytes": 100,
            "declared_sha256": "sha256:" + "1" * 64,
            "actual_sha256": "sha256:" + "1" * 64,
        },
        {
            "path": "graph.json",
            "declared_bytes": 200,
            "actual_bytes": 200,
            "declared_sha256": "sha256:" + "2" * 64,
            "actual_sha256": "sha256:" + "2" * 64,
        },
    ]
    formal_terms = [
        {"value": "MUSEUM-03B", "match_mode": "casefold_substring"},
        *(
            {"value": alias, "match_mode": "casefold_substring"}
            for artist in artists
            for alias in artist["aliases"]
        ),
    ]

    return {
        "fixture_kind": "synthetic_art_batch",
        "batch_id": "art-batch:synthetic-museum-03b-v1",
        "decision": {
            "id": "selection-decision:synthetic-museum-03b",
            "status": "submitted",
            "expected_bundle_hash": bundle_hash,
            "input_bundle_hash": bundle_hash,
            "bundle_stale": False,
            "recommended_scenario_id": "selection-scenario:synthetic-recommended",
            "selected_scenario_id": "selection-scenario:synthetic-recommended",
            "recommended_candidate_ids": candidate_ids,
            "selected_candidate_ids": candidate_ids.copy(),
            "replacements": [],
            "decision_authority": "Mays",
            "expected_authority": "Mays",
            "media_strategy": "mixed",
            "decision_hash": decision_hash,
        },
        "application": {
            "input_hash": application_input_hash,
            "prior_input_hash": application_input_hash,
            "prior_output_hash": application_output_hash,
            "rerun_output_hash": application_output_hash,
            "conflicting_reapply": False,
        },
        "artists": artists,
        "artworks": artworks,
        "contexts": contexts,
        "relationships": relationships,
        "media_assessments": media,
        "package": {
            "declared_files": [item["path"] for item in package_files],
            "actual_files": [item["path"] for item in package_files],
            "files": package_files,
            "contains_symlink": False,
            "path_escape": False,
            "decision_ref": {"id": "selection-decision:synthetic-museum-03b", "hash": decision_hash},
            "primary_node_ids": artist_ids.copy(),
            "media_byte_paths": [],
            "state": "reviewed",
        },
        "public_artifact": {
            "files": [
                {
                    "path": "index.html",
                    "content": "Seven-museum synthetic portal; the art antechamber remains empty.",
                }
            ],
            "formal_terms": formal_terms,
        },
    }


def evaluate_art_batch_fixture(case: dict[str, Any]) -> set[str]:
    """Materialize and validate one declarative art-batch fixture case."""

    if case.get("template") != "synthetic-museum-03b-v1":
        return {"fixture_template_unknown"}
    batch = build_synthetic_batch()
    try:
        apply_mutations(batch, case.get("mutations", []))
    except (KeyError, IndexError, TypeError, ValueError):
        return {"fixture_mutation_invalid"}
    codes = validate_synthetic_batch(batch)
    if case.get("operation") == "legacy_regression_probe":
        codes.update(_evaluate_legacy_regression_probe(case))
    elif case.get("operation", "validate_synthetic_batch") != "validate_synthetic_batch":
        codes.add("fixture_operation_unknown")
    return codes


def validate_synthetic_batch(batch: dict[str, Any]) -> set[str]:
    """Validate the cross-record invariants represented by the synthetic matrix."""

    if batch.get("fixture_kind") != "synthetic_art_batch":
        return {"fixture_not_synthetic"}
    codes = validate_art_batch_contract(batch)
    codes.update(_scan_public_fixture(batch))
    return codes


def validate_fixture_matrix(root: Path = ROOT) -> dict[str, Any]:
    """Require every valid fixture to pass and every invalid one to fail exactly."""

    valid_root = root / "fixtures" / "art-batch" / "valid"
    invalid_root = root / "fixtures" / "art-batch" / "invalid"
    failures: list[str] = []
    valid_count = 0
    invalid_count = 0
    covered: set[int] = set()

    for path in sorted(valid_root.glob("*.json")):
        case = _read_case(path, failures)
        if case is None:
            continue
        codes = evaluate_art_batch_fixture(case)
        if codes:
            failures.append(f"valid:{path.name}:actual={','.join(sorted(codes))}")
        else:
            valid_count += 1

    for path in sorted(invalid_root.glob("*.json")):
        case = _read_case(path, failures)
        if case is None:
            continue
        number = case.get("case_number")
        if not isinstance(number, int):
            failures.append(f"invalid:{path.name}:case_number_missing")
            continue
        covered.add(number)
        expected = case.get("expected_error")
        if not isinstance(expected, str) or not expected:
            failures.append(f"invalid:{path.name}:expected_error_missing")
            continue
        codes = evaluate_art_batch_fixture(case)
        if codes != {expected}:
            failures.append(
                f"invalid:{path.name}:expected={expected}:actual={','.join(sorted(codes)) or 'none'}"
            )
        else:
            invalid_count += 1

    expected_behaviors = set(range(1, 69))
    if covered != expected_behaviors:
        missing = ",".join(str(value) for value in sorted(expected_behaviors - covered))
        extra = ",".join(str(value) for value in sorted(covered - expected_behaviors))
        failures.append(f"behavior_coverage_mismatch:missing={missing}:extra={extra}")
    return {
        "ok": not failures,
        "valid_fixtures": valid_count,
        "invalid_fixtures": invalid_count,
        "numbered_behaviors": len(covered & expected_behaviors),
        "failures": sorted(failures),
    }


def apply_mutations(document: dict[str, Any], mutations: list[dict[str, Any]]) -> None:
    for mutation in mutations:
        operation = mutation["op"]
        if operation == "replace":
            parent, key = _pointer_parent(document, mutation["path"])
            parent[int(key) if isinstance(parent, list) else key] = deepcopy(mutation["value"])
        elif operation == "remove":
            parent, key = _pointer_parent(document, mutation["path"])
            if isinstance(parent, list):
                del parent[int(key)]
            else:
                del parent[key]
        elif operation == "append":
            target = _pointer_value(document, mutation["path"])
            if not isinstance(target, list):
                raise TypeError("append target must be a list")
            target.append(deepcopy(mutation["value"]))
        elif operation == "copy":
            value = deepcopy(_pointer_value(document, mutation["from"]))
            parent, key = _pointer_parent(document, mutation["path"])
            parent[int(key) if isinstance(parent, list) else key] = value
        elif operation == "remove_where":
            target = _pointer_value(document, mutation["path"])
            if not isinstance(target, list):
                raise TypeError("remove_where target must be a list")
            fields = mutation["where"]
            target[:] = [item for item in target if not all(item.get(key) == value for key, value in fields.items())]
        elif operation == "remove_relationships_for_entity":
            entity_id = mutation["entity_id"]
            relationships = document["relationships"]
            relationships[:] = [
                item
                for item in relationships
                if entity_id not in {item.get("source_entity_id"), item.get("target_entity_id")}
            ]
        else:
            raise ValueError(f"unsupported mutation operation: {operation}")


def probe_legacy_contracts() -> dict[str, set[str]]:
    """Run representative legacy validators from all three earlier phases."""

    from museum_pipeline.curation.fixtures import evaluate_curation_invalid_fixture
    from museum_pipeline.validation.dispatch import load_schema_environment
    from museum_pipeline.validation.fixtures import evaluate_invalid_fixture
    from scripts.validate_governance_foundation import validate_fixture

    pipeline_path = ROOT / "fixtures" / "pipeline" / "invalid" / "secret-in-url.json"
    curation_path = ROOT / "fixtures" / "curation" / "invalid" / "computational-similarity.json"
    governance_path = ROOT / "fixtures" / "governance" / "invalid" / "algorithm-as-influence.json"
    pipeline_case = json.loads(pipeline_path.read_text(encoding="utf-8"))
    curation_case = json.loads(curation_path.read_text(encoding="utf-8"))
    governance_codes = {
        issue.code for issue in validate_fixture(governance_path, load_schema_environment(ROOT))
    }
    return {
        "pipeline": evaluate_invalid_fixture(pipeline_case),
        "curation": evaluate_curation_invalid_fixture(curation_case),
        "governance": governance_codes,
    }


def _context(
    context_id: str,
    context_type: str,
    label: str,
    *,
    requires_historical_scope: bool = False,
) -> dict[str, Any]:
    return {
        "id": context_id,
        "context_type": context_type,
        "labels": {"en": label},
        "source_ids": ["source:synthetic-reviewed-context"],
        "requires_historical_scope": requires_historical_scope,
        "historical_time_scope": (
            {"start": "1800", "end": "1950", "precision": "range"}
            if requires_historical_scope
            else None
        ),
    }


def _scan_public_fixture(batch: dict[str, Any]) -> set[str]:
    from scripts.scan_public_artifact_for_candidate_data import scan_public_artifact

    public = batch["public_artifact"]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "dist"
        root.mkdir()
        for item in public.get("files", []):
            path = root / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item.get("content", ""), encoding="utf-8")
        findings = scan_public_artifact(root, formal_art_terms=public.get("formal_terms", []))
    return {item["code"] for item in findings}


def _evaluate_legacy_regression_probe(case: dict[str, Any]) -> set[str]:
    results = probe_legacy_contracts()
    baseline = {
        "pipeline": "secret_in_url",
        "curation": "schema",
        "governance": "algorithmic_influence",
    }
    for family, expected_code in baseline.items():
        if expected_code not in results.get(family, set()):
            return {"legacy_fixture_regression_detected"}
    drift = case.get("simulated_contract_drift", {})
    family = drift.get("family")
    required_code = drift.get("required_code")
    if family not in results or required_code not in results[family]:
        return {"legacy_fixture_regression_detected"}
    return set()


def _pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _pointer_value(document: Any, pointer: str) -> Any:
    current = document
    for part in _pointer_parts(pointer):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = _pointer_parts(pointer)
    if not parts:
        raise ValueError("root replacement is not supported")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def _read_case(path: Path, failures: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        failures.append(f"fixture_unreadable:{path.name}:{type(error).__name__}")
        return None
    if not isinstance(value, dict):
        failures.append(f"fixture_not_object:{path.name}")
        return None
    return value
