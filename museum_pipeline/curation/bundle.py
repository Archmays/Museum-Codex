from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.paths import resolve_within, safe_relative_path
from museum_pipeline.validation.dispatch import ValidationIssue, load_schema_environment, validate_record


REQUIRED_FILES = {
    "candidate-pool.json", "qualified-pool.json", "artwork-rights-preflight.json",
    "relationship-leads.json", "scenario-a.json", "scenario-b.json", "scenario-c.json",
    "recommended-slate.json", "alternates.json", "selection-handoff.md",
    "selection-decision-template.json", "source-snapshots.json", "review-log.json",
}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".mp3", ".mp4", ".wav", ".webm", ".glb", ".gltf"}
ROLE_BY_FILE = {
    "candidate-pool.json": "candidate_pool",
    "qualified-pool.json": "qualified_pool",
    "artwork-rights-preflight.json": "artwork_rights",
    "relationship-leads.json": "relationship_leads",
    "scenario-a.json": "scenario", "scenario-b.json": "scenario", "scenario-c.json": "scenario",
    "recommended-slate.json": "recommended_slate", "alternates.json": "alternates",
    "selection-handoff.md": "selection_handoff",
    "selection-decision-template.json": "selection_decision_template",
    "source-snapshots.json": "source_snapshots", "review-log.json": "review_log",
}


def build_selection_bundle(input_document: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PipelineError("selection_output_not_empty", "Selection bundle output must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink():
        raise PipelineError("symlink_escape", "Selection bundle root cannot be a symbolic link")

    candidates = input_document.get("candidate_pool", [])
    qualified = [item for item in candidates if item.get("candidate_status") == "qualified"]
    artworks = input_document.get("artwork_rights_preflight", [])
    leads = input_document.get("relationship_leads", [])
    scenarios = input_document.get("scenarios", {})
    alternates = input_document.get("alternates", [])
    source_snapshots = input_document.get("source_snapshots", [])
    review_log = input_document.get("review_log", [])
    generated_at = str(input_document.get("generated_at", ""))
    input_hashes = {"research-input.json": canonical_sha256(input_document)}
    source_hashes = sorted({str(item.get("sha256")) for item in source_snapshots if item.get("sha256")})
    adapter_versions = dict(sorted(input_document.get("adapter_versions", {}).items()))

    scenario_records = [scenarios.get(key) for key in ("a", "b", "c")]
    recommended = scenarios.get("recommended")
    if not all(isinstance(item, dict) for item in [*scenario_records, recommended]):
        raise PipelineError("selection_scenarios_missing", "Three scenarios and one recommended slate are required")

    basis = _bundle_basis(
        input_hashes=input_hashes, source_hashes=source_hashes, adapter_versions=adapter_versions,
        candidates=candidates, qualified=qualified, scenarios=scenario_records,
        recommended=recommended, alternates=alternates,
    )
    bundle_hash = canonical_sha256(basis)
    decision = pending_decision_template(bundle_hash)
    handoff = render_selection_handoff(
        candidates=candidates, artworks=artworks, leads=leads, scenarios=scenario_records,
        recommended=recommended, alternates=alternates, bundle_hash=bundle_hash,
    )

    documents: dict[str, Any] = {
        "candidate-pool.json": candidates,
        "qualified-pool.json": qualified,
        "artwork-rights-preflight.json": artworks,
        "relationship-leads.json": leads,
        "scenario-a.json": scenario_records[0],
        "scenario-b.json": scenario_records[1],
        "scenario-c.json": scenario_records[2],
        "recommended-slate.json": recommended,
        "alternates.json": alternates,
        "selection-decision-template.json": decision,
        "source-snapshots.json": source_snapshots,
        "review-log.json": review_log,
    }
    for name, value in documents.items():
        write_canonical_json(output_dir / name, value)
    _write_text_atomic(output_dir / "selection-handoff.md", handoff)

    file_entries = []
    for name in sorted(REQUIRED_FILES):
        path = output_dir / name
        file_entries.append({
            "path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path),
            "content_role": ROLE_BY_FILE[name],
        })
    manifest = {
        "schema_version": "1.0.0",
        "id": f"selection-review-bundle:{uuid.uuid5(uuid.NAMESPACE_URL, bundle_hash)}",
        "entity_type": "selection_review_bundle",
        "phase_id": "MUSEUM-03A",
        "candidate_pool_count": len(candidates),
        "qualified_candidate_count": len(qualified),
        "selection_scenario_ids": [item["id"] for item in scenario_records],
        "recommended_slate_id": recommended["id"],
        "alternate_candidate_ids": [item["candidate_id"] for item in alternates],
        "files": file_entries,
        "input_hashes": input_hashes,
        "source_snapshot_hashes": source_hashes,
        "adapter_versions": adapter_versions,
        "generated_at": generated_at,
        "bundle_hash": bundle_hash,
        "user_confirmation_received": False,
        "candidate_data_publicly_exposed": False,
        "media_downloaded": False,
    }
    write_canonical_json(output_dir / "bundle-manifest.json", manifest)
    issues = validate_selection_bundle(output_dir)
    if issues:
        raise PipelineError("selection_bundle_invalid", f"Selection bundle failed validation with {len(issues)} issue(s)")
    return manifest


def validate_selection_bundle(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    environment = load_schema_environment()
    try:
        root = root.resolve(strict=True)
    except OSError:
        return [ValidationIssue("selection_bundle_missing", "Selection bundle directory is missing")]
    if not root.is_dir():
        return [ValidationIssue("selection_bundle_missing", "Selection bundle path is not a directory")]

    for path in root.rglob("*"):
        if path.is_symlink():
            issues.append(ValidationIssue("symlink_escape", "Selection bundle contains a symbolic link", path.name))
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES:
            issues.append(ValidationIssue("media_bytes_in_selection_bundle", "Selection bundle cannot contain media bytes", path.name))

    manifest_path = root / "bundle-manifest.json"
    manifest = _load_json(manifest_path, issues)
    if not isinstance(manifest, dict):
        return _unique(issues)
    issues.extend(validate_record(manifest, environment=environment))
    entries = manifest.get("files", [])
    entry_paths = [item.get("path") for item in entries if isinstance(item, dict)]
    if len(entry_paths) != len(set(entry_paths)):
        issues.append(ValidationIssue("bundle_file_duplicate", "Manifest file paths must be unique", "$.files"))
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"bundle-manifest.json"}
    if set(entry_paths) != actual or actual != REQUIRED_FILES:
        issues.append(ValidationIssue("bundle_file_set_mismatch", "Bundle files must exactly match the governed selection file set", "$.files"))
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        try:
            safe_relative_path(str(entry.get("path", "")))
            path = resolve_within(root, str(entry.get("path", "")), must_exist=True)
        except (PipelineError, OSError):
            issues.append(ValidationIssue("path_escape", "Manifest file path does not resolve safely", f"$.files[{index}].path"))
            continue
        if path.stat().st_size != entry.get("bytes") or sha256_file(path) != entry.get("sha256"):
            issues.append(ValidationIssue("selection_bundle_stale", "Manifest bytes or SHA-256 no longer match the file", f"$.files[{index}]"))

    candidates = _load_json(root / "candidate-pool.json", issues, [])
    qualified = _load_json(root / "qualified-pool.json", issues, [])
    artworks = _load_json(root / "artwork-rights-preflight.json", issues, [])
    leads = _load_json(root / "relationship-leads.json", issues, [])
    scenario_records = [_load_json(root / name, issues, {}) for name in ("scenario-a.json", "scenario-b.json", "scenario-c.json")]
    recommended = _load_json(root / "recommended-slate.json", issues, {})
    alternates = _load_json(root / "alternates.json", issues, [])
    decision = _load_json(root / "selection-decision-template.json", issues, {})
    source_snapshots = _load_json(root / "source-snapshots.json", issues, [])

    for collection in (candidates, qualified, artworks, leads, scenario_records, [recommended], [decision]):
        for record in collection if isinstance(collection, list) else []:
            if isinstance(record, dict):
                issues.extend(validate_record(record, environment=environment))

    candidate_by_id = {item.get("id"): item for item in candidates if isinstance(item, dict)}
    qualified_ids = {item.get("id") for item in qualified if isinstance(item, dict)}
    expected_qualified = {item_id for item_id, item in candidate_by_id.items() if item.get("candidate_status") == "qualified"}
    if qualified_ids != expected_qualified:
        issues.append(ValidationIssue("qualified_pool_mismatch", "Qualified pool must be the exact qualified subset", "qualified-pool.json"))
    artwork_by_id = {item.get("id"): item for item in artworks if isinstance(item, dict)}
    lead_ids = {item.get("id") for item in leads if isinstance(item, dict)}
    source_ids = {item.get("source_id") for item in source_snapshots if isinstance(item, dict)}

    for candidate_id, candidate in candidate_by_id.items():
        if not set(candidate.get("potential_artwork_ids", [])) <= set(artwork_by_id):
            issues.append(ValidationIssue("candidate_artwork_reference_missing", "Candidate references an artwork outside the bundle", str(candidate_id)))
        if not set(candidate.get("relationship_lead_ids", [])) <= lead_ids:
            issues.append(ValidationIssue("candidate_lead_reference_missing", "Candidate references a relationship lead outside the bundle", str(candidate_id)))
        linked = [item for item in artworks if item.get("candidate_id") == candidate_id]
        observed = Counter(item.get("preflight_status") for item in linked)
        expected_summary = {
            "clear_candidate": observed["rights_path_clear_candidate"],
            "external_iiif": observed["external_iiif_candidate"],
            "external_link_only": observed["external_link_only_candidate"],
            "metadata_only": observed["metadata_only_candidate"],
            "review_required": observed["rights_review_required"],
            "blocked_unknown": observed["blocked_unknown"],
            "blocked_restricted": observed["blocked_restricted"],
        }
        if candidate.get("rights_readiness_summary") != expected_summary:
            issues.append(ValidationIssue("rights_summary_mismatch", "Candidate rights summary must derive from object preflights", str(candidate_id)))
    for artwork in artworks:
        if artwork.get("candidate_id") not in candidate_by_id:
            issues.append(ValidationIssue("artwork_candidate_missing", "Artwork references an unknown candidate", str(artwork.get("id"))))
        if artwork.get("source_id") not in source_ids:
            issues.append(ValidationIssue("artwork_source_missing", "Artwork source is absent from source snapshots", str(artwork.get("id"))))
    for lead in leads:
        if lead.get("source_candidate_id") not in candidate_by_id or (lead.get("target_candidate_id") and lead.get("target_candidate_id") not in candidate_by_id):
            issues.append(ValidationIssue("lead_candidate_missing", "Relationship lead references an unknown candidate", str(lead.get("id"))))
    for scenario in [*scenario_records, recommended]:
        if not set(scenario.get("candidate_ids", [])) <= qualified_ids:
            issues.append(ValidationIssue("scenario_candidate_missing", "Scenario must reference only qualified candidates", str(scenario.get("id"))))
    for alternate in alternates:
        required = {"candidate_id", "replaces_candidate_id", "replacement_reason", "improves", "harms", "rights_difference", "relationship_change", "adapter_change", "research_needed", "full_slate_reaudit"}
        if not isinstance(alternate, dict) or set(alternate) != required:
            issues.append(ValidationIssue("alternate_contract", "Alternate must include the full replacement trade-off contract", "alternates.json"))
            continue
        if alternate["candidate_id"] not in qualified_ids or alternate["replaces_candidate_id"] not in set(recommended.get("candidate_ids", [])):
            issues.append(ValidationIssue("alternate_reference_missing", "Alternate replacement references are not closed", str(alternate.get("candidate_id"))))
    if decision.get("input_bundle_hash") != manifest.get("bundle_hash"):
        issues.append(ValidationIssue("decision_bundle_hash_mismatch", "Decision template must bind the selection bundle hash", "selection-decision-template.json"))
    if manifest.get("candidate_pool_count") != len(candidates) or manifest.get("qualified_candidate_count") != len(qualified):
        issues.append(ValidationIssue("bundle_count_mismatch", "Manifest candidate counts do not match physical records", "bundle-manifest.json"))
    basis = _bundle_basis(
        input_hashes=manifest.get("input_hashes", {}), source_hashes=manifest.get("source_snapshot_hashes", []),
        adapter_versions=manifest.get("adapter_versions", {}), candidates=candidates, qualified=qualified,
        scenarios=scenario_records, recommended=recommended, alternates=alternates,
    )
    if manifest.get("bundle_hash") != canonical_sha256(basis):
        issues.append(ValidationIssue("bundle_hash_mismatch", "Selection bundle hash does not match its semantic input closure", "$.bundle_hash"))
    return _unique(issues)


def pending_decision_template(bundle_hash: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0", "id": f"selection-decision:{uuid.uuid5(uuid.NAMESPACE_URL, bundle_hash + ':decision')}",
        "entity_type": "selection_decision", "status": "pending_user_decision", "decision_type": None,
        "decision_authority": None, "decision_date": None, "selected_scenario_id": None,
        "selected_candidate_ids": [], "replacements": [], "media_strategy": None,
        "public_scope": {"artist_metadata": None, "artwork_metadata": None, "media": None},
        "rationale": None, "acknowledged_limitations": [], "additional_constraints": [],
        "input_bundle_hash": bundle_hash,
    }


def render_selection_handoff(*, candidates: list[dict[str, Any]], artworks: list[dict[str, Any]], leads: list[dict[str, Any]], scenarios: list[dict[str, Any]], recommended: dict[str, Any], alternates: list[dict[str, Any]], bundle_hash: str) -> str:
    by_id = {item["id"]: item for item in candidates}
    artwork_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for artwork in artworks:
        artwork_by_candidate.setdefault(artwork["candidate_id"], []).append(artwork)
    lead_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for lead in leads:
        lead_by_candidate.setdefault(lead["source_candidate_id"], []).append(lead)
        if lead.get("target_candidate_id"):
            lead_by_candidate.setdefault(lead["target_candidate_id"], []).append(lead)
    lines = [
        "# MUSEUM-03A 首批艺术家用户确认包", "",
        "> 本包仅用于用户决策。推荐组合不是批准名单，不代表全部艺术史，也不关闭 OD-004/OD-007。", "",
        "## 选择原则与硬门槛", "",
        "先做个人身份、死亡、Tier 1/2 来源与对象级权利路径硬门槛，再比较全球传统、时代、性别、媒介、关系学习和工程准备度。0–3 只表示准备度与组合贡献。", "",
        f"- 宽池：{len(candidates)} 位", f"- 合格池：{sum(item.get('candidate_status') == 'qualified' for item in candidates)} 位",
        f"- bundle hash：`{bundle_hash}`", "", "## 三套方案", "",
    ]
    for scenario in scenarios:
        names = "、".join(_display_name(by_id[item]) for item in scenario["candidate_ids"])
        lines.extend([f"### {scenario['title']}", "", names, "", scenario["goal"], ""])
    lines.extend(["## 综合推荐 12 人", ""])
    for candidate_id in recommended["candidate_ids"]:
        candidate = by_id[candidate_id]
        candidate_artworks = artwork_by_candidate.get(candidate_id, [])
        statuses = Counter(item["preflight_status"] for item in candidate_artworks)
        sources = sorted(set(candidate.get("authority_source_ids", []) + candidate.get("museum_source_ids", [])))
        lines.extend([
            f"### {_display_name(candidate)}", "",
            f"- 地区与传统：{_traditions(candidate)}",
            f"- 生卒：{candidate['life_display']}",
            f"- 历史区段：{'、'.join(candidate['historical_periods'])}",
            f"- 主要媒介：{'、'.join(candidate['media_materials'])}",
            f"- 首展理由：{candidate.get('inclusion_rationale')}",
            f"- 潜在作品：{len(candidate_artworks)} 件；clear={statuses['rights_path_clear_candidate']}，IIIF={statuses['external_iiif_candidate']}，metadata-only={statuses['metadata_only_candidate']}，需复核={statuses['rights_review_required']}，blocked={statuses['blocked_unknown'] + statuses['blocked_restricted']}",
            f"- 关系线索：{len(lead_by_candidate.get(candidate_id, []))} 条，仅为研究准备度",
            f"- 学习/互动：{'；'.join(candidate['public_learning_themes'] + candidate['interaction_opportunities'])}",
            f"- 来源：{'、'.join(sources)}",
            f"- Adapter：{'；'.join(item['source_id'] + '=' + item['status'] for item in candidate['adapter_readiness'])}",
            f"- 风险与不确定性：{'；'.join(candidate['evidence_gaps'] + candidate['bias_notes']) or '已记录于对象级预审'}", "",
        ])
    lines.extend(["## 备选与替换逻辑", ""])
    for item in alternates:
        lines.append(f"- {_display_name(by_id[item['candidate_id']])} → 可替换 {_display_name(by_id[item['replaces_candidate_id']])}：{item['replacement_reason']}；改善：{item['improves']}；代价：{item['harms']}。")
    lines.extend([
        "", "## OD-007 媒体/公开范围四选项", "",
        "| 选项 | 权利风险 | 可访问性/性能 | 撤回、缓存与署名 | Pages/MUSEUM-05 影响 |",
        "|---|---|---|---|---|",
        "| A Metadata-first | 最低；不发布媒体 | 视觉体验有限，文本最稳 | 撤回最简单，无媒体缓存 | 包体最小，M05 后续补媒体 |",
        "| B External IIIF/source delivery | 中；仅对象级条款明确时 | 可缩放但依赖上游 | 不缓存字节，仍需署名与撤回链接 | 工程中等，需上游可用性策略 |",
        "| C Self-hosted open media only | 低至中；仅 PD/CC0 且闭合 | 最稳定、性能可控 | 项目承担缓存、署名与撤回 | 包体增大，需衍生物/响应式管线 |",
        "| D Mixed | 可逐对象降级，审查复杂 | 体验和稳健性最好 | 三类撤回/缓存/署名路径并存 | 工程复杂度最高，但最适合 M05 渐进交付 |",
        "", "代理建议：**Option D｜Mixed**，但首轮默认 metadata-first；只有对象级权利闭合后才升级为 external IIIF 或 self-hosted open media。OD-007 保持 open。", "",
        "## 仍存偏差与声明", "",
        "开放数据、英语检索、西方机构馆藏史与高分图可得性仍会放大既有偏差。本组合是受范围、证据、权利和学习目标约束的首个试点建议，不代表完整或普世艺术史。", "",
        "## 用户确认清单", "",
        "1. 在 Recommended Slate、Scenario A/B/C 或自定义替换方案中选择恰好 12 人。",
        "2. 选择 OD-007 的 A/B/C/D 媒体策略与公开范围。",
        "3. 填写 `selection-decision-template.json` 的决策权限、日期、理由、限制确认和 bundle hash。", "",
    ])
    return "\n".join(lines)


def _bundle_basis(*, input_hashes: dict[str, str], source_hashes: list[str], adapter_versions: dict[str, str], candidates: list[dict[str, Any]], qualified: list[dict[str, Any]], scenarios: list[dict[str, Any]], recommended: dict[str, Any], alternates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "input_hashes": dict(sorted(input_hashes.items())), "source_snapshot_hashes": sorted(source_hashes),
        "adapter_versions": dict(sorted(adapter_versions.items())), "candidate_ids": sorted(item.get("id") for item in candidates),
        "qualified_ids": sorted(item.get("id") for item in qualified), "scenario_ids": [item.get("id") for item in scenarios],
        "recommended_slate_id": recommended.get("id"), "alternate_ids": [item.get("candidate_id") for item in alternates],
    }


def _display_name(candidate: dict[str, Any]) -> str:
    labels = {item["language"]: item["text"] for item in candidate.get("preferred_labels", [])}
    zh = labels.get("zh-Hans") or labels.get("zh") or next(iter(labels.values()), candidate.get("id", ""))
    en = labels.get("en") or zh
    return f"{zh} / {en}"


def _traditions(candidate: dict[str, Any]) -> str:
    return "、".join(item["label"] for item in candidate.get("regions_traditions", []) if item.get("kind") in {"artistic_tradition", "cultural_language_context", "historical_polity"})


def _load_json(path: Path, issues: list[ValidationIssue], default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        issues.append(ValidationIssue("selection_file_invalid", "Selection file is missing or invalid UTF-8 JSON", path.name))
        return default


def _write_text_atomic(path: Path, text: str) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _unique(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    values = {(item.code, item.message, item.location): item for item in issues}
    return [values[key] for key in sorted(values)]
