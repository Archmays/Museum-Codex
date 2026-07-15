#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from museum_pipeline.art.public_release import DEFAULT_OUTPUT, validate_museum_04_release

APP_ROUTE_MARKERS = (
    'path="/art/artists"',
    'path="/art/artists/:artistId"',
    'path="/art/artworks/:artworkId"',
    'path="/art/compare"',
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_museum_05a(release_root: Path = DEFAULT_OUTPUT, source_root: Path = ROOT) -> dict[str, Any]:
    failures: list[dict[str, str]] = []

    def fail(code: str, message: str, path: Path | str) -> None:
        failures.append({"code": code, "message": message, "path": str(path)})

    release_result = validate_museum_04_release(release_root, require_public=True)
    if not release_result["ok"]:
        fail("m05a_release_invalid", "MUSEUM-04 formal release validation failed", release_root)
        return {"ok": False, "failures": failures, "counts": {}}

    try:
        artists = _read_json(release_root / "artists.json")["artists"]
        artworks = _read_json(release_root / "artworks.json")["artworks"]
        media_index = _read_json(release_root / "media-index.json")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        fail("m05a_release_read", f"Cannot read gallery release: {error}", release_root)
        return {"ok": False, "failures": failures, "counts": {}}

    artist_ids = {artist.get("id") for artist in artists}
    artwork_ids = {artwork.get("id") for artwork in artworks}
    if len(artists) != 12 or len(artist_ids) != 12:
        fail("m05a_artist_count", "Artist gallery closure must contain 12 unique artists", release_root / "artists.json")
    if len(artworks) != 44 or len(artwork_ids) != 44:
        fail("m05a_artwork_count", "Artwork route closure must contain 44 unique works", release_root / "artworks.json")

    artist_work_ids: list[str] = []
    for artist in artists:
        work_ids = artist.get("artwork_ids")
        if not isinstance(work_ids, list) or not 2 <= len(work_ids) <= 4:
            fail("m05a_artist_work_count", "Each artist must expose 2-4 formal works", release_root / "artists.json")
            continue
        artist_work_ids.extend(work_ids)
        if any(work_id not in artwork_ids for work_id in work_ids):
            fail("m05a_artist_work_reference", "Artist references an unknown artwork", release_root / "artists.json")
    if set(artist_work_ids) != artwork_ids or len(artist_work_ids) != 44:
        fail("m05a_artist_work_closure", "Artist galleries must reach each artwork exactly once", release_root / "artists.json")

    decisions: dict[str, int] = {}
    approved_ids: set[str] = set()
    no_image_ids: set[str] = set()
    for artwork in artworks:
        artwork_id = artwork.get("id")
        artist_id = artwork.get("artist_id")
        if artist_id not in artist_ids:
            fail("m05a_artwork_artist", "Artwork references an unknown artist", release_root / "artworks.json")
        media = artwork.get("media") if isinstance(artwork.get("media"), dict) else {}
        decision = media.get("decision")
        decisions[decision] = decisions.get(decision, 0) + 1
        media_ids = media.get("media_ids")
        representative = media.get("representative_media_id")
        if decision == "approved_self_hosted":
            approved_ids.add(artwork_id)
            if not isinstance(media_ids, list) or not media_ids or representative not in media_ids:
                fail("m05a_approved_media_closure", "Approved work lacks representative media closure", release_root / "artworks.json")
        else:
            no_image_ids.add(artwork_id)
            if media_ids != [] or representative is not None:
                fail("m05a_no_image_closure", "Non-approved work must remain a strict no-image record", release_root / "artworks.json")

    expected_decisions = {
        "approved_self_hosted": 31,
        "metadata_only_after_automated_review": 7,
        "blocked_source_unavailable": 4,
        "blocked_rights_conflict": 2,
    }
    if decisions != expected_decisions:
        fail("m05a_media_decisions", f"Unexpected media decision distribution: {decisions}", release_root / "artworks.json")

    index_artworks = media_index.get("artworks")
    assets = media_index.get("assets")
    if not isinstance(index_artworks, list) or not isinstance(assets, list):
        fail("m05a_media_index_shape", "Media index lacks artworks/assets arrays", release_root / "media-index.json")
        index_artworks, assets = [], []
    indexed_ids = {row.get("artwork_id") for row in index_artworks if isinstance(row, dict)}
    if indexed_ids != artwork_ids:
        fail("m05a_media_index_artwork_closure", "Media index must cover all 44 artwork routes", release_root / "media-index.json")

    runtime_artwork_ids: set[str] = set()
    remote_srcs: list[str] = []
    blocked_runtime_ids: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            fail("m05a_media_asset_shape", "Media asset is not an object", release_root / "media-index.json")
            continue
        artwork_id = asset.get("artwork_id")
        runtime_artwork_ids.add(artwork_id)
        src = asset.get("src")
        if not isinstance(src, str) or not re.fullmatch(r"assets/[a-z0-9._-]+/[0-9]+w\.(?:jpg|webp)", src):
            remote_srcs.append(str(src))
        if artwork_id not in approved_ids:
            blocked_runtime_ids.add(artwork_id)
    if len(assets) != 242 or runtime_artwork_ids != approved_ids:
        fail("m05a_runtime_media_closure", "Runtime media must contain 242 derivatives for exactly 31 approved works", release_root / "media-index.json")
    if remote_srcs:
        fail("m05a_remote_media", "Runtime media contains a remote or malformed src", release_root / "media-index.json")
    if blocked_runtime_ids:
        fail("m05a_blocked_media", "Blocked/metadata-only works reached runtime media", release_root / "media-index.json")

    app_path = source_root / "src" / "App.tsx"
    app_source = app_path.read_text(encoding="utf-8") if app_path.exists() else ""
    for marker in APP_ROUTE_MARKERS:
        if marker not in app_source:
            fail("m05a_route_missing", f"Missing route marker {marker}", app_path)

    gallery_root = source_root / "src" / "features" / "art-gallery"
    required_source_files = (
        "ArtGalleryRoute.tsx",
        "artists/ArtistIndexPage.tsx",
        "artists/ArtistGalleryPage.tsx",
        "artwork/ArtworkDetailPage.tsx",
        "artwork/ArtworkZoom.tsx",
        "compare/ComparePage.tsx",
    )
    for relative_path in required_source_files:
        if not (gallery_root / relative_path).is_file():
            fail("m05a_source_missing", "Required M05A source file is missing", gallery_root / relative_path)
    if gallery_root.exists():
        gallery_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(gallery_root.rglob("*.tsx"))
        )
        jsx_remote_media = re.search(
            r"<(?:img|source)\b[^>]*(?:src|srcSet)\s*=\s*(?:[\"']https?://|\{\s*[\"']https?://)",
            gallery_source,
            re.IGNORECASE,
        )
        css_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(gallery_root.rglob("*.css"))
        )
        css_remote_media = re.search(r"url\(\s*[\"']?https?://", css_source, re.IGNORECASE)
        if jsx_remote_media or css_remote_media:
            fail("m05a_source_hotlink", "Gallery source contains a literal remote image hotlink", gallery_root)

    counts = {
        "artist_pages": len(artist_ids),
        "artwork_routes": len(artwork_ids),
        "approved_media_artworks": len(approved_ids),
        "no_image_artworks": len(no_image_ids),
        "runtime_derivatives": len(assets),
        "blocked_runtime_assets": len(blocked_runtime_ids),
    }
    return {"ok": not failures, "failures": failures, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MUSEUM-05A gallery consumption and route closure")
    parser.add_argument("release_root", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_museum_05a(args.release_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        counts = result["counts"]
        print(
            "[PASS] MUSEUM-05A galleries: "
            f"artists={counts['artist_pages']} artworks={counts['artwork_routes']} "
            f"media_artworks={counts['approved_media_artworks']} no_image={counts['no_image_artworks']}"
        )
    else:
        for failure in result["failures"]:
            print(f"[FAIL] {failure['code']}: {failure['message']} ({failure['path']})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
