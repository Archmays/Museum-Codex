from __future__ import annotations

import gzip
import json
import math
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote

# libjpeg-turbo's SIMD IDCT can differ by a few decoded sample values across
# platforms.  Detail-region metrics are release bytes, so use its scalar path
# before Pillow loads the decoder.
os.environ["JSIMD_FORCENONE"] = "1"

from PIL import Image, ImageFilter, ImageStat

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.validation.dispatch import load_schema_environment, validate_record
from scripts.validate_governance_foundation import release_content_hash, validate_release_directory


PHASE_ID = "MUSEUM-05B"
INPUT_RELEASE_ID = "release:art-constellation-1.0.0"
INPUT_RELEASE_HASH = "sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462"
MEDIA_BUNDLE_HASH = "sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565"
RELEASE_ID = "release:art-gallery-interactions-1.1.0"
RELEASE_VERSION = "1.1.0"
GENERATED_AT = "2026-07-16T08:00:00+08:00"
REVIEWED_AT = "2026-07-16"
PACKAGE_LOCK_HASH = "sha256:57113cd49cead7c62265df0f4ff37151d8c94ea8697374581b06d3ef9cdafa9d"
DETAIL_METRIC_SCALE = 100
INPUT_RELEASE = ROOT / "public" / "releases" / "art-constellation-1.0.0"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-gallery-interactions-1.1.0"
RETRY_ARTIFACT = ROOT / "data" / "reviewed" / "art" / "museum-05b" / "media-retry-v1.json"

PERIOD_TRANSLATIONS = {
    "Edo period": "江户时代",
    "Ming dynasty": "明代",
    "Modern": "现代",
    "Modern transition": "近现代转型期",
    "Northern European Renaissance": "北方文艺复兴",
}

PLACE_TRANSLATIONS = {
    "Aguascalientes and Mexico City": "阿瓜斯卡连特斯与墨西哥城",
    "Calcutta, the Isle of Wight, and Kalutara": "加尔各答、怀特岛与卡卢特勒",
    "Edo": "江户",
    "Kilimanoor and Bombay": "基利马努尔与孟买",
    "Königsberg, Berlin, and Moritzburg": "柯尼斯堡、柏林与莫里茨堡",
    "Madrid and Bordeaux": "马德里与波尔多",
    "Nuremberg": "纽伦堡",
    "Pennsylvania, Paris, and Île-de-France": "宾夕法尼亚、巴黎与法兰西岛",
    "Philadelphia and Paris": "费城与巴黎",
    "Suzhou region (historical Changzhou County)": "苏州地区（历史上的长洲县）",
    "The Netherlands, Paris, Arles, and Auvers-sur-Oise": "荷兰、巴黎、阿尔勒与瓦兹河畔欧韦",
}


THEMATIC_TOURS = (
    (
        "paper-ink-reproduction",
        {"zh-Hans": "纸、墨与复制实践", "en": "Paper, Ink, and Reproduction"},
        ["artwork:aic-158971", "artwork:met-851484", "artwork:met-729644", "artwork:met-39799", "artwork:met-54876", "artwork:met-459211"],
    ),
    (
        "line-on-paper",
        {"zh-Hans": "纸面线条", "en": "Line on Paper"},
        ["artwork:aic-158971", "artwork:met-334816", "artwork:met-51858", "artwork:met-39799", "artwork:met-45323", "artwork:met-358856"],
    ),
    (
        "figures-portraits-looking",
        {"zh-Hans": "人物、肖像与观看", "en": "Figures, Portraits, and Looking"},
        ["artwork:aic-111442", "artwork:met-436543", "artwork:met-267426", "artwork:met-436532", "artwork:met-459211", "artwork:aic-60513"],
    ),
    (
        "care-pairing-everyday",
        {"zh-Hans": "照护、成对人物与日常相遇", "en": "Care, Pairing, and Everyday Encounter"},
        ["artwork:aic-111442", "artwork:met-436244", "artwork:met-437984", "artwork:met-56128", "artwork:met-54876", "artwork:met-851484"],
    ),
    (
        "support-and-surface",
        {"zh-Hans": "支撑物与表面：画布、木板与纸", "en": "Support and Surface: Canvas, Panel, and Paper"},
        ["artwork:aic-26650", "artwork:met-16947", "artwork:met-436543", "artwork:met-436528", "artwork:met-436243", "artwork:met-267426"],
    ),
    (
        "landscape-water-sacred-narrative",
        {"zh-Hans": "跨时空的山水、水与神圣叙事", "en": "Landscape, Water, and Sacred Narrative Across Time"},
        ["artwork:met-17016", "artwork:met-851486", "artwork:met-51858", "artwork:met-39799", "artwork:met-37110", "artwork:met-436243"],
    ),
)


def build_museum_05b_release(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_dir = _resolve(output_dir)
    source = _load_source()
    interaction_index = _build_interaction_index(source)
    _validate_interaction_schema(interaction_index)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-05b-release-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / output_dir.name
        _copy_predecessor(staged)
        (staged / "media-retry.json").write_bytes(RETRY_ARTIFACT.read_bytes())
        (staged / "interaction-index.json").write_bytes(canonical_json_bytes(interaction_index))
        manifest = _build_manifest(staged)
        (staged / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        result = validate_museum_05b_release(staged)
        if not result["ok"]:
            raise ValueError("staged MUSEUM-05B release failed: " + ", ".join(result["codes"][:12]))
        _install_immutable(staged, output_dir)

    result = validate_museum_05b_release(output_dir)
    if not result["ok"]:
        raise ValueError("written MUSEUM-05B release failed: " + ", ".join(result["codes"][:12]))
    return result


def validate_museum_05b_release(release_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    release_root = _resolve(release_root)
    failures: list[dict[str, str]] = []
    if not release_root.is_dir():
        _fail(failures, "release_missing", "MUSEUM-05B release directory is absent")
        return _result(release_root, failures, {})

    try:
        old_manifest = _load_json(INPUT_RELEASE / "manifest.json")
        manifest = _load_json(release_root / "manifest.json")
        index = _load_json(release_root / "interaction-index.json")
    except (OSError, json.JSONDecodeError) as error:
        _fail(failures, "release_json_invalid", str(error))
        return _result(release_root, failures, {})

    if old_manifest.get("id") != INPUT_RELEASE_ID or old_manifest.get("content_hash") != INPUT_RELEASE_HASH:
        _fail(failures, "predecessor_drift", "The immutable MUSEUM-04 predecessor no longer matches its protected hash")
    expected_profile = {
        "id": RELEASE_ID,
        "version": RELEASE_VERSION,
        "predecessor": INPUT_RELEASE_ID,
        "status": "publishable",
        "public_release": True,
    }
    for key, expected in expected_profile.items():
        if manifest.get(key) != expected:
            _fail(failures, "manifest_profile", f"{key} must be {expected!r}", f"manifest.{key}")

    try:
        generic_issues = validate_release_directory(release_root, load_schema_environment(ROOT))
        for issue in generic_issues:
            _fail(failures, f"generic_{issue.code}", issue.message, issue.location)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        _fail(failures, "generic_validator_error", str(error))

    _validate_predecessor_bytes(release_root, old_manifest, manifest, failures)
    try:
        _validate_interaction_schema(index)
    except ValueError as error:
        _fail(failures, "interaction_schema", str(error), "interaction-index.json")
    _validate_index_semantics(release_root, index, failures)
    if manifest.get("content_hash") != release_content_hash(manifest.get("manifest_files", [])):
        _fail(failures, "content_hash", "Release content hash does not match its physical manifest")

    counts = index.get("counts", {}) if isinstance(index, dict) else {}
    return _result(release_root, failures, counts, manifest.get("content_hash"))


def _load_source() -> dict[str, Any]:
    manifest = _load_json(INPUT_RELEASE / "manifest.json")
    if manifest.get("id") != INPUT_RELEASE_ID or manifest.get("content_hash") != INPUT_RELEASE_HASH:
        raise ValueError("MUSEUM-04 predecessor hash mismatch")
    names = ("artists", "artworks", "contexts", "claims", "evidence", "sources", "media-index")
    source = {name: _load_json(INPUT_RELEASE / f"{name}.json") for name in names}
    source["manifest"] = manifest
    source["retry"] = _load_json(RETRY_ARTIFACT)
    if source["media-index"].get("media_bundle_hash") != MEDIA_BUNDLE_HASH:
        raise ValueError("MUSEUM-03C media bundle hash mismatch")
    if sha256_file(ROOT / "package-lock.json") != PACKAGE_LOCK_HASH:
        raise ValueError("package-lock.json changed after the validated baseline")
    return source


def _build_interaction_index(source: dict[str, Any]) -> dict[str, Any]:
    artists = sorted(source["artists"]["artists"], key=lambda item: item["id"])
    artworks = sorted(source["artworks"]["artworks"], key=lambda item: item["id"])
    contexts = sorted(source["contexts"]["contexts"], key=lambda item: item["id"])
    claims = source["claims"]["claims"]
    evidence = source["evidence"]["evidence"]
    media_index = source["media-index"]
    context_by_id = {item["id"]: item for item in contexts}
    artwork_by_id = {item["id"]: item for item in artworks}
    artist_by_id = {item["id"]: item for item in artists}
    evidence_by_id = {item["id"]: item for item in evidence}
    source_by_id = {item["id"]: item for item in source["sources"]["sources"]}

    cards = [_observation_card(item, claims, evidence_by_id, source_by_id) for item in artworks]
    heroes, regions = _hero_selections(artists, artwork_by_id, media_index)
    artist_tours = [
        _artist_tour(artist, artwork_by_id, context_by_id, index)
        for index, artist in enumerate(artists)
    ]
    thematic_tours = [
        _thematic_tour(slug, title, artwork_ids, artwork_by_id, artist_by_id)
        for slug, title, artwork_ids in THEMATIC_TOURS
    ]
    lenses = [_lens(kind, contexts, artworks, claims, source_by_id) for kind in ("material", "technique", "subject")]
    retry_hash = source["retry"].get("content_hash")
    if retry_hash != canonical_sha256({k: v for k, v in source["retry"].items() if k != "content_hash"}):
        raise ValueError("MUSEUM-05B media retry artifact hash mismatch")
    visual_count = sum(item["status"] == "visual_detail_path" for item in heroes)
    return {
        "schema_version": "1.0.0",
        "id": "interaction-index:museum-05b-v1",
        "entity_type": "art_gallery_interaction_index",
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "release_version": RELEASE_VERSION,
        "input_release_id": INPUT_RELEASE_ID,
        "input_release_hash": INPUT_RELEASE_HASH,
        "media_bundle_hash": MEDIA_BUNDLE_HASH,
        "generated_at": GENERATED_AT,
        "release_composition": {
            "mode": "immutable_overlay",
            "base_release_id": INPUT_RELEASE_ID,
            "base_release_hash": INPUT_RELEASE_HASH,
            "base_artifact_identity": "base_release_scoped",
            "inherited_manifest_file_count": len(source["manifest"]["manifest_files"]),
            "overlay_files": ["interaction-index.json", "media-retry.json"],
        },
        "counts": {
            "artists": 12,
            "artworks": 44,
            "approved_media_artworks": 31,
            "no_image_artworks": 13,
            "observation_cards": len(cards),
            "hero_selections": len(heroes),
            "visual_heroes": visual_count,
            "textual_observation_paths": len(heroes) - visual_count,
            "detail_regions": len(regions),
            "artist_tours": len(artist_tours),
            "thematic_tours": len(thematic_tours),
            "lenses": len(lenses),
        },
        "cache_reuse": {
            "m03c_originals_reused": True,
            "m03c_derivatives_reused": True,
            "m04_core_artifacts_byte_reused": True,
            "m04_layout_reused": True,
            "m04_search_index_reused": True,
            "scale_benchmarks_reused": True,
            "package_lock_sha256": PACKAGE_LOCK_HASH,
        },
        "observation_cards": cards,
        "hero_selections": heroes,
        "detail_regions": regions,
        "artist_tours": artist_tours,
        "thematic_tours": thematic_tours,
        "lenses": lenses,
        "compare_prompts": _compare_prompts(),
        "print_share_configuration": {
            "allowed_routes": ["/art/artworks/:artworkId", "/art/artists/:artistId", "/art/tours/:tourId", "/art/compare"],
            "allowed_query_keys": ["left", "right", "view", "region", "leftRegion", "rightRegion", "lens"],
            "tracking_parameters": False,
            "upload_data": False,
            "print_image_policy": "approved_small_image_or_metadata_only",
            "forced_colors": True,
            "release_id_in_print": True,
        },
        "media_retry_summary": {
            "artifact_path": "media-retry.json",
            "artifact_hash": retry_hash,
            "status": source["retry"]["status"],
            "artwork_count": 13,
            "download_attempt_count": 0,
            "approved_media_count_before": 31,
            "approved_media_count_after": 31,
            "no_image_count_after": 13,
            "human_review_dependency": False,
        },
        "performance_contract": {
            "home_growth_percent_max": 5,
            "tours_route_gzip_max": 307200,
            "artwork_interaction_chunk_gzip_max": 184320,
            "interaction_json_gzip_max": 122880,
            "detail_regions_gzip_max": 30720,
            "low_bandwidth_default": "no_images",
            "print_loads_large_images": False,
            "initial_loads_all_tour_images": False,
        },
        "review": _review(),
    }


def _observation_card(
    artwork: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    has_image = artwork["media"]["decision"] == "approved_self_hosted"
    linked_claims = [item for item in claims if item.get("subject_id") == artwork["id"]]
    evidence_ids = sorted({value for item in linked_claims for value in item.get("evidence_ids", [])})
    source_ids = sorted({value for evidence_id in evidence_ids for value in evidence_by_id[evidence_id].get("source_ids", [])})
    if not source_ids:
        source_ids = sorted(artwork["source_ids"])
    contexts = {
        "materials": [_context_link(item) for item in artwork.get("materials", [])],
        "techniques": [_context_link(item) for item in artwork.get("techniques", [])],
        "subjects": [_context_link(item) for item in artwork.get("subjects", [])],
    }
    if has_image:
        prompts = [
            _bi("先辨认最强的线条、边缘或形状，再比较它们如何相遇。", "Locate the strongest lines, edges, or shapes, then compare how they meet."),
            _bi("比较最亮与最暗区域的分布，不为其指定情绪。", "Compare the distribution of light and dark areas without assigning an emotion."),
            _bi("从整体到局部观察空间、重复与材料痕迹。", "Move from whole to detail to observe space, repetition, and material traces."),
        ]
        directly = [
            _bi("可观察线条、形状、明暗、空间、重复和表面痕迹。", "Lines, shapes, light-dark structure, space, repetition, and surface traces can be observed."),
            _bi("细节区域仅帮助移动视点，不为图像内容命名。", "Detail regions only move the viewpoint; they do not name image content."),
        ]
        accessibility = _bi("图像与同等完整的文字观察提示并行提供。", "The image is paired with an equally complete text observation path.")
    else:
        prompts = [
            _bi("从官方记录列出的年代、机构与材料开始。", "Begin with the date, institution, and materials listed by the official record."),
            _bi("比较材料、技法与题材字段之间可核验的联系。", "Compare the verifiable links among the material, technique, and subject fields."),
            _bi("打开来源与证据，确认每个解释能走回正式记录。", "Open the sources and evidence to confirm that each interpretation returns to a formal record."),
        ]
        directly = [
            _bi("当前可直接核验的是正式元数据、来源与证据链。", "What can be checked directly here is the formal metadata, sources, and evidence chain."),
            _bi("无批准图像时不布置任何肉眼细节任务。", "No visual-detail task is assigned when no image is approved."),
        ]
        accessibility = _bi("本路径只使用完整元数据与证据，不以假图或视觉描述替代作品。", "This path uses complete metadata and evidence only; no false image or visual description substitutes for the work.")
    chinese_title = artwork["labels"]["zh-Hans"]
    title = {
        "zh-Hans": f"观察{chinese_title}" if chinese_title.startswith("《") else f"观察《{chinese_title}》",
        "en": f"Observe {artwork['labels']['en']}",
    }
    return {
        "id": "observation:" + artwork["id"].split(":", 1)[1],
        "artwork_id": artwork["id"],
        "title": title,
        "prompts": prompts,
        "contexts": contexts,
        "date": _localized_creation_date(artwork["creation"]),
        "institution": deepcopy(artwork["institution"]["label"]),
        "directly_observable": directly,
        "interpretation_requires_sources": [_bi("材料、技法、题材、年代与机构的解释必须由所列来源和证据支持。", "Interpretations of material, technique, subject, date, and institution must be supported by the listed sources and evidence.")],
        "current_evidence_cannot_prove": [_bi("当前证据不能证明作者意图、心理、象征意义、影响、师承、传播或价值高低。", "Current evidence cannot prove intention, psychology, symbolism, influence, instruction, transmission, or artistic rank.")],
        "evidence_ids": evidence_ids,
        "source_ids": source_ids,
        "source_links": [
            {"source_id": source_id, "label": source_by_id[source_id]["locator"]["label"], "url": source_by_id[source_id]["locator"]["url"]}
            for source_id in source_ids
        ],
        "rights_status": artwork["media"]["decision"],
        "image_availability": "approved_image" if has_image else "metadata_only",
        "accessibility_version": {"mode": "image_plus_text" if has_image else "evidence_only", "summary": accessibility},
        "review": _review(),
        "release_id": RELEASE_ID,
        "release_version": RELEASE_VERSION,
    }


def _hero_selections(artists: list[dict[str, Any]], artworks: dict[str, dict[str, Any]], media_index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets_by_artwork: dict[str, list[dict[str, Any]]] = {}
    for asset in media_index["assets"]:
        if asset["format"] == "jpeg":
            assets_by_artwork.setdefault(asset["artwork_id"], []).append(asset)
    heroes: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    for artist in artists:
        candidates = []
        for artwork_id in artist["artwork_ids"]:
            artwork = artworks[artwork_id]
            jpeg_assets = assets_by_artwork.get(artwork_id, [])
            largest = max(jpeg_assets, key=lambda item: (item["width"] * item["height"], item["width"]), default=None)
            completeness = len(artwork.get("materials", [])) + len(artwork.get("techniques", [])) + len(artwork.get("subjects", []))
            candidates.append((largest is not None, largest["width"] * largest["height"] if largest else 0, completeness, artwork_id, largest))
        selected = max(candidates, key=lambda item: (item[0], item[1], item[2], tuple(-ord(char) for char in item[3])))
        _, _, _, artwork_id, asset = selected
        hero_id = "hero:" + artist["id"].split(":", 1)[1]
        selection_hash = canonical_sha256({
            "input_release_hash": INPUT_RELEASE_HASH,
            "artist_id": artist["id"],
            "candidates": [{"artwork_id": item[3], "approved": item[0], "area": item[1], "metadata_context_count": item[2]} for item in candidates],
        })
        if asset is None:
            heroes.append({
                "id": hero_id,
                "artist_id": artist["id"],
                "artwork_id": artwork_id,
                "status": "textual_observation_path",
                "selection_input_hash": selection_hash,
                "rationale": _bi("该艺术家当前没有通过权利与字节闭包的 JPEG；按正式语境字段数量与稳定 ID 选择文字观察入口，不作艺术价值排序。", "No JPEG for this artist currently passes rights and byte closure; the textual entry is selected by formal-context count and stable ID, without ranking artistic value."),
                "source_asset": None,
                "detail_region_ids": [],
            })
            continue
        source_asset = {"media_id": asset["id"], "path": asset["src"], "sha256": asset["sha256"], "width": asset["width"], "height": asset["height"]}
        hero_regions = _detail_regions(hero_id, artwork_id, source_asset)
        regions.extend(hero_regions)
        heroes.append({
            "id": hero_id,
            "artist_id": artist["id"],
            "artwork_id": artwork_id,
            "status": "visual_detail_path",
            "selection_input_hash": selection_hash,
            "rationale": _bi("在权利已批准且有 JPEG 的候选中，依次按最大衍生图像素面积、正式语境字段数量与稳定 ID 确定；不按知名度、市场或艺术价值排序。", "Selected among rights-approved JPEG candidates by largest derivative pixel area, formal-context count, then stable ID; fame, market, and artistic value are not ranked."),
            "source_asset": source_asset,
            "detail_region_ids": [item["id"] for item in hero_regions],
        })
    return sorted(heroes, key=lambda item: item["id"]), sorted(regions, key=lambda item: item["id"])


def _detail_regions(hero_id: str, artwork_id: str, source_asset: dict[str, Any]) -> list[dict[str, Any]]:
    path = INPUT_RELEASE / source_asset["path"]
    with Image.open(path) as image:
        gray = image.convert("L")
        width, height = gray.size
        if (width, height) != (source_asset["width"], source_asset["height"]):
            raise ValueError(f"Hero source dimensions drifted: {source_asset['path']}")
        crop_width = max(1, round(width * 0.32))
        crop_height = max(1, round(height * 0.32))
        margin_x = round(width * 0.06)
        margin_y = round(height * 0.06)
        xs = sorted({margin_x, max(margin_x, (width - crop_width) // 2), max(margin_x, width - margin_x - crop_width)})
        ys = sorted({margin_y, max(margin_y, (height - crop_height) // 2), max(margin_y, height - margin_y - crop_height)})
        global_mean = ImageStat.Stat(gray).mean[0]
        candidates: list[tuple[float, dict[str, float], tuple[int, int, int, int]]] = []
        for y in ys:
            for x in xs:
                box = (x, y, min(width, x + crop_width), min(height, y + crop_height))
                crop = gray.crop(box)
                stat = ImageStat.Stat(crop)
                contrast = stat.stddev[0] / 255.0
                entropy = crop.entropy() / 8.0
                edges = crop.filter(ImageFilter.FIND_EDGES)
                edge_density = sum(1 for value in edges.getdata() if value > 28) / max(1, crop.width * crop.height)
                mean_delta = abs(stat.mean[0] - global_mean) / 255.0
                cx = (x + crop.width / 2) / width
                cy = (y + crop.height / 2) / height
                center = max(0.0, 1.0 - ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5)
                saliency = 0.55 * contrast + 0.3 * mean_delta + 0.15 * center
                score = 0.32 * edge_density + 0.28 * contrast + 0.24 * entropy + 0.16 * saliency
                metrics = {"edge_density": edge_density, "local_contrast": contrast, "entropy": entropy, "saliency": saliency, "score": score}
                candidates.append((score, metrics, box))
        selected: list[tuple[dict[str, float], tuple[int, int, int, int]]] = []
        for _, metrics, box in sorted(candidates, key=lambda item: (-item[0], item[2][1], item[2][0])):
            if all(_iou(box, existing_box) <= 0.25 for _, existing_box in selected):
                selected.append((metrics, box))
            if len(selected) == 3:
                break
    result = []
    slug = artwork_id.split(":", 1)[1]
    for index, (metrics, box) in enumerate(selected, start=1):
        x1, y1, x2, y2 = box
        rect = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
        result.append({
            "id": f"detail-region:{slug}-{index}",
            "hero_id": hero_id,
            "artwork_id": artwork_id,
            "label": {"zh-Hans": f"细节区域 {index}", "en": f"Detail region {index}"},
            "source_asset": deepcopy(source_asset),
            "rect": rect,
            "normalized_rect": {key: round(value, 8) for key, value in {"x": x1 / width, "y": y1 / height, "width": (x2 - x1) / width, "height": (y2 - y1) / height}.items()},
            "metrics": {key: _stable_detail_metric(value) for key, value in metrics.items()},
            "algorithm": {"name": "structural-detail-navigation", "version": "1.0.1", "input_release_hash": INPUT_RELEASE_HASH, "maximum_iou": 0.25, "border_exclusion_ratio": 0.06, "minimum_area_ratio": 0.08, "metric_quantization": "floor_0.01"},
            "semantic_label": None,
        })
    return result


def _artist_tour(
    artist: dict[str, Any],
    artworks: dict[str, dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
    artist_index: int,
) -> dict[str, Any]:
    selected_ids = list(artist["artwork_ids"][:4])
    selected = [artworks[value] for value in selected_ids]
    available_contexts = [
        item
        for artwork in selected
        for group in ("materials", "techniques", "subjects")
        for item in artwork.get(group, [])
    ]
    focus_type = ("material", "technique", "subject")[artist_index % 3]
    matching_focus = [item for item in available_contexts if item["id"].startswith(f"{focus_type}:")]
    focus_ref = sorted(matching_focus or available_contexts, key=lambda item: item["id"])[0]
    focus_context = contexts[focus_ref["id"]]
    name_zh = artist["labels"]["zh-Hans"]
    name_en = artist["labels"]["en"]
    periods = [_localized_registry_label(value, PERIOD_TRANSLATIONS) for value in artist["historical_periods"]]
    places = [_localized_registry_label(item["label"], PLACE_TRANSLATIONS) for item in artist["activity_places"]]
    period_zh = "、".join(item["zh-Hans"] for item in periods)
    period_en = ", ".join(item["en"] for item in periods)
    place_zh = "、".join(item["zh-Hans"] for item in places)
    place_en = ", ".join(item["en"] for item in places)
    return {
        "id": "tour:artist-" + artist["id"].split(":", 1)[1],
        "kind": "artist",
        "title": {"zh-Hans": f"观察{name_zh}", "en": f"Observing {name_en}"},
        "artist_id": artist["id"],
        "entry_question": _bi(f"在这组经审核作品中，{focus_ref['labels']['zh-Hans']}如何成为可比较的观察入口？", f"How can {focus_ref['labels']['en']} serve as an observable entry point across these reviewed works?"),
        "artwork_steps": [_tour_step(index, artwork) for index, artwork in enumerate(selected, start=1)],
        "focus": {"type": focus_context["context_type"], "context_id": focus_context["id"], "label": deepcopy(focus_context["labels"])},
        "time_place_context": _bi(f"本导览只把{period_zh}与{place_zh}作为经审核的时间、地点背景。", f"This tour uses {period_en} and {place_en} only as reviewed period and place context."),
        "evidence_check": _bi(f"打开《{selected[0]['labels']['zh-Hans']}》的证据与来源，核对“{focus_ref['labels']['zh-Hans']}”字段。", f"Open the evidence and source for {selected[0]['labels']['en']} and verify the “{focus_ref['labels']['en']}” field."),
        "do_not_overinterpret": _bi(f"不要把这一顺序解释为{name_zh}的完整传记、全部创作、影响、师承或价值排序。", f"Do not read this sequence as a complete biography, full practice, influence, instruction, or ranking of {name_en}."),
        "reflection_question": _bi(f"围绕“{focus_ref['labels']['zh-Hans']}”，哪些差异能由记录支持，哪些问题仍需更多证据？", f"Around “{focus_ref['labels']['en']},” which differences are supported by records, and which still need more evidence?"),
        "equivalent_paths": {
            "image": _bi("有批准图像时，可在文字卡与结构细节区域之间切换。", "When an approved image exists, move between the text card and structural detail regions."),
            "no_image": _bi("无批准图像时，使用完整元数据、证据、来源和同等反思问题。", "Without an approved image, use complete metadata, evidence, sources, and the same reflection question."),
        },
        "source_ids": sorted({value for artwork in selected for value in artwork["source_ids"]}),
        "disclaimer": _bi("这是固定策展观察导览，不是自动推荐或关系路径。", "This is a fixed curatorial observation tour, not an automatic recommendation or relationship path."),
        "fixed_curatorial": True,
        "algorithmic": False,
        "share_path": "/art/tours/" + quote("tour:artist-" + artist["id"].split(":", 1)[1], safe=""),
    }


def _thematic_tour(slug: str, title: dict[str, str], artwork_ids: list[str], artworks: dict[str, dict[str, Any]], artists: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = [artworks[value] for value in artwork_ids]
    artist_ids = sorted({item["artist_id"] for item in selected})
    context_ids = sorted({context["id"] for item in selected for key in ("materials", "techniques", "subjects") for context in item.get(key, [])})
    metadata_only = sorted(item["id"] for item in selected if item["media"]["decision"] != "approved_self_hosted")
    return {
        "id": f"tour:theme-{slug}",
        "kind": "thematic",
        "title": title,
        "summary": _bi("沿经审核的材料、技法与题材记录并置作品；每一步保留差异与来源边界。", "Place works side by side through reviewed material, technique, and subject records while preserving differences and source boundaries."),
        "artist_ids": artist_ids,
        "artwork_ids": artwork_ids,
        "context_ids": context_ids,
        "period_labels": [
            _localized_registry_label(value, PERIOD_TRANSLATIONS)
            for value in sorted({period for artist_id in artist_ids for period in artists[artist_id]["historical_periods"]})
        ],
        "region_labels": [
            _localized_registry_label(value, PLACE_TRANSLATIONS)
            for value in sorted({place["label"] for artist_id in artist_ids for place in artists[artist_id]["activity_places"]})
        ],
        "source_ids": sorted({value for item in selected for value in item["source_ids"]}),
        "metadata_only_artwork_ids": metadata_only,
        "noncausal_statement": _bi("共同材料、技法或题材只支持固定策展比较，不表示接触、影响、传播、师承或因果。", "Shared material, technique, or subject supports only this fixed curatorial comparison; it does not imply contact, influence, transmission, instruction, or causality."),
        "fixed_curatorial": True,
        "pathfinding": False,
        "automatic_recommendation": False,
        "share_path": "/art/tours/" + quote(f"tour:theme-{slug}", safe=""),
    }


def _lens(
    kind: str,
    contexts: list[dict[str, Any]],
    artworks: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    labels = {
        "material": (_bi("材料透镜", "Material lens"), _bi("只使用馆藏记录中的材料字段，不推断未记录的工艺细节。", "Uses only material fields in collection records and does not infer unrecorded process details.")),
        "technique": (_bi("技法透镜", "Technique lens"), _bi("提供经审核的简明说明，不构成操作教程。", "Offers concise reviewed context and is not an instructional tutorial.")),
        "subject": (_bi("题材透镜", "Subject lens"), _bi("共同题材可供跨时空比较，但不等于影响。", "A shared subject can support comparison across time and place, but does not equal influence.")),
    }
    key = {"material": "materials", "technique": "techniques", "subject": "subjects"}[kind]
    entries = []
    for context in (item for item in contexts if item["context_type"] == kind):
        related = sorted(artwork["id"] for artwork in artworks if any(value["id"] == context["id"] for value in artwork.get(key, [])))
        if not related:
            continue
        evidence_ids = sorted({
            evidence_id
            for claim in claims
            if claim.get("object", {}).get("entity_id") == context["id"] and claim.get("subject_id") in related
            for evidence_id in claim.get("evidence_ids", [])
        })
        entries.append({
            "context_id": context["id"],
            "label": deepcopy(context["labels"]),
            "definition": deepcopy(context["definition"]),
            "artwork_ids": related,
            "evidence_ids": evidence_ids,
            "source_ids": sorted(context["source_ids"]),
            "source_links": [
                {"source_id": source_id, "label": source_by_id[source_id]["locator"]["label"], "url": source_by_id[source_id]["locator"]["url"]}
                for source_id in sorted(context["source_ids"])
            ],
        })
    return {"id": f"lens:{kind}", "type": kind, "title": labels[kind][0], "boundary": labels[kind][1], "entries": entries}


def _compare_prompts() -> list[dict[str, Any]]:
    prompts = {
        "material": _bi("比较记录中的材料与支撑物：哪些相同，哪些不同？", "Compare recorded materials and supports: what is shared and what differs?"),
        "technique": _bi("比较经审核的技法字段，不把差异写成优劣。", "Compare reviewed technique fields without turning differences into rank."),
        "subject": _bi("比较共同或不同题材，同时保留时间、地点与来源边界。", "Compare shared or different subjects while preserving time, place, and source boundaries."),
    }
    boundary = _bi("并置不产生相似度分数，也不判断影响、最佳对比或艺术价值。", "Juxtaposition creates no similarity score and makes no judgment of influence, best match, or artistic value.")
    return [{"id": f"compare-prompt:{kind}", "lens": kind, "prompt": prompts[kind], "boundary": boundary} for kind in ("material", "technique", "subject")]


def _localized_creation_date(creation: dict[str, Any]) -> dict[str, str]:
    start = creation.get("start")
    end = creation.get("end")
    if start and end:
        if start == end:
            zh = f"{'约' if creation.get('uncertain') else ''}{start}年"
        else:
            zh = f"{'约' if creation.get('uncertain') else ''}{start}—{end}年"
    else:
        zh = "正式馆藏记录未提供可显示年代。"
    return _bi(zh, creation.get("description") or "The formal collection record does not provide a display date.")


def _localized_registry_label(value: str, translations: dict[str, str]) -> dict[str, str]:
    if value not in translations:
        raise ValueError(f"Missing deterministic Chinese label for reviewed registry value: {value}")
    return _bi(translations[value], value)


def _tour_step(sequence: int, artwork: dict[str, Any]) -> dict[str, Any]:
    groups = (
        ("materials", "材料", "material"),
        ("techniques", "技法", "technique"),
        ("subjects", "题材", "subject"),
    )
    preferred = groups[(sequence - 1) % len(groups)]
    available = next((group for group in (preferred, *groups) if artwork.get(group[0])), preferred)
    value = artwork.get(available[0], [{}])[0].get("labels", _bi("正式记录", "the formal record"))
    if sequence == 1:
        zh = f"先核对作品记录，并以“{value['zh-Hans']}”这一{available[1]}字段建立观察基准。"
        en = f"Begin with the object record and use the {available[2]} field “{value['en']}” as an observation baseline."
    elif sequence == 2:
        zh = f"再转向“{value['zh-Hans']}”，比较它与前一件作品记录中的相同或不同字段。"
        en = f"Move to “{value['en']}” and compare that field with the preceding object record."
    elif sequence == 3:
        zh = f"第三步以“{value['zh-Hans']}”检验共同字段是否仍保留作品差异。"
        en = f"Use “{value['en']}” to test whether a shared field still preserves differences between works."
    else:
        zh = f"最后从“{value['zh-Hans']}”返回证据与来源，确认导览没有越过记录边界。"
        en = f"Finally, return from “{value['en']}” to evidence and sources to confirm the tour stays within record boundaries."
    return {"sequence": sequence, "artwork_id": artwork["id"], "reason": _bi(zh, en)}


def _copy_predecessor(staged: Path) -> None:
    staged.mkdir(parents=True)
    for source in INPUT_RELEASE.rglob("*"):
        if not source.is_file() or source.name == "manifest.json":
            continue
        relative = source.relative_to(INPUT_RELEASE)
        destination = staged / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _build_manifest(staged: Path) -> dict[str, Any]:
    old = _load_json(INPUT_RELEASE / "manifest.json")
    old_files = deepcopy(old["manifest_files"])
    interaction_path = staged / "interaction-index.json"
    interaction_entry = {
        "bytes": interaction_path.stat().st_size,
        "path": "interaction-index.json",
        "record_ids": ["interaction-index:museum-05b-v1"],
        "record_type": "other",
        "schema_path": "schemas/art/release/art-gallery-interaction-index.schema.json",
        "sha256": sha256_file(interaction_path, prefixed=False),
    }
    retry_path = staged / "media-retry.json"
    retry_entry = {
        "bytes": retry_path.stat().st_size,
        "path": "media-retry.json",
        "record_ids": ["media-retry:museum-05b-no-image-v1"],
        "record_type": "other",
        "schema_path": "schemas/art/media/media-retry.schema.json",
        "sha256": sha256_file(retry_path, prefixed=False),
    }
    files = sorted([*old_files, interaction_entry, retry_entry], key=lambda item: item["path"])
    manifest = deepcopy(old)
    manifest.update({
        "id": RELEASE_ID,
        "version": RELEASE_VERSION,
        "build_version": "museum-05b-v1",
        "created_at": GENERATED_AT,
        "predecessor": INPUT_RELEASE_ID,
        "manifest_files": files,
        "content_hash": release_content_hash(files),
        "release_notes": "Versioned static interaction release: 44 evidence-bound observation cards, 12 artist tours, six fixed thematic tours, eight visual hero paths with structural detail navigation, four textual hero paths, three reviewed lenses, mixed-media compare, and print/share configuration. All predecessor data and media bytes are unchanged; no pathfinding, causal relation, algorithmic similarity, analytics, or external runtime media is added.",
    })
    manifest["schema_versions"] = {
        **old["schema_versions"],
        "art/media/media-retry": "1.0.0",
        "art/release/art-gallery-interaction-index": "1.0.0",
    }
    return manifest


def _validate_predecessor_bytes(release_root: Path, old_manifest: dict[str, Any], manifest: dict[str, Any], failures: list[dict[str, str]]) -> None:
    new_by_path = {item.get("path"): item for item in manifest.get("manifest_files", [])}
    for old_item in old_manifest.get("manifest_files", []):
        path = old_item["path"]
        if new_by_path.get(path) != old_item:
            _fail(failures, "predecessor_manifest_drift", f"Predecessor manifest entry changed: {path}", path)
            continue
        source = INPUT_RELEASE / path
        target = release_root / path
        if not target.is_file() or source.read_bytes() != target.read_bytes():
            _fail(failures, "predecessor_bytes_drift", f"Predecessor bytes changed: {path}", path)
    extras = set(new_by_path) - {item["path"] for item in old_manifest["manifest_files"]}
    if extras != {"interaction-index.json", "media-retry.json"}:
        _fail(failures, "overlay_file_set", f"Expected the two declared overlay files beyond predecessor, got {sorted(extras)}")
    expected_overlay_entries = {
        "interaction-index.json": ("other", "schemas/art/release/art-gallery-interaction-index.schema.json", ["interaction-index:museum-05b-v1"]),
        "media-retry.json": ("other", "schemas/art/media/media-retry.schema.json", ["media-retry:museum-05b-no-image-v1"]),
    }
    for path, (record_type, schema_path, record_ids) in expected_overlay_entries.items():
        entry = new_by_path.get(path, {})
        if entry.get("record_type") != record_type or entry.get("schema_path") != schema_path or entry.get("record_ids") != record_ids:
            _fail(failures, "overlay_typed_identity", f"Overlay file lacks its exact typed record identity: {path}", path)


def _validate_interaction_schema(index: dict[str, Any]) -> None:
    issues = validate_record(
        index,
        requested_schema="schemas/art/release/art-gallery-interaction-index.schema.json",
    )
    if issues:
        issue = issues[0]
        raise ValueError(f"{issue.location}: {issue.message}")


def _validate_index_semantics(release_root: Path, index: dict[str, Any], failures: list[dict[str, str]]) -> None:
    try:
        artworks = _load_json(release_root / "artworks.json")["artworks"]
        artists = _load_json(release_root / "artists.json")["artists"]
        contexts = _load_json(release_root / "contexts.json")["contexts"]
        claims = _load_json(release_root / "claims.json")["claims"]
        evidence = _load_json(release_root / "evidence.json")["evidence"]
        sources = _load_json(release_root / "sources.json")["sources"]
        media = _load_json(release_root / "media-index.json")
        retry = _load_json(release_root / "media-retry.json")
    except (OSError, KeyError, json.JSONDecodeError) as error:
        _fail(failures, "core_read", str(error))
        return

    artwork_by_id = {item["id"]: item for item in artworks}
    artist_by_id = {item["id"]: item for item in artists}
    context_by_id = {item["id"]: item for item in contexts}
    evidence_by_id = {item["id"]: item for item in evidence}
    source_by_id = {item["id"]: item for item in sources}
    source_ids = set(source_by_id)
    artwork_ids = set(artwork_by_id)
    artist_ids = set(artist_by_id)
    context_ids = set(context_by_id)
    evidence_ids = set(evidence_by_id)
    media_decisions = {item["artwork_id"]: item["decision"] for item in media["artworks"]}
    media_assets = {item["id"]: item for item in media["assets"]}
    no_image_ids = {artwork_id for artwork_id, decision in media_decisions.items() if decision != "approved_self_hosted"}

    expected_composition = {
        "mode": "immutable_overlay",
        "base_release_id": INPUT_RELEASE_ID,
        "base_release_hash": INPUT_RELEASE_HASH,
        "base_artifact_identity": "base_release_scoped",
        "inherited_manifest_file_count": len(_load_json(INPUT_RELEASE / "manifest.json")["manifest_files"]),
        "overlay_files": ["interaction-index.json", "media-retry.json"],
    }
    if index.get("release_composition") != expected_composition:
        _fail(failures, "overlay_contract", "Interaction release composition does not exactly bind the immutable predecessor overlay")

    cards = index.get("observation_cards", [])
    card_artwork_ids = [item.get("artwork_id") for item in cards]
    card_ids = [item.get("id") for item in cards]
    if len(cards) != 44 or set(card_artwork_ids) != artwork_ids or len(set(card_ids)) != len(card_ids):
        _fail(failures, "observation_card_closure", "Observation cards must cover exactly all 44 artworks")
    visual_words = ("线条", "明暗", "构图", "眼睛", "人物", "shape", "line", "light", "composition", "eye", "figure")
    claims_by_artwork: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        claims_by_artwork.setdefault(claim.get("subject_id", ""), []).append(claim)
    for card in cards:
        artwork_id = card.get("artwork_id")
        if artwork_id not in artwork_by_id:
            continue
        artwork = artwork_by_id[artwork_id]
        linked_evidence = sorted({value for claim in claims_by_artwork.get(artwork_id, []) for value in claim.get("evidence_ids", [])})
        linked_sources = sorted({value for value in linked_evidence for value in evidence_by_id.get(value, {}).get("source_ids", [])}) or sorted(artwork["source_ids"])
        if card.get("evidence_ids") != linked_evidence or not set(linked_evidence) <= evidence_ids:
            _fail(failures, "observation_evidence_reference", f"Observation evidence does not close exactly: {artwork_id}")
        if card.get("source_ids") != linked_sources or not set(linked_sources) <= source_ids:
            _fail(failures, "observation_source_reference", f"Observation sources do not close exactly: {artwork_id}")
        expected_source_links = [
            {"source_id": source_id, "label": source_by_id[source_id]["locator"]["label"], "url": source_by_id[source_id]["locator"]["url"]}
            for source_id in linked_sources
            if source_id in source_by_id
        ]
        if card.get("source_links") != expected_source_links:
            _fail(failures, "observation_source_link", f"Observation source links do not close exactly: {artwork_id}")
        expected_contexts = {
            "materials": [item["id"] for item in artwork.get("materials", [])],
            "techniques": [item["id"] for item in artwork.get("techniques", [])],
            "subjects": [item["id"] for item in artwork.get("subjects", [])],
        }
        actual_contexts = {key: [item.get("id") for item in card.get("contexts", {}).get(key, [])] for key in expected_contexts}
        if actual_contexts != expected_contexts:
            _fail(failures, "observation_context_reference", f"Observation contexts do not match the artwork: {artwork_id}")
        decision = media_decisions.get(artwork_id)
        expected_availability = "approved_image" if decision == "approved_self_hosted" else "metadata_only"
        if card.get("rights_status") != decision or card.get("image_availability") != expected_availability:
            _fail(failures, "observation_rights_state", f"Observation rights/image state differs from media closure: {artwork_id}")
        if artwork_id in no_image_ids:
            if card.get("image_availability") != "metadata_only" or card.get("accessibility_version", {}).get("mode") != "evidence_only":
                _fail(failures, "metadata_only_mode", f"No-image card exposes a visual mode: {artwork_id}")
            observation_text = " ".join(
                value
                for group in (card.get("prompts", []), card.get("directly_observable", []))
                for entry in group
                for value in entry.values()
            ).lower()
            if any(word in observation_text for word in visual_words):
                _fail(failures, "metadata_only_visual_prompt", f"No-image card assigns a visual-detail prompt: {artwork_id}")

    heroes = index.get("hero_selections", [])
    hero_ids = [item.get("id") for item in heroes]
    hero_artist_ids = [item.get("artist_id") for item in heroes]
    if len(heroes) != 12 or set(hero_artist_ids) != artist_ids or len(set(hero_ids)) != len(hero_ids):
        _fail(failures, "hero_closure", "Hero selections must cover exactly all 12 artists")
    region_rows = index.get("detail_regions", [])
    region_ids = [item.get("id") for item in region_rows]
    region_by_id = {item["id"]: item for item in region_rows if isinstance(item.get("id"), str)}
    if len(region_by_id) != len(region_ids):
        _fail(failures, "detail_id_uniqueness", "Detail region IDs must be unique")
    referenced_regions: set[str] = set()
    hero_by_id = {item["id"]: item for item in heroes if isinstance(item.get("id"), str)}
    for hero in heroes:
        artwork_id = hero.get("artwork_id")
        artist_id = hero.get("artist_id")
        if artwork_id not in artwork_by_id or artwork_by_id[artwork_id]["artist_id"] != artist_id:
            _fail(failures, "hero_reference", f"Hero artist/artwork reference does not close: {hero.get('id')}")
        decision = media_decisions.get(artwork_id)
        if hero["status"] == "textual_observation_path" and (decision == "approved_self_hosted" or hero["source_asset"] is not None or hero["detail_region_ids"]):
            _fail(failures, "textual_hero_media", f"Textual hero exposes media: {hero['id']}")
        if hero["status"] == "visual_detail_path":
            source_asset = hero.get("source_asset")
            media_asset = media_assets.get(source_asset.get("media_id")) if isinstance(source_asset, dict) else None
            expected_asset = None if media_asset is None else {
                "media_id": media_asset["id"], "path": media_asset["src"], "sha256": media_asset["sha256"],
                "width": media_asset["width"], "height": media_asset["height"],
            }
            if decision != "approved_self_hosted" or source_asset != expected_asset or not 1 <= len(hero["detail_region_ids"]) <= 3:
                _fail(failures, "visual_hero_media", f"Visual hero is not bound to its approved artwork media: {hero['id']}")
        for region_id in hero["detail_region_ids"]:
            referenced_regions.add(region_id)
            if region_id not in region_by_id:
                _fail(failures, "detail_reference", f"Missing detail region: {region_id}")
                continue
            region = region_by_id[region_id]
            if region.get("hero_id") != hero.get("id") or region.get("artwork_id") != artwork_id or region.get("source_asset") != hero.get("source_asset"):
                _fail(failures, "detail_owner_reference", f"Detail region crosses hero, artwork, or media ownership: {region_id}")
    if referenced_regions != set(region_by_id):
        _fail(failures, "detail_reference_closure", "Every detail region must be referenced by exactly one hero")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for region in region_by_id.values():
        grouped.setdefault(region["hero_id"], []).append(region)
        asset = region["source_asset"]
        path = release_root / asset["path"]
        if not path.is_file() or sha256_file(path) != asset["sha256"]:
            _fail(failures, "detail_source_hash", f"Detail region source hash mismatch: {region['id']}")
            continue
        rect = region["rect"]
        if rect["x"] < 0 or rect["y"] < 0 or rect["x"] + rect["width"] > asset["width"] or rect["y"] + rect["height"] > asset["height"]:
            _fail(failures, "detail_bounds", f"Detail region exceeds source bounds: {region['id']}")
        normalized = region["normalized_rect"]
        expected_normalized = {
            "x": rect["x"] / asset["width"], "y": rect["y"] / asset["height"],
            "width": rect["width"] / asset["width"], "height": rect["height"] / asset["height"],
        }
        if any(abs(normalized[key] - expected_normalized[key]) > 1e-7 for key in expected_normalized):
            _fail(failures, "detail_normalized_rect", f"Detail pixel and normalized coordinates disagree: {region['id']}")
        algorithm = region["algorithm"]
        margin_x = asset["width"] * algorithm["border_exclusion_ratio"]
        margin_y = asset["height"] * algorithm["border_exclusion_ratio"]
        area_ratio = rect["width"] * rect["height"] / (asset["width"] * asset["height"])
        if rect["x"] + 0.5 < margin_x or rect["y"] + 0.5 < margin_y or rect["x"] + rect["width"] - 0.5 > asset["width"] - margin_x or rect["y"] + rect["height"] - 0.5 > asset["height"] - margin_y:
            _fail(failures, "detail_border", f"Detail region violates border exclusion: {region['id']}")
        if area_ratio + 1e-9 < algorithm["minimum_area_ratio"]:
            _fail(failures, "detail_area", f"Detail region is below its minimum area: {region['id']}")
        metrics = region["metrics"]
        if metrics["edge_density"] <= 0.005 or metrics["local_contrast"] <= 0.005 or metrics["entropy"] <= 0.1:
            _fail(failures, "detail_background", f"Detail region lacks structural information: {region['id']}")
        if region["semantic_label"] is not None or algorithm["input_release_hash"] != INPUT_RELEASE_HASH:
            _fail(failures, "detail_semantics", f"Detail region has semantic content or stale input hash: {region['id']}")
    for hero_id, regions in grouped.items():
        hero = hero_by_id.get(hero_id)
        expected_labels = {
            region_id: {"zh-Hans": f"细节区域 {position}", "en": f"Detail region {position}"}
            for position, region_id in enumerate(hero.get("detail_region_ids", []) if hero else [], start=1)
        }
        for region in regions:
            if region.get("label") != expected_labels.get(region["id"]):
                _fail(failures, "detail_label", f"Detail region label must remain nonsemantic and ordered: {region['id']}")
        boxes = [(item["rect"]["x"], item["rect"]["y"], item["rect"]["x"] + item["rect"]["width"], item["rect"]["y"] + item["rect"]["height"]) for item in regions]
        for left_index, left in enumerate(boxes):
            for right in boxes[left_index + 1:]:
                if _iou(left, right) > 0.25 + 1e-9:
                    _fail(failures, "detail_overlap", f"Detail regions overlap above threshold: {hero_id}")
    artist_tours = index.get("artist_tours", [])
    expected_artist_tour_ids = {"tour:artist-" + value.split(":", 1)[1] for value in artist_ids}
    if len(artist_tours) != 12 or {tour.get("id") for tour in artist_tours} != expected_artist_tour_ids:
        _fail(failures, "artist_tour_closure", "Artist tours must be unique and cover all 12 artists")
    for tour in artist_tours:
        artist = artist_by_id.get(tour.get("artist_id"))
        step_ids = [item.get("artwork_id") for item in tour.get("artwork_steps", [])]
        if artist is None or any(value not in artist["artwork_ids"] for value in step_ids) or len(set(step_ids)) != len(step_ids):
            _fail(failures, "artist_tour_artworks", f"Artist tour steps do not close to one artist: {tour.get('id')}")
            continue
        if [item.get("sequence") for item in tour["artwork_steps"]] != list(range(1, len(step_ids) + 1)):
            _fail(failures, "artist_tour_sequence", f"Artist tour sequence is not contiguous: {tour['id']}")
        context_id = tour.get("focus", {}).get("context_id")
        linked_contexts = {item["id"] for artwork_id in step_ids for key in ("materials", "techniques", "subjects") for item in artwork_by_id[artwork_id].get(key, [])}
        if context_id not in linked_contexts or context_id not in context_by_id or tour["focus"].get("type") != context_by_id[context_id]["context_type"]:
            _fail(failures, "artist_tour_context", f"Artist tour focus is not supported by its works: {tour['id']}")
        expected_sources = sorted({value for artwork_id in step_ids for value in artwork_by_id[artwork_id]["source_ids"]})
        if tour.get("source_ids") != expected_sources or not set(expected_sources) <= source_ids:
            _fail(failures, "artist_tour_sources", f"Artist tour sources do not close: {tour['id']}")

    thematic_tours = index.get("thematic_tours", [])
    expected_theme_ids = {f"tour:theme-{slug}" for slug, _, _ in THEMATIC_TOURS}
    if len(thematic_tours) != 6 or {tour.get("id") for tour in thematic_tours} != expected_theme_ids:
        _fail(failures, "thematic_tour_closure", "Thematic tours must be the six unique reviewed fixed tours")
    for tour in thematic_tours:
        ids = tour.get("artwork_ids", [])
        if not set(ids) <= artwork_ids:
            _fail(failures, "tour_artwork_reference", f"Tour contains unknown artworks: {tour.get('id')}")
            continue
        expected_artists = sorted({artwork_by_id[value]["artist_id"] for value in ids})
        expected_contexts = sorted({context["id"] for value in ids for key in ("materials", "techniques", "subjects") for context in artwork_by_id[value].get(key, [])})
        expected_sources = sorted({source for value in ids for source in artwork_by_id[value]["source_ids"]})
        expected_metadata_only = sorted(value for value in ids if value in no_image_ids)
        if tour.get("artist_ids") != expected_artists or tour.get("context_ids") != expected_contexts or tour.get("source_ids") != expected_sources or tour.get("metadata_only_artwork_ids") != expected_metadata_only:
            _fail(failures, "thematic_reference_closure", f"Thematic tour derived references do not close: {tour['id']}")
        if not expected_metadata_only or len(tour.get("period_labels", [])) < 2 or len(tour.get("region_labels", [])) < 2:
            _fail(failures, "thematic_equivalence", f"Thematic tour lacks a cross-context metadata path: {tour['id']}")

    lenses = index.get("lenses", [])
    if len(lenses) != 3 or {item.get("id") for item in lenses} != {"lens:material", "lens:technique", "lens:subject"}:
        _fail(failures, "lens_closure", "Lenses must contain one unique material, technique, and subject lens")
    for lens in lenses:
        for entry in lens["entries"]:
            context = context_by_id.get(entry["context_id"])
            if context is None or context["context_type"] != lens["type"]:
                _fail(failures, "lens_reference", f"Lens reference is not closed: {entry['context_id']}")
                continue
            key = {"material": "materials", "technique": "techniques", "subject": "subjects"}[lens["type"]]
            related = sorted(artwork["id"] for artwork in artworks if any(item["id"] == context["id"] for item in artwork.get(key, [])))
            linked_evidence = sorted({evidence_id for claim in claims if claim.get("object", {}).get("entity_id") == context["id"] and claim.get("subject_id") in related for evidence_id in claim.get("evidence_ids", [])})
            expected_source_links = [
                {"source_id": source_id, "label": source_by_id[source_id]["locator"]["label"], "url": source_by_id[source_id]["locator"]["url"]}
                for source_id in sorted(context["source_ids"])
            ]
            if entry.get("artwork_ids") != related or entry.get("evidence_ids") != linked_evidence or entry.get("source_ids") != sorted(context["source_ids"]) or entry.get("source_links") != expected_source_links:
                _fail(failures, "lens_derived_reference", f"Lens works, evidence, or sources do not close: {entry['context_id']}")

    if sum(value == "approved_self_hosted" for value in media_decisions.values()) != 31 or sum(value != "approved_self_hosted" for value in media_decisions.values()) != 13:
        _fail(failures, "media_counts", "Media closure is not 31 approved / 13 no-image")
    expected_counts = {
        "artists": len(artists), "artworks": len(artworks),
        "approved_media_artworks": sum(value == "approved_self_hosted" for value in media_decisions.values()),
        "no_image_artworks": len(no_image_ids), "observation_cards": len(cards),
        "hero_selections": len(heroes), "visual_heroes": sum(item.get("status") == "visual_detail_path" for item in heroes),
        "textual_observation_paths": sum(item.get("status") == "textual_observation_path" for item in heroes),
        "detail_regions": len(region_rows), "artist_tours": len(artist_tours),
        "thematic_tours": len(thematic_tours), "lenses": len(lenses),
    }
    if index.get("counts") != expected_counts:
        _fail(failures, "count_closure", "Declared interaction counts do not equal the physical records")

    compare_prompts = index.get("compare_prompts", [])
    if len(compare_prompts) != 3 or {item.get("id") for item in compare_prompts} != {"compare-prompt:material", "compare-prompt:technique", "compare-prompt:subject"}:
        _fail(failures, "compare_prompt_closure", "Compare prompts must cover the three unique formal lenses")
    all_text = json.dumps(index, ensure_ascii=False).lower()
    forbidden = (
        "相似度分数：", "最佳对比：", "bfs", "yen alternatives", "pathfinding\": true", "automatic_recommendation\": true",
        "明显影响了", "显然影响了", "借鉴自", "clearly influenced", "obviously influenced", "was influenced by",
    )
    if any(value in all_text for value in forbidden):
        _fail(failures, "causal_algorithmic_wording", "Interaction index contains forbidden causal, algorithmic, or ranking wording")
    interaction_gzip = len(gzip.compress(canonical_json_bytes(index)))
    regions_gzip = len(gzip.compress(canonical_json_bytes(index.get("detail_regions", []))))
    if interaction_gzip > 122880:
        _fail(failures, "interaction_budget", f"Interaction JSON gzip {interaction_gzip} exceeds 122880")
    if regions_gzip > 30720:
        _fail(failures, "detail_budget", f"Detail region gzip {regions_gzip} exceeds 30720")
    retry_hash = _validate_retry_semantics(retry, no_image_ids, media_decisions, failures)
    retry_summary = index.get("media_retry_summary", {})
    if retry_summary.get("artifact_path") != "media-retry.json" or retry_summary.get("artifact_hash") != retry_hash or retry.get("human_review_dependency") is not False:
        _fail(failures, "retry_closure", "Media retry artifact hash or human-review boundary does not close")


def _validate_retry_semantics(
    retry: dict[str, Any],
    no_image_ids: set[str],
    media_decisions: dict[str, str],
    failures: list[dict[str, str]],
) -> str:
    retry_issues = validate_record(retry, requested_schema="schemas/art/media/media-retry.schema.json")
    if retry_issues:
        _fail(failures, "retry_schema", retry_issues[0].message, retry_issues[0].location)
    retry_hash = canonical_sha256({key: value for key, value in retry.items() if key != "content_hash"})
    result_artwork_ids = [item.get("artwork_id") for item in retry.get("results", [])]
    result_ids = [item.get("id") for item in retry.get("results", [])]
    if retry.get("content_hash") != retry_hash or len(set(result_artwork_ids)) != 13 or set(result_artwork_ids) != no_image_ids or len(set(result_ids)) != 13:
        _fail(failures, "retry_record_closure", "Media retry must hash and cover the exact 13 unique no-image artworks")
    for result in retry.get("results", []):
        artwork_id = result.get("artwork_id")
        expected_id = "media-retry:" + artwork_id.split(":", 1)[1] if isinstance(artwork_id, str) and ":" in artwork_id else None
        if result.get("id") != expected_id or result.get("prior_decision") != media_decisions.get(artwork_id) or result.get("final_decision") != result.get("prior_decision"):
            _fail(failures, "retry_decision_closure", f"Media retry decision or identity drifted: {artwork_id}")
    return retry_hash


def _install_immutable(staged: Path, output: Path) -> None:
    if output.exists():
        if not output.is_dir() or output.is_symlink():
            raise ValueError(f"Refusing non-directory release path: {output}")
        staged_files = {path.relative_to(staged).as_posix(): sha256_file(path) for path in staged.rglob("*") if path.is_file()}
        output_files = {path.relative_to(output).as_posix(): sha256_file(path) for path in output.rglob("*") if path.is_file()}
        if staged_files == output_files:
            return
        raise ValueError(f"Refusing to overwrite immutable release: {output}")
    shutil.move(str(staged), str(output))


def _iou(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    intersection_width = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    intersection_height = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / max(1, left_area + right_area - intersection)


def _stable_detail_metric(value: float) -> float:
    return math.floor(value * DETAIL_METRIC_SCALE + 1e-12) / DETAIL_METRIC_SCALE


def _context_link(value: dict[str, Any]) -> dict[str, Any]:
    return {"id": value["id"], "label": deepcopy(value["labels"])}


def _review() -> dict[str, Any]:
    return {"status": "automated_pass", "reviewer_kind": "automated_release_validation_pipeline", "reviewed_at": REVIEWED_AT, "human_review_dependency": False}


def _bi(zh: str, en: str) -> dict[str, str]:
    return {"zh-Hans": zh, "en": en}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _fail(failures: list[dict[str, str]], code: str, message: str, path: str = "$") -> None:
    failures.append({"code": code, "message": message, "path": path})


def _result(root: Path, failures: list[dict[str, str]], counts: dict[str, Any], content_hash: str | None = None) -> dict[str, Any]:
    return {
        "ok": not failures,
        "phase_id": PHASE_ID,
        "release_id": RELEASE_ID,
        "release_root": root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else str(root),
        "content_hash": content_hash,
        "counts": counts,
        "codes": sorted({item["code"] for item in failures}),
        "failures": failures,
    }
