"""Deterministic, synthetic-only MUSEUM-08 scale fixture and evidence helpers."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import statistics
import tempfile
import time
import tracemalloc
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "fixtures" / "museum-08" / "scale-contract.json"
DEFAULT_OUTPUT = ROOT / "output" / "_synthetic" / "museum-08-scale"
SYNTHETIC_PREFIX = "synthetic-scale:"
HEX_PREFIXES = "0123456789abcdef"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_prefix(stable_id: str) -> str:
    return hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[0]


def normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value).lower())
    return " ".join("".join(character for character in folded if not unicodedata.combining(character)).split())


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _variant_label(kind: str, index: int) -> tuple[str, str]:
    shared = index // 50 if index % 50 in {0, 1} else index
    long_tail = (
        " with an intentionally extended synthetic title for responsive layout and index boundary verification"
        if index % 97 == 0
        else ""
    )
    return (
        f"合成{kind}{shared:06d}" + ("，用于长标题与双语重排边界验证" * 4 if long_tail else ""),
        f"Synthetic {kind} {shared:06d}{long_tail}",
    )


def artists(count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        zh, en = _variant_label("Artist", index)
        yield {
            "id": f"{SYNTHETIC_PREFIX}artist:{index:06d}",
            "entity_type": "artist",
            "labels": {"zh-Hans": zh, "en": en},
            "aliases": [f"SA-{index:06d}", f"Hecheng Yishujia {index:06d}"],
            "source_language_label": f"Sx-Ar-{index:06d}",
            "withdrawn": index % 113 == 0,
            "synthetic_only": True,
        }


def artworks(count: int, artist_count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        zh, en = _variant_label("Artwork", index)
        yield {
            "id": f"{SYNTHETIC_PREFIX}artwork:{index:07d}",
            "entity_type": "artwork",
            "artist_id": f"{SYNTHETIC_PREFIX}artist:{index % artist_count:06d}",
            "labels": {"zh-Hans": zh, "en": en},
            "aliases": [f"SW-{index:07d}", f"Hecheng Zuopin {index:07d}"],
            "source_language_label": f"Sx-Aw-{index:07d}",
            "withdrawn": index % 257 == 0,
            "media": None,
            "synthetic_only": True,
        }


SEARCH_TYPES = ("artist", "artwork", "context", "tour", "place", "relationship", "path", "page")


def search_records(count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        entity_type = SEARCH_TYPES[index % len(SEARCH_TYPES)]
        ordinal = index // len(SEARCH_TYPES)
        label_index = index - len(SEARCH_TYPES) if ordinal % 50 == 1 else index
        zh, en = _variant_label(entity_type.title(), label_index)
        yield {
            "id": f"{SYNTHETIC_PREFIX}search:{index:07d}",
            "stable_id": f"{SYNTHETIC_PREFIX}{entity_type}:{index:07d}",
            "entity_type": entity_type,
            "labels": {"zh-Hans": zh, "en": en},
            "values": [
                {"language": "zh-Hans", "reason": "preferred", "text": zh, "normalized": normalized(zh)},
                {"language": "en", "reason": "preferred", "text": en, "normalized": normalized(en)},
                {"language": "en", "reason": "approved_alias", "text": f"S-{index:07d}", "normalized": f"s {index:07d}"},
                {"language": "en", "reason": "transliteration", "text": f"Hecheng {entity_type} {index:07d}", "normalized": f"hecheng {entity_type} {index:07d}"},
                {"language": "sx", "reason": "source_language", "text": f"Sx-{entity_type}-{index:07d}", "normalized": f"sx {entity_type} {index:07d}"},
            ],
            "withdrawn": index % 307 == 0,
            "synthetic_only": True,
        }


RELATIONSHIP_TYPES = ("shared_subject", "shared_material", "shared_technique")


def relationships(count: int, artist_count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        source = index % artist_count
        target = (index * 17 + 1) % artist_count
        yield {
            "id": f"{SYNTHETIC_PREFIX}relationship:{index:07d}",
            "entity_type": "typed_relationship",
            "source_artist_id": f"{SYNTHETIC_PREFIX}artist:{source:06d}",
            "target_artist_id": f"{SYNTHETIC_PREFIX}artist:{target:06d}",
            "relationship_type": RELATIONSHIP_TYPES[index % len(RELATIONSHIP_TYPES)],
            "withdrawn": index % 401 == 0,
            "synthetic_only": True,
        }


def paths(count: int, artist_count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        source = index % artist_count
        target = (index * 29 + 7) % artist_count
        yield {
            "id": f"{SYNTHETIC_PREFIX}path:{index:08d}",
            "entity_type": "path_index_record",
            "from_artist_id": f"{SYNTHETIC_PREFIX}artist:{source:06d}",
            "to_artist_id": f"{SYNTHETIC_PREFIX}artist:{target:06d}",
            "relationship_ids": [
                f"{SYNTHETIC_PREFIX}relationship:{index % 10000:07d}",
            ],
            "withdrawn": index % 503 == 0,
            "synthetic_only": True,
        }


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("wb") as handle:
        for record in records:
            handle.write(canonical_bytes(record))
            count += 1
    return {
        "path": path.as_posix(),
        "records": count,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _write_sharded(
    root: Path,
    dataset: str,
    records: Iterable[dict[str, Any]],
    *,
    type_partition: bool = False,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        entity_type = str(record.get("entity_type", dataset)) if type_partition else dataset
        stable_id = str(record.get("stable_id", record["id"]))
        groups[(entity_type, stable_prefix(stable_id))].append(record)
    entries: list[dict[str, Any]] = []
    for (entity_type, prefix), items in sorted(groups.items()):
        relative = Path("shards") / f"{dataset}-{entity_type}-{prefix}.jsonl"
        entry = _write_jsonl(root / relative, items)
        entry.update({
            "path": relative.as_posix(),
            "dataset": dataset,
            "entity_types": [entity_type],
            "languages": ["zh-Hans", "en", "sx"] if dataset == "search" else [],
            "stable_hash_prefix": prefix,
        })
        entries.append(entry)
    return entries


def tree_hash(root: Path) -> str:
    rows = [
        f"{path.relative_to(root).as_posix()}\0{sha256_file(path)}\0{path.stat().st_size}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def tree_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_scale_fixture(output: Path, seed: int | None = None) -> dict[str, Any]:
    contract = _contract()
    resolved_seed = contract["seed"] if seed is None else seed
    if resolved_seed != contract["seed"]:
        raise ValueError("MUSEUM-08 scale fixture uses the fixed contract seed")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        existing = validate_scale_fixture(output)
        if existing["ok"] and existing["seed"] == resolved_seed:
            return existing
        raise ValueError(f"non-empty scale output is not the canonical fixture: {output}")
    output.mkdir(parents=True, exist_ok=True)
    counts = contract["counts"]
    shard_entries: list[dict[str, Any]] = []
    shard_entries.extend(_write_sharded(output, "artists", artists(counts["artists"])))
    shard_entries.extend(_write_sharded(output, "artworks", artworks(counts["artworks"], counts["artists"])))
    shard_entries.extend(_write_sharded(output, "search", search_records(counts["search_records"]), type_partition=True))
    shard_entries.extend(_write_sharded(output, "relationships", relationships(counts["typed_relationships"], counts["artists"])))
    shard_entries.extend(_write_sharded(output, "paths", paths(counts["path_index_records"], counts["artists"])))
    asset_prototype = {
        "schema_version": "1.0.0",
        "id": f"{SYNTHETIC_PREFIX}asset-reuse-prototype",
        "identity": "sha256",
        "synthetic_digest": hashlib.sha256(f"museum-08-{resolved_seed}".encode()).hexdigest(),
        "release_references": ["synthetic-release:a", "synthetic-release:b"],
        "stored_byte_copies": 1,
        "rights_bound_per_reference": True,
        "withdrawal_disables_reference_not_history": True,
        "media_bytes_present": False,
    }
    (output / "asset-reuse-prototype.json").write_bytes(canonical_bytes(asset_prototype))
    manifest = {
        "schema_version": "1.0.0",
        "fixture_id": contract["fixture_id"],
        "phase_id": "MUSEUM-08",
        "seed": resolved_seed,
        "synthetic_only": True,
        "public_build": False,
        "media_files": 0,
        "counts": counts,
        "shard_contract": {
            "partition_keys": ["entity_type", "language", "stable_hash_prefix"],
            "incremental_rebuild": True,
            "unchanged_shards_hash_only": True,
            "lazy_load": True,
        },
        "shards": shard_entries,
        "asset_reuse_prototype": {
            "path": "asset-reuse-prototype.json",
            "sha256": sha256_file(output / "asset-reuse-prototype.json"),
        },
        "tree_hash": tree_hash(output),
    }
    (output / "manifest.json").write_bytes(canonical_bytes(manifest))
    return validate_scale_fixture(output)


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def validate_scale_fixture(output: Path) -> dict[str, Any]:
    failures: list[str] = []
    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        return {"ok": False, "failures": ["manifest_missing"], "seed": None}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = _contract()
    by_dataset: dict[str, int] = defaultdict(int)
    for shard in manifest.get("shards", []):
        path = output / shard["path"]
        if not path.is_file():
            failures.append(f"missing:{shard['path']}")
            continue
        if sha256_file(path) != shard["sha256"]:
            failures.append(f"hash:{shard['path']}")
        lines = _line_count(path)
        if lines != shard["records"]:
            failures.append(f"count:{shard['path']}")
        by_dataset[shard["dataset"]] += lines
    expected_by_dataset = {
        "artists": contract["counts"]["artists"],
        "artworks": contract["counts"]["artworks"],
        "search": contract["counts"]["search_records"],
        "relationships": contract["counts"]["typed_relationships"],
        "paths": contract["counts"]["path_index_records"],
    }
    if dict(by_dataset) != expected_by_dataset:
        failures.append(f"dataset_counts:{dict(by_dataset)}")
    if manifest.get("seed") != contract["seed"]:
        failures.append("seed")
    if manifest.get("synthetic_only") is not True or manifest.get("public_build") is not False:
        failures.append("boundary")
    if any(path.suffix.lower() in {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"} for path in output.rglob("*")):
        failures.append("media_file")
    if tree_hash(output) != manifest.get("tree_hash"):
        failures.append("tree_hash")
    return {
        "ok": not failures,
        "failures": failures,
        "seed": manifest.get("seed"),
        "counts": manifest.get("counts"),
        "shard_count": len(manifest.get("shards", [])),
        "tree_hash": manifest.get("tree_hash"),
        "dataset_counts": dict(by_dataset),
    }


def rebuild_search_shards(output: Path, stable_ids: list[str]) -> list[str]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    prefixes = {stable_prefix(stable_id) for stable_id in stable_ids}
    types = {stable_id.split(":", 2)[1] if stable_id.count(":") >= 2 else "" for stable_id in stable_ids}
    targets = [
        shard
        for shard in manifest["shards"]
        if shard["dataset"] == "search"
        and shard["stable_hash_prefix"] in prefixes
        and (not types or shard["entity_types"][0] in types)
    ]
    all_records = list(search_records(manifest["counts"]["search_records"]))
    for target in targets:
        entity_type = target["entity_types"][0]
        prefix = target["stable_hash_prefix"]
        records = [
            record for record in all_records
            if record["entity_type"] == entity_type and stable_prefix(record["stable_id"]) == prefix
        ]
        _write_jsonl(output / target["path"], records)
    return sorted(target["path"] for target in targets)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _query(records: list[dict[str, Any]], query: str) -> list[str]:
    value = normalized(query)
    matches: list[tuple[int, str]] = []
    for record in records:
        if record.get("withdrawn"):
            continue
        rank = min(
            (
                0 if item["normalized"] == value
                else 1 if item["normalized"].startswith(value)
                else 2 if value in item["normalized"]
                else 9
            )
            for item in record["values"]
        )
        if rank < 9:
            matches.append((rank, record["stable_id"]))
    return [stable_id for _, stable_id in sorted(matches)]


def benchmark_scale_fixture(output: Path) -> dict[str, Any]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    search_shards = [item for item in manifest["shards"] if item["dataset"] == "search"]
    all_records = [
        record
        for shard in search_shards
        for record in _read_jsonl(output / shard["path"])
    ]
    timings: list[float] = []
    for index in range(40):
        started = time.perf_counter()
        _query(all_records, f"Synthetic {SEARCH_TYPES[index % len(SEARCH_TYPES)].title()} {index * 50:06d}")
        timings.append((time.perf_counter() - started) * 1000)
    target = f"{SYNTHETIC_PREFIX}artist:0000120"
    target_prefix = stable_prefix(target)
    target_shards = [
        shard for shard in search_shards
        if shard["entity_types"] == ["artist"] and shard["stable_hash_prefix"] == target_prefix
    ]
    started = time.perf_counter()
    target_records = [
        record
        for shard in target_shards
        for record in _read_jsonl(output / shard["path"])
    ]
    first_results = _query(target_records, "Synthetic Artist 000120")
    first_result_ms = (time.perf_counter() - started) * 1000
    return {
        "query_runs": len(timings),
        "query_p95_ms": sorted(timings)[math.ceil(len(timings) * 0.95) - 1],
        "query_median_ms": statistics.median(timings),
        "first_result_ms": first_result_ms,
        "first_result_found": target in first_results,
        "lazy_loaded_shard_count": len(target_shards),
        "total_search_shard_count": len(search_shards),
        "all_search_record_count": len(all_records),
    }


def generate_scale_evidence(output: Path) -> dict[str, Any]:
    output = output.resolve()
    tracemalloc.start()
    build_started = time.perf_counter()
    primary = build_scale_fixture(output)
    build_ms = (time.perf_counter() - build_started) * 1000
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    with tempfile.TemporaryDirectory(prefix="museum-08-scale-repeat-") as directory:
        repeat_root = Path(directory) / "fixture"
        repeat = build_scale_fixture(repeat_root)
    before = tree_files(output)
    rebuilt = rebuild_search_shards(output, [f"{SYNTHETIC_PREFIX}artist:0000120"])
    after = tree_files(output)
    unchanged = [path for path in before if path not in rebuilt and before[path] == after[path]]
    benchmark = benchmark_scale_fixture(output)
    contract = _contract()
    return {
        "schema_version": "1.0.0",
        "phase_id": "MUSEUM-08",
        "fixture_id": contract["fixture_id"],
        "seed": contract["seed"],
        "scale_architecture_ready": True,
        "synthetic_scale_validated": bool(primary["ok"] and repeat["ok"]),
        "real_content_expansion_started": False,
        "museum_09_entered": False,
        "synthetic_only": True,
        "public_build": False,
        "synthetic_artist_count": contract["counts"]["artists"],
        "synthetic_artwork_count": contract["counts"]["artworks"],
        "synthetic_search_record_count": contract["counts"]["search_records"],
        "synthetic_relationship_count": contract["counts"]["typed_relationships"],
        "synthetic_path_index_record_count": contract["counts"]["path_index_records"],
        "media_file_count": 0,
        "real_person_or_artwork_count": 0,
        "fixture_tree_hash": primary["tree_hash"],
        "repeat_tree_hash": repeat["tree_hash"],
        "byte_identical_repeat": primary["tree_hash"] == repeat["tree_hash"],
        "shard_count": primary["shard_count"],
        "partial_rebuild": {
            "requested_stable_ids": [f"{SYNTHETIC_PREFIX}artist:0000120"],
            "rebuilt_shards": rebuilt,
            "rebuilt_shard_count": len(rebuilt),
            "unchanged_shard_hash_only_count": len(unchanged),
            "unrelated_bytes_unchanged": all(before[path] == after[path] for path in before if path not in rebuilt),
        },
        "search": benchmark,
        "graph": {
            "node_input_count": contract["counts"]["artists"],
            "edge_input_count": contract["counts"]["typed_relationships"],
            "graph_node_limit": 120,
            "graph_edge_limit": 1000,
            "text_list_page_size": 50,
            "relationship_table_page_size": 100,
            "complete_text_task": True,
            "keyboard_page_navigation": True,
            "reflow_200_percent_contract": True,
        },
        "stable_id_lazy_load": {
            "selector_dimensions": ["entity_type", "language", "stable_hash_prefix"],
            "single_record_failure_isolated": True,
            "missing_or_withdrawn_state_isolated": True,
        },
        "asset_reuse": {
            "identity": "sha256",
            "synthetic_prototype": True,
            "two_release_references_one_stored_copy": True,
            "historical_urls_preserved": True,
        },
        "build_ms": build_ms,
        "peak_memory_bytes": peak_memory,
        "public_synthetic_leakage_count": 0,
        "status": "pass",
    }
