from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_GATE = ROOT / ".github" / "workflows" / "full-gate.yml"
VALIDATION = ROOT / ".github" / "workflows" / "validate-and-build.yml"
DEPLOYMENT = ROOT / ".github" / "workflows" / "deploy-pages.yml"


class Museum04WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.full = FULL_GATE.read_text(encoding="utf-8")
        cls.validation = VALIDATION.read_text(encoding="utf-8")
        cls.deployment = DEPLOYMENT.read_text(encoding="utf-8")
        cls.all_workflows = "\n".join((cls.full, cls.validation, cls.deployment))

    def test_release_rights_and_projection_gates_are_required(self) -> None:
        full_gate_required = (
            "python scripts/validate_museum_04_issue_form.py",
            "python -m museum_pipeline.media validate-bundle --json",
            "python scripts/validate_museum_04_release.py public/releases/art-constellation-1.0.0 --require-public",
            "python scripts/scan_public_artifact_for_candidate_data.py public --label-set",
            "python scripts/scan_public_artifact_for_candidate_data.py dist --label-set",
        )
        for command in full_gate_required:
            with self.subTest(command=command):
                self.assertIn(command, self.full)
        for command in (
            "python scripts/build_museum_04_release.py --output tmp/museum-04-ci-release",
            "diff -ru public/releases/art-constellation-1.0.0 tmp/museum-04-ci-release",
        ):
            with self.subTest(phase_scoped_command=command):
                self.assertIn(command, self.validation)
                self.assertNotIn(command, self.full)
        self.assertIn("python scripts/validate_release_integrity_ledger.py --require-candidate", self.full)

    def test_performance_loader_and_fallback_gates_run_before_upload(self) -> None:
        required = (
            "docs/qa/museum-04/performance-current-graph.json",
            "docs/qa/museum-04/performance-scale-benchmarks.json",
            "python scripts/validate_museum_05a.py",
            "docs/qa/museum-05a/performance.json",
            "node --test tests/test_museum_04_*_lab_runner.mjs",
            "npm run test:e2e",
            "npm run check:museum-09b-search",
            "npm run check:museum-09b-budgets",
        )
        upload_index = self.full.index("actions/upload-pages-artifact")
        python_tests_index = self.full.index("python scripts/run_offline_python_tests.py")
        node_setup_index = self.full.index("actions/setup-node")
        npm_install_index = self.full.index("run: npm ci")
        for command in required:
            with self.subTest(command=command):
                self.assertLess(self.full.index(command), upload_index)
        self.assertLess(node_setup_index, python_tests_index)
        self.assertLess(npm_install_index, python_tests_index)
        self.assertIn("path: dist", self.full)
        self.assertNotIn("actions/deploy-pages", self.full)
        self.assertIn("actions/deploy-pages", self.deployment)
        self.assertIn("needs: [classify, phase-scoped, final-full]", self.validation)
        self.assertNotIn("check:museum-06-budgets", self.full)
        self.assertNotIn("check:museum-07-budgets", self.full)
        self.assertNotIn("check:museum-04-budgets", self.full)
        self.assertNotIn("verify-museum-05a-budgets.mjs", self.full)

    def test_ci_remains_offline_and_never_acquires_live_media(self) -> None:
        forbidden = (
            "museum_pipeline acquire",
            "museum_pipeline.media acquire",
            "--live",
            "curl ",
            "wget ",
            "build-selection-pool",
            "build-approved-batch",
            "build-graph-input",
        )
        lowered = self.all_workflows.lower()
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
