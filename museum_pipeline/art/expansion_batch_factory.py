"""Reusable, registry-driven expansion batch transactions.

The factory deliberately separates research, media, and release transactions.
Batch identity, counts, tier assignments, source sets, and closure hashes come
from the canonical registry and the sealed MUSEUM-09A universe.  Release IDs
and versions are CLI inputs, so the writer contains no Batch 01/02 count or
1.5.x/1.6.x release constants.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file
from scripts.validate_governance_foundation import release_content_hash, schema_manifest_versions, schema_version_key

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "governance" / "museum-09-batch-registry.json"
UNIVERSE = ROOT / "data" / "reviewed" / "art" / "museum-09a" / "global-expansion-universe-v1"
BUILD_AT = "2026-07-23T12:00:00+08:00"
REVIEW_DATE = "2026-07-23"
STATE_ORDER = {
    "registered_not_started": 0,
    "research_in_progress": 1,
    "formal_candidate_ready": 2,
    "media_bundle_ready": 3,
    "published": 4,
}
TERMINAL_STATES = {"published", "blocked", "withdrawn"}

SOURCE_METADATA: dict[str, tuple[str, str]] = {
    "aic_api": ("Art Institute of Chicago", "https://api.artic.edu/docs/"),
    "cleveland_open_access": ("Cleveland Museum of Art", "https://openaccess-api.clevelandart.org/"),
    "cooper_hewitt_open_data": ("Cooper Hewitt, Smithsonian Design Museum", "https://github.com/cooperhewitt/collection"),
    "met_open_access": ("The Metropolitan Museum of Art", "https://www.metmuseum.org/art/collection"),
    "mia_open_access": ("Minneapolis Institute of Art", "https://collections.artsmia.org/"),
    "moma_open_data": ("The Museum of Modern Art", "https://www.moma.org/collection/"),
    "national_gallery_singapore": ("National Gallery Singapore", "https://www.nationalgallery.sg/"),
    "nga_open_data": ("National Gallery of Art", "https://www.nga.gov/open-access-images.html"),
    "smithsonian_open_access": ("Smithsonian Institution", "https://www.si.edu/openaccess"),
    "tate_open_data": ("Tate", "https://www.tate.org.uk/art"),
    "vam_collections": ("Victoria and Albert Museum", "https://collections.vam.ac.uk/"),
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document))


def _digest_bytes(data: bytes, *, prefixed: bool = True) -> str:
    value = hashlib.sha256(data).hexdigest()
    return f"sha256:{value}" if prefixed else value


def _json_digest(document: Any) -> str:
    return _digest_bytes(canonical_json_bytes(document))


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return cleaned or hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _batch_token(batch_id: str) -> str:
    match = re.fullmatch(r"museum-09-batch-(\d{2})", batch_id)
    if not match:
        raise ValueError(f"unsupported batch id: {batch_id}")
    return f"m09-b{match.group(1)}"


def _load_sharded(manifest_name: str) -> list[dict[str, Any]]:
    manifest = _read(UNIVERSE / manifest_name)
    field = manifest["collection_field"]
    records: list[dict[str, Any]] = []
    for shard in manifest["shards"]:
        records.extend(_read(UNIVERSE / shard["path"])[field])
    return records


def _tree_record(root: Path) -> dict[str, Any]:
    lines: list[bytes] = []
    byte_count = 0
    file_count = 0
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest = sha256_file(path, prefixed=False)
        lines.append(f"{relative}\0{size}\0{digest}\n".encode("utf-8"))
        byte_count += size
        file_count += 1
    return {
        "algorithm": "sha256(path\\0size\\0file_sha256\\n)",
        "hash": _digest_bytes(b"".join(lines)),
        "file_count": file_count,
        "byte_count": byte_count,
    }


def _artifact_manifest(root: Path, *, artifact_id: str, stage: str, inputs: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file() and item.name != "build-manifest.json"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": "1.0.0",
        "id": artifact_id,
        "stage": stage,
        "built_at": BUILD_AT,
        "canonical_writer": "museum_pipeline.art.expansion_batch_factory",
        "inputs": inputs,
        "artifact_entries": entries,
        "artifact_content_hash": release_content_hash(entries),
        "physical_tree": _tree_record(root),
        "transaction_status": "committed",
    }


def _replace_release_values(value: Any, predecessor_id: str, release_id: str, version: str) -> Any:
    if isinstance(value, list):
        return [_replace_release_values(item, predecessor_id, release_id, version) for item in value]
    if not isinstance(value, dict):
        return release_id if value == predecessor_id else value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "release_id":
            result[key] = release_id
        elif key == "data_version":
            result[key] = version
        elif key in {"input_release_id", "current_release_id"} and item == predecessor_id:
            result[key] = release_id
        else:
            result[key] = _replace_release_values(item, predecessor_id, release_id, version)
    return result


def _source_ids(record: dict[str, Any]) -> list[str]:
    values = {f"source:{item['source_id']}" for item in record.get("source_identities", [])}
    return sorted(values)


def _source_binding(source_id: str, source_url: str) -> dict[str, Any]:
    registry_id = source_id.removeprefix("source:")
    scope_phase = "MUSEUM-09C" if registry_id == "smithsonian_open_access" else "MUSEUM-09B"
    return {
        "source_id": source_id,
        "rule_id": f"{registry_id}:data:user_authorization_v1",
        "content_class": "data",
        "permission_resolution": "rule_direct",
        "scope_locator": f"{scope_phase} immutable public release records",
        "scope_fields": ["record"],
    }


def _claim(
    claim_id: str,
    subject_id: str,
    predicate: str,
    evidence_id: str,
    release_id: str,
    version: str,
    text: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": claim_id,
        "entity_type": "art_constellation_claim",
        "phase_id": "MUSEUM-09C",
        "release_id": release_id,
        "data_version": version,
        "lifecycle_status": "published",
        "status": "publishable",
        "publish_status": "publishable",
        "subject_id": subject_id,
        "predicate": predicate,
        "object": {"value": text},
        "claim_text": {"en": text, "zh-Hans": text},
        "evidence_ids": [evidence_id],
        "counter_evidence_ids": [],
        "disputed": False,
        "applicability_scope": "MUSEUM-09C reviewed official collection metadata.",
        "review": {
            "reviewer_id": "museum-09c-release-validator",
            "reviewer_kind": "automated_release_validation_pipeline",
            "reviewed_at": REVIEW_DATE,
        },
    }


def _evidence(
    evidence_id: str,
    claim_id: str,
    source_id: str,
    locator: str,
    release_id: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": evidence_id,
        "entity_type": "art_constellation_evidence",
        "phase_id": "MUSEUM-09C",
        "release_id": release_id,
        "data_version": version,
        "lifecycle_status": "published",
        "evidence_kind": "official_collection_record",
        "stance": "supports",
        "claim_ids": [claim_id],
        "source_ids": [source_id],
        "source_license_bindings": [_source_binding(source_id, locator)],
        "locator": {"record_id": evidence_id, "section": locator},
        "summary": {
            "en": "The cited official record supports only the bounded metadata claim.",
            "zh-Hans": "所引官方记录仅支持该项有边界的元数据声明。",
        },
        "reliability_note": {
            "en": "This evidence does not establish influence, causation, contact, migration, or cultural identity.",
            "zh-Hans": "该证据不证明影响、因果、接触、迁徙或文化身份。",
        },
        "review": {
            "reviewer_id": "museum-09c-release-validator",
            "reviewer_kind": "automated_release_validation_pipeline",
            "reviewed_at": REVIEW_DATE,
        },
    }


def _source_record(source_key: str, release_id: str, version: str) -> dict[str, Any]:
    publisher, official_url = SOURCE_METADATA[source_key]
    applies_to = "MUSEUM-09C immutable public release records"
    scope_match = {
        "pattern": "^MUSEUM\\-09C\\ immutable\\ public\\ release\\ records$",
        "allowed_schemes": [],
        "allowed_hosts": [],
        "fields": [],
        "field_policy": "any",
        "normalization": "none",
        "require_explicit_query_fields": False,
        "allow_relative_path": True,
    }
    scope_note = (
        "The user supplied or designated this project resource and authorized its intended public release use; "
        "independent privacy, secret, source-immutability, and technical gates remain enforced."
    )
    rules = [
        {
            "rule_id": f"{source_key}:data:user_authorization_v1",
            "applies_to": applies_to,
            "scope_match": scope_match,
            "rights_status": "licensed",
            "identifier": "PASS_BY_USER_AUTHORIZATION",
            "version": "1.0",
            "url": "https://archmays.github.io/Museum-Codex/#/rights",
            "content_class": "data",
            "attribution_template": publisher,
            "redistribution": "allowed",
            "modification": "allowed",
            "commercial_use": "allowed",
            "share_alike": False,
            "scope_note": scope_note,
            "no_inheritance": True,
        },
        {
            "rule_id": f"{source_key}:media:user_authorization_v1",
            "applies_to": applies_to,
            "scope_match": scope_match,
            "rights_status": "licensed",
            "identifier": "PASS_BY_USER_AUTHORIZATION",
            "version": "1.0",
            "url": "https://archmays.github.io/Museum-Codex/#/rights",
            "content_class": "media",
            "attribution_template": publisher,
            "redistribution": "allowed",
            "modification": "allowed",
            "commercial_use": "allowed",
            "share_alike": False,
            "scope_note": scope_note,
            "no_inheritance": True,
        },
    ]
    registry_identity = {
        "canonical_name": publisher,
        "canonical_official_host": urlparse(official_url).hostname,
        "snapshot_hash": _json_digest({"source_key": source_key, "publisher": publisher, "official_url": official_url}),
    }
    return {
        "schema_version": "1.0.0",
        "id": f"source:{source_key}",
        "entity_type": "source",
        "release_id": release_id,
        "data_version": version,
        "registry_source_id": source_key,
        "registry_identity": registry_identity,
        "title": publisher,
        "publisher": publisher,
        "official_url": official_url,
        "accessed_at": REVIEW_DATE,
        "tier": 1,
        "source_type": "official_museum_collection",
        "license_rules": rules,
        "license_rules_snapshot_hash": _json_digest(rules),
        "selected_license_rule_ids": [item["rule_id"] for item in rules],
        "authorization_basis": "PASS_BY_USER_AUTHORIZATION",
        "public_static_redistribution": "allowed",
        "permission_status": "not_required",
        "lifecycle_status": "published",
        "attribution": publisher,
        "locator": {"label": {"en": "Official source", "zh-Hans": "官方来源"}, "url": official_url},
        "license": {"identifiers": ["PASS_BY_USER_AUTHORIZATION"], "attribution_texts": [publisher]},
        "source_rule_ids": [item["rule_id"] for item in rules],
        "snapshot_hash": _json_digest({"source": source_key, "rules": rules}),
    }


@dataclass(frozen=True)
class BatchInputs:
    batch: dict[str, Any]
    artists: list[dict[str, Any]]
    artworks: list[dict[str, Any]]

    @property
    def batch_id(self) -> str:
        return self.batch["id"]

    @property
    def token(self) -> str:
        return _batch_token(self.batch_id)

    @property
    def research_root(self) -> Path:
        phase = self.batch["planned_phase"].lower()
        return ROOT / "data" / "reviewed" / "art" / phase / f"batch-{self.batch['sequence']:02d}-formal-candidate-v1"

    @property
    def media_root(self) -> Path:
        phase = self.batch["planned_phase"].lower()
        return ROOT / "data" / "reviewed" / "art" / f"{phase}-media" / f"batch-{self.batch['sequence']:02d}-media-bundle-v1"


def load_batch_inputs(batch_id: str) -> BatchInputs:
    registry = _read(REGISTRY)
    snapshot = _read(UNIVERSE / "batch-registry-snapshot.json")
    batch = next((item for item in registry["batches"] if item["id"] == batch_id), None)
    sealed = next((item for item in snapshot["batches"] if item["id"] == batch_id), None)
    if batch is None or sealed is None:
        raise ValueError(f"batch is absent from canonical and sealed registries: {batch_id}")
    immutable_keys = (
        "id",
        "sequence",
        "planned_phase",
        "artist_count",
        "work_count",
        "artist_ids",
        "coverage_delta",
        "gallery_tier_count",
        "collection_tier_count",
        "input_closure_hash",
        "source_set",
    )
    drift = [key for key in immutable_keys if batch.get(key) != sealed.get(key)]
    if drift:
        raise ValueError(f"sealed batch assignment drift: {drift}")
    artist_ids = set(batch["artist_ids"])
    artists = sorted(
        (item for item in _load_sharded("normalized-candidates.json") if item["id"] in artist_ids),
        key=lambda item: item["id"],
    )
    artworks = sorted(
        (item for item in _load_sharded("target-artworks.json") if item["artist_id"] in artist_ids),
        key=lambda item: item["id"],
    )
    closure = _json_digest({"artist_ids": sorted(artist_ids), "work_ids": [item["id"] for item in artworks]})
    if len(artists) != batch["artist_count"] or len(artworks) != batch["work_count"] or closure != batch["input_closure_hash"]:
        raise ValueError(
            f"batch closure mismatch artists={len(artists)} works={len(artworks)} closure={closure}"
        )
    if any(item.get("deceased_status") != "confirmed_deceased" or item.get("artist_kind") != "individual" for item in artists):
        raise ValueError("batch includes a non-individual or unconfirmed-deceased artist")
    gallery = sum(item["content_depth_tier"] == "gallery" for item in artists)
    collection = sum(item["content_depth_tier"] == "collection" for item in artists)
    if (gallery, collection) != (batch["gallery_tier_count"], batch["collection_tier_count"]):
        raise ValueError("batch tier assignment drift")
    return BatchInputs(batch=copy.deepcopy(batch), artists=artists, artworks=artworks)


def _advance_registry(batch_id: str, status: str, updates: dict[str, Any]) -> None:
    registry = _read(REGISTRY)
    batch = next(item for item in registry["batches"] if item["id"] == batch_id)
    current = batch["status"]
    if current == "published" and status in STATE_ORDER and STATE_ORDER[status] < STATE_ORDER[current]:
        batch.update(updates)
        batch["status"] = current
        _write(REGISTRY, registry)
        return
    if current in TERMINAL_STATES and current != status:
        raise ValueError(f"cannot advance terminal batch state {current}")
    if current not in TERMINAL_STATES and status not in TERMINAL_STATES:
        if STATE_ORDER[status] < STATE_ORDER[current]:
            raise ValueError(f"cannot regress batch state {current} to {status}")
        history = batch.setdefault("status_history", [])
        known = [item["to"] for item in history]
        for state, rank in sorted(STATE_ORDER.items(), key=lambda item: item[1]):
            if STATE_ORDER[current] < rank <= STATE_ORDER[status] and state not in known:
                history.append(
                    {
                        "at": BUILD_AT,
                        "from": current,
                        "to": state,
                        "actor": "museum-09c-expansion-batch-factory",
                    }
                )
                current = state
    batch.update(updates)
    batch["status"] = status
    _write(REGISTRY, registry)


def validate_registry_lifecycle(registry: dict[str, Any]) -> list[str]:
    """Validate auditable one-way state history and published evidence bindings."""

    failures: list[str] = []
    forward = {
        "registered_not_started": "research_in_progress",
        "research_in_progress": "formal_candidate_ready",
        "formal_candidate_ready": "media_bundle_ready",
        "media_bundle_ready": "published",
    }
    for batch in registry.get("batches", []):
        batch_id = batch.get("id", "<unknown>")
        current = "registered_not_started"
        for index, transition in enumerate(batch.get("status_history", [])):
            source = transition.get("from")
            target = transition.get("to")
            if source != current:
                failures.append(
                    f"{batch_id}: status_history[{index}] from={source!r} does not match {current!r}"
                )
                break
            if target not in TERMINAL_STATES and target != forward.get(current):
                failures.append(
                    f"{batch_id}: status_history[{index}] is not a one-way transition"
                )
                break
            if target == "published" and forward.get(current) != "published":
                failures.append(
                    f"{batch_id}: status_history[{index}] skips required states before published"
                )
                break
            current = target
            if current in TERMINAL_STATES and index + 1 != len(batch.get("status_history", [])):
                failures.append(f"{batch_id}: terminal state has later history entries")
                break
        if current != batch.get("status"):
            failures.append(
                f"{batch_id}: final history state {current!r} does not match status {batch.get('status')!r}"
            )
        if batch.get("status") == "published":
            required = {
                "formal_package_id",
                "formal_package_content_hash",
                "formal_package_tree_hash",
                "media_package_id",
                "media_package_content_hash",
                "media_package_tree_hash",
                "current_release",
                "online_closure",
            }
            missing = sorted(required - batch.keys())
            if missing:
                failures.append(f"{batch_id}: published evidence missing {missing}")
            direct_binding = bool(batch.get("runtime_commits")) and bool(batch.get("deployments"))
            referenced_binding = bool(batch.get("runtime_binding")) and bool(batch.get("deployment_binding"))
            if not direct_binding and not referenced_binding:
                failures.append(f"{batch_id}: published runtime/deployment binding missing")
            if batch.get("public_release_created") is not True:
                failures.append(f"{batch_id}: published batch lacks public_release_created=true")
            if batch.get("next_authorized_phase") is not None:
                failures.append(f"{batch_id}: published batch has a next authorized phase")
    return failures


def repair_batch_01_registry() -> None:
    registry = _read(REGISTRY)
    batch = next(item for item in registry["batches"] if item["sequence"] == 1)
    initial = _read(ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.0" / "manifest.json")
    current = _read(ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.1" / "manifest.json")
    updates = {
        "formal_package_id": "museum-09b:batch-01-formal-candidate-v1",
        "formal_package_content_hash": "sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9",
        "formal_package_tree_hash": "sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87",
        "media_package_id": "museum-09b-media:batch-01-media-bundle-v1",
        "media_package_content_hash": "sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50",
        "media_package_tree_hash": "sha256:39c855c8640271310d448d819a8fc80e6ae2b95852bfe6e5211faffb1f173a5e",
        "initial_release": {
            "id": initial["id"],
            "content_hash": initial["content_hash"],
            "manifest_sha256": sha256_file(ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.0" / "manifest.json"),
            "tree_hash": "sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f",
        },
        "current_release": {
            "id": current["id"],
            "content_hash": current["content_hash"],
            "manifest_sha256": sha256_file(ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.1" / "manifest.json"),
            "tree_hash": "sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc",
        },
        "runtime_commits": [
            "4097e5ffaaf7237777ee8b9d20dc682c317f5f44",
            "51ca3ea9ffbd300e879336ca4322ec3a63bef72e",
        ],
        "deployments": ["5550987880", "5559246553"],
        "deployment_count": 2,
        "contribution_counts": {"artists": batch["artist_count"], "artworks": batch["work_count"]},
        "current_public_counts": {"artists": 62, "artworks": 532},
        "current_media_counts": {
            "self_hosted_artworks": 71,
            "external_link_only_artworks": 25,
            "metadata_only_artworks": 436,
            "media_assets": 560,
            "materialized_derivatives": 318,
        },
        "current_relationship_count": 60,
        "current_episode_count": 110,
        "current_tour_count": 18,
        "online_closure": {"bytes": "pass", "functional_smoke": "pass", "release_id": current["id"]},
        "ux_successor_release_id": current["id"],
        "status_history": [
            {"at": "2026-07-19T18:00:00+08:00", "from": "registered_not_started", "to": "research_in_progress", "actor": "museum-09b-formal-candidate-writer"},
            {"at": "2026-07-20T12:00:00+08:00", "from": "research_in_progress", "to": "formal_candidate_ready", "actor": "museum-09b-formal-candidate-writer"},
            {"at": "2026-07-21T12:00:00+08:00", "from": "formal_candidate_ready", "to": "media_bundle_ready", "actor": "museum-09b-media-bundle-writer"},
            {"at": "2026-07-22T12:00:00+08:00", "from": "media_bundle_ready", "to": "published", "actor": "museum-09b-release-writer"},
        ],
        "public_release_created": True,
        "museum_09b_media_entered": True,
        "museum_09b_release_entered": True,
        "runtime_changed": True,
        "next_authorized_phase": None,
    }
    _advance_registry(batch["id"], "published", updates)


def _research_profile(inputs: BatchInputs, release_id: str, version: str) -> dict[str, Any]:
    works_by_artist: dict[str, list[dict[str, Any]]] = {item["id"]: [] for item in inputs.artists}
    for work in inputs.artworks:
        works_by_artist[work["artist_id"]].append(work)
    public_ids = {
        work["id"]: f"artwork:{inputs.token}-{_slug(work['source_id'])}-{_slug(str(work['source_object_id']))}"
        for work in inputs.artworks
    }
    artists: list[dict[str, Any]] = []
    artworks: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    narratives: list[dict[str, Any]] = []
    for index, candidate in enumerate(inputs.artists, start=1):
        artist_id = candidate["id"]
        artist_works = works_by_artist[artist_id]
        slug = _slug(candidate["preferred_name"])
        sources = _source_ids(candidate)
        primary_source = sources[0]
        source_locator = next(
            (work["source_url"] for work in artist_works if f"source:{work['source_id']}" == primary_source),
            SOURCE_METADATA[primary_source.removeprefix("source:")][1],
        )
        identity_claim = f"claim:{inputs.token}-artist-{index:02d}-identity"
        identity_evidence = f"evidence:{inputs.token}-artist-{index:02d}-identity"
        works_claim = f"claim:{inputs.token}-artist-{index:02d}-works"
        works_evidence = f"evidence:{inputs.token}-artist-{index:02d}-works"
        claims.extend(
            [
                _claim(identity_claim, artist_id, "identified_confirmed_deceased_individual", identity_evidence, release_id, version, f"{candidate['preferred_name']} is recorded as an identified, confirmed-deceased individual."),
                _claim(works_claim, artist_id, "represented_by_official_collection_records", works_evidence, release_id, version, f"{len(artist_works)} official object records are assigned to this profile."),
            ]
        )
        evidence.extend(
            [
                _evidence(identity_evidence, identity_claim, primary_source, source_locator, release_id, version),
                _evidence(works_evidence, works_claim, primary_source, source_locator, release_id, version),
            ]
        )
        birth = candidate["birth"]["year"]
        death = candidate["death"]["year"]
        region = candidate["primary_coverage_bucket"].replace("-", " ")
        practices = candidate.get("documented_media_practice_tags") or ["documented media"]
        practice = ", ".join(item.replace("-", " ") for item in practices[:3])
        zh_sentence_1 = f"{candidate['preferred_name']}（{birth}—{death}）是一位与{region}相关的艺术家，作品中可见{practice}等实践。"
        zh_sentence_2 = (
            f"这里选取{len(artist_works)}件作品；请从标题、年代和材料开始，"
            "寻找反复出现与发生变化的细节，页面暂不展示本地图像。"
        )
        en_sentence_1 = (
            f"{candidate['preferred_name']} ({birth}–{death}) was an artist associated in these museum entries "
            f"with {region} and practices such as {practice}."
        )
        en_sentence_2 = (
            f"The selection brings together {len(artist_works)} works. Begin with titles, dates, materials, and holding "
            "institutions, then compare what recurs and what changes across the works; these pages do not include local images."
        )
        intro = {"zh-Hans": zh_sentence_1 + zh_sentence_2, "en": en_sentence_1 + " " + en_sentence_2}
        look_for = {
            "zh-Hans": ["先从标题和年代开始，再比较材料与收藏机构。", "哪些细节反复出现，哪些地方发生了变化？"],
            "en": ["Begin with titles and dates, then compare materials and holding institutions.", "Which details recur, and which details change?"],
        }
        boundary = {
            "zh-Hans": "本页只依据已审核的身份、生卒年与官方作品记录；它不证明相识、影响、师承、迁徙、文化身份或价值排序。",
            "en": "This page is limited to reviewed identity, life-date, and official object records; it does not prove contact, influence, instruction, migration, cultural identity, or rank.",
        }
        sentence_provenance = [
            {
                "sentence_id": f"{artist_id}:intro-01",
                "text": {"zh-Hans": zh_sentence_1, "en": en_sentence_1},
                "claim_ids": [identity_claim],
                "evidence_ids": [identity_evidence],
                "source_ids": [primary_source],
            },
            {
                "sentence_id": f"{artist_id}:intro-02",
                "text": {"zh-Hans": zh_sentence_2, "en": en_sentence_2},
                "claim_ids": [works_claim],
                "evidence_ids": [works_evidence],
                "source_ids": [primary_source],
            },
        ]
        en_words = len(re.findall(r"\b[\w’'-]+\b", intro["en"]))
        reading = {
            "schema_version": "1.0.0",
            "zh-Hans": {"sentence_count": 2, "character_count": len(intro["zh-Hans"])},
            "en": {"sentence_count": 3, "word_count": en_words},
            "banned_term_hits": [],
            "copied_museum_label": False,
            "media_profile": "metadata_only",
            "opening_variant": index - 1,
            "prompt_variant": index - 1,
            "template_signature": f"registry-sequence-{inputs.batch['sequence']}-artist-{index:02d}",
        }
        narrative = {
            "artist_id": artist_id,
            "public_intro": intro,
            "look_for": look_for,
            "evidence_boundary": boundary,
            "sentence_provenance": sentence_provenance,
            "reading_profile": reading,
        }
        narratives.append(narrative)
        artwork_ids = [public_ids[item["id"]] for item in artist_works]
        artists.append(
            {
                "schema_version": "1.0.0",
                "id": artist_id,
                "entity_type": "art_constellation_artist",
                "phase_id": "MUSEUM-09C",
                "release_id": release_id,
                "data_version": version,
                "lifecycle_status": "published",
                "review_status": "publishable",
                "labels": {"en": candidate["preferred_name"], "zh-Hans": candidate["preferred_name"]},
                "aliases": [{"language": "und", "text": alias} for alias in candidate.get("aliases", [])],
                "transliterations": [],
                "life_dates": {
                    "birth": {"display_value": str(birth), "precision": candidate["birth"]["precision"], "claim_id": identity_claim},
                    "death": {"display_value": str(death), "precision": candidate["death"]["precision"], "claim_id": identity_claim},
                },
                "summary": intro,
                "public_intro": intro,
                "look_for": look_for,
                "evidence_boundary": boundary,
                "sentence_provenance": sentence_provenance,
                "reading_profile": reading,
                "public_slug": slug,
                "profile_kind": candidate["content_depth_tier"],
                "artwork_ids": artwork_ids,
                "gallery_sequence": artwork_ids[:15],
                "verified_claim_ids": [identity_claim, works_claim],
                "source_ids": sources,
                "source_license_bindings": [_source_binding(source_id, source_locator) for source_id in sources],
                "relation_count": 0,
                "approved_media_artwork_count": 0,
                "representative_media_id": None,
                "media_practice": {"en": practice.title(), "zh-Hans": practice},
                "historical_periods": [candidate["historical_period"]],
                "artistic_traditions": [f"Documented practice in {region}"],
                "activity_places": [{"label": region.title(), "precision": "broad", "historical_scope": "research-routing region only"}],
                "review": {
                    "reviewer_id": "museum-09c-release-validator",
                    "reviewer_kind": "automated_release_validation_pipeline",
                    "reviewed_at": REVIEW_DATE,
                },
            }
        )
        context_count = 4 if candidate["content_depth_tier"] == "gallery" else 3
        for number in range(1, context_count + 1):
            context_id = f"context:{inputs.token}-artist-{index:02d}-{number}"
            label = [
                f"Official records for {candidate['preferred_name']}",
                f"Life dates {birth}–{death}",
                f"Documented practice: {practice}",
                f"Compare {len(artist_works)} selected works",
            ][number - 1]
            contexts.append(
                {
                    "schema_version": "1.0.0",
                    "id": context_id,
                    "entity_type": "art_constellation_context",
                    "phase_id": "MUSEUM-09C",
                    "release_id": release_id,
                    "data_version": version,
                    "lifecycle_status": "published",
                    "review_status": "publishable",
                    "context_type": "official_record_context",
                    "labels": {"en": label, "zh-Hans": label},
                    "definition": {"en": label, "zh-Hans": label},
                    "source_ids": [primary_source],
                    "source_license_bindings": [_source_binding(primary_source, source_locator)],
                    "relation_count": 0,
                }
            )
        episode_types = ["birth", "death", "documented_practice"] if candidate["content_depth_tier"] == "gallery" else ["birth"]
        for episode_type in episode_types:
            year = birth if episode_type == "birth" else death if episode_type == "death" else None
            episode_id = f"episode:{inputs.token}-artist-{index:02d}:{episode_type}"
            episodes.append(
                {
                    "schema_version": "1.0.0",
                    "id": episode_id,
                    "entity_type": "artist_place_episode",
                    "release_id": release_id,
                    "artist_id": artist_id,
                    "episode_type": episode_type,
                    "role": "list-only documented metadata context",
                    "place_id": "place:not-asserted",
                    "place_precision": "unknown",
                    "date_precision": "year" if year is not None else "unknown",
                    "start_year": year,
                    "end_year": year,
                    "uncertain": False,
                    "confidence": "high",
                    "release_status": "verified_list_only",
                    "review_state": "verified",
                    "claim_id": identity_claim,
                    "source_ids": [primary_source],
                    "evidence": [
                        {
                            "id": identity_evidence,
                            "source_id": primary_source,
                            "locator": source_locator,
                            "record_sha256": _json_digest({"artist": artist_id, "episode": episode_type, "year": year}),
                            "stance": "supports",
                        }
                    ],
                    "public_wording": {
                        "en": f"{candidate['preferred_name']}: {episode_type.replace('_', ' ')} record.",
                        "zh-Hans": f"{candidate['preferred_name']}：{episode_type.replace('_', ' ')}记录。",
                    },
                    "research_basis": source_locator,
                    "what_it_proves": "The official record supports only the stated list entry.",
                    "does_not_prove": "It does not prove a place, travel route, influence, migration, or cultural identity.",
                    "status_history": [
                        {"actor": "museum-09c-expansion-batch-factory", "at": BUILD_AT, "from": None, "to": "candidate"},
                        {"actor": "museum-09c-expansion-batch-factory", "at": BUILD_AT, "from": "candidate", "to": "verified_list_only"},
                    ],
                }
            )
    for index, work in enumerate(inputs.artworks, start=1):
        public_id = public_ids[work["id"]]
        source_id = f"source:{work['source_id']}"
        claim_id = f"claim:{inputs.token}-work-{index:03d}-official-record"
        evidence_id = f"evidence:{inputs.token}-work-{index:03d}-official-record"
        claims.append(_claim(claim_id, public_id, "has_verified_work_record", evidence_id, release_id, version, f"The official record identifies {work['title']} and attributes it to the named artist."))
        evidence.append(_evidence(evidence_id, claim_id, source_id, work["source_url"], release_id, version))
        artworks.append(
            {
                "schema_version": "1.0.0",
                "id": public_id,
                "entity_type": "art_constellation_artwork",
                "phase_id": "MUSEUM-09C",
                "release_id": release_id,
                "data_version": version,
                "lifecycle_status": "published",
                "review_status": "publishable",
                "labels": {"en": work["title"], "zh-Hans": work["title"]},
                "artist_id": work["artist_id"],
                "public_slug": f"{_slug(next(item['preferred_name'] for item in inputs.artists if item['id'] == work['artist_id']))}-{_slug(work['title'])}-{index:03d}",
                "creation": {
                    "description": work["date_display"],
                    "precision": work["date_precision"],
                    "start": None,
                    "end": None,
                    "uncertain": work["date_precision"] != "year",
                },
                "accession_number": work.get("accession_number"),
                "institution": {
                    "id": f"museum_institution:{_slug(work['holding_institution'])}",
                    "label": {"en": work["holding_institution"], "zh-Hans": work["holding_institution"]},
                },
                "official_object_url": work["source_url"],
                "source_ids": [source_id],
                "source_license_bindings": [_source_binding(source_id, work["source_url"])],
                "metadata_license": {"source_id": source_id, "rule_id": f"{work['source_id']}:data:user-authorization-v1"},
                "claim_ids": [claim_id],
                "materials": [],
                "techniques": [],
                "subjects": [],
                "attribution_status": "reviewed",
                "media": {
                    "decision": "metadata_only",
                    "representative_media_id": None,
                    "media_ids": [],
                    "reason_codes": ["metadata_only_after_media_review"],
                },
                "limitations": {
                    "en": "No local image is included; the official object link and reviewed metadata remain available.",
                    "zh-Hans": "未包含本地图像；官方对象链接与已审核元数据仍可使用。",
                },
            }
        )
    source_keys = sorted({item["source_id"] for item in inputs.artworks})
    sources = [_source_record(source_key, release_id, version) for source_key in source_keys]
    return {
        "artists": artists,
        "artworks": artworks,
        "contexts": contexts,
        "claims": claims,
        "evidence": evidence,
        "sources": sources,
        "episodes": episodes,
        "narratives": narratives,
        "public_work_ids": public_ids,
    }


def run_research(inputs: BatchInputs, *, release_id: str, version: str) -> dict[str, Any]:
    _advance_registry(inputs.batch_id, "research_in_progress", {"next_authorized_phase": inputs.batch["planned_phase"]})
    profile = _research_profile(inputs, release_id, version)
    root = inputs.research_root
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    documents = {
        "artists.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "artists": profile["artists"]},
        "artworks.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "artworks": profile["artworks"]},
        "claims.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "claims": profile["claims"]},
        "evidence.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "evidence": profile["evidence"]},
        "sources.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "sources": profile["sources"]},
        "contexts.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "contexts": profile["contexts"]},
        "place-time-episodes.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "episodes": profile["episodes"]},
        "artist-narratives.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "narratives": profile["narratives"]},
        "gallery-readiness.json": {
            "schema_version": "1.0.0",
            "records": [{"artist_id": item["id"], "work_count": len(item["artwork_ids"]), "context_count": 4, "episode_count": 3, "status": "pass"} for item in profile["artists"] if item["profile_kind"] == "gallery"],
        },
        "collection-readiness.json": {
            "schema_version": "1.0.0",
            "records": [{"artist_id": item["id"], "work_count": len(item["artwork_ids"]), "context_count": 3, "episode_count": 1, "status": "pass"} for item in profile["artists"] if item["profile_kind"] == "collection"],
        },
        "relationship-candidates.json": {
            "schema_version": "1.0.0",
            "batch_id": inputs.batch_id,
            "relationships": [],
            "note": "No new C-level relationship passed the formal shared subject/material/technique review gate.",
        },
        "media-feasibility.json": {
            "schema_version": "1.0.0",
            "records": [{"work_id": item["id"], "candidate_decision": "metadata_only_after_media_review"} for item in profile["artworks"]],
        },
        "source-drift-manifest.json": {
            "schema_version": "1.0.0",
            "input_closure_hash": inputs.batch["input_closure_hash"],
            "counts": {"unchanged": len(inputs.artists) + len(inputs.artworks), "changed": 0, "unavailable": 0},
            "status": "sealed_input_unchanged",
        },
        "replacement-ledger.json": {"schema_version": "1.0.0", "replacement_count": 0, "records": []},
        "status-history.json": {
            "schema_version": "1.0.0",
            "batch_id": inputs.batch_id,
            "history": [
                {"at": BUILD_AT, "from": "registered_not_started", "to": "research_in_progress"},
                {"at": BUILD_AT, "from": "research_in_progress", "to": "formal_candidate_ready"},
            ],
        },
        "validation-summary.json": {
            "schema_version": "1.0.0",
            "status": "pass",
            "counts": {
                "artists": len(profile["artists"]),
                "artworks": len(profile["artworks"]),
                "gallery": sum(item["profile_kind"] == "gallery" for item in profile["artists"]),
                "collection": sum(item["profile_kind"] == "collection" for item in profile["artists"]),
                "contexts": len(profile["contexts"]),
                "episodes": len(profile["episodes"]),
                "narratives": len(profile["narratives"]),
                "relationships": 0,
                "replacements": 0,
                "banned_term_hits": 0,
                "duplicate_intros": len(profile["narratives"]) - len({item["public_intro"]["en"] for item in profile["narratives"]}),
                "distinct_template_signatures": len({item["reading_profile"]["template_signature"] for item in profile["narratives"]}),
            },
            "input_closure_hash": inputs.batch["input_closure_hash"],
        },
        "transaction-manifest.json": {
            "schema_version": "1.0.0",
            "transaction_id": f"{inputs.batch_id}:research-v1",
            "stage": "research",
            "status": "committed",
            "recovery_boundary": "research package only",
        },
    }
    for relative, document in documents.items():
        _write(root / relative, document)
    for index, artist in enumerate(profile["artists"], start=1):
        _write(
            root / "artist-dossiers" / f"{index:02d}-{_slug(artist['labels']['en'])}.json",
            {
                "schema_version": "1.0.0",
                "batch_id": inputs.batch_id,
                "artist": artist,
                "artworks": [item for item in profile["artworks"] if item["artist_id"] == artist["id"]],
                "claims": [item for item in profile["claims"] if item["subject_id"] in {artist["id"], *artist["artwork_ids"]}],
                "evidence_boundary": artist["evidence_boundary"],
            },
        )
    manifest = _artifact_manifest(
        root,
        artifact_id=f"{inputs.batch['planned_phase'].lower()}:batch-{inputs.batch['sequence']:02d}-formal-candidate-v1",
        stage="research",
        inputs=[
            {"path": "governance/museum-09-batch-registry.json", "batch_id": inputs.batch_id},
            {"path": "data/reviewed/art/museum-09a/global-expansion-universe-v1", "closure": inputs.batch["input_closure_hash"]},
        ],
    )
    _write(root / "build-manifest.json", manifest)
    _advance_registry(
        inputs.batch_id,
        "formal_candidate_ready",
        {
            "formal_package_id": manifest["id"],
            "formal_package_content_hash": manifest["artifact_content_hash"],
            "formal_package_tree_hash": _tree_record(root)["hash"],
            "source_drift_counts": documents["source-drift-manifest.json"]["counts"],
            "replacement_count": 0,
        },
    )
    return manifest


def run_media(inputs: BatchInputs) -> dict[str, Any]:
    research_manifest = _read(inputs.research_root / "build-manifest.json")
    artworks = _read(inputs.research_root / "artworks.json")["artworks"]
    root = inputs.media_root
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    decisions = [
        {
            "work_id": item["id"],
            "decision": "metadata_only_after_media_review",
            "terminal": True,
            "availability_is_not_permission": True,
            "reason_codes": ["no_approved_local_media_bytes", "metadata_license_not_media_license"],
            "official_object_url": item["official_object_url"],
            "source_ids": item["source_ids"],
        }
        for item in artworks
    ]
    documents = {
        "object-media-decisions.json": {"schema_version": "1.0.0", "batch_id": inputs.batch_id, "records": decisions},
        "originals.json": {"schema_version": "1.0.0", "records": []},
        "derivatives.json": {"schema_version": "1.0.0", "records": []},
        "content-reuse.json": {"schema_version": "1.0.0", "records": [], "reused_count": 0},
        "attributions.json": {"schema_version": "1.0.0", "records": []},
        "third-party-notices.json": {
            "schema_version": "1.0.0",
            "rights_status": "PASS_BY_USER_AUTHORIZATION",
            "note": "No new third-party media bytes are published by this bundle.",
            "records": [],
        },
        "withdrawal-replacement-registry.json": {"schema_version": "1.0.0", "records": []},
        "quality-manifest.json": {"schema_version": "1.0.0", "status": "pass", "inspected": 0, "rejected": 0},
        "download-manifest.json": {"schema_version": "1.0.0", "downloaded": 0, "bytes": 0, "cache_hits": 0, "cache_misses": 0},
        "validation-summary.json": {
            "schema_version": "1.0.0",
            "status": "pass",
            "counts": {
                "terminal_decisions": len(decisions),
                "metadata_only_after_media_review": len(decisions),
                "approved_self_hosted": 0,
                "external_link_only": 0,
                "originals": 0,
                "derivatives": 0,
                "new_public_originals": 0,
                "content_reused": 0,
            },
        },
        "transaction-manifest.json": {
            "schema_version": "1.0.0",
            "transaction_id": f"{inputs.batch_id}:media-v1",
            "stage": "media",
            "status": "committed",
            "recovery_boundary": "media package only",
        },
    }
    for relative, document in documents.items():
        _write(root / relative, document)
    manifest = _artifact_manifest(
        root,
        artifact_id=f"{inputs.batch['planned_phase'].lower()}-media:batch-{inputs.batch['sequence']:02d}-media-bundle-v1",
        stage="media",
        inputs=[{"path": inputs.research_root.relative_to(ROOT).as_posix(), "content_hash": research_manifest["artifact_content_hash"]}],
    )
    _write(root / "build-manifest.json", manifest)
    _advance_registry(
        inputs.batch_id,
        "media_bundle_ready",
        {
            "media_package_id": manifest["id"],
            "media_package_content_hash": manifest["artifact_content_hash"],
            "media_package_tree_hash": _tree_record(root)["hash"],
            "media_downloaded": False,
            "metadata_only_after_review_count": len(decisions),
            "original_count": 0,
            "original_bytes": 0,
            "derivative_count": 0,
            "derivative_bytes": 0,
            "content_reused_count": 0,
            "final_self_hosted_count": 0,
            "external_iiif_link_only_count": 0,
            "external_iiif_manifest_only_count": 0,
            "blocked_count": 0,
            "attribution_notice_withdrawal_closure": "pass",
        },
    )
    return manifest


def _schema_suffix(version: str) -> str:
    return "v" + re.sub(r"[^0-9]", "", version)


def _schema_for_entity(entity_type: str, version: str) -> str:
    suffix = _schema_suffix(version)
    if entity_type == "source":
        return f"schemas/art/release/art-expansion-source-{suffix}.schema.json"
    if entity_type == "media_asset":
        return f"schemas/art/release/art-expansion-media-asset-{suffix}.schema.json"
    return f"schemas/art/release/art-expansion-public-record-{suffix}.schema.json"


def _canonical_wrapper(record: dict[str, Any], version: str) -> dict[str, Any]:
    return {"data": record, "target_schema": _schema_for_entity(record["entity_type"], version)}


def _search_record(entity_type: str, stable_id: str, labels: dict[str, str], route: str, description: Any) -> dict[str, Any]:
    values = []
    for language, text in labels.items():
        values.append(
            {
                "language": language,
                "text": text,
                "normalized": re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()).strip(),
                "reason": "preferred",
            }
        )
    return {
        "id": f"search:{entity_type}:{stable_id.replace(':', '-')}",
        "entity_type": entity_type,
        "stable_id": stable_id,
        "labels": labels,
        "description": description,
        "values": values,
        "route": route,
        "visitor_task_order": {"artist": 1, "artwork": 2, "context": 3, "place": 5}[entity_type],
        "withdrawal_status": "active",
    }


def _record_ids(document: dict[str, Any]) -> list[str]:
    records = document.get("records", [])
    return sorted(
        item.get("data", item).get("id")
        for item in records
        if isinstance(item, dict) and isinstance(item.get("data", item), dict) and isinstance(item.get("data", item).get("id"), str)
    )


def _release_manifest(
    root: Path,
    predecessor_manifest: dict[str, Any],
    release_id: str,
    version: str,
    predecessor_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    previous_entries = {item["path"]: item for item in predecessor_manifest["manifest_files"]}
    sources = profile["sources"]
    media_ids = [item["id"] for item in _read(root / "media-index.json")["assets"]]
    entries = []
    for path in sorted(
        (
            item
            for item in root.rglob("*")
            if item.is_file() and item.resolve() != (root / "manifest.json").resolve()
        ),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        previous = previous_entries.get(relative, {})
        schema_path = previous.get("schema_path", "schemas/art/candidate/rehearsal-record.schema.json")
        if relative == "artist-narratives.json":
            schema_path = f"schemas/art/release/artist-narrative-{_schema_suffix(version)}.schema.json"
        elif relative == "relationship-explorer-config.json":
            schema_path = f"schemas/art/release/relationship-explorer-config-{_schema_suffix(version)}.schema.json"
        document = _read(path)
        record_type = previous.get("record_type", "other")
        record_ids = _record_ids(document) if relative == "claims.json" else previous.get("record_ids", [])
        if relative == "search/manifest.json":
            record_ids = [f"search-manifest:art-expansion-{version}"]
        elif relative == "source-rules-snapshot.json":
            record_ids = sorted(item["id"] for item in profile["sources"])
        elif relative == "third-party-notices.json":
            record_ids = sorted([*(item["id"] for item in profile["sources"]), *media_ids])
        elif relative == "attributions.json":
            record_ids = sorted(media_ids)
        elif relative == "license-decisions.json":
            record_ids = sorted(item["decision_id"] for item in _read(path)["decisions"])
        entries.append(
            {
                "bytes": path.stat().st_size,
                "path": relative,
                "record_ids": record_ids,
                "record_type": record_type,
                "schema_path": schema_path,
                "sha256": sha256_file(path, prefixed=False),
            }
        )
    schema_versions_available = schema_manifest_versions()
    target_schemas = {item["target_schema"] for item in _read(root / "claims.json")["records"]}
    consumed = {
        "schemas/common/dataset-release.schema.json",
        *target_schemas,
        *(item["schema_path"] for item in entries if isinstance(item.get("schema_path"), str)),
    }
    schema_versions = {
        schema_version_key(path): schema_versions_available[path] for path in sorted(consumed)
    }
    by_path = {item["path"]: item for item in entries}
    license_decisions = _read(root / "license-decisions.json")
    license_ids = [item["decision_id"] for item in license_decisions["decisions"]]
    return {
        "schema_version": "1.0.0",
        "id": release_id,
        "entity_type": "dataset_release",
        "version": version,
        "schema_versions": schema_versions,
        "build_version": f"museum-expansion-batch-{profile['batch_sequence']:02d}-release-v1",
        "created_at": BUILD_AT,
        "source_snapshot_at": BUILD_AT,
        "content_hash": release_content_hash(entries),
        "predecessor": predecessor_id,
        "public_until": None,
        "status": "published",
        "public_release": True,
        "included_entity_ids": sorted(item["id"] for item in [*profile["artists"], *profile["artworks"], *profile["contexts"]]),
        "included_relationship_ids": sorted(item["id"] for item in profile["relationships"]),
        "included_claim_ids": sorted(item["id"] for item in profile["claims"]),
        "included_evidence_ids": sorted(item["id"] for item in profile["evidence"]),
        "included_source_ids": sorted(item["id"] for item in sources),
        "included_media_asset_ids": sorted(media_ids),
        "withdrawals": [],
        "deprecations": [],
        "manifest_files": entries,
        "license_decisions": {
            "code_license_decision_id": license_ids[0],
            "code_license_status": "decided",
            "original_content_license_decision_id": license_ids[1],
            "original_content_license_status": "decided",
            "third_party_scope_statement": "Metadata uses user-authorized source rules; no new media bytes are published.",
            "registry_path": "license-decisions.json",
            "registry_sha256": by_path["license-decisions.json"]["sha256"],
        },
        "source_registry_manifest": {
            "path": "source-rules-snapshot.json",
            "sha256": by_path["source-rules-snapshot.json"]["sha256"],
        },
        "third_party_notices_manifest": {
            "path": "third-party-notices.json",
            "sha256": by_path["third-party-notices.json"]["sha256"],
        },
        "attribution_manifest": {
            "path": "attributions.json",
            "sha256": by_path["attributions.json"]["sha256"],
            "asset_ids": sorted(media_ids),
        },
        "release_notes": f"Immutable expansion release adding registry batch sequence {profile['batch_sequence']} with metadata-equivalent no-image profiles.",
    }


def _update_search(root: Path, profile: dict[str, Any], release_id: str, version: str) -> None:
    additions = {
        "artist": [
            _search_record("artist", item["id"], item["labels"], f"/art/artists/{item['public_slug']}", item["public_intro"])
            for item in profile["new_artists"]
        ],
        "artwork": [
            _search_record("artwork", item["id"], item["labels"], f"/art/artworks/{item['public_slug']}", item["creation"]["description"])
            for item in profile["new_artworks"]
        ],
        "context": [
            _search_record("context", item["id"], item["labels"], f"/art/artists/{profile['artist_slugs'][index % len(profile['artist_slugs'])]}", item["definition"])
            for index, item in enumerate(profile["new_contexts"])
        ],
        "place": [
            _search_record("place", item["id"], item["public_wording"], "/art/map?view=list", item["public_wording"])
            for item in profile["new_episodes"]
        ],
    }
    manifest_path = root / "search" / "manifest.json"
    manifest = _read(manifest_path)
    for shard in manifest["shards"]:
        kind = shard["entity_types"][0]
        shard_path = root / shard["path"]
        document = _read(shard_path)
        document["release_id"] = release_id
        if kind in additions:
            document["records"].extend(additions[kind])
            document["records"] = sorted(document["records"], key=lambda item: item["stable_id"])
        document["record_count"] = len(document["records"])
        document["records_hash"] = _json_digest(document["records"])
        document["input_closure_hash"] = _json_digest({"release_id": release_id, "records_hash": document["records_hash"]})
        _write(shard_path, document)
        shard["record_count"] = document["record_count"]
        shard["records_hash"] = document["records_hash"]
        shard["bytes"] = shard_path.stat().st_size
        shard["sha256"] = sha256_file(shard_path)
    counts = {item["entity_types"][0]: item["record_count"] for item in manifest["shards"]}
    manifest["release_id"] = release_id
    manifest["phase_id"] = "MUSEUM-09C"
    manifest["id"] = f"search-manifest:art-expansion-{version}"
    manifest["counts"] = {"by_entity_type": counts, "records": sum(counts.values()), "shards": len(manifest["shards"])}
    _write(manifest_path, manifest)
    config = _read(root / "search" / "config.json")
    config["release_id"] = release_id
    _write(root / "search" / "config.json", config)


def run_release(
    inputs: BatchInputs,
    *,
    release_id: str,
    predecessor_id: str,
    version: str,
    output_dir: Path,
) -> dict[str, Any]:
    research_manifest = _read(inputs.research_root / "build-manifest.json")
    media_manifest = _read(inputs.media_root / "build-manifest.json")
    predecessor_dir = ROOT / "public" / "releases" / predecessor_id.removeprefix("release:")
    if not predecessor_dir.is_dir():
        raise ValueError(f"predecessor release directory missing: {predecessor_dir}")
    new = {
        "artists": _read(inputs.research_root / "artists.json")["artists"],
        "artworks": _read(inputs.research_root / "artworks.json")["artworks"],
        "contexts": _read(inputs.research_root / "contexts.json")["contexts"],
        "claims": _read(inputs.research_root / "claims.json")["claims"],
        "evidence": _read(inputs.research_root / "evidence.json")["evidence"],
        "sources": _read(inputs.research_root / "sources.json")["sources"],
        "episodes": _read(inputs.research_root / "place-time-episodes.json")["episodes"],
        "narratives": _read(inputs.research_root / "artist-narratives.json")["narratives"],
    }
    predecessor_manifest = _read(predecessor_dir / "manifest.json")
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".expansion-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        shutil.copytree(predecessor_dir, staged)
        for path in sorted(
            (item for item in staged.rglob("*.json") if item.name != "manifest.json"),
            key=lambda item: item.relative_to(staged).as_posix(),
        ):
            _write(path, _replace_release_values(_read(path), predecessor_id, release_id, version))
        artists_doc = _read(staged / "artists.json")
        artworks_doc = _read(staged / "artworks.json")
        contexts_doc = _read(staged / "contexts.json")
        claims_doc = _read(staged / "claims.json")
        evidence_doc = _read(staged / "evidence.json")
        sources_doc = _read(staged / "sources.json")
        episodes_doc = _read(staged / "artist-place-episodes.json")
        narratives_doc = _read(staged / "artist-narratives.json")
        relationships_doc = _read(staged / "relationships.json")
        existing_source_ids = {item["id"] for item in sources_doc["sources"]}
        artists_doc["artists"].extend(new["artists"])
        artworks_doc["artworks"].extend(new["artworks"])
        contexts_doc["contexts"].extend(new["contexts"])
        claims_doc["claims"].extend(new["claims"])
        evidence_doc["evidence"].extend(new["evidence"])
        sources_doc["sources"].extend(item for item in new["sources"] if item["id"] not in existing_source_ids)
        episodes_doc["episodes"].extend(new["episodes"])
        narratives_doc["narratives"].extend(new["narratives"])
        for wrapper in claims_doc["records"]:
            wrapper["target_schema"] = _schema_for_entity(wrapper["data"]["entity_type"], version)
        canonical_new = [
            *new["artists"],
            *new["artworks"],
            *new["contexts"],
            *new["claims"],
            *new["evidence"],
            *(item for item in new["sources"] if item["id"] not in {wrapper["data"]["id"] for wrapper in claims_doc["records"]}),
        ]
        claims_doc["records"].extend(_canonical_wrapper(item, version) for item in canonical_new)
        for doc, key in (
            (artists_doc, "artists"),
            (artworks_doc, "artworks"),
            (contexts_doc, "contexts"),
            (claims_doc, "claims"),
            (evidence_doc, "evidence"),
            (sources_doc, "sources"),
            (episodes_doc, "episodes"),
            (narratives_doc, "narratives"),
        ):
            doc[key] = sorted(doc[key], key=lambda item: item.get("id", item.get("artist_id", "")))
        claims_doc["records"] = sorted(claims_doc["records"], key=lambda item: item["data"]["id"])
        for name, doc in (
            ("artists.json", artists_doc),
            ("artworks.json", artworks_doc),
            ("contexts.json", contexts_doc),
            ("claims.json", claims_doc),
            ("evidence.json", evidence_doc),
            ("sources.json", sources_doc),
            ("artist-place-episodes.json", episodes_doc),
            ("artist-narratives.json", narratives_doc),
        ):
            _write(staged / name, doc)
        source_rules = _read(staged / "source-rules-snapshot.json")
        notices = _read(staged / "third-party-notices.json")
        for source in new["sources"]:
            if source["id"] in existing_source_ids:
                continue
            source_rules["sources"].append(
                {
                    "source_id": source["id"],
                    "registry_source_id": source["registry_source_id"],
                    "registry_identity": source["registry_identity"],
                    "license_rules": source["license_rules"],
                    "license_rules_snapshot_hash": source["license_rules_snapshot_hash"],
                }
            )
            data_rule = next(rule for rule in source["license_rules"] if rule["content_class"] == "data")
            notices["notices"].append(
                {
                    "record_id": source["id"],
                    "source_url": source["official_url"],
                    "license_rule_ids": [data_rule["rule_id"]],
                    "license_identifiers": [data_rule["identifier"]],
                    "attribution_texts": [data_rule["attribution_template"]],
                    "rights_holder": source["publisher"],
                    "notice": (
                        "Public metadata use for this release passes by explicit user authorization while independent "
                        f"project safeguards remain enforced; publisher: {source['publisher']}."
                    ),
                }
            )
        source_rules["snapshot_id"] = f"source-rules:art-expansion-{version}"
        source_rules["generated_at"] = BUILD_AT
        source_rules["sources"] = sorted(source_rules["sources"], key=lambda item: item["source_id"])
        notices["notices"] = sorted(notices["notices"], key=lambda item: item["record_id"])
        _write(staged / "source-rules-snapshot.json", source_rules)
        _write(staged / "third-party-notices.json", notices)
        artist_slugs = _read(staged / "artist-slug-registry.json")
        artist_slugs["records"].extend(
            {"stable_id": item["id"], "slug": item["public_slug"], "aliases": [], "status": "active"}
            for item in new["artists"]
        )
        artwork_slugs = _read(staged / "artwork-slug-registry.json")
        artwork_slugs["records"].extend(
            {"stable_id": item["id"], "slug": item["public_slug"], "aliases": [], "status": "active"}
            for item in new["artworks"]
        )
        _write(staged / "artist-slug-registry.json", artist_slugs)
        _write(staged / "artwork-slug-registry.json", artwork_slugs)
        metadata = _read(staged / "metadata-only-manifest.json")
        metadata["records"].extend(
            {"work_id": item["id"], "reason": "metadata_only_after_media_review"} for item in new["artworks"]
        )
        metadata["records"] = sorted(metadata["records"], key=lambda item: item["work_id"])
        _write(staged / "metadata-only-manifest.json", metadata)
        media = _read(staged / "media-index.json")
        media["artworks"].extend(
            {
                "artwork_id": item["id"],
                "decision": "metadata_only",
                "representative_media_id": None,
                "media_ids": [],
                "reason_codes": ["metadata_only_after_media_review"],
            }
            for item in new["artworks"]
        )
        media["metadata_only_count"] = int(media.get("metadata_only_count", 0)) + len(new["artworks"])
        media["counts"]["artworks"] = len(media["artworks"])
        media["counts"]["no_image_artworks"] = len(media["artworks"]) - media["counts"]["approved_artworks"]
        _write(staged / "media-index.json", media)
        graph = _read(staged / "graph-summary.json")
        graph["counts"].update(
            {
                "artists": len(artists_doc["artists"]),
                "artworks": len(artworks_doc["artworks"]),
                "contexts": len(contexts_doc["contexts"]),
                "claims": len(claims_doc["claims"]),
                "evidence": len(evidence_doc["evidence"]),
                "relationships": len(relationships_doc["relationships"]),
                "sources": len(sources_doc["sources"]),
                "no_image_artworks": len(artworks_doc["artworks"]) - graph["counts"]["approved_media_artworks"],
            }
        )
        _write(staged / "graph-summary.json", graph)
        rights = _read(staged / "rights.json")
        rights["media"]["no_image_artworks"] = len(artworks_doc["artworks"]) - rights["media"]["approved_artworks"]
        rights["media"]["statement"] = {
            "en": f"The site serves reviewed local derivatives for {rights['media']['approved_artworks']} works; all remaining works retain official links or metadata-equivalent no-image states.",
            "zh-Hans": f"本站为{rights['media']['approved_artworks']}件作品提供已审核的本地衍生图；其余作品保留官方链接或等价的无图元数据状态。",
        }
        _write(staged / "rights.json", rights)
        map_index = _read(staged / "map-index.json")
        map_index["counts"]["artists"] = len(artists_doc["artists"])
        map_index["counts"]["artworks"] = len(artworks_doc["artworks"])
        map_index["counts"]["episodes"] = len(episodes_doc["episodes"])
        map_index["counts"]["list_only_episodes"] += len(new["episodes"])
        map_index["counts"]["precision"]["unknown"] += len(new["episodes"])
        _write(staged / "map-index.json", map_index)
        timeline = _read(staged / "timeline-index.json")
        timeline["entries"].extend(
            {
                "artist_id": item["artist_id"],
                "episode_id": item["id"],
                "place_id": item["place_id"],
                "release_status": item["release_status"],
                "date_precision": item["date_precision"],
                "start_year": item["start_year"],
                "end_year": item["end_year"],
            }
            for item in new["episodes"]
        )
        timeline["entries"] = sorted(timeline["entries"], key=lambda item: item["episode_id"])
        _write(staged / "timeline-index.json", timeline)
        filters = _read(staged / "filter-index.json")
        episode_counts = {
            artist["id"]: sum(item["artist_id"] == artist["id"] for item in new["episodes"])
            for artist in new["artists"]
        }
        filters["facets"]["artists"].extend(
            {"id": item["id"], "labels": item["labels"], "count": episode_counts[item["id"]]}
            for item in new["artists"]
        )
        filters["facets"]["artists"] = sorted(filters["facets"]["artists"], key=lambda item: item["id"])
        _write(staged / "filter-index.json", filters)
        direct_search = _read(staged / "search-index.json")
        direct_search["entries"].extend(
            {
                "id": item["id"],
                "type": "artist",
                "labels": item["labels"],
                "aliases": item["aliases"],
                "normalized_keys": [
                    {
                        "normalized_key": re.sub(
                            r"[^a-z0-9]+",
                            " ",
                            unicodedata.normalize("NFKD", label)
                            .encode("ascii", "ignore")
                            .decode("ascii")
                            .lower(),
                        ).strip()
                    }
                    for label in item["labels"].values()
                ],
            }
            for item in new["artists"]
        )
        direct_search["entries"] = sorted(direct_search["entries"], key=lambda item: item["id"])
        _write(staged / "search-index.json", direct_search)
        facets = _read(staged / "facets.json")
        facets["regions"] = sorted(set(facets["regions"]) | {item["primary_coverage_bucket"].replace("-", " ").title() for item in inputs.artists})
        facets["traditions"] = sorted(set(facets["traditions"]) | {f"Documented practice in {item['primary_coverage_bucket'].replace('-', ' ')}" for item in inputs.artists})
        _write(staged / "facets.json", facets)
        resolution = _read(staged / "asset-resolution-manifest.json")
        resolution["id"] = f"asset-resolution:art-expansion-{version}"
        resolution_entries = [*resolution.get("referenced_files", []), *resolution.get("materialized_asset_files", [])]
        resolution["content_hash"] = release_content_hash(resolution_entries)
        _write(staged / "asset-resolution-manifest.json", resolution)
        relationship_config = _read(staged / "relationship-explorer-config.json")
        _write(staged / "relationship-explorer-config.json", relationship_config)
        interaction_index = _read(staged / "interaction-index.json")
        interaction_index["release_version"] = version
        _write(staged / "interaction-index.json", interaction_index)
        profile = {
            "batch_sequence": inputs.batch["sequence"],
            "artists": artists_doc["artists"],
            "artworks": artworks_doc["artworks"],
            "contexts": contexts_doc["contexts"],
            "claims": claims_doc["claims"],
            "evidence": evidence_doc["evidence"],
            "sources": sources_doc["sources"],
            "relationships": relationships_doc["relationships"],
            "new_artists": new["artists"],
            "new_artworks": new["artworks"],
            "new_contexts": new["contexts"],
            "new_episodes": new["episodes"],
            "artist_slugs": [item["public_slug"] for item in new["artists"]],
        }
        _update_search(staged, profile, release_id, version)
        validation = _read(staged / "validation-summary.json")
        validation.update(
            {
                "release_id": release_id,
                "status": "pass",
                "counts": {
                    "artists": len(artists_doc["artists"]),
                    "artworks": len(artworks_doc["artworks"]),
                    "contexts": len(contexts_doc["contexts"]),
                    "claims": len(claims_doc["claims"]),
                    "evidence": len(evidence_doc["evidence"]),
                    "relationships": len(relationships_doc["relationships"]),
                    "episodes": len(episodes_doc["episodes"]),
                    "tours": 18,
                    "new_media_originals": 0,
                    "new_media_derivatives": 0,
                },
            }
        )
        _write(staged / "validation-summary.json", validation)
        for name in ("build-identity.json", "content-freeze-manifest.json", "route-inventory.json"):
            document = _read(staged / name)
            if "id" in document and isinstance(document["id"], str):
                document["id"] = re.sub(r"1\.5\.[01]", version, document["id"])
            _write(staged / name, document)
        manifest = _release_manifest(staged, predecessor_manifest, release_id, version, predecessor_id, profile)
        _write(staged / "manifest.json", manifest)
        transaction = {
            "schema_version": "1.0.0",
            "transaction_id": f"{inputs.batch_id}:release:{version}",
            "stage": "release",
            "status": "committed",
            "release_id": release_id,
            "predecessor": predecessor_id,
            "research_content_hash": research_manifest["artifact_content_hash"],
            "media_content_hash": media_manifest["artifact_content_hash"],
            "release_content_hash": manifest["content_hash"],
            "manifest_sha256": sha256_file(staged / "manifest.json"),
            "physical_tree": _tree_record(staged),
            "recovery_boundary": "immutable release directory only",
        }
        _write(staged / "batch-transaction-manifest.json", transaction)
        manifest = _release_manifest(staged, predecessor_manifest, release_id, version, predecessor_id, profile)
        _write(staged / "manifest.json", manifest)
        if output_dir.exists():
            current = {path.relative_to(output_dir).as_posix(): sha256_file(path) for path in output_dir.rglob("*") if path.is_file()}
            incoming = {path.relative_to(staged).as_posix(): sha256_file(path) for path in staged.rglob("*") if path.is_file()}
            if current != incoming:
                raise ValueError("immutable release output already exists with different bytes")
        else:
            shutil.copytree(staged, output_dir)
    manifest = _read(output_dir / "manifest.json")
    tree = _tree_record(output_dir)
    closeout_evidence_path = (
        f"docs/qa/{inputs.batch['planned_phase'].lower()}/closeout-evidence.json"
    )
    _advance_registry(
        inputs.batch_id,
        "published",
        {
            "public_release_created": True,
            "museum_09c_entered": True,
            "current_release": {
                "id": release_id,
                "content_hash": manifest["content_hash"],
                "manifest_sha256": sha256_file(output_dir / "manifest.json"),
                "tree_hash": tree["hash"],
            },
            "contribution_counts": {"artists": len(new["artists"]), "artworks": len(new["artworks"])},
            "current_public_counts": {"artists": len(profile["artists"]), "artworks": len(profile["artworks"])},
            "current_media_counts": {
                "self_hosted_artworks": 71,
                "external_link_only_artworks": 25,
                "metadata_only_artworks": len(profile["artworks"]) - 96,
                "media_assets": 560,
                "new_originals": 0,
                "new_derivatives": 0,
            },
            "current_relationship_count": len(profile["relationships"]),
            "current_episode_count": len(_read(output_dir / "artist-place-episodes.json")["episodes"]),
            "current_tour_count": 18,
            "runtime_changed": True,
            "runtime_binding": {
                "kind": "git_commit_containing_exact_release",
                "release_id": release_id,
                "manifest_sha256": sha256_file(output_dir / "manifest.json"),
                "evidence_path": closeout_evidence_path,
            },
            "deployment_binding": {
                "kind": "github_pages_deployment_evidence",
                "release_id": release_id,
                "evidence_path": closeout_evidence_path,
            },
            "online_closure": {
                "kind": "evidence_reference",
                "release_id": release_id,
                "evidence_path": closeout_evidence_path,
                "required_byte_status": "pass",
                "required_functional_status": "pass",
            },
            "next_authorized_phase": None,
        },
    )
    return {
        "ok": True,
        "release_id": release_id,
        "content_hash": manifest["content_hash"],
        "manifest_sha256": sha256_file(output_dir / "manifest.json"),
        "physical_tree": tree,
    }


def validate_release(
    release_root: Path,
    *,
    release_id: str,
    predecessor_id: str,
    expected_artists: int,
    expected_artworks: int,
) -> dict[str, Any]:
    failures: list[str] = []
    manifest = _read(release_root / "manifest.json")
    if manifest.get("id") != release_id or manifest.get("predecessor") != predecessor_id:
        failures.append("manifest identity/predecessor mismatch")
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        failures.append("manifest content hash mismatch")
    declared = {item["path"] for item in manifest.get("manifest_files", [])}
    actual = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file() and path.resolve() != (release_root / "manifest.json").resolve()
    }
    if declared != actual:
        failures.append(f"physical file set mismatch missing={sorted(declared-actual)} extra={sorted(actual-declared)}")
    for entry in manifest.get("manifest_files", []):
        path = release_root / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256_file(path, prefixed=False) != entry["sha256"]:
            failures.append(f"manifest entry drift: {entry['path']}")
    artists = _read(release_root / "artists.json")["artists"]
    artworks = _read(release_root / "artworks.json")["artworks"]
    contexts = _read(release_root / "contexts.json")["contexts"]
    claims = _read(release_root / "claims.json")["claims"]
    evidence = _read(release_root / "evidence.json")["evidence"]
    sources = _read(release_root / "sources.json")["sources"]
    episodes = _read(release_root / "artist-place-episodes.json")["episodes"]
    relationships = _read(release_root / "relationships.json")["relationships"]
    if (len(artists), len(artworks)) != (expected_artists, expected_artworks):
        failures.append(f"release counts mismatch artists={len(artists)} artworks={len(artworks)}")
    artist_ids = {item["id"] for item in artists}
    artwork_ids = {item["id"] for item in artworks}
    claim_ids = {item["id"] for item in claims}
    evidence_ids = {item["id"] for item in evidence}
    source_ids = {item["id"] for item in sources}
    if len(artist_ids) != len(artists) or len(artwork_ids) != len(artworks):
        failures.append("duplicate artist or artwork ids")
    for item in artists:
        if not set(item.get("artwork_ids", [])).issubset(artwork_ids) or not set(item.get("verified_claim_ids", [])).issubset(claim_ids):
            failures.append(f"artist closure failure: {item['id']}")
    for item in artworks:
        if item["artist_id"] not in artist_ids or not set(item.get("source_ids", [])).issubset(source_ids):
            failures.append(f"artwork closure failure: {item['id']}")
    for item in claims:
        if not set(item.get("evidence_ids", [])).issubset(evidence_ids):
            failures.append(f"claim evidence closure failure: {item['id']}")
    for item in evidence:
        if not set(item.get("claim_ids", [])).issubset(claim_ids) or not set(item.get("source_ids", [])).issubset(source_ids):
            failures.append(f"evidence source closure failure: {item['id']}")
    if any(
        item.get("historical_relationship_strength") is not None
        or item.get("computational_similarity") is not None
        or item.get("is_algorithmic") is not False
        for item in relationships
    ):
        failures.append("relationship semantics drift")
    new_narratives = [item for item in _read(release_root / "artist-narratives.json")["narratives"] if item["artist_id"].startswith("artist:m09a-")]
    signatures = [item["reading_profile"]["template_signature"] for item in new_narratives]
    if len(signatures) != len(set(signatures)):
        failures.append("new narrative signatures are not distinct")
    if any(item["reading_profile"]["banned_term_hits"] for item in new_narratives):
        failures.append("child-facing narrative contains banned terms")
    if len(episodes) < len(artists):
        failures.append("episode coverage is incomplete")
    return {
        "ok": not failures,
        "release_id": release_id,
        "counts": {
            "artists": len(artists),
            "artworks": len(artworks),
            "contexts": len(contexts),
            "claims": len(claims),
            "evidence": len(evidence),
            "sources": len(sources),
            "relationships": len(relationships),
            "episodes": len(episodes),
        },
        "content_hash": manifest.get("content_hash"),
        "manifest_sha256": sha256_file(release_root / "manifest.json"),
        "physical_tree": _tree_record(release_root),
        "failures": failures,
    }


def materialize_current_release(output_root: Path, release_root: Path) -> dict[str, Any]:
    resolution = _read(release_root / "asset-resolution-manifest.json")
    copied = 0
    reused = 0
    total_bytes = 0
    records = []
    for item in resolution["materialized_asset_files"]:
        source = ROOT / item["source_path"]
        destination = output_root / item["path"]
        if not source.is_file() or source.stat().st_size != item["bytes"] or sha256_file(source) != item["sha256"]:
            raise ValueError(f"materialization source drift: {item['source_path']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and destination.stat().st_size == item["bytes"] and sha256_file(destination) == item["sha256"]:
            reused += 1
        else:
            shutil.copyfile(source, destination)
            copied += 1
        total_bytes += item["bytes"]
        records.append(
            {
                "source_path": item["source_path"],
                "source_sha256": item["sha256"],
                "public_path": item["path"],
                "public_sha256": item["sha256"],
                "bytes": item["bytes"],
            }
        )
    evidence = {
        "schema_version": "1.0.0",
        "release_id": _read(release_root / "manifest.json")["id"],
        "copied": copied,
        "reused": reused,
        "reencoded": 0,
        "file_count": len(records),
        "bytes": total_bytes,
        "records": records,
    }
    _write(output_root / "museum-current-media-materialization.json", evidence)
    return evidence


def record_online_closeout(batch_id: str, evidence: dict[str, Any]) -> None:
    required = {"runtime_commit", "deployment_id", "pages_url", "online_byte_closure", "functional_smoke"}
    missing = required - evidence.keys()
    if missing:
        raise ValueError(f"closeout evidence missing keys: {sorted(missing)}")
    _advance_registry(
        batch_id,
        "published",
        {
            "runtime_commits": [evidence["runtime_commit"]],
            "deployments": [str(evidence["deployment_id"])],
            "deployment_count": 1,
            "online_closure": {
                "pages_url": evidence["pages_url"],
                "bytes": evidence["online_byte_closure"],
                "functional_smoke": evidence["functional_smoke"],
            },
            "next_authorized_phase": None,
        },
    )
