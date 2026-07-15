from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages.yml"


class Museum04WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_release_rights_and_projection_gates_are_required(self) -> None:
        required = (
            "python scripts/validate_museum_04_issue_form.py",
            "python -m museum_pipeline.media validate-bundle --json",
            "python scripts/build_museum_04_release.py --output tmp/museum-04-ci-release",
            "diff -ru public/releases/art-constellation-1.0.0 tmp/museum-04-ci-release",
            "python scripts/validate_museum_04_release.py public/releases/art-constellation-1.0.0 --require-public",
            "python scripts/scan_public_artifact_for_candidate_data.py public --label-set",
            "python scripts/scan_public_artifact_for_candidate_data.py dist --label-set",
        )
        for command in required:
            with self.subTest(command=command):
                self.assertIn(command, self.text)

    def test_performance_loader_and_fallback_gates_run_before_upload(self) -> None:
        required = (
            "python scripts/validate_museum_04_performance_evidence.py",
            "python scripts/validate_museum_05a.py",
            "python scripts/validate_museum_05a_performance.py",
            "node --test tests/test_museum_04_*_lab_runner.mjs",
            "node scripts/verify-museum-04-budgets.mjs",
            "node scripts/verify-museum-05a-budgets.mjs",
            "npm run test:e2e",
        )
        upload_index = self.text.index("actions/upload-pages-artifact")
        deploy_index = self.text.index("actions/deploy-pages")
        python_tests_index = self.text.index("python scripts/run_offline_python_tests.py")
        node_setup_index = self.text.index("actions/setup-node")
        npm_install_index = self.text.index("run: npm ci")
        for command in required:
            with self.subTest(command=command):
                self.assertLess(self.text.index(command), upload_index)
                self.assertLess(self.text.index(command), deploy_index)
        self.assertLess(node_setup_index, python_tests_index)
        self.assertLess(npm_install_index, python_tests_index)
        self.assertIn("path: dist", self.text)
        self.assertIn("deploy:\n    needs: build", self.text)

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
        lowered = self.text.lower()
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
