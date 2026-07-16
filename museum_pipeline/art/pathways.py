from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter, deque
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import release_content_hash, validate_release_directory


PHASE_ID = "MUSEUM-06"
INPUT_RELEASE_ID = "release:art-gallery-interactions-1.1.0"
INPUT_RELEASE_HASH = "sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009"
RELEASE_ID = "release:art-pathways-1.2.0"
RELEASE_VERSION = "1.2.0"
ALGORITHM_VERSION = "museum-paths-bibfs-yen-1.0.0"
GENERATED_AT = "2026-07-16T12:00:00+08:00"
REVIEWED_AT = "2026-07-16"
INPUT_RELEASE = ROOT / "public" / "releases" / "art-gallery-interactions-1.1.0"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-pathways-1.2.0"
LEAD_INPUT = ROOT / "data" / "review" / "curation" / "museum-03a" / "bundle-20260713-v5" / "relationship-leads.json"
LEAD_CLOSURE = ROOT / "research" / "art" / "museum-03b-relationship-lead-closure.json"
IDENTITY_BASIS = ROOT / "research" / "art" / "museum-03b-approved-identity-basis.json"
AB_REVIEW_OUTPUT = ROOT / "research" / "art" / "museum-06-ab-lead-review.json"

MAX_K = 3
MAX_HOPS = 6
MAX_EXPANSIONS = 10_000
FILTER_ORDER = [
    "current_release",
    "public_display",
    "reviewed_verified",
    "not_withdrawn",
    "not_deprecated",
    "rights_visibility",
    "mode_level",
    "relation_type",
    "direction",
    "time_region",
]
MODE_LEVELS = {"historical": {"A", "B"}, "context": {"B"}, "comparison": {"C"}}
MODE_DISCLAIMERS = {
    "historical": {
        "zh-Hans": "最短 hop 路径只描述当前 release 中经审核的历史关系，不是唯一或真实的历史传播链。",
        "en": "The shortest-hop path describes reviewed historical relations in this release; it is not a unique or actual chain of transmission.",
    },
    "context": {
        "zh-Hans": "语境路径只显示共享的具体历史语境，不推出艺术家直接接触或影响。",
        "en": "A context path shows only a shared specific historical context and does not infer direct contact or influence.",
    },
    "comparison": {
        "zh-Hans": "C｜策展比较：路径不证明艺术家相识、影响、师承或传播。",
        "en": "C | Curatorial comparison: this path does not prove acquaintance, influence, instruction, or transmission.",
    },
}
NO_PATH_NOTICE = {
    "zh-Hans": "当前 release 和筛选条件下没有可展示路径，不代表现实中不存在关系。",
    "en": "No displayable path exists in the current release under these filters; this does not mean no relationship exists in reality.",
}


class SearchBudgetReached(RuntimeError):
    pass


@dataclass
class ExpansionBudget:
    limit: int
    used: int = 0

    def expand(self) -> None:
        if self.used >= self.limit:
            raise SearchBudgetReached
        self.used += 1


@dataclass(frozen=True)
class CandidatePath:
    artist_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]


def default_query(start_artist_id: str, end_artist_id: str, mode: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "fixed_release_id": RELEASE_ID,
        "start_artist_id": start_artist_id,
        "end_artist_id": end_artist_id,
        "mode": mode,
        "allowed_relationship_types": [],
        "allowed_levels": sorted(MODE_LEVELS[mode]),
        "period_filter": None,
        "region_filter": None,
        "direction_policy": "respect_semantic_direction",
        "max_hops": MAX_HOPS,
        "k": MAX_K,
        "candidate_expansion_limit": MAX_EXPANSIONS,
    }


def find_paths(graph_input: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic filtered bidirectional BFS plus bounded loopless Yen."""
    graph_hash = graph_input.get("graph_hash", "sha256:" + "0" * 64)
    result = _empty_result(graph_hash, query)
    artists = {item["id"]: item for item in graph_input.get("artists", [])}
    start = query.get("start_artist_id")
    end = query.get("end_artist_id")
    if query.get("fixed_release_id") != RELEASE_ID:
        result["status"] = "incompatible_release"
        return result
    if start not in artists:
        result["status"] = "invalid_start"
        return result
    if end not in artists:
        result["status"] = "invalid_end"
        return result
    if start == end:
        result["status"] = "same_endpoint"
        return result
    if artists[start].get("withdrawn") or artists[start].get("lifecycle_status") == "withdrawn":
        result["status"] = "withdrawn_endpoint"
        return result
    if artists[end].get("withdrawn") or artists[end].get("lifecycle_status") == "withdrawn":
        result["status"] = "withdrawn_endpoint"
        return result
    if query.get("mode") not in MODE_LEVELS:
        result["status"] = "runtime_calculation_failed"
        return result
    max_hops = int(query.get("max_hops", 0))
    k = int(query.get("k", 0))
    limit = int(query.get("candidate_expansion_limit", 0))
    if not 1 <= max_hops <= MAX_HOPS or not 1 <= k <= MAX_K or not 1 <= limit <= MAX_EXPANSIONS:
        result["status"] = "runtime_calculation_failed"
        return result

    edges = _filtered_edges(graph_input, query)
    edge_by_id = {item["id"]: item for item in edges}
    forward, reverse = _adjacency(artists, edges)
    budget = ExpansionBudget(limit)
    accepted: list[CandidatePath] = []
    candidates: dict[tuple[tuple[str, ...], tuple[str, ...]], CandidatePath] = {}
    budget_reached = False
    try:
        first = _bidirectional_shortest(start, end, forward, reverse, edge_by_id, artists, max_hops, budget)
        if first is None:
            result["status"] = "no_path_for_current_release_and_filters"
            result["expansions_used"] = budget.used
            result["disclaimer"] = NO_PATH_NOTICE
            return result
        accepted.append(first)
        while len(accepted) < k:
            previous = accepted[-1]
            for spur_index in range(len(previous.artist_ids) - 1):
                root_nodes = previous.artist_ids[: spur_index + 1]
                root_edges = previous.relationship_ids[:spur_index]
                removed_edges: set[str] = set()
                for path in accepted:
                    if path.artist_ids[: spur_index + 1] == root_nodes and len(path.relationship_ids) > spur_index:
                        removed_edges.add(path.relationship_ids[spur_index])
                banned_nodes = set(root_nodes[:-1])
                remaining_hops = max_hops - len(root_edges)
                spur = _bidirectional_shortest(
                    root_nodes[-1], end, forward, reverse, edge_by_id, artists, remaining_hops, budget,
                    banned_nodes=banned_nodes, banned_edges=removed_edges,
                )
                if spur is None:
                    continue
                combined = CandidatePath(
                    artist_ids=tuple((*root_nodes[:-1], *spur.artist_ids)),
                    relationship_ids=tuple((*root_edges, *spur.relationship_ids)),
                )
                if len(set(combined.artist_ids)) != len(combined.artist_ids):
                    continue
                identity = (combined.artist_ids, combined.relationship_ids)
                if all(identity != (item.artist_ids, item.relationship_ids) for item in accepted):
                    candidates[identity] = combined
            if not candidates:
                break
            selected_identity, selected = min(
                candidates.items(), key=lambda item: _candidate_sort_key(item[1], edge_by_id, artists)
            )
            del candidates[selected_identity]
            accepted.append(selected)
    except SearchBudgetReached:
        budget_reached = True

    accepted = sorted(accepted, key=lambda item: _candidate_sort_key(item, edge_by_id, artists))[:k]
    result["paths"] = [_serialize_path(item, rank, edge_by_id, artists, query) for rank, item in enumerate(accepted, 1)]
    result["status"] = "search_budget_reached" if budget_reached else "ready"
    result["expansions_used"] = budget.used
    return result


def _filtered_edges(graph_input: dict[str, Any], query: dict[str, Any]) -> list[dict[str, Any]]:
    mode = query["mode"]
    allowed_mode_levels = MODE_LEVELS[mode]
    requested_levels = set(query.get("allowed_levels") or allowed_mode_levels)
    requested_types = set(query.get("allowed_relationship_types") or [])
    period_filter = set(query.get("period_filter") or [])
    region_filter = {item.casefold() for item in query.get("region_filter") or []}
    output = []
    for edge in sorted(graph_input.get("relationships", []), key=lambda item: item["id"]):
        checks = (
            edge.get("release_id") == RELEASE_ID,
            edge.get("public_display") is True,
            edge.get("review_status") in {"verified", "publishable"},
            not edge.get("withdrawn") and edge.get("lifecycle_status") != "withdrawn",
            not edge.get("deprecated") and edge.get("lifecycle_status") != "deprecated",
            edge.get("rights_visibility") == "public",
            edge.get("level") in allowed_mode_levels and edge.get("level") in requested_levels,
            not requested_types or edge.get("type") in requested_types,
            edge.get("directed") in {True, False},
            (not period_filter or bool(period_filter.intersection(edge.get("periods", []))))
            and (not region_filter or bool(region_filter.intersection(value.casefold() for value in edge.get("regions", [])))),
        )
        if all(checks) and edge.get("is_algorithmic") is False and edge.get("computational_similarity") is None:
            output.append(edge)
    return output


def _adjacency(
    artists: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]]]:
    forward = {artist_id: [] for artist_id in artists}
    reverse = {artist_id: [] for artist_id in artists}
    for edge in edges:
        source, target, edge_id = edge["source_artist_id"], edge["target_artist_id"], edge["id"]
        if source not in artists or target not in artists:
            continue
        forward[source].append((target, edge_id))
        reverse[target].append((source, edge_id))
        if not edge["directed"]:
            forward[target].append((source, edge_id))
            reverse[source].append((target, edge_id))
    for adjacency in (forward, reverse):
        for values in adjacency.values():
            values.sort(key=lambda item: (item[1], item[0]))
    return forward, reverse


def _bidirectional_shortest(
    start: str,
    end: str,
    forward: dict[str, list[tuple[str, str]]],
    reverse: dict[str, list[tuple[str, str]]],
    edge_by_id: dict[str, dict[str, Any]],
    artists: dict[str, dict[str, Any]],
    max_hops: int,
    budget: ExpansionBudget,
    *,
    banned_nodes: set[str] | None = None,
    banned_edges: set[str] | None = None,
) -> CandidatePath | None:
    banned_nodes = banned_nodes or set()
    banned_edges = banned_edges or set()
    if start in banned_nodes or end in banned_nodes or max_hops < 1:
        return None
    forward_dist = _bounded_distances(start, forward, max_hops, budget, banned_nodes, banned_edges)
    if end not in forward_dist:
        return None
    distance = forward_dist[end]
    reverse_dist = _bounded_distances(end, reverse, distance, budget, banned_nodes, banned_edges)
    paths: list[CandidatePath] = []

    def visit(node: str, nodes: list[str], edge_ids: list[str]) -> None:
        if len(edge_ids) == distance:
            if node == end:
                paths.append(CandidatePath(tuple(nodes), tuple(edge_ids)))
            return
        for neighbor, edge_id in forward.get(node, []):
            budget.expand()
            if edge_id in banned_edges or neighbor in banned_nodes or neighbor in nodes:
                continue
            if forward_dist.get(neighbor) != len(edge_ids) + 1:
                continue
            if reverse_dist.get(neighbor) != distance - len(edge_ids) - 1:
                continue
            visit(neighbor, [*nodes, neighbor], [*edge_ids, edge_id])

    visit(start, [start], [])
    if not paths:
        return None
    return min(paths, key=lambda item: _candidate_sort_key(item, edge_by_id, artists))


def _bounded_distances(
    start: str,
    adjacency: dict[str, list[tuple[str, str]]],
    max_hops: int,
    budget: ExpansionBudget,
    banned_nodes: set[str],
    banned_edges: set[str],
) -> dict[str, int]:
    distance = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if distance[node] >= max_hops:
            continue
        for neighbor, edge_id in adjacency.get(node, []):
            budget.expand()
            if edge_id in banned_edges or neighbor in banned_nodes or neighbor in distance:
                continue
            distance[neighbor] = distance[node] + 1
            queue.append(neighbor)
    return distance


def _candidate_sort_key(
    path: CandidatePath,
    edge_by_id: dict[str, dict[str, Any]],
    artists: dict[str, dict[str, Any]],
) -> tuple[Any, ...]:
    edges = [edge_by_id[value] for value in path.relationship_ids]
    level_rank = min({"A": 1, "B": 2, "C": 3}[edge["level"]] for edge in edges)
    confidence = sum(float(edge["evidence_confidence"]) for edge in edges) / len(edges)
    coherence = _time_coherence(path.artist_ids, artists)
    repetitions = sum(value - 1 for value in Counter(edge["type"] for edge in edges).values())
    return (
        len(edges), level_rank, -round(confidence, 6), {"coherent": 0, "mixed": 1, "discontinuous": 2}[coherence],
        repetitions, path.relationship_ids, path.artist_ids,
    )


def _time_coherence(artist_ids: Iterable[str], artists: dict[str, dict[str, Any]]) -> str:
    periods = []
    for artist_id in artist_ids:
        span = artists[artist_id].get("life_span", {})
        if isinstance(span.get("birth_year"), int) and isinstance(span.get("death_year"), int):
            periods.append((span["birth_year"], span["death_year"]))
    if len(periods) < 2:
        return "mixed"
    if max(start for start, _ in periods) <= min(end for _, end in periods):
        return "coherent"
    ordered = sorted(periods)
    largest_gap = max(max(0, ordered[index + 1][0] - ordered[index][1]) for index in range(len(ordered) - 1))
    return "mixed" if largest_gap <= 50 else "discontinuous"


def _serialize_path(
    candidate: CandidatePath,
    rank: int,
    edge_by_id: dict[str, dict[str, Any]],
    artists: dict[str, dict[str, Any]],
    query: dict[str, Any],
) -> dict[str, Any]:
    edges = [edge_by_id[value] for value in candidate.relationship_ids]
    key = _candidate_sort_key(candidate, edge_by_id, artists)
    steps = []
    for index, edge in enumerate(edges):
        source = candidate.artist_ids[index]
        target = candidate.artist_ids[index + 1]
        steps.append({
            "sequence": index + 1,
            "source_artist_id": source,
            "target_artist_id": target,
            "relationship_id": edge["id"],
            "direction": "directed_forward" if edge["directed"] else "undirected",
            "relationship_type": edge["type"],
            "level": edge["level"],
            "context_ids": edge["context_ids"],
            "claim_ids": edge["claim_ids"],
            "evidence_ids": edge["evidence_ids"],
            "source_ids": edge["source_ids"],
            "supporting_artwork_ids": edge["supporting_artwork_ids"],
            "evidence_confidence": edge["evidence_confidence"],
            "why_connected": edge["why_connected"],
            "does_not_prove": edge["does_not_prove"],
            "rights_attribution": edge["rights_attribution"],
            "withdrawal_status": "active",
        })
    slug = "--".join(value.split(":", 1)[1] for value in (query["start_artist_id"], query["end_artist_id"]))
    return {
        "id": f"path:{slug}-{query['mode']}-{rank:02d}",
        "rank": rank,
        "hop_count": len(edges),
        "artist_ids": list(candidate.artist_ids),
        "relationship_ids": list(candidate.relationship_ids),
        "steps": steps,
        "evidence_level": edges[0]["level"],
        "evidence_confidence": round(sum(item["evidence_confidence"] for item in edges) / len(edges), 6),
        "time_coherence": _time_coherence(candidate.artist_ids, artists),
        "relation_type_repeat_count": key[4],
        "ranking_tuple": {
            "hop_count": key[0],
            "evidence_level_rank": key[1],
            "evidence_confidence_desc": key[2],
            "time_coherence_penalty": key[3],
            "relation_type_repeat_count": key[4],
            "stable_relation_id_sequence": list(key[5]),
            "stable_artist_id_sequence": list(key[6]),
        },
    }


def _empty_result(graph_hash: str, query: dict[str, Any]) -> dict[str, Any]:
    start = str(query.get("start_artist_id", "unknown")).replace(":", "-")
    end = str(query.get("end_artist_id", "unknown")).replace(":", "-")
    mode = str(query.get("mode", "unknown"))
    return {
        "schema_version": "1.0.0",
        "id": f"path-result:{start}--{end}--{mode}",
        "entity_type": "art_path_result",
        "release_id": RELEASE_ID,
        "algorithm_version": ALGORITHM_VERSION,
        "input_graph_hash": graph_hash,
        "status": "runtime_calculation_failed",
        "query": deepcopy(query),
        "paths": [],
        "expansions_used": 0,
        "disclaimer": deepcopy(MODE_DISCLAIMERS.get(mode, NO_PATH_NOTICE)),
    }


def review_ab_leads(*, write: bool = False) -> dict[str, Any]:
    leads = _load_json(LEAD_INPUT)
    closure = _load_json(LEAD_CLOSURE)
    identity_basis = _load_json(IDENTITY_BASIS)
    selected = {item["approved_candidate_id"]: item["artist_id"] for item in identity_basis["bindings"]}
    closure_by_id = {item["lead_id"]: item for item in closure["entries"]}
    reviewed = []
    for lead in sorted(
        (item for item in leads if item["likely_evidence_level"] in {"A", "B"}), key=lambda item: item["id"]
    ):
        old = closure_by_id[lead["id"]]
        source = selected.get(lead["source_candidate_id"])
        target = selected.get(lead["target_candidate_id"])
        if not source or not target:
            disposition = "out_of_scope"
            gate = "endpoint_not_in_formal_artist_set"
        else:
            disposition = "retained_for_more_evidence"
            gate = "exact_time_overlap_and_independent_source_closure_missing"
        if disposition != old["disposition"]:
            raise ValueError(f"A/B review drift for {lead['id']}: {old['disposition']} -> {disposition}")
        reviewed.append({
            "lead_id": lead["id"],
            "likely_evidence_level": lead["likely_evidence_level"],
            "proposed_relation_type": lead["proposed_relation_type"],
            "source_artist_id": source,
            "target_artist_id": target,
            "terminal_disposition": disposition,
            "automated_gate_result": gate,
            "formal_relationship_created": False,
            "human_review_dependency": False,
            "source_lineage_independence_closed": False if source and target else None,
            "claim_evidence_source_closed": False,
        })
    counts = Counter(item["terminal_disposition"] for item in reviewed)
    document = {
        "schema_version": "1.0.0",
        "id": "ab-lead-review:museum-06-v1",
        "entity_type": "museum_06_ab_lead_review",
        "phase_id": PHASE_ID,
        "input_lead_set_hash": canonical_sha256(leads),
        "input_closure_hash": closure["content_hash"],
        "reviewed_at": REVIEWED_AT,
        "scope": "existing_museum_03a_museum_03b_a_b_leads_only",
        "input_lead_count": len(reviewed),
        "level_counts": dict(sorted(Counter(item["likely_evidence_level"] for item in reviewed).items())),
        "disposition_counts": {key: counts.get(key, 0) for key in (
            "promoted_to_formal_relationship", "retained_for_more_evidence", "rejected", "out_of_scope", "superseded"
        )},
        "human_review_dependency": False,
        "open_web_search_performed": False,
        "entries": reviewed,
    }
    document["content_hash"] = canonical_sha256(document)
    if write:
        AB_REVIEW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        AB_REVIEW_OUTPUT.write_bytes(canonical_json_bytes(document))
    return document


def load_closed_ab_review() -> dict[str, Any]:
    """Use private review inputs when present, otherwise the committed closed result."""
    private_inputs = (LEAD_INPUT, LEAD_CLOSURE, IDENTITY_BASIS)
    if all(path.is_file() for path in private_inputs):
        return review_ab_leads(write=True)
    review = _load_json(AB_REVIEW_OUTPUT)
    recorded_hash = review.get("content_hash")
    hash_input = {key: value for key, value in review.items() if key != "content_hash"}
    if recorded_hash != canonical_sha256(hash_input):
        raise ValueError("committed A/B review content hash mismatch")
    if review.get("human_review_dependency") is not False:
        raise ValueError("committed A/B review cannot depend on human review")
    if review.get("scope") != "existing_museum_03a_museum_03b_a_b_leads_only":
        raise ValueError("committed A/B review scope mismatch")
    return review


def build_graph_input() -> dict[str, Any]:
    artists_document = _load_json(INPUT_RELEASE / "artists.json")
    relationships_document = _load_json(INPUT_RELEASE / "relationships.json")
    sources_document = _load_json(INPUT_RELEASE / "sources.json")
    source_by_id = {item["id"]: item for item in sources_document["sources"]}
    artists = []
    for item in sorted(artists_document["artists"], key=lambda value: value["id"]):
        artists.append({
            "id": item["id"],
            "labels": item["labels"],
            "aliases": item.get("aliases", []),
            "periods": sorted(item.get("historical_periods", [])),
            "regions": sorted({place["label"] for place in item.get("activity_places", [])}),
            "life_span": {
                "birth_year": _year(item.get("life_dates", {}).get("birth", {}).get("display_value")),
                "death_year": _year(item.get("life_dates", {}).get("death", {}).get("display_value")),
            },
            "public_display": True,
            "review_status": item["review_status"],
            "lifecycle_status": item["lifecycle_status"],
            "withdrawn": False,
        })
    artist_by_id = {item["id"]: item for item in artists}
    relationships = []
    for item in sorted(relationships_document["relationships"], key=lambda value: value["id"]):
        endpoint_periods = sorted(set(artist_by_id[item["source_artist_id"]]["periods"] + artist_by_id[item["target_artist_id"]]["periods"]))
        endpoint_regions = sorted(set(artist_by_id[item["source_artist_id"]]["regions"] + artist_by_id[item["target_artist_id"]]["regions"]))
        attributions = sorted({source_by_id[source_id]["attribution"] for source_id in item["source_ids"]})
        relationships.append({
            "id": item["id"],
            "release_id": RELEASE_ID,
            "source_artist_id": item["source_artist_id"],
            "target_artist_id": item["target_artist_id"],
            "type": item["type"],
            "level": item["level"],
            "directed": item["directed"],
            "is_algorithmic": item["is_algorithmic"],
            "computational_similarity": item["computational_similarity"],
            "public_display": True,
            "review_status": item["review_status"],
            "lifecycle_status": item["lifecycle_status"],
            "withdrawn": False,
            "deprecated": False,
            "rights_visibility": "public",
            "periods": endpoint_periods,
            "regions": endpoint_regions,
            "context_ids": item["context_ids"],
            "claim_ids": item["claim_ids"],
            "evidence_ids": item["evidence_ids"],
            "source_ids": item["source_ids"],
            "supporting_artwork_ids": item["supporting_artwork_ids"],
            "evidence_confidence": item["evidence_confidence"],
            "why_connected": item["short_explanation"],
            "does_not_prove": item["what_it_does_not_mean"],
            "rights_attribution": attributions,
        })
    payload = {"artists": artists, "relationships": relationships}
    graph_hash = canonical_sha256(payload)
    return {
        "schema_version": "1.0.0",
        "id": "path-graph-input:museum-06-v1",
        "entity_type": "art_path_graph_input",
        "release_id": RELEASE_ID,
        "input_release_id": INPUT_RELEASE_ID,
        "input_release_hash": INPUT_RELEASE_HASH,
        "graph_hash": graph_hash,
        "artists": artists,
        "relationships": relationships,
        "counts": {
            "artists": len(artists),
            "relationships": len(relationships),
            "levels": dict(sorted(Counter(item["level"] for item in relationships).items())),
            "directed": sum(item["directed"] for item in relationships),
            "algorithmic": sum(item["is_algorithmic"] for item in relationships),
        },
    }


def build_museum_06_release(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    predecessor = _load_json(INPUT_RELEASE / "manifest.json")
    if predecessor.get("id") != INPUT_RELEASE_ID or predecessor.get("content_hash") != INPUT_RELEASE_HASH:
        raise ValueError("MUSEUM-05B predecessor hash mismatch")
    review = load_closed_ab_review()
    graph_input = build_graph_input()
    artifacts = _build_artifacts(graph_input, review)
    _validate_new_artifacts(artifacts)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-06-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        _copy_predecessor(staged)
        for filename, document in artifacts.items():
            (staged / filename).write_bytes(canonical_json_bytes(document))
        manifest = _build_manifest(staged, predecessor, artifacts)
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        validation = validate_museum_06_release(staged)
        if not validation["ok"]:
            raise ValueError("staged MUSEUM-06 release failed: " + ", ".join(validation["codes"][:12]))
        _install_immutable(staged, output_dir)
    return validate_museum_06_release(output_dir)


def _build_artifacts(graph_input: dict[str, Any], review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pairs = []
    precomputed_path_count = 0
    artist_ids = [item["id"] for item in graph_input["artists"]]
    for start, end in combinations(artist_ids, 2):
        modes = {mode: find_paths(graph_input, default_query(start, end, mode)) for mode in MODE_LEVELS}
        precomputed_path_count += sum(len(result["paths"]) for result in modes.values())
        pairs.append({
            "pair_id": f"path-pair:{start.split(':', 1)[1]}--{end.split(':', 1)[1]}",
            "start_artist_id": start,
            "end_artist_id": end,
            "modes": modes,
        })
    explanations = []
    for edge in graph_input["relationships"]:
        explanations.append({key: deepcopy(edge[key]) for key in (
            "id", "source_artist_id", "target_artist_id", "type", "level", "directed", "context_ids", "claim_ids",
            "evidence_ids", "source_ids", "supporting_artwork_ids", "evidence_confidence", "why_connected",
            "does_not_prove", "rights_attribution",
        )})
    algorithm = {
        "schema_version": "1.0.0", "id": "path-algorithm:museum-06-v1", "entity_type": "art_path_algorithm_contract",
        "release_id": RELEASE_ID, "algorithm_version": ALGORITHM_VERSION, "input_release_id": INPUT_RELEASE_ID,
        "input_release_hash": INPUT_RELEASE_HASH, "filter_order": FILTER_ORDER,
        "modes": {
            "historical": {"levels": ["A", "B"], "directed": True, "allows_algorithmic": False},
            "context": {"levels": ["B"], "directed": True, "allows_algorithmic": False},
            "comparison": {"levels": ["C"], "explicit_opt_in": True, "undirected": True, "allows_algorithmic": False},
        },
        "bounds": {"k_max": MAX_K, "max_hops": MAX_HOPS, "candidate_expansion_limit": MAX_EXPANSIONS},
        "shortest_path": {"method": "deterministic_bidirectional_bfs", "unit": "hop", "composite_weight": False},
        "alternative_paths": {"method": "bounded_yen", "loopless": True, "duplicate_complete_paths": False},
        "ranking_tuple": ["hop_count", "mode_compatible_evidence_level", "evidence_confidence_desc", "time_coherence", "relation_type_repeat_count", "stable_relation_id_sequence", "stable_artist_id_sequence"],
        "runtime_data_structure": "graphology@0.26.0 mixed multigraph",
        "disclaimers": MODE_DISCLAIMERS,
    }
    path_index = {
        "schema_version": "1.0.0", "id": "path-index:museum-06-default-v1", "entity_type": "art_path_index",
        "release_id": RELEASE_ID, "algorithm_version": ALGORITHM_VERSION, "input_graph_hash": graph_input["graph_hash"],
        "default_pair_count": len(pairs), "precomputed_path_count": precomputed_path_count, "pairs": pairs,
    }
    explanation_collection = {
        "schema_version": "1.0.0", "id": "path-explanations:museum-06-v1", "entity_type": "art_path_explanation_collection",
        "release_id": RELEASE_ID, "input_graph_hash": graph_input["graph_hash"], "explanations": explanations,
    }
    ab_summary = {
        "schema_version": "1.0.0", "id": "ab-review-summary:museum-06-v1", "entity_type": "art_path_ab_review_summary",
        "release_id": RELEASE_ID, "input_lead_count": review["input_lead_count"], "level_counts": review["level_counts"],
        "disposition_counts": review["disposition_counts"], "promoted_relationship_ids": [], "human_review_dependency": False,
        "private_lead_ids_in_release": False,
    }
    performance = {
        "schema_version": "1.0.0", "id": "path-performance:museum-06-v1", "entity_type": "art_path_performance_contract",
        "release_id": RELEASE_ID, "stable_seed": "museum-06-path-benchmark-seed-20260716",
        "budgets": {
            "path_route_total_gzip_bytes": 256000, "default_path_index_gzip_bytes": 65536,
            "path_algorithm_chunk_gzip_bytes": 81920, "current_query_p95_ms": 50, "route_interaction_p95_ms": 150,
            "default_66_pair_build_ms": 1000, "synthetic_1k_5k_median_ms": 200,
            "synthetic_10k_60k_median_ms": 500, "synthetic_50k_300k_expansion_limit": 10000,
            "mobile_heap_increment_bytes": 26214400, "cls": 0.1,
        },
        "synthetic_fixtures_public_release": False,
    }
    route = {
        "schema_version": "1.0.0", "id": "path-route:museum-06-v1", "entity_type": "art_path_route_config",
        "release_id": RELEASE_ID, "route": "#/art/paths",
        "url_state_allowlist": ["from", "to", "mode", "types", "period", "region", "maxHops", "path", "view"],
        "default_mode": "comparison", "storage": "none", "external_runtime_api": False, "analytics": False,
    }
    return {
        "path-algorithm-contract.json": algorithm,
        "path-graph-input.json": graph_input,
        "path-index.json": path_index,
        "path-explanations.json": explanation_collection,
        "ab-review-summary.json": ab_summary,
        "path-performance-contract.json": performance,
        "path-route-config.json": route,
    }


def validate_museum_06_release(release_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    release_root = release_root.resolve()
    failures: list[dict[str, str]] = []
    if not release_root.is_dir():
        _fail(failures, "release_missing", "MUSEUM-06 release directory is absent")
        return _result(release_root, failures)
    try:
        predecessor = _load_json(INPUT_RELEASE / "manifest.json")
        manifest = _load_json(release_root / "manifest.json")
        graph_input = _load_json(release_root / "path-graph-input.json")
        path_index = _load_json(release_root / "path-index.json")
        explanations = _load_json(release_root / "path-explanations.json")
        ab_summary = _load_json(release_root / "ab-review-summary.json")
    except (OSError, json.JSONDecodeError, KeyError) as error:
        _fail(failures, "release_json_invalid", str(error))
        return _result(release_root, failures)
    if predecessor.get("id") != INPUT_RELEASE_ID or predecessor.get("content_hash") != INPUT_RELEASE_HASH:
        _fail(failures, "predecessor_drift", "The protected MUSEUM-05B predecessor hash changed")
    for key, expected in {
        "id": RELEASE_ID, "version": RELEASE_VERSION, "predecessor": INPUT_RELEASE_ID,
        "status": "publishable", "public_release": True,
    }.items():
        if manifest.get(key) != expected:
            _fail(failures, "manifest_profile", f"{key} must be {expected!r}", f"manifest.{key}")
    try:
        for issue in validate_release_directory(release_root, load_schema_environment(ROOT)):
            _fail(failures, f"generic_{issue.code}", issue.message, issue.location)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        _fail(failures, "generic_validator_error", str(error))
    _validate_overlay(release_root, predecessor, manifest, failures)
    if graph_input.get("graph_hash") != canonical_sha256({
        "artists": graph_input.get("artists"), "relationships": graph_input.get("relationships")
    }):
        _fail(failures, "graph_hash", "Path graph hash does not match canonical graph input", "path-graph-input.json")
    if graph_input.get("counts") != {"artists": 12, "relationships": 36, "levels": {"C": 36}, "directed": 0, "algorithmic": 0}:
        _fail(failures, "graph_counts", "Graph must retain exactly 12 artists and 36 C-only nonalgorithmic relationships")
    pairs = path_index.get("pairs", [])
    expected_pairs = {
        tuple(sorted(pair))
        for pair in combinations((item["id"] for item in graph_input.get("artists", [])), 2)
    }
    actual_pairs = {tuple(sorted((item.get("start_artist_id"), item.get("end_artist_id")))) for item in pairs}
    if len(pairs) != 66 or actual_pairs != expected_pairs:
        _fail(failures, "pair_closure", "Path index must contain each of the 66 unordered artist pairs exactly once")
    if path_index.get("input_graph_hash") != graph_input.get("graph_hash"):
        _fail(failures, "path_index_graph_hash", "Path index graph hash does not bind graph input")
    calculated_path_count = 0
    for pair in pairs:
        for mode in MODE_LEVELS:
            result = pair.get("modes", {}).get(mode, {})
            calculated_path_count += len(result.get("paths", []))
            if mode in {"historical", "context"} and result.get("status") != "no_path_for_current_release_and_filters":
                _fail(failures, "empty_ab_mode", f"{mode} must be an accurate empty state while A/B counts are zero")
            for path in result.get("paths", []):
                if any(step.get("level") not in MODE_LEVELS[mode] for step in path.get("steps", [])):
                    _fail(failures, "mode_level_mixing", f"Path {path.get('id')} mixes incompatible relationship levels")
                if len(set(path.get("artist_ids", []))) != len(path.get("artist_ids", [])):
                    _fail(failures, "path_loop", f"Path {path.get('id')} repeats an artist")
    if path_index.get("precomputed_path_count") != calculated_path_count:
        _fail(failures, "path_count", "Precomputed path count does not match indexed path records")
    if ab_summary.get("disposition_counts") != {
        "promoted_to_formal_relationship": 0, "retained_for_more_evidence": 1, "rejected": 0,
        "out_of_scope": 8, "superseded": 0,
    }:
        _fail(failures, "ab_dispositions", "A/B review must close to 0 promoted, 1 retained, and 8 out of scope")
    _validate_path_semantics(release_root, graph_input, path_index, explanations, ab_summary, failures)
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        _fail(failures, "content_hash", "Release content hash does not match its physical manifest")
    return _result(release_root, failures, {
        "artist_count": graph_input.get("counts", {}).get("artists"),
        "relationship_count": graph_input.get("counts", {}).get("relationships"),
        "default_pair_count": len(pairs),
        "precomputed_path_count": calculated_path_count,
    }, manifest.get("content_hash"))


def _validate_path_semantics(
    release_root: Path,
    graph_input: dict[str, Any],
    path_index: dict[str, Any],
    explanations: dict[str, Any],
    ab_summary: dict[str, Any],
    failures: list[dict[str, str]],
) -> None:
    try:
        formal_relationship_ids = {item["id"] for item in _load_json(release_root / "relationships.json")["relationships"]}
        claim_ids = {item["id"] for item in _load_json(release_root / "claims.json")["claims"]}
        evidence_ids = {item["id"] for item in _load_json(release_root / "evidence.json")["evidence"]}
        source_ids = {item["id"] for item in _load_json(release_root / "sources.json")["sources"]}
        artwork_ids = {item["id"] for item in _load_json(release_root / "artworks.json")["artworks"]}
    except (OSError, KeyError, json.JSONDecodeError) as error:
        _fail(failures, "path_closure_read", str(error))
        return
    edges = graph_input.get("relationships", [])
    edge_by_id = {item.get("id"): item for item in edges}
    if set(edge_by_id) != formal_relationship_ids:
        _fail(failures, "relationship_closure", "Path graph relationship IDs must equal the formal release relationship set")
    for edge_id, edge in edge_by_id.items():
        missing_claims = set(edge.get("claim_ids", [])) - claim_ids
        missing_evidence = set(edge.get("evidence_ids", [])) - evidence_ids
        missing_sources = set(edge.get("source_ids", [])) - source_ids
        missing_artworks = set(edge.get("supporting_artwork_ids", [])) - artwork_ids
        if missing_claims:
            _fail(failures, "missing_claim", f"{edge_id} has missing claims {sorted(missing_claims)}")
        if missing_evidence:
            _fail(failures, "missing_evidence", f"{edge_id} has missing evidence {sorted(missing_evidence)}")
        if missing_sources:
            _fail(failures, "missing_source", f"{edge_id} has missing sources {sorted(missing_sources)}")
        if missing_artworks:
            _fail(failures, "missing_supporting_artwork", f"{edge_id} has missing artworks {sorted(missing_artworks)}")
        if edge.get("is_algorithmic") is not False or edge.get("computational_similarity") is not None:
            _fail(failures, "algorithmic_edge", f"{edge_id} must not be algorithmic")
    explanation_by_id = {item.get("id"): item for item in explanations.get("explanations", [])}
    if set(explanation_by_id) != set(edge_by_id):
        _fail(failures, "explanation_closure", "Path explanations must close exactly over graph relationships")
    for pair in path_index.get("pairs", []):
        for mode, result in pair.get("modes", {}).items():
            if result.get("input_graph_hash") != graph_input.get("graph_hash"):
                _fail(failures, "result_graph_hash", f"{result.get('id')} does not bind the graph hash")
            for path in result.get("paths", []):
                if any(edge_id not in edge_by_id for edge_id in path.get("relationship_ids", [])):
                    _fail(failures, "unknown_edge", f"{path.get('id')} contains an unknown relationship")
                for step in path.get("steps", []):
                    edge = edge_by_id.get(step.get("relationship_id"))
                    if edge is None:
                        continue
                    for key in ("level", "type", "claim_ids", "evidence_ids", "source_ids", "supporting_artwork_ids"):
                        step_key = "relationship_type" if key == "type" else key
                        if step.get(step_key) != edge.get(key):
                            _fail(failures, "step_edge_mismatch", f"{path.get('id')} step does not match {edge.get('id')} field {key}")
            if mode not in MODE_LEVELS:
                _fail(failures, "unknown_mode", f"Unknown indexed path mode {mode}")
    public_overlay = json.dumps(
        {"graph": graph_input, "index": path_index, "explanations": explanations, "ab": ab_summary},
        ensure_ascii=False, sort_keys=True,
    )
    if "relationship-lead:" in public_overlay:
        _fail(failures, "private_lead_leakage", "Public path artifacts contain a private relationship lead ID")
    if ab_summary.get("private_lead_ids_in_release") is not False:
        _fail(failures, "private_lead_flag", "A/B review summary must deny private lead IDs in release")


def _validate_new_artifacts(artifacts: dict[str, dict[str, Any]]) -> None:
    schema_by_file = {
        "path-index.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "path-graph-input.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "path-algorithm-contract.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "path-explanations.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "ab-review-summary.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "path-performance-contract.json": "schemas/art/release/art-pathways-artifact.schema.json",
        "path-route-config.json": "schemas/art/release/art-pathways-artifact.schema.json",
    }
    for filename, document in artifacts.items():
        issues = validate_record(document, requested_schema=schema_by_file[filename])
        if issues:
            raise ValueError(f"{filename} {issues[0].location}: {issues[0].message}")


def _copy_predecessor(staged: Path) -> None:
    staged.mkdir(parents=True)
    for source in INPUT_RELEASE.rglob("*"):
        if not source.is_file() or source.name == "manifest.json":
            continue
        destination = staged / source.relative_to(INPUT_RELEASE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _build_manifest(
    staged: Path, predecessor: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    entries = deepcopy(predecessor["manifest_files"])
    for filename, document in artifacts.items():
        path = staged / filename
        entries.append({
            "bytes": path.stat().st_size,
            "path": filename,
            "record_ids": [document["id"]],
            "record_type": "other",
            "schema_path": "schemas/art/release/art-pathways-artifact.schema.json",
            "sha256": sha256_file(path, prefixed=False),
        })
    entries.sort(key=lambda item: item["path"])
    manifest = deepcopy(predecessor)
    manifest.update({
        "id": RELEASE_ID, "version": RELEASE_VERSION, "build_version": "museum-06-v1", "created_at": GENERATED_AT,
        "predecessor": INPUT_RELEASE_ID, "manifest_files": entries, "content_hash": release_content_hash(entries),
        "release_notes": "Immutable explainable artist-path overlay with deterministic bidirectional BFS, bounded loopless Yen alternatives, 66 default artist pairs, strict A/B/C mode separation, per-edge Claim/Evidence/Source explanations, and a bounded automated re-review of the nine existing A/B leads. No algorithmic similarity, influence score, private lead, analytics, user history, new media, or external runtime API is added.",
    })
    manifest["schema_versions"] = {
        **predecessor["schema_versions"],
        "art/release/art-pathways-artifact": "1.0.0",
    }
    return manifest


def _validate_overlay(
    release_root: Path, predecessor: dict[str, Any], manifest: dict[str, Any], failures: list[dict[str, str]]
) -> None:
    new_entries = {item["path"]: item for item in manifest.get("manifest_files", [])}
    old_entries = {item["path"]: item for item in predecessor.get("manifest_files", [])}
    for path, old_entry in old_entries.items():
        if new_entries.get(path) != old_entry:
            _fail(failures, "predecessor_manifest_drift", f"Predecessor manifest entry changed: {path}", path)
        elif not (release_root / path).is_file() or (release_root / path).read_bytes() != (INPUT_RELEASE / path).read_bytes():
            _fail(failures, "predecessor_bytes_drift", f"Predecessor bytes changed: {path}", path)
    expected = {
        "path-algorithm-contract.json", "path-graph-input.json", "path-index.json", "path-explanations.json",
        "ab-review-summary.json", "path-performance-contract.json", "path-route-config.json",
    }
    if set(new_entries) - set(old_entries) != expected:
        _fail(failures, "overlay_file_set", "MUSEUM-06 overlay file set is not exact")


def _install_immutable(staged: Path, output_dir: Path) -> None:
    if output_dir.exists():
        if _directory_file_hashes(staged) != _directory_file_hashes(output_dir):
            raise ValueError(f"immutable output already exists with different bytes: {output_dir}")
        return
    shutil.copytree(staged, output_dir)


def _directory_file_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file()}


def _year(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def _result(
    release_root: Path, failures: list[dict[str, str]], counts: dict[str, Any] | None = None,
    content_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": not failures,
        "phase_id": PHASE_ID,
        "release_root": str(release_root),
        "release_id": RELEASE_ID,
        "content_hash": content_hash,
        "counts": counts or {},
        "codes": [item["code"] for item in failures],
        "failures": failures,
    }
