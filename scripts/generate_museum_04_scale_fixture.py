from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROFILES = {
    "1k": (1_000, 5_000),
    "10k": (10_000, 60_000),
    "50k": (50_000, 300_000),
}

VISIBLE_CAPS = {
    "mobile": (150, 600),
    "desktop": (300, 1_200),
}

RELATION_TYPES = ("shared_subject", "shared_material", "shared_technique")
CONTEXTS = ("subject:synthetic-observation", "material:synthetic-paper", "technique:synthetic-print")


@dataclass(frozen=True)
class ScalePlan:
    profile: str
    vertex_count: int
    edge_count: int
    device: str
    visible_vertex_cap: int
    visible_edge_cap: int
    full_initial_render: bool
    full_render_request_allowed: bool
    rendering_mode: str
    strategy: str


def scale_plan(profile: str, device: str = "mobile") -> ScalePlan:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    if device not in VISIBLE_CAPS:
        raise ValueError(f"Unknown device class: {device}")

    vertex_count, edge_count = PROFILES[profile]
    vertex_cap, edge_cap = VISIBLE_CAPS[device]
    if profile == "1k":
        rendering_mode = "capped_progressive"
        strategy = "load_model_render_capped_progressive_neighborhood"
        full_render_request_allowed = device == "desktop"
    elif profile == "10k":
        rendering_mode = "partitioned_capped_neighborhood"
        strategy = "partition_search_then_render_capped_neighborhood"
        full_render_request_allowed = False
    else:
        rendering_mode = "partition_or_list_fallback"
        strategy = "refuse_full_render_use_partition_or_list"
        full_render_request_allowed = False

    return ScalePlan(
        profile=profile,
        vertex_count=vertex_count,
        edge_count=edge_count,
        device=device,
        visible_vertex_cap=vertex_cap,
        visible_edge_cap=edge_cap,
        full_initial_render=False,
        full_render_request_allowed=full_render_request_allowed,
        rendering_mode=rendering_mode,
        strategy=strategy,
    )


def iter_nodes(vertex_count: int) -> Iterator[dict[str, Any]]:
    for index in range(vertex_count):
        stable = f"{index:05d}"
        yield {
            "id": f"synthetic-artist:{stable}",
            "entity_type": "synthetic_public_artist",
            "synthetic": True,
            "labels": {
                "zh-Hans": f"合成艺术家 {stable}",
                "en": f"Synthetic Artist {stable}",
            },
            "life_dates": {"birth": "synthetic", "death": "synthetic", "precision": "synthetic"},
            "activity_period": f"synthetic-period-{index % 12:02d}",
            "region": f"synthetic-region-{index % 8:02d}",
            "tradition": f"synthetic-tradition-{index % 10:02d}",
            "medium_material_summary": {
                "zh-Hans": "仅用于规模测试的合成材料摘要。",
                "en": "Synthetic material summary for scale testing only.",
            },
            "source_ids": ["source:synthetic-scale-fixture"],
            "review_status": "synthetic_fixture",
            "release_id": "release:synthetic-museum-04-scale-fixture",
        }


def iter_edges(vertex_count: int, edge_count: int) -> Iterator[dict[str, Any]]:
    if vertex_count < 2:
        raise ValueError("At least two vertices are required")
    max_unique = vertex_count * (vertex_count - 1) // 2
    if edge_count > max_unique:
        raise ValueError("Requested edge count exceeds the undirected simple-graph maximum")

    emitted = 0
    offset = 1
    while emitted < edge_count:
        if offset >= vertex_count:
            raise ValueError("Unable to produce the requested number of unique edges")
        for source_index in range(vertex_count):
            if emitted >= edge_count:
                break
            target_index = (source_index + offset) % vertex_count
            source, target = sorted((source_index, target_index))
            # When offset reaches half the ring, the reverse pair repeats. The
            # MUSEUM-04 profiles use only offsets 1..6, but keep the generator
            # correct for arbitrary inputs.
            if vertex_count % 2 == 0 and offset == vertex_count // 2 and source_index >= vertex_count // 2:
                continue
            relation_type = RELATION_TYPES[emitted % len(RELATION_TYPES)]
            context_id = CONTEXTS[emitted % len(CONTEXTS)]
            stable = f"{emitted:06d}"
            yield {
                "id": f"synthetic-rel:{stable}",
                "entity_type": "synthetic_public_relationship",
                "synthetic": True,
                "source_artist_id": f"synthetic-artist:{source:05d}",
                "target_artist_id": f"synthetic-artist:{target:05d}",
                "relationship_type": relation_type,
                "evidence_level": "C",
                "directed": False,
                "context_ids": [context_id],
                "explanation": {
                    "zh-Hans": "合成边仅用于测试规模、筛选与渲染边界，不表达任何历史事实。",
                    "en": "This synthetic edge tests scale, filtering, and rendering boundaries only; it states no historical fact.",
                },
                "what_it_means": {
                    "zh-Hans": "两个合成节点共享一个合成比较语境。",
                    "en": "Two synthetic nodes share a synthetic comparison context.",
                },
                "what_it_does_not_mean": {
                    "zh-Hans": "不表示相识、影响、师承、传播、亲密程度或价值。",
                    "en": "It does not indicate contact, influence, teaching, transmission, closeness, or value.",
                },
                "evidence_confidence": 0.8,
                "curatorial_relevance": 0.8,
                "historical_relationship_strength": None,
                "computational_similarity": None,
                "is_algorithmic": False,
                "claim_ids": [f"synthetic-claim:{stable}"],
                "evidence_ids": [f"synthetic-evidence:{stable}"],
                "source_ids": ["source:synthetic-scale-fixture"],
                "review_status": "synthetic_fixture",
                "release_id": "release:synthetic-museum-04-scale-fixture",
                "limitations": {
                    "zh-Hans": "合成 fixture，不进入公开 release。",
                    "en": "Synthetic fixture; never shipped in a public release.",
                },
            }
            emitted += 1
        offset += 1


def deterministic_sample_hash(profile: str, sample_size: int = 32) -> str:
    vertices, edges = PROFILES[profile]
    digest = hashlib.sha256()
    for record in list(iter_nodes(vertices))[:sample_size]:
        digest.update(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    for index, record in enumerate(iter_edges(vertices, edges)):
        if index >= sample_size:
            break
        digest.update(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def write_fixture(profile: str, output: Path) -> None:
    vertices, edges = PROFILES[profile]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        header = {
            "schema_version": "1.0.0",
            "fixture_id": f"synthetic-museum-04-{profile}",
            "synthetic": True,
            "shipped": False,
            "profile": profile,
            "vertex_count": vertices,
            "edge_count": edges,
            "nodes": None,
            "edges": None,
        }
        prefix = json.dumps({key: value for key, value in header.items() if key not in {"nodes", "edges"}}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:-1]
        handle.write(prefix + ',"nodes":[')
        for index, node in enumerate(iter_nodes(vertices)):
            if index:
                handle.write(",")
            handle.write(json.dumps(node, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write('],"edges":[')
        for index, edge in enumerate(iter_edges(vertices, edges)):
            if index:
                handle.write(",")
            handle.write(json.dumps(edge, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write("]}\n")


def summary(profile: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "synthetic": True,
        "shipped": False,
        "profile": profile,
        "counts": {"vertices": PROFILES[profile][0], "edges": PROFILES[profile][1]},
        "mobile": asdict(scale_plan(profile, "mobile")),
        "desktop": asdict(scale_plan(profile, "desktop")),
        "sample_hash": deterministic_sample_hash(profile),
        "governance_fields_preserved": [
            "evidence_level",
            "evidence_confidence",
            "curatorial_relevance",
            "historical_relationship_strength",
            "computational_similarity",
            "claim_ids",
            "evidence_ids",
            "source_ids",
            "limitations",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic, non-shipped MUSEUM-04 scale fixtures")
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--output", type=Path, help="Write the full synthetic fixture to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output:
        write_fixture(args.profile, args.output)
    print(json.dumps(summary(args.profile), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
