from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from museum_pipeline.art.batch_validation import validate_approved_batch
from museum_pipeline.media.constants import (
    EXPECTED_M03B_GRAPH_HASH,
    EXPECTED_M03B_PACKAGE_HASH,
    M03B_PACKAGE,
)


@dataclass(frozen=True)
class MediaInputs:
    package_root: Path
    manifest: dict[str, Any]
    graph: dict[str, Any]
    artists: tuple[dict[str, Any], ...]
    artworks: tuple[dict[str, Any], ...]
    assessments: tuple[dict[str, Any], ...]

    @property
    def artist_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in self.artists}

    @property
    def assessment_by_artwork(self) -> dict[str, dict[str, Any]]:
        return {item["artwork_id"]: item for item in self.assessments}


def load_media_inputs(package_root: Path = M03B_PACKAGE) -> MediaInputs:
    result = validate_approved_batch(package_root)
    if not result["ok"]:
        codes = ", ".join(item["code"] for item in result["failures"][:12])
        raise ValueError(f"sealed MUSEUM-03B package failed validation: {codes}")
    manifest = _load(package_root / "package-manifest.json")
    graph = _load(package_root / "graph-input.json")
    if manifest.get("content_hash") != EXPECTED_M03B_PACKAGE_HASH:
        raise ValueError("sealed MUSEUM-03B package content hash changed")
    if graph.get("content_hash") != EXPECTED_M03B_GRAPH_HASH:
        raise ValueError("sealed MUSEUM-03B graph content hash changed")
    artists = tuple(_load(package_root / "artists.json"))
    artworks = tuple(_load(package_root / "artworks.json"))
    assessments = tuple(_load(package_root / "media-assessments.json"))
    outcomes = {item["outcome"] for item in assessments}
    counts = {
        "artists": len(artists),
        "artworks": len(artworks),
        "contexts": len(_load(package_root / "contexts.json")),
        "relationships": len(_load(package_root / "relationships.json")),
        "assessments": len(assessments),
    }
    if counts != {"artists": 12, "artworks": 44, "contexts": 31, "relationships": 36, "assessments": 44}:
        raise ValueError(f"MUSEUM-03B count gate changed: {counts}")
    if outcomes - {"self_hosted_open_media_eligible", "external_iiif_candidate", "metadata_only"}:
        raise ValueError("MUSEUM-03B media outcome vocabulary changed")
    if any(item.get("bytes_downloaded") or item.get("media_bytes_present") for item in assessments):
        raise ValueError("MUSEUM-03B zero-media baseline changed")
    return MediaInputs(package_root, manifest, graph, artists, artworks, assessments)


def normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def years(value: object) -> set[str]:
    text = str(value or "")
    found = set(re.findall(r"(?<!\d)(?:1[0-9]{3}|20[0-9]{2})(?!\d)", text))
    for start, short_end in re.findall(r"((?:1[0-9]{3}|20[0-9]{2}))\s*[–—-]\s*([0-9]{2})(?!\d)", text):
        found.add(start[:2] + short_end)
    return found


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
