from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-museum-05a-budgets.mjs"
RELEASE_ID = "release:art-constellation-1.0.0"
M04_INITIAL_FILES = (
    "manifest.json",
    "graph-summary.json",
    "artists.json",
    "layout.json",
    "facets.json",
    "search-index.json",
)
GALLERY_DETAIL_FILES = (
    "artworks.json",
    "media-index.json",
    "attributions.json",
    "withdrawal-mapping.json",
)

CONSTELLATION = "src/features/art-constellation/ArtConstellationPage.tsx"
SIGMA = "src/features/art-constellation/SigmaGraphRenderer.tsx"
GALLERY = "src/features/art-gallery/ArtGalleryRoute.tsx"
ARTIST_INDEX = "src/features/art-gallery/artists/ArtistIndexPage.tsx"
ARTIST_GALLERY = "src/features/art-gallery/artists/ArtistGalleryPage.tsx"
ARTWORK_DETAIL = "src/features/art-gallery/artwork/ArtworkDetailPage.tsx"
COMPARE = "src/features/art-gallery/compare/ComparePage.tsx"
PAGES = (ARTIST_INDEX, ARTIST_GALLERY, ARTWORK_DETAIL, COMPARE)


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def create_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    dist = root / "dist"
    assets = dist / "assets"
    release = dist / "releases" / "art-constellation-1.0.0"
    manifest_path = dist / ".vite" / "manifest.json"
    output = root / "bundle-budget.json"
    assets.mkdir(parents=True)
    release.mkdir(parents=True)

    files = {
        "index.js": "console.log('home')",
        "index.css": "body{color:#111}",
        "constellation.js": "export const constellation=true",
        "constellation.css": ".constellation{display:grid}",
        "sigma.js": "export const sigma=true",
        "gallery.js": "export const gallery=true",
        "gallery.css": ".gallery{display:grid}",
        "release-loader.js": "export const releaseLoader=true",
        "types.js": "export{}",
        "media.js": "export const media=true",
        "artwork-shared.js": "export const artworkShared=true",
        "artwork-shared.css": ".zoom{overflow:hidden}",
        "artwork-image.js": "export const artworkImage=true",
        "artist-index.js": "export const artistIndex=true",
        "artist-gallery.js": "export const artistGallery=true",
        "artists.css": ".artists{display:grid}",
        "artwork-detail.js": "export const artworkDetail=true",
        "compare.js": "export const compare=true",
        "compare.css": ".compare{display:grid}",
    }
    for name, content in files.items():
        write(assets / name, content)
    write(dist / "index.html", '<!doctype html><script type="module" src="/Museum-Codex/assets/index.js"></script>')

    manifest = {
        "_release-loader.js": {"file": "assets/release-loader.js", "imports": ["index.html"]},
        "_types.js": {"file": "assets/types.js"},
        "_media.js": {"file": "assets/media.js"},
        "_artwork-shared.js": {
            "file": "assets/artwork-shared.js",
            "imports": ["index.html", "_types.js", "_media.js"],
            "css": ["assets/artwork-shared.css"],
        },
        "_artwork-image.js": {"file": "assets/artwork-image.js", "imports": ["index.html"]},
        "index.html": {
            "file": "assets/index.js",
            "src": "index.html",
            "isEntry": True,
            "dynamicImports": [CONSTELLATION, GALLERY],
            "css": ["assets/index.css"],
        },
        CONSTELLATION: {
            "file": "assets/constellation.js",
            "src": CONSTELLATION,
            "isDynamicEntry": True,
            "imports": ["index.html", "_release-loader.js", "_types.js", "_artwork-image.js"],
            "dynamicImports": [SIGMA],
            "css": ["assets/constellation.css"],
        },
        SIGMA: {
            "file": "assets/sigma.js",
            "src": SIGMA,
            "isDynamicEntry": True,
            "imports": ["index.html", "_types.js"],
        },
        GALLERY: {
            "file": "assets/gallery.js",
            "src": GALLERY,
            "isDynamicEntry": True,
            "imports": ["index.html", "_release-loader.js"],
            "dynamicImports": list(PAGES),
            "css": ["assets/gallery.css"],
        },
        ARTIST_INDEX: {
            "file": "assets/artist-index.js",
            "src": ARTIST_INDEX,
            "isDynamicEntry": True,
            "imports": ["index.html", "_types.js", "_artwork-image.js", "_media.js"],
            "css": ["assets/artists.css"],
        },
        ARTIST_GALLERY: {
            "file": "assets/artist-gallery.js",
            "src": ARTIST_GALLERY,
            "isDynamicEntry": True,
            "imports": ["index.html", "_types.js", "_artwork-image.js", "_media.js"],
            "css": ["assets/artists.css"],
        },
        ARTWORK_DETAIL: {
            "file": "assets/artwork-detail.js",
            "src": ARTWORK_DETAIL,
            "isDynamicEntry": True,
            "imports": ["index.html", "_types.js", "_media.js", "_artwork-shared.js"],
        },
        COMPARE: {
            "file": "assets/compare.js",
            "src": COMPARE,
            "isDynamicEntry": True,
            "imports": ["index.html", "_types.js", "_media.js", "_artwork-shared.js"],
            "css": ["assets/compare.css"],
        },
    }
    write(manifest_path, json.dumps(manifest))

    artwork_ids = [f"artwork:test-{index:02d}" for index in range(44)]
    media_assets: list[dict[str, str]] = []
    for artwork_id in artwork_ids[:31]:
        slug = artwork_id.removeprefix("artwork:")
        for width in (320, 640, 960, 1600):
            for extension in ("jpg", "webp"):
                if len(media_assets) == 242:
                    break
                media_assets.append(
                    {
                        "id": f"media:{slug}-{width}-{extension}",
                        "artwork_id": artwork_id,
                        "src": f"assets/{slug}/{width}w.{extension}",
                    }
                )
            if len(media_assets) == 242:
                break
        if len(media_assets) == 242:
            break

    release_manifest = {
        "id": RELEASE_ID,
        "attribution_manifest": {"path": "attributions.json"},
    }
    media_index = {
        "release_id": RELEASE_ID,
        "artworks": [{"artwork_id": artwork_id} for artwork_id in artwork_ids],
        "assets": media_assets,
    }
    for name in (*M04_INITIAL_FILES, *GALLERY_DETAIL_FILES):
        value: dict[str, object] = {}
        if name == "manifest.json":
            value = release_manifest
        elif name == "media-index.json":
            value = media_index
        write(release / name, json.dumps(value))
    return dist, release, manifest_path, output


def run_gate(dist: Path, release: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "node",
            str(SCRIPT),
            "--dist",
            str(dist),
            "--release",
            str(release),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class Museum05ABudgetGateTests(unittest.TestCase):
    def test_valid_lazy_build_passes_and_evidence_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _, output = create_fixture(Path(directory))
            first = run_gate(dist, release, output)
            first_evidence = output.read_bytes()
            second = run_gate(dist, release, output)
            second_evidence = output.read_bytes()
            report = json.loads(second_evidence)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual(first_evidence, second_evidence)
        self.assertEqual("pass", report["status"])
        self.assertTrue(report["lazyBoundaries"]["pass"])
        self.assertTrue(report["m04Regression"]["pass"])
        constellation_paths = {
            item["path"]
            for kind in ("js", "css")
            for item in report["m04Regression"]["constellationRoute"][kind]
        }
        self.assertNotIn("assets/gallery.js", constellation_paths)
        self.assertNotIn("assets/artist-index.js", constellation_paths)
        self.assertEqual(44, report["mediaLocatorEmbedding"]["artworkRowsChecked"])
        self.assertEqual(242, report["mediaLocatorEmbedding"]["derivativeUrlsChecked"])
        self.assertEqual([], report["mediaLocatorEmbedding"]["embeddedMatches"])
        self.assertTrue(all(route["pass"] for route in report["galleryRoutes"].values()))

    def test_page_statically_reachable_from_home_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, manifest_path, output = create_fixture(Path(directory))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["index.html"]["imports"] = [ARTIST_INDEX]
            write(manifest_path, json.dumps(manifest))
            result = run_gate(dist, release, output)
        self.assertEqual(1, result.returncode)
        self.assertIn("artistIndex is present in the home initial closure", result.stderr)
        self.assertIn("artistIndex is statically bundled into ArtGalleryRoute", result.stderr)

    def test_missing_direct_lazy_page_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, manifest_path, output = create_fixture(Path(directory))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest[GALLERY]["dynamicImports"].remove(COMPARE)
            write(manifest_path, json.dumps(manifest))
            result = run_gate(dist, release, output)
        self.assertEqual(1, result.returncode)
        self.assertIn("compare is not a direct lazy page of ArtGalleryRoute", result.stderr)

    def test_home_media_embedding_and_budgets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _, output = create_fixture(Path(directory))
            noise = [hashlib.sha256(str(index).encode()).hexdigest() for index in range(7_000)]
            write(dist / "assets" / "index.js", "\n".join(noise) + "\nassets/test-00/320w.jpg")
            write(release / "artworks.json", json.dumps({"noise": noise}))
            result = run_gate(dist, release, output)
        self.assertEqual(1, result.returncode)
        self.assertIn("home initial gzip", result.stderr)
        self.assertIn("gallery initial JSON gzip", result.stderr)
        self.assertIn("home initial closure embeds", result.stderr)


if __name__ == "__main__":
    unittest.main()
