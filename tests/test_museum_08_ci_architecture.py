from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.classify_ci_impact import _parse_name_status, classify_changes, write_github_outputs
from scripts.generate_release_integrity_ledger import closure_path_record
from scripts.validate_docs_only import validate as validate_docs_only_path
from scripts.validate_release_integrity_ledger import validate_ledger

ROOT = Path(__file__).resolve().parents[1]


class Museum08CiImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "museum-08" / "ci-impact-cases.json").read_text(encoding="utf-8")
        )

    def test_all_synthetic_change_cases(self) -> None:
        self.assertGreaterEqual(len(self.fixture["cases"]), 20)
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                result = classify_changes(
                    _parse_name_status(case["paths"]),
                    case.get("mode", "auto"),
                    first_push=case.get("first_push", False),
                )
                for key, expected in case["expect"].items():
                    if key in {"affected_phases", "releases_to_rebuild", "releases_hash_only", "browser_suites", "reason_codes"}:
                        self.assertTrue(set(expected).issubset(set(result[key])), (key, expected, result[key]))
                    else:
                        self.assertEqual(expected, result[key], (key, result))

    def test_docs_only_has_zero_heavy_work_and_zero_deploy(self) -> None:
        result = classify_changes(_parse_name_status(["M\tdocs/qa/museum-08/note.md"]))
        self.assertTrue(result["docs_only"])
        self.assertFalse(result["full_required"])
        self.assertFalse(result["deploy_required"])
        self.assertEqual([], result["releases_to_rebuild"])
        self.assertEqual([], result["browser_suites"])

    def test_closure_path_hash_normalizes_cross_platform_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf_path = root / "lf.json"
            crlf_path = root / "crlf.json"
            lf_path.write_bytes(b'{\n  "status": "pass"\n}\n')
            crlf_path.write_bytes(b'{\r\n  "status": "pass"\r\n}\r\n')
            lf_record = closure_path_record(lf_path, "evidence.json")
            crlf_record = closure_path_record(crlf_path, "evidence.json")
            self.assertEqual(lf_record, crlf_record)

    def test_docs_only_validator_accepts_png_evidence_without_text_decoding(self) -> None:
        screenshot = ROOT / "docs" / "qa" / "museum-08" / "screenshots" / "search-empty-390x844.png"
        if not screenshot.exists():
            self.skipTest("M08 screenshot evidence is added in the same implementation wave")
        self.assertEqual([], validate_docs_only_path(screenshot))

    def test_phase_local_rebuilds_only_current_phase(self) -> None:
        result = classify_changes(_parse_name_status(["M\tmuseum_pipeline/art/candidate.py"]))
        self.assertEqual(["release:art-v1-candidate-1.4.0"], result["releases_to_rebuild"])
        self.assertEqual(
            {
                "release:art-constellation-1.0.0",
                "release:art-gallery-interactions-1.1.0",
                "release:art-pathways-1.2.0",
                "release:art-time-place-1.3.0",
            },
            set(result["releases_hash_only"]),
        )

    def test_github_outputs_are_single_line_json(self) -> None:
        result = classify_changes(_parse_name_status(["M\tsrc/features/art-search/search.ts"]))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            write_github_outputs(result, output)
            values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
        self.assertEqual("true", values["runtime_changed"])
        self.assertEqual(["search"], json.loads(values["browser_suites"]))

    def test_workflow_concurrency_and_deploy_boundaries_are_declared(self) -> None:
        validation = (ROOT / ".github" / "workflows" / "validate-and-build.yml")
        deployment = (ROOT / ".github" / "workflows" / "deploy-pages.yml")
        if not validation.exists() or not deployment.exists():
            self.skipTest("workflow split is added in the same implementation wave")
        validation_text = validation.read_text(encoding="utf-8")
        deployment_text = deployment.read_text(encoding="utf-8")
        self.assertIn("museum-validate-${{ github.ref }}", validation_text)
        self.assertIn("cancel-in-progress: true", validation_text)
        self.assertIn("group: pages", deployment_text)
        self.assertIn("cancel-in-progress: false", deployment_text)
        self.assertIn("deploy_required", validation_text)

    def test_release_ledger_detects_manifest_and_builder_tamper(self) -> None:
        source = ROOT / "governance" / "release-integrity-ledger.json"
        if not source.exists():
            self.skipTest("ledger is generated in the same implementation wave")
        ledger = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            tampered_path = Path(directory) / "ledger.json"
            tampered = deepcopy(ledger)
            tampered["releases"][0]["manifest_sha256"] = "sha256:" + "0" * 64
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            result = validate_ledger(tampered_path)
            self.assertFalse(result["ok"])
            self.assertIn("manifest_sha_drift", {failure["code"] for failure in result["failures"]})

            tampered = deepcopy(ledger)
            tampered["releases"][0]["builder"]["items"][0]["sha256"] = "sha256:" + "1" * 64
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            result = validate_ledger(tampered_path)
            self.assertFalse(result["ok"])
            self.assertIn("builder_drift", {failure["code"] for failure in result["failures"]})


if __name__ == "__main__":
    unittest.main()
