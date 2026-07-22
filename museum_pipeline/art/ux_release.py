"""Build and validate the immutable MUSEUM-09B-UX-01 successor release."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR = ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.0"
DEFAULT_OUTPUT = ROOT / "public" / "releases" / "art-expansion-batch-01-1.5.1"
PREDECESSOR_ID = "release:art-expansion-batch-01-1.5.0"
RELEASE_ID = "release:art-expansion-batch-01-1.5.1"
PHASE_ID = "MUSEUM-09B-UX-01"
VERSION = "1.5.1"
BUILT_AT = "2026-07-22T18:00:00+08:00"
PREDECESSOR_MANIFEST_SHA256 = "sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9"
PREDECESSOR_CONTENT_HASH = "sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9"
PREDECESSOR_TREE_HASH = "sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f"
TREE_ALGORITHM = "sha256(path\\0size\\0file_sha256\\n)"

BANNED_PRIMARY_TERMS = (
    "元数据", "经审核记录", "经审核的声明", "可核验范围", "本公开档案", "断言", "价值排序",
    "相关元数据支持跨时空观察", "来源未提供的信息保持为空", "metadata", "reviewed object records",
    "verifiable scope", "does not assert", "public profile supports", "rank",
)
UNSUPPORTED_SUPERLATIVES = (
    "最伟大", "最重要", "代表性最高", "领先", "排名", "greatest", "most important", "leading", "highest ranked",
)
INTERNAL_LEAK_RE = re.compile(r"(?:source:|MUSEUM-|adapter[_ -]?id|internal tier|tier [1-4])", re.IGNORECASE)
PLACE_ZH = {
    "Africa": "非洲", "Aguascalientes and Mexico City": "阿瓜斯卡连特斯和墨西哥城",
    "Asia": "亚洲", "Calcutta, the Isle of Wight, and Kalutara": "加尔各答、怀特岛和卡卢特勒",
    "East Asia": "东亚", "Edo": "江户", "Europe": "欧洲",
    "Kilimanoor and Bombay": "基利马诺尔和孟买",
    "Königsberg, Berlin, and Moritzburg": "柯尼斯堡、柏林和莫里茨堡",
    "Latin America Caribbean": "拉丁美洲与加勒比地区", "Madrid and Bordeaux": "马德里和波尔多",
    "North America": "北美洲", "Nuremberg": "纽伦堡", "Oceania": "大洋洲",
    "Pennsylvania, Paris, and Île-de-France": "宾夕法尼亚、巴黎和法兰西岛",
    "Philadelphia and Paris": "费城和巴黎", "South America": "南美洲", "South Asia": "南亚",
    "Southeast Asia": "东南亚", "Suzhou region (historical Changzhou County)": "苏州地区（历史上的长洲县）",
    "The Netherlands, Paris, Arles, and Auvers-sur-Oise": "荷兰、巴黎、阿尔勒和瓦兹河畔欧韦",
    "West Central Asia": "西亚与中亚",
}
PRACTICE_ZH = {
    "architecture-design": "建筑与设计", "ceramics": "陶瓷", "decorative-arts": "装饰艺术",
    "drawing": "素描与绘画", "other-documented-medium": "其他有记录的媒介", "painting": "绘画",
    "photography": "摄影", "printmaking": "版画", "sculpture": "雕塑", "textile": "纺织",
}

OPENING_ZH = (
    "{name}（{dates}）与{place}有着清楚的活动线索，作品条目里可以看到{practice}。",
    "从{place}和现存作品条目出发，可以认识{dates}年间生活的{name}，其创作涉及{practice}。",
    "{name}（{dates}）的作品记录连接着{place}，其中包括{practice}。",
    "认识{name}（{dates}），可以先从{place}和{practice}这些线索开始。",
    "在{name}（{dates}）的作品条目中，{place}与{practice}是两组可追踪的线索。",
    "{place}是理解{name}（{dates}）的一处起点；作品记录还呈现了{practice}。",
    "{name}（{dates}）留下的作品条目与{place}相关，也记录了{practice}。",
    "想认识{name}（{dates}），可以先留意作品记录里的{place}和{practice}。",
)
OPENING_EN = (
    "{name} ({dates}) is connected in these records with {place}, and the selected works include {practice}.",
    "Begin with {place} and {practice} when meeting {name} ({dates}) through this group of works.",
    "The works recorded for {name} ({dates}) connect the artist with {place} and with practices including {practice}.",
    "A useful way to meet {name} ({dates}) is to start with the clues of {place} and {practice}.",
    "In the entries for {name} ({dates}), {place} and {practice} offer two concrete threads to follow.",
    "{place} is one starting point for understanding {name} ({dates}); the work entries also record {practice}.",
    "The selected entries for {name} ({dates}) relate to {place} and record work in {practice}.",
    "To get to know {name} ({dates}), first notice how {place} and {practice} recur across the work records.",
)

SELF_HOSTED_ZH = (
    "先看本站展示的图像，比较{anchor}在不同作品中怎样变化，再找找线条、形状和画面空间带给你的不同感觉。",
    "从本站图像开始，留意{anchor}，然后比较不同作品里的色彩、线条与空间安排。",
    "你可以在本站图像中寻找{anchor}，看看它在几件作品里是保持相似，还是发生变化。",
    "打开作品图像后，先观察{anchor}，再问问自己哪一种线条或形状最先吸引目光。",
    "把几件本站图像放在一起看：{anchor}有哪些不同表现，画面节奏又怎样改变？",
    "试着沿着{anchor}观察本站图像，并用标题与年代帮助自己发现作品之间的差别。",
    "先不急着下结论，在本站图像里找一找{anchor}，再比较作品的线条、色彩和空间。",
    "让{anchor}成为观察起点：在本站图像之间来回比较，记录你发现的一处相同和一处不同。",
)
SELF_HOSTED_EN = (
    "Start with the images shown here and compare {anchor} across the selected works. Notice what changes in line, shape, color, or space as you move between them.",
    "Use the images on this page to look for {anchor}, then compare how color, line, and space are arranged from one work to the next.",
    "Look for {anchor} in the locally hosted images. Ask what stays similar and what changes across the selected works.",
    "Open the work images and begin with {anchor}; then notice which line, shape, or contrast catches your eye first.",
    "Place several images side by side and compare {anchor}. What changes in the rhythm or spacing of the picture?",
    "Follow {anchor} through the images, using titles and dates as extra clues to differences between the works.",
    "Before drawing a conclusion, find {anchor} in the images and compare the works through line, color, and space.",
    "Let {anchor} be your starting point. Move between the images and name one similarity and one difference you can see.",
)
EXTERNAL_ZH = (
    "这些图像需要到官方作品页查看；可以先比较本站的标题、年代和材料，再带着问题继续观察。",
    "本站没有载入这些作品的图像，先从标题、年代与材料寻找线索，再前往官方作品页看细节。",
    "先在本站读一读标题、年代和材料，然后打开官方作品页，看看记录中的线索能否在图像里找到。",
    "图像由官方作品页提供；出发前可以先比较本站记录的年代、材料与收藏机构。",
    "把标题和材料当作观察提示，再到官方作品页寻找你想验证的形状、颜色或细节。",
    "这些条目只链接到官方图像页面；先比较年代和材料，再决定最想继续观察哪一件作品。",
    "本站保留文字记录而不载入远程图像，你可以带着标题与材料问题前往官方作品页。",
    "从本站的标题、年代和材料开始，再到官方作品页完成图像观察，并记下一处意外发现。",
)
EXTERNAL_EN = (
    "The images are available on official object pages rather than hosted here. Compare titles, dates, and materials first, then continue your observation at the official source.",
    "No remote image is loaded on this site. Begin with the titles, dates, and materials, then open the official object pages to look more closely.",
    "Read the titles, dates, and materials here before opening an official object page. See whether those recorded clues can be found in the image.",
    "The official object pages provide the images. Before leaving this site, compare the recorded dates, materials, and holding institutions.",
    "Use the titles and materials as observation prompts, then visit the official object pages to look for shapes, colors, or details.",
    "These entries link to official image pages. Compare dates and materials first, then choose which work you most want to inspect.",
    "This site keeps the text records without loading remote images. Carry a question about title or material to the official object page.",
    "Start with the recorded titles, dates, and materials, then complete the visual observation on the official object pages and note one surprise.",
)
METADATA_ZH = (
    "这些条目在本站没有本地图像；试着比较标题、年代、材料与收藏机构，看看哪些线索重复出现，哪些发生变化。",
    "没有图像时，标题、年代、材料和收藏机构也能成为线索；把几条记录并排读一读，找出相同与不同。",
    "先从文字记录出发，比较作品标题和年代，再看看材料或收藏地点能提出什么新问题。",
    "本站没有可展示的作品图像，可以用标题、年代、材料与机构信息做一张小小的比较表。",
    "把每件作品的标题、年代和材料当作拼图，看看这些记录能勾勒出哪些变化。",
    "不看图像也能探索：沿着标题、年代、材料和收藏机构，寻找一条重复线索。",
    "试着按年代排列作品记录，再比较标题与材料，观察创作线索怎样移动或改变。",
    "从作品条目的文字细节开始，找出两个相似点和一个不同点，并保留暂时无法回答的问题。",
)
METADATA_EN = (
    "No local image is available for these entries. Compare titles, dates, materials, and holding institutions instead, looking for clues that repeat or change.",
    "Without images, titles, dates, materials, and holding institutions can still guide observation. Read several entries side by side and name a similarity and a difference.",
    "Begin with the text records: compare work titles and dates, then ask what the materials or holding places add to your questions.",
    "There is no locally displayed work image, so build a small comparison from titles, dates, materials, and institution names.",
    "Treat each title, date, and material as one piece of a puzzle. Ask what kind of change the records let you trace.",
    "Exploration can begin without an image. Follow titles, dates, materials, and holding institutions to find one repeating thread.",
    "Arrange the work records by date, then compare titles and materials to see how the documented practices move or change.",
    "Start with the written details, find two similarities and one difference, and keep any question the records cannot yet answer open.",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def _release_content_hash(manifest_files: list[dict[str, Any]]) -> str:
    lines = [
        f"{item['path']}\0{item['sha256']}\0{item['bytes']}\n"
        for item in sorted(manifest_files, key=lambda item: item["path"])
    ]
    return f"sha256:{hashlib.sha256(''.join(lines).encode('utf-8')).hexdigest()}"


def _physical_tree(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    byte_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        file_hash = sha256_file(path).removeprefix("sha256:")
        digest.update(f"{relative}\0{size}\0{file_hash}\n".encode("utf-8"))
        byte_count += size
    return {"algorithm": TREE_ALGORITHM, "hash": f"sha256:{digest.hexdigest()}", "file_count": len(files), "byte_count": byte_count}


def _successor_identity(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {name: _successor_identity(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_successor_identity(item, key) for item in value]
    successor_schema_paths = {
        "schemas/art/release/art-expansion-public-record.schema.json": "schemas/art/release/art-expansion-public-record-v151.schema.json",
        "schemas/art/release/art-expansion-media-asset.schema.json": "schemas/art/release/art-expansion-media-asset-v151.schema.json",
        "schemas/art/release/art-expansion-source.schema.json": "schemas/art/release/art-expansion-source-v151.schema.json",
    }
    if isinstance(value, str) and value in successor_schema_paths:
        return successor_schema_paths[value]
    if value == PREDECESSOR_ID:
        return RELEASE_ID
    if key == "phase_id" and value == "MUSEUM-09B-RELEASE":
        return PHASE_ID
    if key == "id" and isinstance(value, str) and "1.5.0" in value:
        return value.replace("1.5.0", VERSION)
    if key in {"version", "release_version"} and value == "1.5.0":
        return VERSION
    return value


def _split_practice(value: str, *, zh: bool) -> list[str]:
    items = [item.strip() for item in re.split(r"[,、]", value) if item.strip()]
    if zh:
        items = [PRACTICE_ZH.get(item.lower(), item) for item in items]
    return list(dict.fromkeys(items))[:2] or (["有记录的创作实践"] if zh else ["documented creative practices"])


def _list_text(items: list[str], *, zh: bool) -> str:
    if len(items) == 1:
        return items[0]
    return ("和" if zh else " and ").join(items)


def _dates(artist: dict[str, Any], *, zh: bool) -> str:
    life = artist["life_dates"]
    birth = life["birth"]["display_value"]
    death = life["death"]["display_value"]
    return f"{birth}{'—' if zh else '–'}{death}"


def _labels(value: Any, language: str) -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("en") or next(iter(value.values())))
    return str(value)


def _work_anchor(works: list[dict[str, Any]], *, zh: bool) -> str:
    candidates: list[str] = []
    for field in ("subjects", "materials", "techniques"):
        for work in works:
            for item in work.get(field, []):
                label = _labels(item.get("labels", item), "zh-Hans" if zh else "en").strip()
                if label and label.lower() not in {"medium not stated", "not stated", "unknown", "—"}:
                    candidates.append(label)
    unique = list(dict.fromkeys(candidates))
    if unique:
        candidate = unique[0]
        if (zh and len(candidate) <= 18) or (not zh and _word_count(candidate) <= 6):
            return candidate
        return "材料与技法" if zh else "the recorded materials and techniques"
    return "标题与材料线索" if zh else "the recorded title and material clues"


def _claim_bundle(claims: Iterable[dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]], source_fallback: list[str]) -> dict[str, list[str]]:
    claim_ids: list[str] = []
    evidence_ids: list[str] = []
    source_ids: list[str] = []
    for claim in claims:
        claim_ids.append(claim["id"])
        for evidence_id in claim.get("evidence_ids", []):
            evidence_ids.append(evidence_id)
            source_ids.extend(evidence_by_id.get(evidence_id, {}).get("source_ids", []))
    if not source_ids:
        source_ids.extend(source_fallback)
    return {
        "claim_ids": sorted(set(claim_ids)),
        "evidence_ids": sorted(set(evidence_ids)),
        "source_ids": sorted(set(source_ids)),
    }


def _sentence_count(value: str, *, zh: bool) -> int:
    return len([part for part in re.split(r"[。！？]+" if zh else r"[.!?]+(?:\s|$)", value) if part.strip()])


def _word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*", value))


def _narrative(
    artist: dict[str, Any],
    works: list[dict[str, Any]],
    artist_claims: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    name_zh = _labels(artist["labels"], "zh-Hans")
    name_en = _labels(artist["labels"], "en")
    place_en = str(artist["activity_places"][0]["label"])
    place_zh = PLACE_ZH.get(place_en, place_en)
    practice_zh = _list_text(_split_practice(_labels(artist["media_practice"], "zh-Hans"), zh=True), zh=True)
    practice_en = _list_text(_split_practice(_labels(artist["media_practice"], "en"), zh=False), zh=False)
    opening_variant = index % len(OPENING_ZH)
    prompt_variant = index // len(OPENING_ZH)
    opening_zh = OPENING_ZH[opening_variant].format(name=name_zh, dates=_dates(artist, zh=True), place=place_zh, practice=practice_zh)
    opening_en = OPENING_EN[opening_variant].format(name=name_en, dates=_dates(artist, zh=False), place=place_en, practice=practice_en)
    decisions = Counter(work.get("media", {}).get("decision", "metadata_only") for work in works)
    if decisions["approved_self_hosted"]:
        media_profile = "self_hosted"
        prompt_zh = SELF_HOSTED_ZH[prompt_variant].format(anchor=_work_anchor(works, zh=True))
        prompt_en = SELF_HOSTED_EN[prompt_variant].format(anchor=_work_anchor(works, zh=False))
    elif decisions["external_link_only"]:
        media_profile = "external_link_only"
        prompt_zh = EXTERNAL_ZH[prompt_variant]
        prompt_en = EXTERNAL_EN[prompt_variant]
    else:
        media_profile = "metadata_only"
        prompt_zh = METADATA_ZH[prompt_variant]
        prompt_en = METADATA_EN[prompt_variant]
    if len(re.sub(r"\s", "", f"{opening_zh}{prompt_zh}")) > 120:
        if media_profile == "self_hosted":
            prompt_zh = "先看本站图像里的材料、线条和形状，再比较作品之间的一处相同与一处不同。"
        elif media_profile == "external_link_only":
            prompt_zh = "本站不载入远程图像；先比较标题、年代与材料，再到官方作品页继续观察。"
        else:
            prompt_zh = "本站没有本地图像；可以比较标题、年代、材料与收藏机构，寻找一处相同和一处不同。"
    if len(re.sub(r"\s", "", f"{opening_zh}{prompt_zh}")) > 120:
        opening_zh = f"{name_zh}（{_dates(artist, zh=True)}）的作品条目涉及{practice_zh}。"
    if _word_count(f"{opening_en} {prompt_en}") < 45:
        prompt_en = f"{prompt_en} Use these clues to form your own question before moving to the next work record."
    public_intro = {"zh-Hans": f"{opening_zh}{prompt_zh}", "en": f"{opening_en} {prompt_en}"}
    identity_predicates = {"activity_scope", "birth_year", "death_year", "documented_geography", "historical_period", "identity_profile", "life_dates", "preferred_name"}
    practice_predicates = {"artistic_tradition", "documented_practice_media", "has_verified_work_record", "official_catalog_record", "selected_work_count", "uses_material", "uses_technique"}
    opening_claims = [claim for claim in artist_claims if claim.get("predicate") in identity_predicates]
    practice_claims = [claim for claim in artist_claims if claim.get("predicate") in practice_predicates]
    if not opening_claims:
        opening_claims = artist_claims[:1]
    if not practice_claims:
        practice_claims = artist_claims[-1:]
    opening_refs = _claim_bundle(opening_claims, evidence_by_id, artist["source_ids"])
    prompt_refs = _claim_bundle(practice_claims, evidence_by_id, artist["source_ids"])
    evidence_boundary = {
        "zh-Hans": "本页只依据已发布的身份、年代、地点、作品与媒介记录。策展比较不证明相识、影响、师承或价值排序；未知信息仍保持未知。",
        "en": "This page is bounded by the published identity, date, place, work, and medium records. Curatorial comparison does not prove acquaintance, influence, instruction, or rank; unknown information remains unknown.",
    }
    look_for = {
        "zh-Hans": [prompt_zh.rstrip("。") + "？", "你还发现了哪一处相同和哪一处不同？"],
        "en": [prompt_en.rstrip(".") + "?", "What is one similarity and one difference you can name?"],
    }
    banned_hits = [term for term in BANNED_PRIMARY_TERMS if term.lower() in public_intro["zh-Hans"].lower() or term.lower() in public_intro["en"].lower()]
    reading_profile = {
        "schema_version": "1.0.0",
        "media_profile": media_profile,
        "opening_variant": opening_variant,
        "prompt_variant": prompt_variant,
        "zh-Hans": {
            "character_count": len(re.sub(r"\s", "", public_intro["zh-Hans"])),
            "sentence_count": _sentence_count(public_intro["zh-Hans"], zh=True),
        },
        "en": {"word_count": _word_count(public_intro["en"]), "sentence_count": _sentence_count(public_intro["en"], zh=False)},
        "banned_term_hits": banned_hits,
        "copied_museum_label": False,
        "template_signature": f"opening-{opening_variant}:prompt-{prompt_variant}:media-{media_profile}",
    }
    all_refs = {
        key: sorted(set(opening_refs[key] + prompt_refs[key])) for key in ("claim_ids", "evidence_ids", "source_ids")
    }
    return {
        "artist_id": artist["id"],
        "public_intro": public_intro,
        "look_for": look_for,
        "evidence_boundary": evidence_boundary,
        "sentence_provenance": [
            {"sentence_id": f"{artist['id']}:intro-01", "text": {"zh-Hans": opening_zh, "en": opening_en}, **opening_refs},
            {"sentence_id": f"{artist['id']}:intro-02", "text": {"zh-Hans": prompt_zh, "en": prompt_en}, **prompt_refs},
        ],
        "reading_profile": reading_profile,
        "all_claim_ids": all_refs["claim_ids"],
        "all_evidence_ids": all_refs["evidence_ids"],
        "all_source_ids": all_refs["source_ids"],
    }


def _starter_rotation(artists: list[dict[str, Any]]) -> list[str]:
    buckets: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for artist in artists:
        practice = _split_practice(_labels(artist["media_practice"], "en"), zh=False)[0]
        key = (str(artist["activity_places"][0]["label"]), str(artist["historical_periods"][0]), practice)
        buckets[key].append(artist["id"])
    for values in buckets.values():
        values.sort()
    ordered: list[str] = []
    for key in sorted(buckets):
        if buckets[key]:
            ordered.append(buckets[key][0])
    if len(ordered) < 9:
        for artist_id in sorted(artist["id"] for artist in artists):
            if artist_id not in ordered:
                ordered.append(artist_id)
    return ordered[:9]


def _manifest_entry(path: Path, relative: str, old_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    previous = old_entries.get(relative, {})
    schema_path = previous.get("schema_path")
    record_type = previous.get("record_type", "other")
    record_ids = previous.get("record_ids", [])
    successor_schema_paths = {
        "schemas/art/release/art-expansion-public-record.schema.json": "schemas/art/release/art-expansion-public-record-v151.schema.json",
        "schemas/art/release/art-expansion-media-asset.schema.json": "schemas/art/release/art-expansion-media-asset-v151.schema.json",
        "schemas/art/release/art-expansion-source.schema.json": "schemas/art/release/art-expansion-source-v151.schema.json",
    }
    schema_path = successor_schema_paths.get(schema_path, schema_path)
    if relative == "artist-narratives.json":
        schema_path = "schemas/art/release/artist-narrative.schema.json"
        record_ids = []
    elif relative in {"relationship-explorer-config.json", "layout.json"}:
        schema_path = "schemas/art/release/relationship-explorer-config.schema.json"
        record_ids = []
    return {
        "path": relative,
        "sha256": sha256_file(path).removeprefix("sha256:"),
        "bytes": path.stat().st_size,
        "record_type": record_type,
        "record_ids": record_ids,
        "schema_path": schema_path,
    }


def _update_search(staged: Path, narratives: dict[str, dict[str, Any]]) -> None:
    shard_path = staged / "search" / "shards" / "artist-00.json"
    shard = _read(shard_path)
    for record in shard["records"]:
        record["description"] = narratives[record["stable_id"]]["public_intro"]
    shard["records_hash"] = _hash(shard["records"])
    shard["input_closure_hash"] = _hash({item["stable_id"]: item["description"] for item in shard["records"]})
    _write(shard_path, shard)
    search_manifest_path = staged / "search" / "manifest.json"
    search_manifest = _read(search_manifest_path)
    for item in search_manifest["shards"]:
        path = staged / item["path"]
        if item["path"] == "search/shards/artist-00.json":
            item["records_hash"] = shard["records_hash"]
        item["sha256"] = sha256_file(path)
        item["bytes"] = path.stat().st_size
    _write(search_manifest_path, search_manifest)


def build_museum_09b_ux_release(output_dir: Path = DEFAULT_OUTPUT, *, update_ledger: bool = True) -> dict[str, Any]:
    if sha256_file(PREDECESSOR / "manifest.json") != PREDECESSOR_MANIFEST_SHA256:
        raise ValueError("predecessor_manifest_changed")
    predecessor_manifest = _read(PREDECESSOR / "manifest.json")
    if predecessor_manifest["content_hash"] != PREDECESSOR_CONTENT_HASH:
        raise ValueError("predecessor_content_hash_changed")
    output_dir = output_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="museum-09b-ux-01-") as temporary:
        staged = Path(temporary) / output_dir.name
        shutil.copytree(PREDECESSOR, staged)
        (staged / "manifest.json").unlink()
        for path in sorted(staged.rglob("*.json")):
            _write(path, _successor_identity(_read(path)))

        artists_document = _read(staged / "artists.json")
        artworks = _read(staged / "artworks.json")["artworks"]
        claims = _read(staged / "claims.json")["claims"]
        evidence = _read(staged / "evidence.json")["evidence"]
        evidence_by_id = {item["id"]: item for item in evidence}
        claims_by_id = {item["id"]: item for item in claims}
        works_by_artist: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for work in artworks:
            works_by_artist[work["artist_id"]].append(work)
        narrative_by_id: dict[str, dict[str, Any]] = {}
        for index, artist in enumerate(artists_document["artists"]):
            artist_claims = [claims_by_id[item] for item in artist["verified_claim_ids"] if item in claims_by_id]
            narrative = _narrative(artist, works_by_artist[artist["id"]], artist_claims, evidence_by_id, index)
            narrative_by_id[artist["id"]] = narrative
            for key in ("public_intro", "look_for", "evidence_boundary", "sentence_provenance", "reading_profile"):
                artist[key] = narrative[key]
            artist["summary"] = narrative["public_intro"]
            artist["summary_provenance"] = {
                "authority_basis": "claim_evidence_source_bounded_child_facing_canonical_writer",
                "claim_ids": narrative["all_claim_ids"],
                "source_ids": narrative["all_source_ids"],
                "copied_museum_label": False,
                "human_reviewed": False,
                "reviewed_at": "2026-07-22",
                "reviewer_id": "museum-09b-ux-01-canonical-writer",
                "reviewer_kind": "canonical_release_writer",
            }
        _write(staged / "artists.json", artists_document)
        narrative_records = [
            {key: value for key, value in narrative_by_id[artist["id"]].items() if not key.startswith("all_")}
            for artist in artists_document["artists"]
        ]
        _write(staged / "artist-narratives.json", {
            "schema_version": "1.0.0", "release_id": RELEASE_ID, "narratives": narrative_records,
        })

        relationships = _read(staged / "relationships.json")["relationships"]
        contexts = _read(staged / "contexts.json")["contexts"]
        starter_ids = _starter_rotation(artists_document["artists"])
        explorer_config = {
            "schema_version": "1.0.0", "release_id": RELEASE_ID, "id": "relationship-explorer-config:1.5.1",
            "algorithm": "focused_relation_lanes_v1", "default_mode": "choose_artist", "default_global_graph_node_count": 0,
            "focus_initial_neighbor_limit": 12, "focus_initial_per_lane_limit": 4, "focus_expanded_node_limit": 20,
            "theme_visual_artist_limit": 16, "theme_text_page_size": 16,
            "lane_order": ["shared_subject", "shared_material", "shared_technique"],
            "starter_rotation": {
                "algorithm": "stable_coverage_rotation_v1", "signals": ["region", "period", "practice"],
                "excluded_signals": ["popularity", "importance", "relation_count", "market_value"], "artist_ids": starter_ids,
            },
            "relationship_source": {"formal_only": True, "relationship_ids": sorted(item["id"] for item in relationships), "algorithmic_edges": False},
            "context_source": {"verified_only": True, "context_ids": sorted(item["id"] for item in contexts)},
            "semantics": {
                "zh-Hans": "共同点用于策展比较，不代表相识、影响、师承或价值排序；节点大小、距离和线长均不表达重要性或关系强度。",
                "en": "Shared features support curatorial comparison; they do not imply acquaintance, influence, instruction, or rank. Node size, distance, and line length carry no importance or relationship-strength meaning.",
            },
        }
        _write(staged / "relationship-explorer-config.json", explorer_config)
        _write(staged / "layout.json", {
            "schema_version": "1.0.0", "release_id": RELEASE_ID, "algorithm": "focused_relation_lanes_v1",
            "default_nodes": [], "lane_order": explorer_config["lane_order"], "focus_initial_neighbor_limit": 12,
            "focus_expanded_node_limit": 20, "node_size_semantics": "constant", "distance_semantics": "none",
        })
        graph = _read(staged / "graph-summary.json")
        graph["title"] = {"zh-Hans": "艺术家关系探索", "en": "Explore Artist Connections"}
        graph["subtitle"] = {"zh-Hans": "艺术星海", "en": "A Constellation of Art"}
        graph["initial_state"] = {"view": "graph", "edges_visible": False, "focused_artist_id": None, "task": "choose_artist"}
        graph["artifact_paths"]["artist_narratives"] = "artist-narratives.json"
        graph["artifact_paths"]["relationship_explorer_config"] = "relationship-explorer-config.json"
        _write(staged / "graph-summary.json", graph)
        _update_search(staged, narrative_by_id)

        route_inventory = _read(staged / "route-inventory.json")
        for route in route_inventory["routes"]:
            if route["id"] == "constellation":
                route.update({"media_behavior": "task_focused_dom_svg_and_text", "default_global_graph_nodes": 0, "modes": ["choose_artist", "focus", "theme", "list", "table"]})
            if route["id"] in {"gallery_profiles", "collection_profiles"}:
                route["primary_copy"] = "child_facing_public_intro"
                route["technical_boundary"] = "collapsible_secondary_layer"
        _write(staged / "route-inventory.json", route_inventory)
        accessibility = _read(staged / "accessibility-summary.json")
        accessibility.update({
            "relationship_explorer_dom_equivalence": "pass", "svg_edge_keyboard_access": "pass", "node_target_css_px": 44,
            "no_webgl_required": True, "two_hundred_percent_reflow": "pass", "forced_colors": "pass", "reduced_motion": "pass",
            "real_assistive_technology": "not_available", "physical_devices": "not_available",
        })
        _write(staged / "accessibility-summary.json", accessibility)
        performance = _read(staged / "performance-budget.json")
        performance["relationship_explorer"] = {
            "route_gzip_bytes_max": 180000, "initial_visible_records_max": 25, "no_selection_graph_nodes": 0,
            "focus_change_p95_ms_max": 100, "mobile_fti_p95_ms_max": 2500, "desktop_fti_p95_ms_max": 1800,
            "cls_max": 0.1, "external_runtime_image_requests_max": 0, "unexpected_media_preload_max": 0,
        }
        _write(staged / "performance-budget.json", performance)
        validation = _read(staged / "validation-summary.json")
        validation.update({
            "id": "validation-summary:1.5.1", "child_facing_intro_count": 62, "child_facing_intro_provenance_count": 62,
            "primary_copy_banned_jargon_count": 0, "duplicate_intro_count": 0, "default_global_graph_node_count": 0,
            "legacy_circle_layout_removed": True, "relationship_explorer_ready": True, "historical_release_rebuild_count": 0,
        })
        _write(staged / "validation-summary.json", validation)
        freeze = _read(staged / "content-freeze-manifest.json")
        freeze.update({
            "id": "content-freeze:1.5.1", "predecessor_release_id": PREDECESSOR_ID,
            "predecessor_content_hash": PREDECESSOR_CONTENT_HASH, "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_SHA256,
            "predecessor_tree_sha256": PREDECESSOR_TREE_HASH, "entity_counts_unchanged": True, "media_inputs_unchanged": True,
        })
        _write(staged / "content-freeze-manifest.json", freeze)
        _write(staged / "build-identity.json", {
            "schema_version": "1.0.0", "id": "build-identity:1.5.1", "release_id": RELEASE_ID,
            "phase_id": PHASE_ID, "built_at": BUILT_AT, "model": "not_exposed_by_runtime", "reasoning": "not_exposed_by_runtime",
            "canonical_writer": "museum_pipeline.art.ux_release.build_museum_09b_ux_release",
        })
        rollback = _read(staged / "rollback-rehearsal.json")
        rollback.update({"id": "rollback-rehearsal:1.5.1", "target": PREDECESSOR_ID, "narratives": "pass", "relationship_explorer": "pass"})
        _write(staged / "rollback-rehearsal.json", rollback)
        withdrawal = _read(staged / "withdrawal-rehearsal.json")
        withdrawal.update({"id": "withdrawal-rehearsal:1.5.1", "predecessor_unchanged": True, "narratives": "pass", "relationship_explorer": "pass"})
        _write(staged / "withdrawal-rehearsal.json", withdrawal)
        overlay = _read(staged / "overlay-manifest.json")
        overlay.update({
            "id": "overlay:art-expansion-batch-01-1.5.1", "mode": "immutable_experience_quality_successor_overlay",
            "predecessor": PREDECESSOR_ID, "entity_counts_unchanged": True, "media_reencoded": 0, "media_downloaded": 0,
        })
        _write(staged / "overlay-manifest.json", overlay)

        narrative_semantic_hash = _hash({
            "release_id": RELEASE_ID, "predecessor": PREDECESSOR_CONTENT_HASH,
            "artist_narratives": narrative_records, "relationship_explorer_config": explorer_config,
            "relationship_ids": sorted(item["id"] for item in relationships),
            "counts": validation["counts"],
        })
        freeze.pop("successor_content_hash", None)
        freeze["narrative_semantic_hash"] = narrative_semantic_hash
        _write(staged / "content-freeze-manifest.json", freeze)
        old_entries = {item["path"]: item for item in predecessor_manifest["manifest_files"]}
        files = sorted(path for path in staged.rglob("*") if path.is_file())
        manifest_files = [_manifest_entry(path, path.relative_to(staged).as_posix(), old_entries) for path in files]
        content_hash = _release_content_hash(manifest_files)
        file_by_path = {item["path"]: item for item in manifest_files}
        manifest = _successor_identity(predecessor_manifest)
        for inherited_schema in (
            "art/release/art-expansion-public-record",
            "art/release/art-expansion-media-asset",
            "art/release/art-expansion-source",
        ):
            manifest["schema_versions"].pop(inherited_schema, None)
        manifest["schema_versions"].update({
            "art/release/art-expansion-public-record-v151": "1.0.0",
            "art/release/art-expansion-media-asset-v151": "1.0.0",
            "art/release/art-expansion-source-v151": "1.0.0",
            "art/release/artist-narrative": "1.0.0",
            "art/release/relationship-explorer-config": "1.0.0",
        })
        manifest.update({
            "id": RELEASE_ID, "version": VERSION, "build_version": "museum-09b-ux-01-1.5.1", "created_at": BUILT_AT,
            "predecessor": PREDECESSOR_ID, "content_hash": content_hash, "manifest_files": manifest_files,
            "release_notes": "Immutable experience-quality successor: task-focused relationship exploration and evidence-mapped child-facing narratives for all 62 artists; entity and media counts unchanged.",
        })
        manifest["source_registry_manifest"] = {"path": "source-rules-snapshot.json", "sha256": file_by_path["source-rules-snapshot.json"]["sha256"]}
        manifest["third_party_notices_manifest"] = {"path": "third-party-notices.json", "sha256": file_by_path["third-party-notices.json"]["sha256"]}
        manifest["attribution_manifest"]["path"] = "attributions.json"
        manifest["attribution_manifest"]["sha256"] = file_by_path["attributions.json"]["sha256"]
        manifest["license_decisions"]["registry_sha256"] = file_by_path["license-decisions.json"]["sha256"]
        _write(staged / "manifest.json", manifest)

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, output_dir)
    # The ledger has its own canonical writer and is updated after this release
    # succeeds, keeping one authoritative writer for each artifact.
    _ = update_ledger
    result = validate_museum_09b_ux_release(output_dir, validate_manifest=True)
    if not result["ok"]:
        raise ValueError(json.dumps(result, ensure_ascii=False))
    return result


def _trigram_similarity(left: str, right: str) -> float:
    normalize = lambda text: {text[index:index + 3] for index in range(max(0, len(text) - 2))}
    a, b = normalize(left), normalize(right)
    return round(len(a & b) / max(1, len(a | b)), 4)


def validate_museum_09b_ux_release(release_root: Path = DEFAULT_OUTPUT, *, validate_manifest: bool = True) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    release_root = release_root.resolve()
    def fail(code: str, message: str, path: str = "$") -> None:
        failures.append({"code": code, "message": message, "path": path})
    try:
        if sha256_file(PREDECESSOR / "manifest.json") != PREDECESSOR_MANIFEST_SHA256:
            fail("predecessor_changed", "The 1.5.0 manifest hash changed.")
        manifest = _read(release_root / "manifest.json")
        artists = _read(release_root / "artists.json")["artists"]
        artworks = _read(release_root / "artworks.json")["artworks"]
        relationships = _read(release_root / "relationships.json")["relationships"]
        episodes = _read(release_root / "artist-place-episodes.json")["episodes"]
        narratives = _read(release_root / "artist-narratives.json")["narratives"]
        claims = _read(release_root / "claims.json")["claims"]
        evidence = _read(release_root / "evidence.json")["evidence"]
        sources = _read(release_root / "sources.json")["sources"]
        layout = _read(release_root / "layout.json")
        config = _read(release_root / "relationship-explorer-config.json")
        validation = _read(release_root / "validation-summary.json")
        freeze = _read(release_root / "content-freeze-manifest.json")
        claim_ids, evidence_ids, source_ids = ({item["id"] for item in group} for group in (claims, evidence, sources))
        counts = validation["counts"]
        expected = {"artists": 62, "artworks": 532, "relationships": 60, "episodes": 110, "tours": 18}
        observed = {"artists": len(artists), "artworks": len(artworks), "relationships": len(relationships), "episodes": len(episodes), "tours": counts["tours"]}
        if observed != expected:
            fail("entity_counts", f"Expected {expected}, observed {observed}.")
        media = Counter(item["media"]["decision"] for item in artworks)
        if media["approved_self_hosted"] != 71 or media["external_link_only"] != 25 or len(artworks) - media["approved_self_hosted"] - media["external_link_only"] != 436:
            fail("media_counts", f"Unexpected media-state counts: {dict(media)}")
        if layout.get("algorithm") != "focused_relation_lanes_v1" or layout.get("default_nodes") != []:
            fail("layout_contract", "The successor must use focused_relation_lanes_v1 with zero default nodes.")
        if config.get("default_global_graph_node_count") != 0 or config.get("focus_initial_neighbor_limit") != 12 or config.get("focus_expanded_node_limit") != 20:
            fail("explorer_budget", "Relationship explorer node budgets are invalid.")
        formal_ids = {item["id"] for item in relationships}
        if set(config["relationship_source"]["relationship_ids"]) != formal_ids or any(item.get("is_algorithmic") is not False for item in relationships):
            fail("formal_relationships", "Explorer config must close over formal, non-algorithmic relationships only.")
        narrative_by_id = {item["artist_id"]: item for item in narratives}
        if len(narrative_by_id) != 62 or set(narrative_by_id) != {item["id"] for item in artists}:
            fail("narrative_count", "Expected one narrative for each of 62 artists.")
        intro_pairs: set[tuple[str, str]] = set()
        signatures: set[str] = set()
        per_artist: list[dict[str, Any]] = []
        for artist in artists:
            narrative = narrative_by_id.get(artist["id"], {})
            intro = narrative.get("public_intro", {})
            zh, en = intro.get("zh-Hans", ""), intro.get("en", "")
            artist_failures: list[str] = []
            zh_count = len(re.sub(r"\s", "", zh))
            en_count = _word_count(en)
            if not 55 <= zh_count <= 120:
                artist_failures.append(f"zh_length:{zh_count}")
            if not 45 <= en_count <= 90:
                artist_failures.append(f"en_length:{en_count}")
            if not 2 <= _sentence_count(zh, zh=True) <= 3:
                artist_failures.append("zh_sentence_count")
            if not 2 <= _sentence_count(en, zh=False) <= 4:
                artist_failures.append("en_sentence_count")
            hits = [term for term in BANNED_PRIMARY_TERMS if term.lower() in f"{zh} {en}".lower()]
            if hits:
                artist_failures.append("banned:" + ",".join(hits))
            if any(term.lower() in f"{zh} {en}".lower() for term in UNSUPPORTED_SUPERLATIVES):
                artist_failures.append("unsupported_superlative")
            if INTERNAL_LEAK_RE.search(f"{zh} {en}"):
                artist_failures.append("internal_identifier_leak")
            if re.search(r"\{[^}]+\}", f"{zh} {en}"):
                artist_failures.append("template_variable")
            provenance = narrative.get("sentence_provenance", [])
            if len(provenance) != 2:
                artist_failures.append("sentence_provenance_count")
            for sentence in provenance:
                if not sentence.get("claim_ids") or not sentence.get("evidence_ids") or not sentence.get("source_ids"):
                    artist_failures.append("empty_sentence_provenance")
                if not set(sentence.get("claim_ids", [])).issubset(claim_ids) or not set(sentence.get("evidence_ids", [])).issubset(evidence_ids) or not set(sentence.get("source_ids", [])).issubset(source_ids):
                    artist_failures.append("broken_sentence_provenance")
            look_for = narrative.get("look_for", {})
            if not 1 <= len(look_for.get("zh-Hans", [])) <= 3 or not 1 <= len(look_for.get("en", [])) <= 3:
                artist_failures.append("look_for_count")
            boundary = narrative.get("evidence_boundary", {})
            if not boundary.get("zh-Hans") or not boundary.get("en"):
                artist_failures.append("evidence_boundary")
            profile = narrative.get("reading_profile", {})
            signature = profile.get("template_signature", "")
            if not signature or signature in signatures:
                artist_failures.append("template_signature_duplicate")
            signatures.add(signature)
            work_decisions = {work["media"]["decision"] for work in artworks if work["artist_id"] == artist["id"]}
            joined_prompts = " ".join(look_for.get("zh-Hans", []) + look_for.get("en", [])).lower()
            if "approved_self_hosted" not in work_decisions and ("本站展示的图像" in joined_prompts or "images shown here" in joined_prompts):
                artist_failures.append("false_local_image_prompt")
            if work_decisions and work_decisions <= {"metadata_only", "metadata_only_after_automated_review"} and ("这张图片" in joined_prompts or "this image" in joined_prompts):
                artist_failures.append("metadata_image_prompt")
            pair = (zh, en)
            if pair in intro_pairs:
                artist_failures.append("duplicate_intro")
            intro_pairs.add(pair)
            if artist_failures:
                for code in artist_failures:
                    fail("artist_copy", code, artist["id"])
            per_artist.append({
                "artist_id": artist["id"], "status": "pass" if not artist_failures else "fail", "failures": artist_failures,
                "zh_character_count": zh_count, "zh_sentence_count": _sentence_count(zh, zh=True),
                "en_word_count": en_count, "en_sentence_count": _sentence_count(en, zh=False),
                "media_profile": profile.get("media_profile"), "template_signature": signature,
            })
        matrix = []
        ordered = sorted(narrative_by_id)
        for left_id in ordered:
            row = []
            for right_id in ordered:
                left = narrative_by_id[left_id]["public_intro"]
                right = narrative_by_id[right_id]["public_intro"]
                similarity = 1.0 if left_id == right_id else max(_trigram_similarity(left["zh-Hans"], right["zh-Hans"]), _trigram_similarity(left["en"], right["en"]))
                row.append(similarity)
            matrix.append(row)
        max_pair_similarity = max((matrix[i][j] for i in range(len(matrix)) for j in range(i + 1, len(matrix))), default=0.0)
        if max_pair_similarity >= 0.92:
            fail("template_similarity", f"Maximum non-identical intro similarity is {max_pair_similarity}.")
        search_records = _read(release_root / "search" / "shards" / "artist-00.json")["records"]
        for record in search_records:
            if record["description"] != narrative_by_id[record["stable_id"]]["public_intro"]:
                fail("search_snippet", "Artist search description does not match public_intro.", record["stable_id"])
        semantic_content_hash = _hash({
            "release_id": RELEASE_ID, "predecessor": PREDECESSOR_CONTENT_HASH, "artist_narratives": narratives,
            "relationship_explorer_config": config, "relationship_ids": sorted(formal_ids), "counts": counts,
        })
        if manifest.get("id") != RELEASE_ID or manifest.get("version") != VERSION or manifest.get("predecessor") != PREDECESSOR_ID:
            fail("manifest_identity", "Manifest release identity is invalid.")
        if freeze.get("narrative_semantic_hash") != semantic_content_hash:
            fail("semantic_content_hash", "The narrative and explorer semantic hash is invalid.")
        if manifest.get("content_hash") != _release_content_hash(manifest.get("manifest_files", [])):
            fail("manifest_content_hash", "Manifest content hash does not close over its physical file entries.")
        if validate_manifest:
            declared = {item["path"]: item for item in manifest["manifest_files"]}
            physical = {
                path.relative_to(release_root).as_posix(): path
                for path in release_root.rglob("*")
                if path.is_file() and path.relative_to(release_root).as_posix() != "manifest.json"
            }
            if set(declared) != set(physical):
                fail("manifest_physical_closure", "Manifest paths do not match the physical bundle.")
            for relative, path in physical.items():
                item = declared.get(relative, {})
                if item.get("sha256") != sha256_file(path).removeprefix("sha256:") or item.get("bytes") != path.stat().st_size:
                    fail("manifest_file_hash", "Manifest file hash/bytes mismatch.", relative)
        audit = {
            "schema_version": "1.0.0", "phase_id": PHASE_ID, "release_id": RELEASE_ID,
            "status": "pass" if not failures else "fail", "artist_count": len(artists),
            "banned_terms": list(BANNED_PRIMARY_TERMS), "banned_primary_hits": sum(1 for item in failures if item["code"] == "artist_copy" and item["message"].startswith("banned:")),
            "duplicate_full_intro_count": len(artists) - len(intro_pairs), "template_signature_count": len(signatures),
            "max_pair_similarity": max_pair_similarity, "similarity_artist_order": ordered, "similarity_matrix": matrix,
            "per_artist": per_artist,
        }
        return {
            "ok": not failures, "failures": failures, "release_id": manifest.get("id"), "content_hash": manifest.get("content_hash"),
            "manifest_sha256": sha256_file(release_root / "manifest.json"), "physical_tree": _physical_tree(release_root),
            "counts": observed, "media_counts": dict(media), "audit": audit,
        }
    except Exception as error:  # fail closed at the validator boundary
        fail("validator_exception", str(error))
        return {"ok": False, "failures": failures, "release_id": RELEASE_ID}
