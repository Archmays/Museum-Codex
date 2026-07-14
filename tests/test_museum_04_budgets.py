from __future__ import annotations

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
)


def create_build(root: Path) -> tuple[Path, Path, Path]:
    dist = root / "dist"
    assets = dist / "assets"
    release = dist / "releases" / "art-constellation-0.1.0"
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
            (release / "rights.json").write_text(
                json.dumps({"media": {"bytes": 0, "count": 0, "downloaded": False, "statement": {"en": "No media."}}}),
                encoding="utf-8",
            )
            result = run_gate(dist, release)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("home js=", result.stdout)
        self.assertIn("route js=", result.stdout)
        self.assertIn("graph-summary=", result.stdout)
        self.assertIn("deferred-details=", result.stdout)

    def test_nonzero_or_addressable_media_envelope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist, release, _ = create_build(Path(directory))
            (release / "rights.json").write_text(
                json.dumps({"media": {"bytes": 0, "count": 0, "downloaded": False, "url": "https://example.invalid/art.jpg"}}),
                encoding="utf-8",
            )
            result = run_gate(dist, release)
        self.assertEqual(1, result.returncode)
        self.assertIn("non-empty media field at rights.json.media", result.stderr)

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
