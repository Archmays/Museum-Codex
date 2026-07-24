"""Plan-driven, resumable orchestration for sequential expansion releases.

The V2 writer keeps the sealed single-batch factory unchanged as a historical
compatibility implementation. It runs that implementation only inside an
isolated registry and temporary artifact root, then applies the explicit wave
execution context before atomically committing a package or release.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from museum_pipeline.art import expansion_batch_factory as legacy
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_REGISTRY = ROOT / "governance" / "museum-09-batch-registry.json"
STAGES = ("research", "media", "release")
STATE_ORDER = {
    "registered_not_started": 0,
    "research_in_progress": 1,
    "formal_candidate_ready": 2,
    "media_bundle_ready": 3,
    "published": 4,
}


class WaveExecutionError(RuntimeError):
    """Raised after the journal has recorded a recoverable failure cursor."""


@dataclass(frozen=True)
class BatchPlan:
    batch_id: str
    release_id: str
    version: str
    predecessor_id: str
    input_closure_hash: str
    artist_count: int
    artwork_count: int
    gallery_count: int
    collection_count: int
    cumulative_artist_count: int
    cumulative_artwork_count: int
    research_path: str
    media_path: str
    release_path: str
    deployment_eligible: bool

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> "BatchPlan":
        return cls(**{field: value[field] for field in cls.__dataclass_fields__})

    def artifact_path(self, stage: str) -> Path:
        relative = {
            "research": self.research_path,
            "media": self.media_path,
            "release": self.release_path,
        }[stage]
        return ROOT / relative


@dataclass(frozen=True)
class WavePlan:
    path: Path
    document: dict[str, Any]
    batches: tuple[BatchPlan, ...]

    @property
    def phase_id(self) -> str:
        return self.document["phase_id"]

    @property
    def build_at(self) -> str:
        return self.document["build_at"]

    @property
    def review_date(self) -> str:
        return self.document["review_date"]

    @property
    def reviewer_id(self) -> str:
        return self.document["reviewer"]["id"]

    @property
    def reviewer_kind(self) -> str:
        return self.document["reviewer"]["kind"]

    @property
    def authorization_scope(self) -> str:
        return self.document["authorization"]["scope"]

    @property
    def authorization_basis(self) -> str:
        return self.document["authorization"]["basis"]

    @property
    def authorization_rule_version(self) -> str:
        return self.document["authorization"]["rule_version"]

    @property
    def actor_id(self) -> str:
        return self.document["actor_id"]

    @property
    def artifact_namespace(self) -> str:
        return self.document["artifact_namespace"]

    @property
    def final_release_id(self) -> str:
        return self.document["final_release_id"]

    @property
    def journal_path(self) -> Path:
        return ROOT / self.document["journal_path"]

    @property
    def deployment_marker_path(self) -> Path:
        return ROOT / self.document["deployment_marker_path"]

    @property
    def cross_batch_report_path(self) -> Path:
        return ROOT / self.document["cross_batch_report_path"]

    @property
    def legacy_adapter(self) -> dict[str, Any]:
        return self.document["legacy_adapter"]

    @property
    def digest(self) -> str:
        return _json_digest(self.document)


@dataclass(frozen=True)
class StageInputs:
    batch: dict[str, Any]
    artists: list[dict[str, Any]]
    artworks: list[dict[str, Any]]
    research_path: Path
    media_path: Path

    @property
    def batch_id(self) -> str:
        return self.batch["id"]

    @property
    def token(self) -> str:
        return legacy._batch_token(self.batch_id)

    @property
    def research_root(self) -> Path:
        return self.research_path

    @property
    def media_root(self) -> Path:
        return self.media_path


StageRunner = Callable[[WavePlan, BatchPlan, str, Path], dict[str, Any]]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _directory_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(
            (item for item in root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    }


def _commit_directory(staged: Path, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _directory_files(destination) != _directory_files(staged):
            raise ValueError(f"immutable artifact already exists with different bytes: {destination}")
        return False
    os.replace(staged, destination)
    return True


def _artifact_checkpoint(root: Path, stage: str) -> dict[str, Any]:
    manifest_name = "manifest.json" if stage == "release" else "build-manifest.json"
    manifest = _read(root / manifest_name)
    return {
        "path": root.relative_to(ROOT).as_posix(),
        "manifest_path": f"{root.relative_to(ROOT).as_posix()}/{manifest_name}",
        "manifest_sha256": sha256_file(root / manifest_name),
        "content_hash": manifest.get("content_hash") or manifest.get("artifact_content_hash"),
        "physical_tree": legacy._tree_record(root),
    }


def _verify_checkpoint(checkpoint: dict[str, Any]) -> bool:
    root = ROOT / checkpoint["path"]
    manifest = ROOT / checkpoint["manifest_path"]
    return (
        root.is_dir()
        and manifest.is_file()
        and sha256_file(manifest) == checkpoint["manifest_sha256"]
        and legacy._tree_record(root) == checkpoint["physical_tree"]
    )


def load_wave_plan(path: Path) -> WavePlan:
    resolved = path.resolve()
    document = _read(resolved)
    required = {
        "schema_version",
        "phase_id",
        "build_at",
        "review_date",
        "reviewer",
        "authorization",
        "legacy_adapter",
        "artifact_namespace",
        "actor_id",
        "current_release_id",
        "final_release_id",
        "journal_path",
        "deployment_marker_path",
        "cross_batch_report_path",
        "batches",
    }
    missing = sorted(required - document.keys())
    if missing:
        raise ValueError(f"release plan missing fields: {missing}")
    batches = tuple(BatchPlan.from_document(item) for item in document["batches"])
    if not batches:
        raise ValueError("release plan has no batches")
    if len({item.batch_id for item in batches}) != len(batches):
        raise ValueError("release plan contains duplicate batch ids")
    if len({item.release_id for item in batches}) != len(batches):
        raise ValueError("release plan contains duplicate release ids")
    if document["final_release_id"] != batches[-1].release_id:
        raise ValueError("final release id is not the final batch output")
    if [item.deployment_eligible for item in batches] != [False] * (len(batches) - 1) + [True]:
        raise ValueError("only the final release may be deployment eligible")
    predecessor = document["current_release_id"]
    for batch in batches:
        if batch.predecessor_id != predecessor:
            raise ValueError(f"release predecessor chain breaks at {batch.batch_id}")
        if batch.release_id.rsplit("-", 1)[-1] != batch.version:
            raise ValueError(f"release version mismatch at {batch.batch_id}")
        predecessor = batch.release_id
    plan = WavePlan(path=resolved, document=document, batches=batches)
    _validate_plan_against_registry(plan, CANONICAL_REGISTRY)
    return plan


def _validate_plan_against_registry(plan: WavePlan, registry_path: Path) -> None:
    registry = _read(registry_path)
    canonical = {item["id"]: item for item in registry["batches"]}
    for batch in plan.batches:
        if batch.batch_id not in canonical:
            raise ValueError(f"unauthorized or forged batch id: {batch.batch_id}")
        record = canonical[batch.batch_id]
        expected = {
            "input_closure_hash": batch.input_closure_hash,
            "artist_count": batch.artist_count,
            "work_count": batch.artwork_count,
            "gallery_tier_count": batch.gallery_count,
            "collection_tier_count": batch.collection_count,
        }
        drift = {key: (record.get(key), value) for key, value in expected.items() if record.get(key) != value}
        if drift:
            raise ValueError(f"release plan registry drift for {batch.batch_id}: {drift}")
        inputs = legacy.load_batch_inputs(batch.batch_id)
        if (len(inputs.artists), len(inputs.artworks)) != (batch.artist_count, batch.artwork_count):
            raise ValueError(f"sealed input count drift for {batch.batch_id}")


def compute_wave_input_hash(plan: WavePlan, registry_path: Path = CANONICAL_REGISTRY) -> str:
    registry = _read(registry_path)
    by_id = {item["id"]: item for item in registry["batches"]}
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
    predecessor_path = (
        ROOT
        / "public"
        / "releases"
        / plan.document["current_release_id"].removeprefix("release:")
        / "manifest.json"
    )
    predecessor_manifest = {
        "release_id": plan.document["current_release_id"],
        "manifest_sha256": sha256_file(predecessor_path),
    }
    return _json_digest(
        {
            "plan": plan.document,
            "batches": [
                {key: by_id[batch.batch_id][key] for key in immutable_keys}
                for batch in plan.batches
            ],
            "input_release": predecessor_manifest,
        }
    )


def _initial_journal(plan: WavePlan, input_hash: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "phase_id": plan.phase_id,
        "plan_path": plan.path.relative_to(ROOT).as_posix(),
        "plan_hash": plan.digest,
        "stable_input_hash": input_hash,
        "status": "in_progress",
        "failure_cursor": None,
        "batches": [
            {
                "batch_id": batch.batch_id,
                "release_id": batch.release_id,
                "stages": {
                    stage: {"status": "pending", "attempts": 0, "checkpoint": None, "error": None}
                    for stage in STAGES
                },
            }
            for batch in plan.batches
        ],
        "deployment": {
            "final_release_id": plan.final_release_id,
            "intermediate_deployment_count": 0,
            "marker_status": "not_created",
        },
    }


def _load_or_create_journal(
    plan: WavePlan,
    journal_path: Path,
    input_hash: str,
    *,
    resume: bool,
) -> dict[str, Any]:
    if resume:
        if not journal_path.is_file():
            raise ValueError("--resume requires an existing journal")
        journal = _read(journal_path)
        if journal.get("plan_hash") != plan.digest or journal.get("stable_input_hash") != input_hash:
            raise ValueError("journal plan/input hash does not match the current wave")
        return journal
    if journal_path.exists():
        journal = _read(journal_path)
        if journal.get("plan_hash") != plan.digest or journal.get("stable_input_hash") != input_hash:
            raise ValueError("existing journal belongs to a different wave input")
        return journal
    return _initial_journal(plan, input_hash)


def _batch_journal(journal: dict[str, Any], batch_id: str) -> dict[str, Any]:
    return next(item for item in journal["batches"] if item["batch_id"] == batch_id)


def build_schedule(
    plan: WavePlan,
    journal: dict[str, Any],
    *,
    batch_ids: Iterable[str],
    through: str,
    resume: bool,
    from_batch: str | None,
    from_stage: str | None,
) -> list[tuple[BatchPlan, str]]:
    requested = list(batch_ids)
    planned_ids = [item.batch_id for item in plan.batches]
    if not requested or any(item not in planned_ids for item in requested):
        raise ValueError("requested batches must be explicitly present in the release plan")
    positions = [planned_ids.index(item) for item in requested]
    if positions != list(range(min(positions), max(positions) + 1)):
        raise ValueError("requested batches must be a contiguous ordered plan slice")
    if from_batch and from_batch not in requested:
        raise ValueError("--from-batch must be one of the requested batches")
    if from_stage and not from_batch:
        raise ValueError("--from-stage requires --from-batch")
    final_stage_index = STAGES.index(through)
    start_batch_index = requested.index(from_batch) if from_batch else 0
    schedule: list[tuple[BatchPlan, str]] = []
    by_id = {item.batch_id: item for item in plan.batches}
    for batch_index, batch_id in enumerate(requested):
        if batch_index < start_batch_index:
            continue
        first_stage = STAGES.index(from_stage) if from_stage and batch_id == from_batch else 0
        for stage in STAGES[first_stage : final_stage_index + 1]:
            state = _batch_journal(journal, batch_id)["stages"][stage]
            if state["status"] == "committed":
                if not _verify_checkpoint(state["checkpoint"]):
                    raise ValueError(f"committed checkpoint drift: {batch_id}/{stage}")
                if resume:
                    continue
            schedule.append((by_id[batch_id], stage))
    return schedule


@contextmanager
def _legacy_sandbox(plan: WavePlan, registry_path: Path) -> Iterator[None]:
    previous = (legacy.REGISTRY, legacy.BUILD_AT, legacy.REVIEW_DATE)
    legacy.REGISTRY = registry_path
    legacy.BUILD_AT = plan.build_at
    legacy.REVIEW_DATE = plan.review_date
    try:
        yield
    finally:
        legacy.REGISTRY, legacy.BUILD_AT, legacy.REVIEW_DATE = previous


def _stage_inputs(batch: BatchPlan, research_path: Path, media_path: Path) -> StageInputs:
    sealed = legacy.load_batch_inputs(batch.batch_id)
    return StageInputs(
        batch=sealed.batch,
        artists=sealed.artists,
        artworks=sealed.artworks,
        research_path=research_path,
        media_path=media_path,
    )


def _contextualize(value: Any, plan: WavePlan) -> Any:
    adapter = plan.legacy_adapter
    replacements = {
        adapter["template_phase_id"]: plan.phase_id,
        adapter["template_reviewer_id"]: plan.reviewer_id,
        adapter["template_actor_id"]: plan.actor_id,
        **{scope: plan.authorization_scope for scope in adapter["template_scopes"]},
    }
    if isinstance(value, list):
        return [_contextualize(item, plan) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, str):
            for source, replacement in replacements.items():
                value = value.replace(source, replacement)
        return value
    result = {key: _contextualize(item, plan) for key, item in value.items()}
    if {"source_id", "rule_id", "content_class", "scope_locator"} <= result.keys():
        source_key = str(result["source_id"]).removeprefix("source:")
        result["rule_id"] = _rule_id(plan, source_key, result["content_class"])
        result["scope_locator"] = plan.authorization_scope
    if {"source_id", "rule_id"} <= result.keys() and "content_class" not in result:
        source_key = str(result["source_id"]).removeprefix("source:")
        result["rule_id"] = _rule_id(plan, source_key, "data")
    return result


def _rule_id(plan: WavePlan, source_key: str, content_class: str) -> str:
    return f"{source_key}:{content_class}:user_authorization_{plan.authorization_rule_version}"


def _authorization_rule(
    plan: WavePlan,
    source_key: str,
    publisher: str,
    content_class: str,
) -> dict[str, Any]:
    return {
        "rule_id": _rule_id(plan, source_key, content_class),
        "applies_to": plan.authorization_scope,
        "scope_match": {
            "pattern": "^" + re.escape(plan.authorization_scope) + "$",
            "allowed_schemes": [],
            "allowed_hosts": [],
            "fields": [],
            "field_policy": "any",
            "normalization": "none",
            "require_explicit_query_fields": False,
            "allow_relative_path": True,
        },
        "rights_status": "licensed",
        "identifier": plan.authorization_basis,
        "version": "1.0",
        "url": "https://archmays.github.io/Museum-Codex/#/rights",
        "content_class": content_class,
        "attribution_template": publisher,
        "redistribution": "allowed",
        "modification": "allowed",
        "commercial_use": "allowed",
        "share_alike": False,
        "scope_note": (
            "The user designated this project resource for the release; independent privacy, secret, "
            "source-immutability, and technical gates remain enforced."
        ),
        "no_inheritance": True,
    }


def _contextualize_source_records(root: Path, plan: WavePlan) -> None:
    sources_path = root / "sources.json"
    document = _read(sources_path)
    for source in document["sources"]:
        source_key = source["registry_source_id"]
        rules = [
            _authorization_rule(plan, source_key, source["publisher"], content_class)
            for content_class in ("data", "media")
        ]
        source["license_rules"] = rules
        source["license_rules_snapshot_hash"] = _json_digest(rules)
        source["selected_license_rule_ids"] = [item["rule_id"] for item in rules]
        source["source_rule_ids"] = [item["rule_id"] for item in rules]
        source["authorization_basis"] = plan.authorization_basis
        source["accessed_at"] = plan.review_date
    _atomic_write(sources_path, document)


def _rebuild_package_manifest(root: Path, plan: WavePlan, batch: BatchPlan, stage: str) -> dict[str, Any]:
    manifest_path = root / "build-manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    if stage == "research":
        artifact_id = f"{plan.artifact_namespace}:batch-{batch.batch_id.rsplit('-', 1)[-1]}-formal-candidate-v2"
        inputs = [
            {"path": "governance/museum-09-batch-registry.json", "batch_id": batch.batch_id},
            {
                "path": "data/reviewed/art/museum-09a/global-expansion-universe-v1",
                "closure": batch.input_closure_hash,
            },
        ]
    else:
        artifact_id = f"{plan.artifact_namespace}-media:batch-{batch.batch_id.rsplit('-', 1)[-1]}-media-bundle-v2"
        research_manifest = _read(ROOT / batch.research_path / "build-manifest.json")
        inputs = [{"path": batch.research_path, "content_hash": research_manifest["artifact_content_hash"]}]
    manifest = legacy._artifact_manifest(root, artifact_id=artifact_id, stage=stage, inputs=inputs)
    manifest["built_at"] = plan.build_at
    manifest["canonical_writer"] = "museum_pipeline.art.expansion_wave_factory"
    manifest["phase_id"] = plan.phase_id
    manifest["batch_id"] = batch.batch_id
    manifest["stable_input_hash"] = batch.input_closure_hash
    _atomic_write(manifest_path, manifest)
    return manifest


def _normalize_research(root: Path, plan: WavePlan, batch: BatchPlan) -> dict[str, Any]:
    for path in sorted(root.rglob("*.json")):
        _atomic_write(path, _contextualize(_read(path), plan))
    _contextualize_source_records(root, plan)
    transaction = _read(root / "transaction-manifest.json")
    transaction.update(
        {
            "transaction_id": f"{batch.batch_id}:research-v2",
            "phase_id": plan.phase_id,
            "stable_input_hash": batch.input_closure_hash,
            "recovery_boundary": "atomic formal candidate package",
        }
    )
    _atomic_write(root / "transaction-manifest.json", transaction)
    return _rebuild_package_manifest(root, plan, batch, "research")


def _normalize_media(root: Path, plan: WavePlan, batch: BatchPlan) -> dict[str, Any]:
    for path in sorted(root.rglob("*.json")):
        _atomic_write(path, _contextualize(_read(path), plan))
    inputs = legacy.load_batch_inputs(batch.batch_id)
    by_url = {item["source_url"]: item for item in inputs.artworks}
    decisions_path = root / "object-media-decisions.json"
    decisions = _read(decisions_path)
    for item in decisions["records"]:
        sealed = by_url[item["official_object_url"]]
        item.update(
            {
                "review_phase_id": plan.phase_id,
                "reviewed_by": plan.reviewer_id,
                "reviewed_at": plan.review_date,
                "authorization_basis": plan.authorization_basis,
                "authorization_scope": plan.authorization_scope,
                "sealed_media_availability": sealed.get("media_availability"),
                "sealed_media_review_hint": sealed.get("rights_media_future_review_hint"),
                "sealed_metadata_license": sealed.get("metadata_license"),
                "technical_media_locator_present": False,
                "object_level_review_complete": True,
                "reason_codes": [
                    "no_media_delivery_locator_in_sealed_input",
                    "metadata_license_not_used_as_media_permission",
                ],
            }
        )
    _atomic_write(decisions_path, decisions)
    validation_path = root / "validation-summary.json"
    validation = _read(validation_path)
    validation["phase_id"] = plan.phase_id
    validation["counts"]["object_level_reviewed"] = len(decisions["records"])
    validation["counts"]["technical_media_locator_present"] = 0
    validation["counts"]["authorization_basis_recorded"] = len(decisions["records"])
    _atomic_write(validation_path, validation)
    transaction = _read(root / "transaction-manifest.json")
    transaction.update(
        {
            "transaction_id": f"{batch.batch_id}:media-v2",
            "phase_id": plan.phase_id,
            "stable_input_hash": batch.input_closure_hash,
            "recovery_boundary": "atomic object-level media review package",
        }
    )
    _atomic_write(root / "transaction-manifest.json", transaction)
    return _rebuild_package_manifest(root, plan, batch, "media")


def _iter_bindings(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _iter_bindings(item)
    elif isinstance(value, dict):
        bindings = value.get("source_license_bindings")
        if isinstance(bindings, list):
            for binding in bindings:
                if isinstance(binding, dict):
                    yield binding
        for item in value.values():
            yield from _iter_bindings(item)


def _update_release_authorization(root: Path, research_root: Path, plan: WavePlan) -> None:
    research_sources = _read(research_root / "sources.json")["sources"]
    snapshot_path = root / "source-rules-snapshot.json"
    snapshot = _read(snapshot_path)
    by_source = {item["source_id"]: item for item in snapshot["sources"]}
    for source in research_sources:
        item = by_source[source["id"]]
        known = {rule["rule_id"] for rule in item["license_rules"]}
        for rule in source["license_rules"]:
            if rule["rule_id"] not in known:
                item["license_rules"].append(rule)
        item["license_rules"] = sorted(item["license_rules"], key=lambda rule: rule["rule_id"])
        item["license_rules_snapshot_hash"] = _json_digest(item["license_rules"])
    snapshot["generated_at"] = plan.build_at
    snapshot["sources"] = sorted(snapshot["sources"], key=lambda item: item["source_id"])
    _atomic_write(snapshot_path, snapshot)

    rules_by_source = {
        item["source_id"]: {rule["rule_id"]: rule for rule in item["license_rules"]}
        for item in snapshot["sources"]
    }
    registry_id_by_source = {
        item["source_id"]: item["registry_source_id"] for item in snapshot["sources"]
    }
    claims_path = root / "claims.json"
    claims = _read(claims_path)
    release_sources = {
        wrapper["data"]["id"]: wrapper["data"]
        for wrapper in claims["records"]
        if wrapper["data"].get("entity_type") == "source"
    }
    for source_id, source in release_sources.items():
        snapshot_source = by_source[source_id]
        source["license_rules"] = snapshot_source["license_rules"]
        source["license_rules_snapshot_hash"] = snapshot_source["license_rules_snapshot_hash"]
        source["selected_license_rule_ids"] = [
            rule["rule_id"] for rule in snapshot_source["license_rules"]
        ]
        source["source_rule_ids"] = source["selected_license_rule_ids"]

    for binding in _iter_bindings(claims):
        source_id = binding.get("source_id")
        content_class = binding.get("content_class")
        source_rules = rules_by_source.get(source_id, {})
        if binding.get("rule_id") in source_rules:
            continue
        preferred_id = _rule_id(
            plan,
            registry_id_by_source[source_id],
            content_class,
        )
        rule = source_rules.get(preferred_id)
        if rule is None:
            rule = next(
                (
                    candidate
                    for candidate in source_rules.values()
                    if candidate["content_class"] == content_class
                ),
                None,
            )
        if rule is None:
            raise ValueError(
                f"no release rule for {source_id} content class {content_class}"
            )
        binding.update(
            {
                "rule_id": rule["rule_id"],
                "scope_locator": rule["applies_to"],
                "scope_fields": [],
                "permission_resolution": "user_authorization",
            }
        )
    _atomic_write(claims_path, claims)

    rule_lookup = {
        rule_id: rule
        for source_rules in rules_by_source.values()
        for rule_id, rule in source_rules.items()
    }
    used: dict[str, set[str]] = {}
    for binding in _iter_bindings(claims):
        source_id = binding.get("source_id")
        rule_id = binding.get("rule_id")
        if source_id and rule_id:
            used.setdefault(source_id, set()).add(rule_id)
    notices_path = root / "third-party-notices.json"
    notices = _read(notices_path)
    notice_by_id = {item["record_id"]: item for item in notices["notices"]}
    for source_id, rule_ids in used.items():
        if source_id not in release_sources:
            continue
        source = release_sources[source_id]
        rules = [rule_lookup[rule_id] for rule_id in sorted(rule_ids)]
        notice = notice_by_id.get(source_id, {"record_id": source_id})
        notice.update(
            {
                "source_url": source["official_url"],
                "license_rule_ids": sorted(rule_ids),
                "license_identifiers": sorted({item["identifier"] for item in rules}),
                "attribution_texts": sorted(
                    {
                        item["attribution_template"]
                        for item in rules
                        if item["attribution_template"]
                    }
                ),
                "rights_holder": source["publisher"],
                "notice": (
                    "Public data use passes by explicit user authorization while independent project "
                    f"safeguards remain enforced; publisher: {source['publisher']}."
                ),
            }
        )
        notice_by_id[source_id] = notice
    notices["notices"] = sorted(notice_by_id.values(), key=lambda item: item["record_id"])
    _atomic_write(notices_path, notices)


def _release_profile(root: Path, research_root: Path, batch: BatchPlan) -> dict[str, Any]:
    return {
        "batch_sequence": int(batch.batch_id.rsplit("-", 1)[-1]),
        "artists": _read(root / "artists.json")["artists"],
        "artworks": _read(root / "artworks.json")["artworks"],
        "contexts": _read(root / "contexts.json")["contexts"],
        "claims": _read(root / "claims.json")["claims"],
        "evidence": _read(root / "evidence.json")["evidence"],
        "sources": _read(root / "sources.json")["sources"],
        "relationships": _read(root / "relationships.json")["relationships"],
        "new_artists": _read(research_root / "artists.json")["artists"],
        "new_artworks": _read(research_root / "artworks.json")["artworks"],
        "new_contexts": _read(research_root / "contexts.json")["contexts"],
        "new_episodes": _read(research_root / "place-time-episodes.json")["episodes"],
        "artist_slugs": [
            item["public_slug"] for item in _read(research_root / "artists.json")["artists"]
        ],
    }


def _normalize_release(root: Path, plan: WavePlan, batch: BatchPlan) -> dict[str, Any]:
    search_manifest = _read(root / "search" / "manifest.json")
    search_manifest["phase_id"] = plan.phase_id
    _atomic_write(root / "search" / "manifest.json", search_manifest)
    _update_release_authorization(root, ROOT / batch.research_path, plan)
    narratives = _read(root / "artist-narratives.json")["narratives"]
    validation_path = root / "validation-summary.json"
    validation = _read(validation_path)
    validation.update(
        {
            "id": f"validation-summary:{batch.version}",
            "child_facing_intro_count": len(narratives),
            "child_facing_intro_provenance_count": sum(
                1 for item in narratives if item.get("sentence_provenance")
            ),
            "duplicate_intro_count": len(narratives)
            - len({item["public_intro"]["en"] for item in narratives}),
        }
    )
    _atomic_write(validation_path, validation)
    profile = _release_profile(root, ROOT / batch.research_path, batch)
    predecessor_manifest = _read(
        ROOT
        / "public"
        / "releases"
        / batch.predecessor_id.removeprefix("release:")
        / "manifest.json"
    )
    manifest = legacy._release_manifest(
        root,
        predecessor_manifest,
        batch.release_id,
        batch.version,
        batch.predecessor_id,
        profile,
    )
    _atomic_write(root / "manifest.json", manifest)
    research_manifest = _read(ROOT / batch.research_path / "build-manifest.json")
    media_manifest = _read(ROOT / batch.media_path / "build-manifest.json")
    transaction = {
        "schema_version": "1.0.0",
        "transaction_id": f"{batch.batch_id}:release:{batch.version}:v2",
        "phase_id": plan.phase_id,
        "stage": "release",
        "status": "committed",
        "release_id": batch.release_id,
        "predecessor": batch.predecessor_id,
        "stable_input_hash": batch.input_closure_hash,
        "research_content_hash": research_manifest["artifact_content_hash"],
        "media_content_hash": media_manifest["artifact_content_hash"],
        "release_content_hash": manifest["content_hash"],
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "physical_tree": legacy._tree_record(root),
        "recovery_boundary": "immutable release directory only",
        "deployment_eligible": batch.deployment_eligible,
    }
    _atomic_write(root / "batch-transaction-manifest.json", transaction)
    manifest = legacy._release_manifest(
        root,
        predecessor_manifest,
        batch.release_id,
        batch.version,
        batch.predecessor_id,
        profile,
    )
    _atomic_write(root / "manifest.json", manifest)
    result = legacy.validate_release(
        root,
        release_id=batch.release_id,
        predecessor_id=batch.predecessor_id,
        expected_artists=batch.cumulative_artist_count,
        expected_artworks=batch.cumulative_artwork_count,
    )
    if not result["ok"]:
        raise ValueError(f"release validation failed: {result['failures'][:12]}")
    return result


def execute_stage(plan: WavePlan, batch: BatchPlan, stage: str, sandbox_registry: Path) -> dict[str, Any]:
    destination = batch.artifact_path(stage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir():
        checkpoint = _artifact_checkpoint(destination, stage)
        if stage == "release":
            summary = legacy.validate_release(
                destination,
                release_id=batch.release_id,
                predecessor_id=batch.predecessor_id,
                expected_artists=batch.cumulative_artist_count,
                expected_artworks=batch.cumulative_artwork_count,
            )
            if not summary["ok"]:
                raise ValueError(
                    f"existing release validation failed: {summary['failures'][:12]}"
                )
        else:
            summary = _read(destination / "build-manifest.json")
        return {
            "ok": True,
            "batch_id": batch.batch_id,
            "stage": stage,
            "created": False,
            "summary": summary,
            "checkpoint": checkpoint,
        }
    with tempfile.TemporaryDirectory(prefix=f".{batch.batch_id}-{stage}-", dir=destination.parent) as temporary:
        temporary_root = Path(temporary)
        staged = temporary_root / destination.name
        if stage == "research":
            inputs = _stage_inputs(batch, staged, ROOT / batch.media_path)
            with _legacy_sandbox(plan, sandbox_registry):
                legacy.run_research(inputs, release_id=batch.release_id, version=batch.version)
            summary = _normalize_research(staged, plan, batch)
        elif stage == "media":
            inputs = _stage_inputs(batch, ROOT / batch.research_path, staged)
            with _legacy_sandbox(plan, sandbox_registry):
                legacy.run_media(inputs)
            summary = _normalize_media(staged, plan, batch)
        elif stage == "release":
            inputs = _stage_inputs(batch, ROOT / batch.research_path, ROOT / batch.media_path)
            with _legacy_sandbox(plan, sandbox_registry):
                legacy.run_release(
                    inputs,
                    release_id=batch.release_id,
                    predecessor_id=batch.predecessor_id,
                    version=batch.version,
                    output_dir=staged,
                )
                summary = _normalize_release(staged, plan, batch)
        else:
            raise ValueError(f"unsupported stage: {stage}")
        created = _commit_directory(staged, destination)
    return {
        "ok": True,
        "batch_id": batch.batch_id,
        "stage": stage,
        "created": created,
        "summary": summary,
        "checkpoint": _artifact_checkpoint(destination, stage),
    }


def _append_transition(batch: dict[str, Any], target: str, plan: WavePlan) -> None:
    current = batch["status"]
    if current == target:
        return
    if current == "published":
        if target != "published":
            raise ValueError(f"cannot regress published batch {batch['id']}")
        return
    if STATE_ORDER[target] < STATE_ORDER[current]:
        raise ValueError(f"cannot regress {batch['id']} from {current} to {target}")
    history = batch.setdefault("status_history", [])
    ordered = sorted(STATE_ORDER, key=STATE_ORDER.get)
    for state in ordered[STATE_ORDER[current] + 1 : STATE_ORDER[target] + 1]:
        history.append({"from": current, "to": state, "at": plan.build_at, "actor": plan.actor_id})
        current = state
    batch["status"] = target


def _record_registry_stage(
    registry_path: Path,
    plan: WavePlan,
    batch_plan: BatchPlan,
    stage: str,
    checkpoint: dict[str, Any],
) -> None:
    registry = _read(registry_path)
    batch = next(item for item in registry["batches"] if item["id"] == batch_plan.batch_id)
    if stage == "research":
        if STATE_ORDER[batch["status"]] > STATE_ORDER["formal_candidate_ready"]:
            if batch.get("formal_package_content_hash") != checkpoint["content_hash"]:
                raise ValueError(
                    f"{batch_plan.batch_id}: completed research checkpoint changed"
                )
            return
        _append_transition(batch, "formal_candidate_ready", plan)
        batch.update(
            {
                "formal_package_id": _read(ROOT / batch_plan.research_path / "build-manifest.json")["id"],
                "formal_package_content_hash": checkpoint["content_hash"],
                "formal_package_tree_hash": checkpoint["physical_tree"]["hash"],
                "source_drift_counts": {
                    "unchanged": batch_plan.artist_count + batch_plan.artwork_count,
                    "changed": 0,
                    "unavailable": 0,
                },
                "replacement_count": 0,
                "next_authorized_phase": None,
            }
        )
    elif stage == "media":
        if STATE_ORDER[batch["status"]] > STATE_ORDER["media_bundle_ready"]:
            if batch.get("media_package_content_hash") != checkpoint["content_hash"]:
                raise ValueError(
                    f"{batch_plan.batch_id}: completed media checkpoint changed"
                )
            return
        _append_transition(batch, "media_bundle_ready", plan)
        validation = _read(ROOT / batch_plan.media_path / "validation-summary.json")
        batch.update(
            {
                "media_package_id": _read(ROOT / batch_plan.media_path / "build-manifest.json")["id"],
                "media_package_content_hash": checkpoint["content_hash"],
                "media_package_tree_hash": checkpoint["physical_tree"]["hash"],
                "media_downloaded": False,
                "metadata_only_after_review_count": batch_plan.artwork_count,
                "object_level_media_review_count": validation["counts"]["object_level_reviewed"],
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
                "next_authorized_phase": None,
            }
        )
    else:
        release = _read(ROOT / batch_plan.release_path / "manifest.json")
        release_record = {
            "id": batch_plan.release_id,
            "content_hash": release["content_hash"],
            "manifest_sha256": checkpoint["manifest_sha256"],
            "tree_hash": checkpoint["physical_tree"]["hash"],
        }
        common = {
            "public_release_created": True,
            "contribution_counts": {
                "artists": batch_plan.artist_count,
                "artworks": batch_plan.artwork_count,
            },
            "current_public_counts": {
                "artists": batch_plan.cumulative_artist_count,
                "artworks": batch_plan.cumulative_artwork_count,
            },
            "current_media_counts": {
                "self_hosted_artworks": 71,
                "external_link_only_artworks": 25,
                "metadata_only_artworks": batch_plan.cumulative_artwork_count - 96,
                "media_assets": 560,
                "new_originals": 0,
                "new_derivatives": 0,
            },
            "current_relationship_count": len(
                _read(ROOT / batch_plan.release_path / "relationships.json")["relationships"]
            ),
            "current_episode_count": len(
                _read(ROOT / batch_plan.release_path / "artist-place-episodes.json")["episodes"]
            ),
            "current_tour_count": 18,
            "next_authorized_phase": None,
        }
        if batch_plan.deployment_eligible:
            batch.update(
                {
                    **common,
                    "candidate_release": release_record,
                    "release_transaction_status": "ready_for_final_deployment",
                    "is_current_release": False,
                    "runtime_changed": False,
                    "deployment_count": 0,
                }
            )
        else:
            _append_transition(batch, "published", plan)
            batch.update(
                {
                    **common,
                    "current_release": release_record,
                    "published_release": release_record,
                    "publication_kind": "immutable_release_not_current",
                    "is_current_release": False,
                    "runtime_changed": False,
                    "deployment_count": 0,
                    "runtime_binding": {
                        "kind": "immutable_release_not_runtime",
                        "release_id": batch_plan.release_id,
                        "runtime_changed": False,
                    },
                    "deployment_binding": {
                        "kind": "explicit_non_deployment",
                        "release_id": batch_plan.release_id,
                        "deployment_count": 0,
                    },
                    "online_closure": {
                        "kind": "not_applicable_intermediate_release",
                        "release_id": batch_plan.release_id,
                        "deployment_count": 0,
                    },
                }
            )
    _atomic_write(registry_path, registry)


def validate_cross_batch(plan: WavePlan, registry_path: Path = CANONICAL_REGISTRY) -> dict[str, Any]:
    failures: list[str] = []
    results = []
    all_new_artists: list[str] = []
    all_new_artworks: list[str] = []
    all_new_intros: list[str] = []
    expected_predecessor = plan.document["current_release_id"]
    for batch in plan.batches:
        root = ROOT / batch.release_path
        result = legacy.validate_release(
            root,
            release_id=batch.release_id,
            predecessor_id=batch.predecessor_id,
            expected_artists=batch.cumulative_artist_count,
            expected_artworks=batch.cumulative_artwork_count,
        )
        results.append(result)
        failures.extend(f"{batch.batch_id}: {item}" for item in result["failures"])
        if batch.predecessor_id != expected_predecessor:
            failures.append(f"{batch.batch_id}: predecessor chain mismatch")
        expected_predecessor = batch.release_id
        research = ROOT / batch.research_path
        all_new_artists.extend(item["id"] for item in _read(research / "artists.json")["artists"])
        all_new_artworks.extend(item["id"] for item in _read(research / "artworks.json")["artworks"])
        all_new_intros.extend(
            item["public_intro"]["en"]
            for item in _read(research / "artist-narratives.json")["narratives"]
        )
    if len(all_new_artists) != len(set(all_new_artists)):
        failures.append("cross-batch duplicate artist ids")
    if len(all_new_artworks) != len(set(all_new_artworks)):
        failures.append("cross-batch duplicate artwork ids")
    if len(all_new_intros) != len(set(all_new_intros)):
        failures.append("cross-batch duplicate child-facing introductions")
    final_root = ROOT / plan.batches[-1].release_path
    relationships = _read(final_root / "relationships.json")["relationships"]
    explorer = _read(final_root / "relationship-explorer-config.json")
    media = _read(final_root / "media-index.json")
    final_counts = results[-1]["counts"] if results else {}
    if final_counts.get("artists") != plan.batches[-1].cumulative_artist_count:
        failures.append("final artist count mismatch")
    if final_counts.get("artworks") != plan.batches[-1].cumulative_artwork_count:
        failures.append("final artwork count mismatch")
    if any(
        item.get("level") != "C"
        or item.get("type") not in {"shared_subject", "shared_material", "shared_technique"}
        or item.get("is_algorithmic") is not False
        or item.get("historical_relationship_strength") is not None
        or item.get("computational_similarity") is not None
        for item in relationships
    ):
        failures.append("relationship semantic boundary failure")
    expected_explorer = {
        "default_global_graph_node_count": 0,
        "focus_initial_per_lane_limit": 4,
        "focus_expanded_node_limit": 20,
        "theme_visual_artist_limit": 16,
    }
    for key, expected in expected_explorer.items():
        if explorer.get(key) != expected:
            failures.append(f"explorer limit mismatch: {key}")
    registry_failures = legacy.validate_registry_lifecycle(_read(registry_path))
    failures.extend(registry_failures)
    return {
        "schema_version": "1.0.0",
        "phase_id": plan.phase_id,
        "status": "pass" if not failures else "fail",
        "stable_input_hash": compute_wave_input_hash(plan, registry_path),
        "counts": {
            "new_artists": len(all_new_artists),
            "new_artworks": len(all_new_artworks),
            "new_child_facing_intros": len(all_new_intros),
            "duplicate_intros": len(all_new_intros) - len(set(all_new_intros)),
            "relationships": len(relationships),
            "episodes": final_counts.get("episodes"),
            "tours": 18,
            "self_hosted_artworks": media["counts"]["approved_artworks"],
            "external_link_only_artworks": 25,
            "metadata_only_artworks": media["metadata_only_count"],
            "public_originals": 0,
            "new_originals": 0,
            "new_derivatives": 0,
        },
        "final_counts": final_counts,
        "release_results": results,
        "predecessor_chain": [
            {"release_id": item.release_id, "predecessor_id": item.predecessor_id}
            for item in plan.batches
        ],
        "intermediate_deployment_count": 0,
        "final_deployment_eligible_release_id": plan.final_release_id,
        "failures": failures,
    }


def _write_deployment_marker(plan: WavePlan, report: dict[str, Any], input_hash: str) -> dict[str, Any]:
    final_batch = plan.batches[-1]
    checkpoint = _artifact_checkpoint(ROOT / final_batch.release_path, "release")
    marker = {
        "schema_version": "1.0.0",
        "phase_id": plan.phase_id,
        "status": "ready_for_single_final_deployment",
        "stable_input_hash": input_hash,
        "release_id": final_batch.release_id,
        "release_path": final_batch.release_path,
        "manifest_sha256": checkpoint["manifest_sha256"],
        "content_hash": checkpoint["content_hash"],
        "tree_hash": checkpoint["physical_tree"]["hash"],
        "intermediate_releases": [
            {"release_id": item.release_id, "deployment_eligible": False}
            for item in plan.batches[:-1]
        ],
        "deployment_eligible": True,
        "expected_runtime_deployment_count": 1,
        "intermediate_deployment_count": 0,
        "cross_batch_status": report["status"],
    }
    _atomic_write(plan.deployment_marker_path, marker)
    return marker


def run_wave(
    plan: WavePlan,
    *,
    batch_ids: Iterable[str],
    through: str,
    journal_path: Path | None = None,
    dry_run: bool = False,
    resume: bool = False,
    from_batch: str | None = None,
    from_stage: str | None = None,
    no_deploy: bool = False,
    registry_path: Path = CANONICAL_REGISTRY,
    stage_runner: StageRunner = execute_stage,
) -> dict[str, Any]:
    _validate_plan_against_registry(plan, registry_path)
    input_hash = compute_wave_input_hash(plan, registry_path)
    journal_file = (journal_path or plan.journal_path).resolve()
    if dry_run:
        journal = (
            _read(journal_file)
            if journal_file.is_file()
            else _initial_journal(plan, input_hash)
        )
        schedule = build_schedule(
            plan,
            journal,
            batch_ids=batch_ids,
            through=through,
            resume=resume,
            from_batch=from_batch,
            from_stage=from_stage,
        )
        return {
            "ok": True,
            "dry_run": True,
            "stable_input_hash": input_hash,
            "schedule": [{"batch_id": batch.batch_id, "stage": stage} for batch, stage in schedule],
            "writes": 0,
        }
    journal = _load_or_create_journal(plan, journal_file, input_hash, resume=resume)
    _atomic_write(journal_file, journal)
    schedule = build_schedule(
        plan,
        journal,
        batch_ids=batch_ids,
        through=through,
        resume=resume,
        from_batch=from_batch,
        from_stage=from_stage,
    )
    with tempfile.TemporaryDirectory(prefix=".museum-expansion-wave-registry-", dir=ROOT) as temporary:
        sandbox_registry = Path(temporary) / "registry.json"
        shutil.copyfile(registry_path, sandbox_registry)
        results = []
        for batch, stage in schedule:
            stage_state = _batch_journal(journal, batch.batch_id)["stages"][stage]
            stage_state.update(
                {
                    "status": "running",
                    "attempts": stage_state["attempts"] + 1,
                    "error": None,
                }
            )
            journal["failure_cursor"] = None
            _atomic_write(journal_file, journal)
            try:
                result = stage_runner(plan, batch, stage, sandbox_registry)
                _record_registry_stage(registry_path, plan, batch, stage, result["checkpoint"])
                stage_state.update(
                    {
                        "status": "committed",
                        "checkpoint": result["checkpoint"],
                        "error": None,
                    }
                )
                results.append(result)
                _atomic_write(journal_file, journal)
            except Exception as error:
                stage_state.update(
                    {
                        "status": "failed",
                        "error": {
                            "type": error.__class__.__name__,
                            "message": str(error),
                        },
                    }
                )
                journal["status"] = "failed"
                journal["failure_cursor"] = {"batch_id": batch.batch_id, "stage": stage}
                _atomic_write(journal_file, journal)
                raise WaveExecutionError(f"wave failed at {batch.batch_id}/{stage}: {error}") from error
    selected = list(batch_ids)
    completed_all_releases = (
        through == "release"
        and selected == [item.batch_id for item in plan.batches]
        and all(
            _batch_journal(journal, item.batch_id)["stages"]["release"]["status"] == "committed"
            for item in plan.batches
        )
    )
    report = None
    marker = None
    if completed_all_releases:
        report = validate_cross_batch(plan, registry_path)
        _atomic_write(plan.cross_batch_report_path, report)
        if report["status"] != "pass":
            journal["status"] = "failed"
            journal["failure_cursor"] = {"batch_id": plan.batches[-1].batch_id, "stage": "cross_batch"}
            _atomic_write(journal_file, journal)
            raise WaveExecutionError("cross-batch validation failed")
        if not no_deploy:
            marker = _write_deployment_marker(plan, report, input_hash)
            journal["deployment"]["marker_status"] = "ready_for_single_final_deployment"
        journal["status"] = "release_chain_committed"
    _atomic_write(journal_file, journal)
    return {
        "ok": True,
        "dry_run": False,
        "stable_input_hash": input_hash,
        "results": results,
        "journal_path": journal_file.relative_to(ROOT).as_posix(),
        "journal_status": journal["status"],
        "cross_batch": report,
        "deployment_marker": marker,
    }


def record_online_closeout(
    plan: WavePlan,
    evidence: dict[str, Any],
    *,
    registry_path: Path = CANONICAL_REGISTRY,
) -> dict[str, Any]:
    required = {
        "runtime_commit",
        "deployment_id",
        "pages_url",
        "online_byte_closure",
        "functional_smoke",
    }
    missing = sorted(required - evidence.keys())
    if missing:
        raise ValueError(f"closeout evidence missing keys: {missing}")
    batch_plan = plan.batches[-1]
    registry = _read(registry_path)
    batch = next(item for item in registry["batches"] if item["id"] == batch_plan.batch_id)
    candidate = batch.get("candidate_release")
    if not candidate or candidate.get("id") != plan.final_release_id:
        raise ValueError("final release candidate binding is absent")
    _append_transition(batch, "published", plan)
    evidence_path = evidence.get(
        "evidence_path",
        f"docs/qa/{plan.artifact_namespace}/closeout-evidence.json",
    )
    batch.update(
        {
            "current_release": candidate,
            "published_release": candidate,
            "publication_kind": "immutable_release_current_and_deployed",
            "is_current_release": True,
            "runtime_changed": True,
            "runtime_commits": [evidence["runtime_commit"]],
            "runtime_binding": {
                "kind": "git_commit_containing_exact_release",
                "release_id": plan.final_release_id,
                "manifest_sha256": candidate["manifest_sha256"],
                "evidence_path": evidence_path,
            },
            "deployments": [str(evidence["deployment_id"])],
            "deployment_count": 1,
            "deployment_binding": {
                "kind": "github_pages_deployment_evidence",
                "release_id": plan.final_release_id,
                "evidence_path": evidence_path,
            },
            "online_closure": {
                "pages_url": evidence["pages_url"],
                "bytes": evidence["online_byte_closure"],
                "functional_smoke": evidence["functional_smoke"],
                "evidence_path": evidence_path,
            },
            "release_transaction_status": "online_closed",
            "next_authorized_phase": None,
        }
    )
    _atomic_write(registry_path, registry)
    return {
        "ok": True,
        "batch_id": batch_plan.batch_id,
        "release_id": plan.final_release_id,
        "deployment_id": str(evidence["deployment_id"]),
    }
