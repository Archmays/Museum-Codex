from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

from museum_pipeline.canonical_json import canonical_json_bytes, write_canonical_json
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.media.acquisition import commons_profile
from museum_pipeline.media.constants import (
    BUNDLE_ROOT,
    EXPECTED_M03B_GRAPH_HASH,
    EXPECTED_M03B_PACKAGE_HASH,
    LEDGER_PATH,
    M03B_PACKAGE,
    MEDIA_VAULT,
    PHASE_ID,
    PIPELINE_EXECUTOR,
    REVIEWED_ROOT,
    TARGET_WIDTHS,
    artwork_slug,
    artwork_vault,
)
from museum_pipeline.media.image_processing import PROCESSOR_VERSION, build_derivatives
from museum_pipeline.media.inputs import load_media_inputs
from museum_pipeline.media.state import load_json, replace_generated, utc_now
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record


_DATA_FILES = {
    "acquisition-requests.json": ("media_acquisition_request", "schemas/art/media/acquisition-request.schema.json"),
    "acquisition-events.json": ("media_acquisition_event", "schemas/art/media/acquisition-event.schema.json"),
    "byte-records.json": ("media_byte_record", "schemas/art/media/byte-record.schema.json"),
    "identity-rights-cross-checks.json": ("media_identity_rights_cross_check", "schemas/art/media/identity-rights-cross-check.schema.json"),
    "quality-assessments.json": ("media_quality_assessment", "schemas/art/media/quality-assessment.schema.json"),
    "automated-reviews.json": ("media_automated_review", "schemas/art/media/automated-review.schema.json"),
    "derivative-records.json": ("media_derivative_record", "schemas/art/media/derivative-record.schema.json"),
    "alternative-source-searches.json": ("media_alternative_source_search", "schemas/art/media/alternative-source-search.schema.json"),
}

_SPECIAL_FILE_SCHEMAS = {
    "attributions.json": ("attributions", "schemas/common/attribution-manifest.schema.json"),
    "third-party-notices.json": ("notices", "schemas/common/third-party-notices.schema.json"),
    "source-rules-snapshot.json": ("source_rules", "schemas/common/source-rules-snapshot.schema.json"),
    "discovery-source-profiles.json": ("source_rules", None),
    "withdrawal-mapping.json": ("withdrawals", "schemas/art/media/withdrawal-mapping.schema.json"),
}

_CANONICAL_CHANGES_STATEMENT = (
    "EXIF orientation, ICC normalization when present, metadata-safe stripping, resizing and compression only; "
    "no crop, upscaling, AI generation or artwork-content change."
)

# Exact MUSEUM-03C v1 source inspection closure. The tracked byte records bind
# derivatives to these reviewed source hashes; only the seven sources whose
# decoded originals contained an ICC profile may claim ICC normalization.
_M03C_V1_SOURCE_SHA256 = frozenset(
    {
        "sha256:0734b3b3b3b7bccab4e3e788d3ce52efcdad89c55fc893065febc8cbddbef70a",
        "sha256:132418e0c7bc20f2931a15a8e74ab7e724b3e5f49f50386d83be103b22b2aefc",
        "sha256:13c82396b294cad4ba314fa1d7ac88e6d6196c9eadd64626ebe39fd10355cd54",
        "sha256:185918711b6ca34e19a72deca2b21958df10b40daa32509125cd050712a58620",
        "sha256:18af62b2138d9f2238a49a54eaa0d4f3ee614298875ebf142484c0e22ee27181",
        "sha256:1bb1951ad1adf7eb2c0c2ce5d9d3a444a33c9fd5b76e025695fa8b62049421a5",
        "sha256:28cf0d96b8d115ec119e1cfefb69cc05e4d8838c9a948a31353e47f4812a262e",
        "sha256:29760f9ab10ebfce0a3b0deebd13c2b1d8b99c98efd08be6d61b87f94cb4c11b",
        "sha256:29a94a1646bba06e2ae68288d503032b183ae577b91d97618e4bb942333c7617",
        "sha256:3357aaac7a219e403f7610b8e8779e71c3609bbf6e4ef6ce7240e2256e58cdd7",
        "sha256:36d697cb6c5a36847b7f3e6d3f4206d552c41d19fc71c727969fb1eae8285e32",
        "sha256:3b529941d1b290d91bda709e2e1f717f0c66c7933515f801541f68cea7fa593f",
        "sha256:48aba1461c0fa2553d88e04095a818cf97ad779f961adf59ffc77e7db5fca866",
        "sha256:4a4556e880f4fefd2bd4d635ee9b1a495cf6632a24cb72b83eda6d0033ddb711",
        "sha256:5272f1a4f0a06af57037ec9ee3c24863611faf878e311bff8da6fb8fbf05a6b7",
        "sha256:6582c354f2183d6b71e4472b647d7d6114d1ef8a26082e627b9e423d7676fceb",
        "sha256:6ac7985d9a4f089cd6264f144e93a6854aa2bbe1fdbba9943c7a0db790d46f1f",
        "sha256:6b851d821d565e61817250b272417c79721724f8dba2deaffe9b4c9ca4c35685",
        "sha256:8661b704d0d40ae50c8f36cb583ebc49fa5bea20a34fb20eb3fddb397f00dd99",
        "sha256:8791d364c5b4b3fa400d31ed7f9ef4fd3cc4a154847ab40aad626149141233fd",
        "sha256:8cd1e30b909c748fabeb1518440696af3e57b33cd52dd9a72c0c33064c16ebf4",
        "sha256:a11a66e5c2b3cf3b6a04a0476913e8aa03518cc69d6bcda99f1a3feb13c38c09",
        "sha256:a62d9b7a1f783a9627cae07321681fadc122b0e0badb4e1c707c410748f03b18",
        "sha256:ae3d5818174b65d8d8c7a18a4ef103499f6204dc85ec1c3c288ddb97da7c83d2",
        "sha256:af896d90f60db786ac28fd19ad726a2a205626d6d48dedff55ce46813b60cd72",
        "sha256:b410eeec0473c4e63eef12434a5a7c4613401c6e18670718d7727f36a441495c",
        "sha256:c21e33c8b614bf94dc432e3d814c8f047e03454198d4c51239cb88d4cecc93be",
        "sha256:d13127acc9f678bf7bbde6db3c94dfc9c772e5b036275bf0023bcd2743915c54",
        "sha256:e4d8fd7fbfc99d805c9fe20d334ab989d3fc68ed68891f6769fcc677146e0fb1",
        "sha256:fb0df662eccafa88eb405bb2ca9b81ab8fb04fd875b7f00627281cee25a6d6fd",
        "sha256:ff5aa3522da8df47d9032e12dd11cb85a06d5efc7f95a4fc50bd5646b267439f",
    }
)
_M03C_V1_ICC_SOURCE_SHA256 = frozenset(
    {
        "sha256:18af62b2138d9f2238a49a54eaa0d4f3ee614298875ebf142484c0e22ee27181",
        "sha256:3b529941d1b290d91bda709e2e1f717f0c66c7933515f801541f68cea7fa593f",
        "sha256:6b851d821d565e61817250b272417c79721724f8dba2deaffe9b4c9ca4c35685",
        "sha256:8791d364c5b4b3fa400d31ed7f9ef4fd3cc4a154847ab40aad626149141233fd",
        "sha256:c21e33c8b614bf94dc432e3d814c8f047e03454198d4c51239cb88d4cecc93be",
        "sha256:e4d8fd7fbfc99d805c9fe20d334ab989d3fc68ed68891f6769fcc677146e0fb1",
        "sha256:ff5aa3522da8df47d9032e12dd11cb85a06d5efc7f95a4fc50bd5646b267439f",
    }
)


def build_bundle() -> dict[str, Any]:
    if BUNDLE_ROOT.exists():
        result = validate_bundle()
        if result["ok"]:
            return {**result, "summary": "existing M03C media bundle reused", "reused": True}
        raise ValueError("existing M03C bundle is invalid and will not be overwritten: " + ", ".join(result["issues"][:8]))
    inputs = load_media_inputs()
    generated_at = utc_now()
    REVIEWED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".media-bundle-v1-", dir=REVIEWED_ROOT) as temporary:
        staged = Path(temporary) / "media-bundle-v1"
        staged.mkdir()
        collections: dict[str, list[dict[str, Any]]] = {name: [] for name in _DATA_FILES}
        derivative_to_media: dict[str, str] = {}
        source_by_id = {item["id"]: item for item in json.loads((M03B_PACKAGE / "sources.json").read_text(encoding="utf-8"))}
        notices: list[dict[str, Any]] = []
        attributions: list[dict[str, Any]] = []
        withdrawals: list[dict[str, Any]] = []
        for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
            directory = artwork_vault(artwork["id"])
            request = load_json(directory / "acquisition-request.json")
            collections["acquisition-requests.json"].append(request)
            for event_name in (
                "metadata-acquisition-event.json",
                "original-acquisition-event.json",
                "preview-acquisition-event.json",
            ):
                if (directory / event_name).exists():
                    collections["acquisition-events.json"].append(load_json(directory / event_name))
            cross = load_json(directory / "identity-rights-cross-check.json")
            review = load_json(directory / "automated-review.json")
            collections["identity-rights-cross-checks.json"].append(cross)
            collections["automated-reviews.json"].append(review)
            if (directory / "alternative-source-search.json").exists():
                collections["alternative-source-searches.json"].append(load_json(directory / "alternative-source-search.json"))
            byte_record = load_json(directory / "byte-record.json") if (directory / "byte-record.json").exists() else None
            quality = load_json(directory / "quality-assessment.json") if (directory / "quality-assessment.json").exists() else None
            if byte_record:
                collections["byte-records.json"].append(byte_record)
            if quality:
                collections["quality-assessments.json"].append(quality)
            if review["decision"] != "approved_self_hosted":
                continue
            if byte_record is None or quality is None:
                raise ValueError(f"approved review lacks byte/quality closure for {artwork['id']}")
            source_path = MEDIA_VAULT.parents[3] / byte_record["vault_relative_path"]
            output_dir = staged / "assets" / artwork_slug(artwork["id"])
            source_bytes = _verified_source_bytes(source_path, byte_record)
            built = build_derivatives(
                source_bytes,
                byte_record["magic_mime"],
                output_dir,
                widths=TARGET_WIDTHS,
            )
            if (
                built["source"]["sha256"] != byte_record["sha256"]
                or built["source"]["bytes"] != byte_record["byte_length"]
                or built["source"]["mime"] != byte_record["magic_mime"]
            ):
                raise ValueError(f"derivative processor source evidence drifted for {artwork['id']}")
            derivatives = _derivative_records(artwork["id"], byte_record, built, generated_at)
            actual_ids = [item["id"] for item in derivatives]
            if actual_ids != review["derivative_ids"]:
                raise ValueError(f"predicted derivative closure changed for {artwork['id']}")
            collections["derivative-records.json"].extend(derivatives)
            for derivative in derivatives:
                media_id = derivative["id"].replace("media-derivative:", "media:")
                derivative_to_media[derivative["id"]] = media_id
                license_record = cross["rights"]["license"]
                attributions.append(
                    {
                        "asset_id": media_id,
                        "attribution": cross["rights"]["attribution"],
                        "license_identifier": license_record["identifier"],
                        "license_url": license_record["url"],
                        "source_url": byte_record["source_url"],
                        "changes_statement": _CANONICAL_CHANGES_STATEMENT,
                    }
                )
                notices.append(
                    {
                        "record_id": media_id,
                        "notice": "Third-party artwork reproduction; the source-specific object-level license remains controlling.",
                        "source_url": byte_record["source_url"],
                        "license_rule_ids": [cross["rights"]["source_rule_id"]],
                        "license_identifiers": [license_record["identifier"]],
                        "attribution_texts": [cross["rights"]["attribution"]],
                        "rights_holder": None,
                    }
                )
                withdrawals.append(
                    {
                        "media_id": media_id,
                        "artwork_id": artwork["id"],
                        "derivative_paths": [derivative["storage_path"]],
                        "source_id": byte_record["source_id"],
                        "rights_record_id": cross["id"],
                        "status": "active",
                        "effective_at": None,
                        "replacement_media_id": None,
                        "public_notice": "Remove this exact derivative from every public manifest if its source rights status becomes withdrawn, revoked, expired or disputed.",
                    }
                )
        for name, records in collections.items():
            write_canonical_json(staged / name, records)
        source_rules = _source_rules_snapshot(source_by_id, generated_at)
        attribution_document = {"assets": sorted(attributions, key=lambda item: item["asset_id"])}
        notices_document = {
            "scope_statement": "MUSEUM-03C approved derivatives only; metadata-only and blocked works have no bundled media bytes.",
            "notices": sorted(notices, key=lambda item: item["record_id"]),
        }
        withdrawal_document = {
            "schema_version": "1.0.0",
            "id": "withdrawal-map:museum-03c-media-bundle-v1",
            "entity_type": "media_withdrawal_mapping",
            "branch_id": "art",
            "phase_id": PHASE_ID,
            "executor": PIPELINE_EXECUTOR,
            "human_review_dependency": False,
            "bundle_id": "media-bundle:museum-03c-v1",
            "mappings": sorted(withdrawals, key=lambda item: item["media_id"]),
            "procedure_url": "https://archmays.github.io/Museum-Codex/#/about",
            "generated_at": generated_at,
            "data_version": "1.0.0",
        }
        write_canonical_json(staged / "attributions.json", attribution_document)
        write_canonical_json(staged / "third-party-notices.json", notices_document)
        write_canonical_json(staged / "source-rules-snapshot.json", source_rules)
        write_canonical_json(staged / "discovery-source-profiles.json", {"profiles": [commons_profile()]})
        write_canonical_json(staged / "withdrawal-mapping.json", withdrawal_document)
        ledger = _ledger(inputs, collections, generated_at)
        ledger_bytes = canonical_json_bytes(ledger)
        manifest_files = _manifest_files(staged, collections, derivative_to_media)
        approved_media_ids = sorted(derivative_to_media.values())
        media_entries = [item for item in manifest_files if item["record_type"] == "media"]
        manifest = {
            "schema_version": "1.0.0",
            "id": "media-bundle:museum-03c-v1",
            "entity_type": "media_bundle_manifest",
            "branch_id": "art",
            "phase_id": PHASE_ID,
            "executor": PIPELINE_EXECUTOR,
            "human_review_dependency": False,
            "bundle_version": "1.0.0",
            "m03b_package_hash": inputs.manifest["content_hash"],
            "m03b_graph_hash": inputs.graph["content_hash"],
            "ledger_path": "data/reviewed/art/museum-03c/media-source-ledger.json",
            "ledger_sha256": "sha256:" + __import__("hashlib").sha256(ledger_bytes).hexdigest(),
            "manifest_files": manifest_files,
            "approved_media_ids": approved_media_ids,
            "counts": {
                "artworks_reviewed": 44,
                "approved_media": len(approved_media_ids),
                "media_files": len(media_entries),
                "media_bytes": sum(item["bytes"] for item in media_entries),
            },
            "attribution_path": "attributions.json",
            "notices_path": "third-party-notices.json",
            "source_rules_path": "source-rules-snapshot.json",
            "withdrawal_mapping_path": "withdrawal-mapping.json",
            "content_hash": "",
            "release_allowed": bool(approved_media_ids),
            "generated_at": generated_at,
            "data_version": "1.0.0",
        }
        manifest["content_hash"] = canonical_sha256(
            {key: value for key, value in manifest.items() if key != "content_hash"}
        )
        write_canonical_json(staged / "manifest.json", manifest)
        _validate_staged(staged, ledger)
        replace_generated(LEDGER_PATH, ledger)
        staged.rename(BUNDLE_ROOT)
    result = validate_bundle()
    if not result["ok"]:
        raise ValueError("installed M03C bundle failed validation: " + ", ".join(result["issues"][:8]))
    return {**result, "summary": "M03C derivatives, ledger and media bundle built", "reused": False}


def validate_bundle(root: Path = BUNDLE_ROOT, ledger_path: Path = LEDGER_PATH) -> dict[str, Any]:
    issues: list[str] = []
    if not root.is_dir() or root.is_symlink() or not ledger_path.is_file() or ledger_path.is_symlink():
        return {"ok": False, "issues": ["bundle_or_ledger_missing"], "counts": {}}
    try:
        manifest = load_json(root / "manifest.json")
        ledger = load_json(ledger_path)
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "issues": ["bundle_or_ledger_invalid_json"], "counts": {}}
    if not isinstance(manifest, dict) or not isinstance(ledger, dict):
        return {
            "ok": False,
            "issues": ["bundle_manifest_or_ledger_not_object"],
            "counts": {},
        }
    environment = load_schema_environment()
    issues.extend(f"manifest:{item.code}:{item.location}" for item in validate_record(manifest, environment=environment))
    issues.extend(f"ledger:{item.code}:{item.location}" for item in validate_record(ledger, environment=environment))
    manifest_items = manifest.get("manifest_files", [])
    if not isinstance(manifest_items, list):
        issues.append("manifest_files_not_array")
        manifest_items = []
    paths: list[str] = []
    for index, item in enumerate(manifest_items):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            issues.append(f"manifest_entry_path_invalid:{index}")
            continue
        paths.append(item["path"])
    if len(paths) != len(set(paths)):
        issues.append("manifest_duplicate_paths")
    declared = {item["path"]: item for item in manifest_items if isinstance(item, dict) and isinstance(item.get("path"), str)}
    for path in root.rglob("*"):
        if path.is_symlink():
            issues.append(f"bundle_symlink_forbidden:{path.relative_to(root).as_posix()}")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "manifest.json"}
    if set(declared) != actual:
        issues.append(f"physical_file_set_mismatch:missing={sorted(set(declared)-actual)}:extra={sorted(actual-set(declared))}")
    typed_records: dict[str, list[dict[str, Any]]] = {}
    documents: dict[str, Any] = {}
    resolved_root = root.resolve()
    for relative, item in declared.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError:
            issues.append(f"path_escape:{relative}")
            continue
        expected_contract = _manifest_file_contract(relative)
        if expected_contract is None:
            issues.append(f"undeclared_file_contract:{relative}")
        elif (item.get("record_type"), item.get("schema_path")) != expected_contract:
            issues.append(f"manifest_file_contract_mismatch:{relative}")
        expected_bytes = item.get("bytes")
        if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 0:
            issues.append(f"manifest_entry_bytes_invalid:{relative}")
        elif path.stat().st_size != expected_bytes:
            issues.append(f"bytes_mismatch:{relative}")
        expected_sha256 = item.get("sha256")
        if not isinstance(expected_sha256, str):
            issues.append(f"manifest_entry_sha256_invalid:{relative}")
        elif sha256_file(path) != expected_sha256:
            issues.append(f"hash_mismatch:{relative}")
        if relative.endswith(".json"):
            payload = path.read_bytes()
            try:
                document = json.loads(payload.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                issues.append(f"json_invalid:{relative}")
                continue
            if canonical_json_bytes(document) != payload:
                issues.append(f"noncanonical_json:{relative}")
            documents[relative] = document
            schema_path = item.get("schema_path")
            if schema_path:
                schema = environment.by_path.get(schema_path)
                if schema is None:
                    issues.append(f"schema_path_unknown:{relative}:{schema_path}")
                else:
                    validator = Draft202012Validator(
                        schema,
                        registry=environment.registry,
                        format_checker=FormatChecker(),
                    )
                    schema_documents = document if relative in _DATA_FILES and isinstance(document, list) else [document]
                    for index, schema_document in enumerate(schema_documents):
                        for error in validator.iter_errors(schema_document):
                            suffix = "/".join(str(part) for part in error.absolute_path) or "$"
                            location = f"{index}/{suffix}" if len(schema_documents) > 1 else suffix
                            issues.append(f"document_schema:{relative}:{location}:{error.validator}")
            records = document if isinstance(document, list) else [document]
            typed_records[relative] = [record for record in records if isinstance(record, dict) and record.get("entity_type")]
            for record in typed_records[relative]:
                issues.extend(
                    f"record:{relative}:{record.get('id')}:{problem.code}:{problem.location}"
                    for problem in validate_record(record, environment=environment)
                )
            observed_ids = _document_record_ids(relative, document)
            expected_record_ids = item.get("record_ids")
            if not isinstance(expected_record_ids, list):
                issues.append(f"manifest_entry_record_ids_invalid:{relative}")
            elif observed_ids != expected_record_ids:
                issues.append(f"record_ids_mismatch:{relative}")
    if sha256_file(ledger_path) != manifest.get("ledger_sha256"):
        issues.append("ledger_hash_mismatch")
    if manifest.get("content_hash") != canonical_sha256(
        {key: value for key, value in manifest.items() if key != "content_hash"}
    ):
        issues.append("manifest_content_hash_mismatch")
    if ledger.get("content_hash") != canonical_sha256({key: value for key, value in ledger.items() if key != "content_hash"}):
        issues.append("ledger_content_hash_mismatch")
    try:
        _validate_bundle_semantics(manifest, ledger, declared, documents, typed_records, root, issues)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        issues.append(f"bundle_semantic_structure_invalid:{type(error).__name__}")
    return {"ok": not issues, "issues": sorted(set(issues)), "counts": manifest.get("counts", {}), "bundle_content_hash": manifest.get("content_hash")}


def _manifest_file_contract(relative: str) -> tuple[str, str | None] | None:
    if relative in _DATA_FILES:
        return "data", _DATA_FILES[relative][1]
    if relative in _SPECIAL_FILE_SCHEMAS:
        return _SPECIAL_FILE_SCHEMAS[relative]
    if relative.startswith("assets/") and relative.endswith((".jpg", ".webp", ".avif")):
        return "media", None
    return None


def _document_record_ids(relative: str, document: Any) -> list[str]:
    if isinstance(document, list):
        return [item["id"] for item in document if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if not isinstance(document, dict):
        return []
    if relative == "attributions.json":
        return [item["asset_id"] for item in document.get("assets", [])]
    if relative == "third-party-notices.json":
        return [item["record_id"] for item in document.get("notices", [])]
    if relative == "source-rules-snapshot.json":
        return [document["snapshot_id"]] if isinstance(document.get("snapshot_id"), str) else []
    if relative == "discovery-source-profiles.json":
        return [item["source_id"] for item in document.get("profiles", []) if isinstance(item, dict)]
    if relative == "withdrawal-mapping.json":
        return [document["id"]] if isinstance(document.get("id"), str) else []
    return [document["id"]] if isinstance(document.get("id"), str) else []


def _record_index(records: list[dict[str, Any]], label: str, issues: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            issues.append(f"record_id_missing:{label}")
            continue
        if record_id in result:
            issues.append(f"record_id_duplicate:{label}:{record_id}")
        result[record_id] = record
    return result


def _validate_bundle_semantics(
    manifest: dict[str, Any],
    ledger: dict[str, Any],
    declared: dict[str, dict[str, Any]],
    documents: dict[str, Any],
    typed_records: dict[str, list[dict[str, Any]]],
    root: Path,
    issues: list[str],
) -> None:
    if manifest.get("m03b_package_hash") != EXPECTED_M03B_PACKAGE_HASH:
        issues.append("manifest_m03b_package_hash_mismatch")
    if manifest.get("m03b_graph_hash") != EXPECTED_M03B_GRAPH_HASH:
        issues.append("manifest_m03b_graph_hash_mismatch")
    if ledger.get("m03b_package_hash") != EXPECTED_M03B_PACKAGE_HASH:
        issues.append("ledger_m03b_package_hash_mismatch")
    if ledger.get("m03b_graph_hash") != EXPECTED_M03B_GRAPH_HASH:
        issues.append("ledger_m03b_graph_hash_mismatch")
    if manifest.get("ledger_path") != "data/reviewed/art/museum-03c/media-source-ledger.json":
        issues.append("ledger_path_mismatch")
    expected_special_paths = {
        "attribution_path": "attributions.json",
        "notices_path": "third-party-notices.json",
        "source_rules_path": "source-rules-snapshot.json",
        "withdrawal_mapping_path": "withdrawal-mapping.json",
    }
    for field, expected in expected_special_paths.items():
        if manifest.get(field) != expected:
            issues.append(f"manifest_special_path_mismatch:{field}")

    try:
        inputs = load_media_inputs()
    except ValueError as error:
        issues.append(f"m03b_input_validation_failed:{error}")
        return
    expected_artwork_ids = {item["id"] for item in inputs.artworks}
    requests = _record_index(typed_records.get("acquisition-requests.json", []), "requests", issues)
    events = _record_index(typed_records.get("acquisition-events.json", []), "events", issues)
    byte_records = _record_index(typed_records.get("byte-records.json", []), "bytes", issues)
    crosses = _record_index(typed_records.get("identity-rights-cross-checks.json", []), "crosses", issues)
    qualities = _record_index(typed_records.get("quality-assessments.json", []), "qualities", issues)
    reviews = _record_index(typed_records.get("automated-reviews.json", []), "reviews", issues)
    derivatives = _record_index(typed_records.get("derivative-records.json", []), "derivatives", issues)
    alternatives = _record_index(typed_records.get("alternative-source-searches.json", []), "alternatives", issues)

    if {item.get("artwork_id") for item in requests.values()} != expected_artwork_ids or len(requests) != 44:
        issues.append("request_artwork_closure_mismatch")
    request_by_artwork = {item.get("artwork_id"): item for item in requests.values()}
    byte_by_artwork = {item.get("artwork_id"): item for item in byte_records.values()}
    cross_by_artwork = {item.get("artwork_id"): item for item in crosses.values()}
    quality_by_artwork = {item.get("artwork_id"): item for item in qualities.values()}
    review_by_artwork = {item.get("artwork_id"): item for item in reviews.values()}
    alternative_by_artwork = {item.get("artwork_id"): item for item in alternatives.values()}
    derivative_by_artwork: dict[str, list[dict[str, Any]]] = {}
    for derivative in derivatives.values():
        derivative_by_artwork.setdefault(str(derivative.get("artwork_id")), []).append(derivative)
    if {item.get("sha256") for item in byte_records.values()} != _M03C_V1_SOURCE_SHA256:
        issues.append("byte_source_transform_evidence_closure_mismatch")

    for byte_record in byte_records.values():
        request = requests.get(byte_record.get("request_id"))
        event = events.get(byte_record.get("event_id"))
        if request is None or request.get("artwork_id") != byte_record.get("artwork_id"):
            issues.append(f"byte_request_reference_mismatch:{byte_record['id']}")
        if (
            event is None
            or event.get("request_id") != byte_record.get("request_id")
            or event.get("artwork_id") != byte_record.get("artwork_id")
            or event.get("event_type") != "download_completed"
            or event.get("terminal") is not True
            or event.get("status_code") != 200
            or event.get("body_sha256") != byte_record.get("sha256")
            or event.get("bytes_received") != byte_record.get("byte_length")
            or event.get("final_url") != byte_record.get("final_url")
        ):
            issues.append(f"byte_event_reference_mismatch:{byte_record['id']}")

    for artwork_id in expected_artwork_ids:
        request = request_by_artwork.get(artwork_id)
        cross = cross_by_artwork.get(artwork_id)
        review = review_by_artwork.get(artwork_id)
        byte_record = byte_by_artwork.get(artwork_id)
        quality = quality_by_artwork.get(artwork_id)
        alternative = alternative_by_artwork.get(artwork_id)
        if request is None or cross is None or review is None:
            issues.append(f"artwork_terminal_record_missing:{artwork_id}")
            continue
        expected_byte_id = byte_record["id"] if byte_record else None
        expected_quality_id = quality["id"] if quality else None
        expected_alternative_id = alternative["id"] if alternative else None
        if cross.get("byte_record_id") != expected_byte_id:
            issues.append(f"cross_byte_reference_mismatch:{cross['id']}")
        if quality is not None:
            if quality.get("byte_record_id") != expected_byte_id or quality.get("artwork_id") != artwork_id:
                issues.append(f"quality_byte_reference_mismatch:{quality['id']}")
            if (
                quality.get("metrics", {}).get("width") != byte_record.get("width")
                or quality.get("metrics", {}).get("height") != byte_record.get("height")
                or quality.get("metrics", {}).get("pixels") != byte_record.get("pixels")
                or quality.get("metrics", {}).get("phash") != byte_record.get("phash")
            ):
                issues.append(f"quality_metric_reference_mismatch:{quality['id']}")
        if (
            review.get("cross_check_id") != cross.get("id")
            or review.get("byte_record_id") != expected_byte_id
            or review.get("quality_assessment_id") != expected_quality_id
            or review.get("alternative_source_search_id") != expected_alternative_id
        ):
            issues.append(f"review_reference_mismatch:{review['id']}")
        expected_derivatives = sorted(
            item["id"] for item in derivative_by_artwork.get(artwork_id, [])
        )
        if sorted(review.get("derivative_ids", [])) != expected_derivatives:
            issues.append(f"review_derivative_reference_mismatch:{review['id']}")
        if review.get("decision") == "approved_self_hosted":
            if not byte_record or not quality or quality.get("quality_status") not in {"pass", "low_resolution"}:
                issues.append(f"approved_review_missing_quality_closure:{review['id']}")
            if cross.get("closure_status") != "pass" or review.get("mandatory_closure") != {
                "identity": "pass", "rights": "pass", "bytes": "pass", "quality": "pass"
            }:
                issues.append(f"approved_review_mandatory_closure_mismatch:{review['id']}")
        elif expected_derivatives:
            issues.append(f"blocked_or_metadata_review_has_derivatives:{review['id']}")

    for derivative in derivatives.values():
        parent = byte_records.get(derivative.get("parent_byte_record_id"))
        if (
            parent is None
            or parent.get("artwork_id") != derivative.get("artwork_id")
            or derivative.get("source_sha256") != parent.get("sha256")
        ):
            issues.append(f"derivative_parent_reference_mismatch:{derivative['id']}")
        expected_transform_steps = _expected_derivative_transform_steps(parent, derivative)
        if (
            expected_transform_steps is None
            or derivative.get("transform_version") != PROCESSOR_VERSION
            or derivative.get("transform_steps") != expected_transform_steps
        ):
            issues.append(f"derivative_transform_closure_mismatch:{derivative['id']}")
        target = root / str(derivative.get("storage_path", ""))
        if (
            not target.is_file()
            or target.is_symlink()
            or sha256_file(target) != derivative.get("sha256")
            or target.stat().st_size != derivative.get("byte_length")
        ):
            issues.append(f"derivative_physical_mismatch:{derivative['id']}")
        media_id = derivative["id"].replace("media-derivative:", "media:")
        manifest_entry = declared.get(str(derivative.get("storage_path")))
        if manifest_entry is None or manifest_entry.get("record_ids") != [media_id]:
            issues.append(f"derivative_manifest_reference_mismatch:{derivative['id']}")

    approved_derivative_ids = {
        derivative_id
        for review in reviews.values()
        if review.get("decision") == "approved_self_hosted"
        for derivative_id in review.get("derivative_ids", [])
    }
    if set(derivatives) != approved_derivative_ids:
        issues.append("review_derivative_closure_mismatch")
    media_ids = {item.replace("media-derivative:", "media:") for item in derivatives}
    if media_ids != set(manifest.get("approved_media_ids", [])):
        issues.append("approved_media_id_mismatch")

    _validate_rights_documents(documents, inputs, byte_by_artwork, cross_by_artwork, derivatives, media_ids, issues)
    _validate_ledger_and_counts(
        manifest,
        ledger,
        request_by_artwork,
        byte_by_artwork,
        cross_by_artwork,
        quality_by_artwork,
        review_by_artwork,
        derivative_by_artwork,
        declared,
        issues,
    )


def _validate_rights_documents(
    documents: dict[str, Any],
    inputs: Any,
    byte_by_artwork: dict[str, dict[str, Any]],
    cross_by_artwork: dict[str, dict[str, Any]],
    derivatives: dict[str, dict[str, Any]],
    media_ids: set[str],
    issues: list[str],
) -> None:
    attributions = documents.get("attributions.json", {}).get("assets", [])
    notices = documents.get("third-party-notices.json", {}).get("notices", [])
    mappings = documents.get("withdrawal-mapping.json", {}).get("mappings", [])
    attribution_by_id = {item.get("asset_id"): item for item in attributions}
    notice_by_id = {item.get("record_id"): item for item in notices}
    mapping_by_id = {item.get("media_id"): item for item in mappings}
    if set(attribution_by_id) != media_ids:
        issues.append("attribution_closure_mismatch")
    if set(notice_by_id) != media_ids:
        issues.append("notices_closure_mismatch")
    if set(mapping_by_id) != media_ids:
        issues.append("withdrawal_closure_mismatch")
    derivative_by_media = {
        item["id"].replace("media-derivative:", "media:"): item for item in derivatives.values()
    }
    for media_id, derivative in derivative_by_media.items():
        artwork_id = derivative["artwork_id"]
        byte_record = byte_by_artwork.get(artwork_id, {})
        cross = cross_by_artwork.get(artwork_id, {})
        rights = cross.get("rights", {})
        license_record = rights.get("license", {})
        attribution = attribution_by_id.get(media_id, {})
        notice = notice_by_id.get(media_id, {})
        mapping = mapping_by_id.get(media_id, {})
        if (
            attribution.get("attribution") != rights.get("attribution")
            or attribution.get("license_identifier") != license_record.get("identifier")
            or attribution.get("license_url") != license_record.get("url")
            or attribution.get("source_url") != byte_record.get("source_url")
        ):
            issues.append(f"attribution_rights_mismatch:{media_id}")
        if attribution.get("changes_statement") != _CANONICAL_CHANGES_STATEMENT:
            issues.append(f"attribution_changes_statement_mismatch:{media_id}")
        if (
            notice.get("source_url") != byte_record.get("source_url")
            or notice.get("license_rule_ids") != [rights.get("source_rule_id")]
            or notice.get("license_identifiers") != [license_record.get("identifier")]
            or notice.get("attribution_texts") != [rights.get("attribution")]
        ):
            issues.append(f"notice_rights_mismatch:{media_id}")
        if (
            mapping.get("artwork_id") != artwork_id
            or mapping.get("derivative_paths") != [derivative.get("storage_path")]
            or mapping.get("source_id") != byte_record.get("source_id")
            or mapping.get("rights_record_id") != cross.get("id")
            or mapping.get("status") != "active"
        ):
            issues.append(f"withdrawal_mapping_mismatch:{media_id}")

    snapshot = documents.get("source-rules-snapshot.json", {})
    source_by_id = {
        item["id"]: item
        for item in json.loads((inputs.package_root / "sources.json").read_text(encoding="utf-8"))
    }
    expected_sources = {}
    for source_id in ("source:aic_api", "source:met_open_access"):
        source = source_by_id[source_id]
        rules = [rule for rule in source["license_rules"] if rule["content_class"] == "media"]
        expected_sources[source_id] = {
            "source_id": source_id,
            "registry_source_id": source["registry_source_id"],
            "registry_identity": source["registry_identity"],
            "license_rules_snapshot_hash": canonical_sha256(rules),
            "license_rules": rules,
        }
    observed_sources = {item.get("source_id"): item for item in snapshot.get("sources", [])}
    if observed_sources != expected_sources:
        issues.append("source_rules_canonical_binding_mismatch")
    valid_rule_ids = {
        rule["rule_id"]
        for source in expected_sources.values()
        for rule in source["license_rules"]
    }
    for cross in cross_by_artwork.values():
        if cross.get("closure_status") == "pass" and cross.get("rights", {}).get("source_rule_id") not in valid_rule_ids:
            issues.append(f"cross_source_rule_unbound:{cross['id']}")
    if documents.get("discovery-source-profiles.json") != {"profiles": [commons_profile()]}:
        issues.append("discovery_source_profile_mismatch")


def _validate_ledger_and_counts(
    manifest: dict[str, Any],
    ledger: dict[str, Any],
    request_by_artwork: dict[str, dict[str, Any]],
    byte_by_artwork: dict[str, dict[str, Any]],
    cross_by_artwork: dict[str, dict[str, Any]],
    quality_by_artwork: dict[str, dict[str, Any]],
    review_by_artwork: dict[str, dict[str, Any]],
    derivative_by_artwork: dict[str, list[dict[str, Any]]],
    declared: dict[str, dict[str, Any]],
    issues: list[str],
) -> None:
    entries = ledger.get("entries", [])
    ledger_by_artwork = {item.get("artwork_id"): item for item in entries}
    if len(entries) != 44 or len(ledger_by_artwork) != 44 or set(ledger_by_artwork) != set(review_by_artwork):
        issues.append("ledger_artwork_closure_mismatch")
    for artwork_id, review in review_by_artwork.items():
        entry = ledger_by_artwork.get(artwork_id, {})
        byte_record = byte_by_artwork.get(artwork_id)
        quality = quality_by_artwork.get(artwork_id)
        derivatives = sorted(derivative_by_artwork.get(artwork_id, []), key=lambda item: item["id"])
        if (
            entry.get("request_id") != request_by_artwork[artwork_id]["id"]
            or entry.get("byte_record_id") != (byte_record["id"] if byte_record else None)
            or entry.get("cross_check_id") != cross_by_artwork[artwork_id]["id"]
            or entry.get("quality_assessment_id") != (quality["id"] if quality else None)
            or entry.get("review_id") != review["id"]
            or entry.get("final_decision") != review["decision"]
            or entry.get("original_bytes") != (byte_record["byte_length"] if byte_record else 0)
            or entry.get("derivative_ids") != [item["id"] for item in derivatives]
        ):
            issues.append(f"ledger_entry_reference_mismatch:{artwork_id}")
    decision_counts = Counter(item["decision"] for item in review_by_artwork.values())
    expected_counts = {
        decision: decision_counts.get(decision, 0)
        for decision in (
            "approved_self_hosted", "approved_external_delivery", "metadata_only_after_automated_review",
            "blocked_rights_conflict", "blocked_identity_conflict", "blocked_quality_failure",
            "blocked_source_unavailable",
        )
    }
    derivatives = [item for values in derivative_by_artwork.values() for item in values]
    expected_ledger = {
        "counts": expected_counts,
        "original_downloads": len(byte_by_artwork),
        "original_bytes": sum(item["byte_length"] for item in byte_by_artwork.values()),
        "derivative_count": len(derivatives),
        "derivative_bytes": sum(item["byte_length"] for item in derivatives),
    }
    for field, expected in expected_ledger.items():
        if ledger.get(field) != expected:
            issues.append(f"ledger_derived_count_mismatch:{field}")
    media_entries = [item for item in declared.values() if item.get("record_type") == "media"]
    expected_manifest_counts = {
        "artworks_reviewed": len(review_by_artwork),
        "approved_media": len(derivatives),
        "media_files": len(media_entries),
        "media_bytes": sum(
            item.get("bytes", 0)
            for item in media_entries
            if isinstance(item.get("bytes"), int) and not isinstance(item.get("bytes"), bool)
        ),
    }
    if manifest.get("counts") != expected_manifest_counts:
        issues.append("manifest_derived_counts_mismatch")
    if manifest.get("release_allowed") is not bool(derivatives):
        issues.append("release_allowed_mismatch")


def _expected_derivative_transform_steps(
    parent: dict[str, Any] | None,
    derivative: dict[str, Any],
) -> list[str] | None:
    if parent is None:
        return None
    source_sha256 = parent.get("sha256")
    if source_sha256 not in _M03C_V1_SOURCE_SHA256:
        return None
    steps = {"compression", "metadata_safe_strip"}
    if source_sha256 in _M03C_V1_ICC_SOURCE_SHA256:
        steps.add("icc_normalization")
    if (derivative.get("width"), derivative.get("height")) != (
        parent.get("width"),
        parent.get("height"),
    ):
        steps.add("resize")
    return sorted(steps)


def _derivative_records(
    artwork_id: str,
    byte_record: dict[str, Any],
    built: dict[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    slug = artwork_slug(artwork_id)
    records: list[dict[str, Any]] = []
    for item in built["generated"]:
        format_name = "jpeg" if item["format"] == "JPEG" else item["format"].lower()
        transform = item["transform"]
        steps = ["metadata_safe_strip", "compression"]
        if transform["orientation"] != "identity":
            steps.insert(0, "orientation")
        if transform["color"] == "icc_to_srgb":
            steps.append("icc_normalization")
        if transform["resize"] != "identity":
            steps.append("resize")
        records.append(
            {
                "schema_version": "1.0.0",
                "id": f"media-derivative:{slug}-{item['width']}w-{format_name}",
                "entity_type": "media_derivative_record",
                "branch_id": "art",
                "phase_id": PHASE_ID,
                "executor": PIPELINE_EXECUTOR,
                "human_review_dependency": False,
                "artwork_id": artwork_id,
                "parent_byte_record_id": byte_record["id"],
                "source_sha256": item["source_sha256"],
                "format": format_name,
                "width": item["width"],
                "height": item["height"],
                "byte_length": item["bytes"],
                "sha256": item["sha256"],
                "storage_path": f"assets/{slug}/{item['path']}",
                "transform_steps": sorted(set(steps)),
                "transform_version": PROCESSOR_VERSION,
                "rights_modification_allowed": True,
                "upscaled": False,
                "ai_used": False,
                "content_altered": False,
                "watermark_removed": False,
                "generated_at": generated_at,
                "data_version": "1.0.0",
            }
        )
    return records


def _verified_source_bytes(source_path: Path, byte_record: dict[str, Any]) -> bytes:
    if not source_path.is_file() or source_path.is_symlink():
        raise ValueError(f"approved source is missing or unsafe for {byte_record['artwork_id']}")
    source_bytes = source_path.read_bytes()
    if len(source_bytes) != byte_record["byte_length"] or sha256_file(source_path) != byte_record["sha256"]:
        raise ValueError(f"source bytes drifted after automated review for {byte_record['artwork_id']}")
    return source_bytes


def _source_rules_snapshot(source_by_id: dict[str, dict[str, Any]], generated_at: str) -> dict[str, Any]:
    sources = []
    for source_id in ("source:aic_api", "source:met_open_access"):
        source = source_by_id[source_id]
        media_rules = [rule for rule in source["license_rules"] if rule["content_class"] == "media"]
        sources.append(
            {
                "source_id": source_id,
                "registry_source_id": source["registry_source_id"],
                "registry_identity": source["registry_identity"],
                "license_rules_snapshot_hash": canonical_sha256(media_rules),
                "license_rules": media_rules,
            }
        )
    return {
        "schema_version": "1.0.0",
        "snapshot_id": "source-rules-snapshot:museum-03c-media-bundle-v1",
        "generated_at": generated_at,
        "sources": sources,
    }


def _ledger(inputs, collections: dict[str, list[dict[str, Any]]], generated_at: str) -> dict[str, Any]:  # noqa: ANN001
    reviews = {item["artwork_id"]: item for item in collections["automated-reviews.json"]}
    bytes_by_artwork = {item["artwork_id"]: item for item in collections["byte-records.json"]}
    quality_by_artwork = {item["artwork_id"]: item for item in collections["quality-assessments.json"]}
    cross_by_artwork = {item["artwork_id"]: item for item in collections["identity-rights-cross-checks.json"]}
    assessment_by_artwork = inputs.assessment_by_artwork
    derivative_by_artwork: dict[str, list[dict[str, Any]]] = {}
    for derivative in collections["derivative-records.json"]:
        derivative_by_artwork.setdefault(derivative["artwork_id"], []).append(derivative)
    entries = []
    counts: Counter[str] = Counter()
    for artwork in sorted(inputs.artworks, key=lambda item: item["id"]):
        review = reviews[artwork["id"]]
        byte_record = bytes_by_artwork.get(artwork["id"])
        quality = quality_by_artwork.get(artwork["id"])
        derivatives = sorted(derivative_by_artwork.get(artwork["id"], []), key=lambda item: item["id"])
        counts[review["decision"]] += 1
        entries.append(
            {
                "artwork_id": artwork["id"],
                "source_id": artwork["official_object_record"]["source_id"],
                "baseline_outcome": assessment_by_artwork[artwork["id"]]["outcome"],
                "request_id": f"media-request:{artwork_slug(artwork['id'])}",
                "byte_record_id": byte_record["id"] if byte_record else None,
                "cross_check_id": cross_by_artwork[artwork["id"]]["id"],
                "quality_assessment_id": quality["id"] if quality else None,
                "review_id": review["id"],
                "final_decision": review["decision"],
                "original_bytes": byte_record["byte_length"] if byte_record else 0,
                "derivative_ids": [item["id"] for item in derivatives],
                "error_codes": review["decision_reason_codes"] if review["decision"].startswith("blocked_") else [],
            }
        )
    payload = {
        "schema_version": "1.0.0",
        "id": "media-ledger:museum-03c-v1",
        "entity_type": "media_source_ledger",
        "branch_id": "art",
        "phase_id": PHASE_ID,
        "executor": PIPELINE_EXECUTOR,
        "human_review_dependency": False,
        "m03b_package_hash": inputs.manifest["content_hash"],
        "m03b_graph_hash": inputs.graph["content_hash"],
        "total_artworks": 44,
        "entries": entries,
        "counts": {decision: counts.get(decision, 0) for decision in (
            "approved_self_hosted", "approved_external_delivery", "metadata_only_after_automated_review",
            "blocked_rights_conflict", "blocked_identity_conflict", "blocked_quality_failure", "blocked_source_unavailable",
        )},
        "original_downloads": len(bytes_by_artwork),
        "original_bytes": sum(item["byte_length"] for item in bytes_by_artwork.values()),
        "derivative_count": len(collections["derivative-records.json"]),
        "derivative_bytes": sum(item["byte_length"] for item in collections["derivative-records.json"]),
        "content_hash": "",
        "generated_at": generated_at,
        "data_version": "1.0.0",
    }
    payload["content_hash"] = canonical_sha256({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def _manifest_files(
    staged: Path,
    collections: dict[str, list[dict[str, Any]]],
    derivative_to_media: dict[str, str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    special = {
        "attributions.json": ("attributions", "schemas/common/attribution-manifest.schema.json", sorted(derivative_to_media.values())),
        "third-party-notices.json": ("notices", "schemas/common/third-party-notices.schema.json", sorted(derivative_to_media.values())),
        "source-rules-snapshot.json": ("source_rules", "schemas/common/source-rules-snapshot.schema.json", ["source-rules-snapshot:museum-03c-media-bundle-v1"]),
        "discovery-source-profiles.json": ("source_rules", None, ["source:wikimedia_commons"]),
        "withdrawal-mapping.json": ("withdrawals", "schemas/art/media/withdrawal-mapping.schema.json", ["withdrawal-map:museum-03c-media-bundle-v1"]),
    }
    for name, (_, schema_path) in _DATA_FILES.items():
        path = staged / name
        records = collections[name]
        entries.append(_manifest_entry(path, staged, "data", schema_path, [item["id"] for item in records]))
    for name, (record_type, schema_path, record_ids) in special.items():
        entries.append(_manifest_entry(staged / name, staged, record_type, schema_path, record_ids))
    derivative_by_path = {item["storage_path"]: item for item in collections["derivative-records.json"]}
    for relative, derivative in sorted(derivative_by_path.items()):
        media_id = derivative_to_media[derivative["id"]]
        entries.append(_manifest_entry(staged / relative, staged, "media", None, [media_id]))
    return sorted(entries, key=lambda item: item["path"])


def _manifest_entry(
    path: Path,
    root: Path,
    record_type: str,
    schema_path: str | None,
    record_ids: list[str],
) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "record_type": record_type,
        "schema_path": schema_path,
        "record_ids": record_ids,
    }


def _validate_staged(staged: Path, ledger: dict[str, Any]) -> None:
    environment = load_schema_environment()
    for name, (_, schema_path) in _DATA_FILES.items():
        for record in load_json(staged / name):
            problems = validate_record(record, environment=environment)
            if problems:
                raise ValueError(f"staged {name} schema failure: {problems[0].location} {problems[0].message}")
    for name, schema_path in (
        ("attributions.json", "schemas/common/attribution-manifest.schema.json"),
        ("third-party-notices.json", "schemas/common/third-party-notices.schema.json"),
        ("source-rules-snapshot.json", "schemas/common/source-rules-snapshot.schema.json"),
        ("withdrawal-mapping.json", "schemas/art/media/withdrawal-mapping.schema.json"),
    ):
        schema = environment.by_path[schema_path]
        errors = list(Draft202012Validator(schema, registry=environment.registry, format_checker=FormatChecker()).iter_errors(load_json(staged / name)))
        if errors:
            raise ValueError(f"staged {name} schema failure: {errors[0].message}")
    ledger_problems = validate_record(ledger, environment=environment)
    if ledger_problems:
        raise ValueError(f"staged ledger schema failure: {ledger_problems[0].location} {ledger_problems[0].message}")
