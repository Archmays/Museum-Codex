from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-museum-04-budgets.mjs"
INITIAL_FILES = (
    "manifest.json",
    "graph-summary.json",
    "artists.json",
    "layout.json",
    "facets.json",
    "search-index.json",
)
DEFERRED_FILES = (
    "contexts.json",
    "relationships.json",
    "artworks.json",
    "evidence.json",
    "sources.json",
    "rights.json",
    "media-index.json",
    "attributions.json",
    "third-party-notices.json",
    "withdrawal-mapping.json",
)
RELEASE_ID = "release:art-constellation-1.0.0"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_media_contract(release: Path) -> None:
    artwork_ids = [f"artwork:test-{index:02d}" for index in range(44)]
    asset_rows: list[dict[str, object]] = []
    manifest_files: list[dict[str, object]] = []
    grouped: dict[str, list[str]] = {artwork_id: [] for artwork_id in artwork_ids}
    combinations = [(width, image_format) for width in (320, 640, 960, 1600) for image_format in ("jpeg", "webp")]
    for artwork_id in artwork_ids[:31]:
        slug = artwork_id.removeprefix("artwork:")
        for width, image_format in combinations:
            if len(asset_rows) == 242:
                break
            extension = "jpg" if image_format == "jpeg" else "webp"
            mime_type = "image/jpeg" if image_format == "jpeg" else "image/webp"
            payload = b"\xff\xd8\xff\xd9" if image_format == "jpeg" else b"RIFF\x04\x00\x00\x00WEBP"
            relative_path = f"assets/{slug}/{width}w.{extension}"
            path = release / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            child_id = f"media:{slug}-{width}w-{image_format}"
            grouped[artwork_id].append(child_id)
            asset_rows.append(
                {
                    "id": child_id,
                    "artwork_id": artwork_id,
                    "parent_media_id": f"media:{slug}-source",
                    "src": relative_path,
                    "format": image_format,
                    "mime_type": mime_type,
                    "width": width,
                    "height": width,
                    "bytes": len(payload),
                    "sha256": f"sha256:{sha256(payload)}",
                    "role": "thumbnail" if width <= 640 else "detail",
                }
            )
            manifest_files.append(
                {
                    "path": relative_path,
                    "sha256": sha256(payload),
                    "bytes": len(payload),
                    "record_type": "media",
                    "schema_path": None,
                    "record_ids": [child_id],
                }
            )
    artwork_rows = []
    for artwork_id in artwork_ids:
        media_ids = grouped[artwork_id]
        representative = next(
            (asset["id"] for asset in asset_rows if asset["artwork_id"] == artwork_id and asset["width"] == 320),
            None,
        )
        artwork_rows.append(
            {
                "artwork_id": artwork_id,
                "decision": "approved_self_hosted" if media_ids else "metadata_only_after_automated_review",
                "reason_codes": [] if media_ids else ["no_approved_delivery"],
                "representative_media_id": representative,
                "media_ids": media_ids,
            }
        )
    media_index = {
        "schema_version": "1.0.0",
        "release_id": RELEASE_ID,
        "media_bundle_id": "media-bundle:test",
        "media_bundle_hash": "sha256:" + "1" * 64,
        "delivery_policy": {
            "external_runtime_api": False,
            "external_delivery_count": 0,
            "blocked_asset_count": 0,
            "preferred": "self_hosted",
            "low_bandwidth_default": "metadata_only",
        },
        "counts": {
            "approved_artworks": 31,
            "no_image_artworks": 13,
            "assets": len(asset_rows),
            "bytes": sum(int(asset["bytes"]) for asset in asset_rows),
        },
        "artworks": artwork_rows,
        "assets": asset_rows,
    }
    parent_ids = [f"media:{artwork_id.removeprefix('artwork:')}-source" for artwork_id in artwork_ids[:31]]
    release_manifest = {
        "id": RELEASE_ID,
        "included_media_asset_ids": parent_ids + [str(asset["id"]) for asset in asset_rows],
        "manifest_files": manifest_files,
    }
    (release / "media-index.json").write_text(json.dumps(media_index), encoding="utf-8")
    (release / "manifest.json").write_text(json.dumps(release_manifest), encoding="utf-8")


def create_build(root: Path) -> tuple[Path, Path, Path]:
    dist = root / "dist"
    assets = dist / "assets"
    release = dist / "releases" / "art-constellation-1.0.0"
    manifest_path = dist / ".vite" / "manifest.json"
    assets.mkdir(parents=True)
    release.mkdir(parents=True)
    manifest_path.parent.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><script type="module" src="/Museum-Codex/assets/index.js"></script>',
        encoding="utf-8",
    )
    (assets / "index.js").write_text("console.log('home')", encoding="utf-8")
    (assets / "index.css").write_text("body{color:#111}", encoding="utf-8")
    (assets / "ArtConstellationPage.js").write_text("export const route=true", encoding="utf-8")
    (assets / "constellation.css").write_text(".graph{display:grid}", encoding="utf-8")
    (assets / "SigmaGraphRenderer.js").write_text("const graphologyBundle=true", encoding="utf-8")
    manifest = {
        "index.html": {
            "file": "assets/index.js",
            "isEntry": True,
            "css": ["assets/index.css"],
            "dynamicImports": ["src/features/art-constellation/ArtConstellationPage.tsx"],
        },
        "src/features/art-constellation/ArtConstellationPage.tsx": {
            "file": "assets/ArtConstellationPage.js",
            "isDynamicEntry": True,
            "css": ["assets/constellation.css"],
            "dynamicImports": ["src/features/art-constellation/SigmaGraphRenderer.tsx"],
        },
        "src/features/art-constellation/SigmaGraphRenderer.tsx": {
            "file": "assets/SigmaGraphRenderer.js",
            "isDynamicEntry": True,
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for name in (*INITIAL_FILES, *DEFERRED_FILES):
        (release / name).write_text("{}\n", encoding="utf-8")
    build_media_contract(release)
    return dist, release, manifest_path


def run_gate(dist: Path, release: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(SCRIPT), "--dist", str(dist), "--release", str(release)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class Museum04BudgetGateTests(unittest.TestCase):
    def test_valid_lazy_build_passes_and_reports_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            result = run_gate(dist, release)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("home js=", result.stdout)
        self.assertIn("route js=", result.stdout)
        self.assertIn("graph-summary=", result.stdout)
        self.assertIn("deferred-details=", result.stdout)
        self.assertIn("physical-media=242 files", result.stdout)
        self.assertIn("records=273 artwork-rows=44 initial-media=0 B/0 requests", result.stdout)

    def test_initial_media_address_and_image_preload_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            (release / "artists.json").write_text(
                json.dumps({"artists": [{"src": "assets/test-00/320w.jpg"}]}),
                encoding="utf-8",
            )
            (dist / "index.html").write_text(
                '<!doctype html><link rel="preload" as="image" href="assets/test.jpg">'
                '<img src="/Museum-Codex/releases/art-constellation-1.0.0/assets/test/320w.jpg">',
                encoding="utf-8",
            )
            (dist / "assets" / "index.css").write_text(
                '.hero{background-image:url("/Museum-Codex/releases/art-constellation-1.0.0/assets/test/640w.webp")}',
                encoding="utf-8",
            )
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("initial data addresses media", result.stderr)
        self.assertIn("initial image preload is forbidden", result.stderr)
        self.assertIn("initial HTML image address is forbidden", result.stderr)
        self.assertIn("initial CSS image address is forbidden", result.stderr)

    def test_media_manifest_hash_and_physical_closure_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            media_index = json.loads((release / "media-index.json").read_text(encoding="utf-8"))
            first_path = release / media_index["assets"][0]["src"]
            first_path.write_bytes(b"\xff\xd8\xffchanged")
            second_path = release / media_index["assets"][1]["src"]
            second_path.unlink()
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("manifest media byte count mismatch", result.stderr)
        self.assertIn("manifest media file is absent from physical closure", result.stderr)

    def test_hotlink_and_large_representative_thumbnail_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            media_index_path = release / "media-index.json"
            media_index = json.loads(media_index_path.read_text(encoding="utf-8"))
            media_index["assets"][0]["src"] = "https://example.invalid/hotlink.jpg"
            media_index["delivery_policy"]["external_runtime_api"] = True
            first_artwork = media_index["artworks"][0]
            first_artwork["representative_media_id"] = next(
                asset["id"] for asset in media_index["assets"]
                if asset["artwork_id"] == first_artwork["artwork_id"] and asset["width"] == 1600
            )
            media_index_path.write_text(json.dumps(media_index), encoding="utf-8")
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("bounded local JPEG/WebP path", result.stderr)
        self.assertIn("delivery_policy.external_runtime_api", result.stderr)
        self.assertIn("representative thumbnail must prefer 320w/640w", result.stderr)

    def test_graph_renderer_in_home_initial_closure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, manifest_path = create_build(Path(directory))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["index.html"]["imports"] = ["src/features/art-constellation/SigmaGraphRenderer.tsx"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("SigmaGraphRenderer is present in the home initial closure", result.stderr)
        self.assertIn("graph library fingerprint found", result.stderr)

    def test_missing_initial_json_and_external_runtime_request_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            (release / "search-index.json").unlink()
            (dist / "assets" / "index.js").write_text('fetch("https://example.invalid/api")', encoding="utf-8")
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("required file is missing: search-index.json", result.stderr)
        self.assertIn("external runtime JavaScript request", result.stderr)

    def test_repo_only_benchmark_harness_and_marker_cannot_ship(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            benchmark = dist / "benchmarks" / "scale-harness.js"
            benchmark.parent.mkdir()
            benchmark.write_text("__MUSEUM04_SCALE_BENCHMARK__", encoding="utf-8")
            fixture = dist / "fixtures" / "1k.json"
            fixture.parent.mkdir()
            fixture.write_text("{}", encoding="utf-8")
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("repo-only benchmark artifact was shipped", result.stderr)
        self.assertIn("repo-only benchmark marker was shipped", result.stderr)
        self.assertIn("synthetic scale fixture file was shipped", result.stderr)


if __name__ == "__main__":
    unittest.main()
