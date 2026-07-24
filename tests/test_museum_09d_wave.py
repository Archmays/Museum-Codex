from __future__ import annotations

import copy
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from museum_pipeline.art.expansion_wave_factory import (
    ROOT,
    _artifact_checkpoint,
    _initial_journal,
    build_schedule,
    compute_wave_input_hash,
    load_wave_plan,
    run_wave,
)
from scripts.classify_ci_impact import Change, classify_changes

PLAN_PATH = ROOT / "docs" / "05_roadmap" / "museum-09d-wave-01" / "release-plan.json"


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class Museum09DWaveFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_wave_plan(PLAN_PATH)
        cls.input_hash = compute_wave_input_hash(cls.plan)

    def test_three_batch_plan_and_release_chain_are_exact(self) -> None:
        self.assertEqual(
            [
                "museum-09-batch-03",
                "museum-09-batch-04",
                "museum-09-batch-05",
            ],
            [item.batch_id for item in self.plan.batches],
        )
        self.assertEqual(
            [
                ("release:art-expansion-batch-02-1.6.0", "release:art-expansion-batch-03-1.7.0"),
                ("release:art-expansion-batch-03-1.7.0", "release:art-expansion-batch-04-1.8.0"),
                ("release:art-expansion-batch-04-1.8.0", "release:art-expansion-batch-05-1.9.0"),
            ],
            [(item.predecessor_id, item.release_id) for item in self.plan.batches],
        )
        self.assertEqual([False, False, True], [item.deployment_eligible for item in self.plan.batches])

    def test_dry_run_has_no_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="museum-09d-dry-run-") as temporary:
            journal = Path(temporary) / "journal.json"
            result = run_wave(
                self.plan,
                batch_ids=[item.batch_id for item in self.plan.batches],
                through="release",
                journal_path=journal,
                dry_run=True,
            )
            self.assertEqual(0, result["writes"])
            self.assertFalse(journal.exists())
            self.assertEqual(9, len(result["schedule"]))

    def test_batch04_failure_resume_starts_at_failed_stage(self) -> None:
        journal = _initial_journal(self.plan, self.input_hash)
        with tempfile.TemporaryDirectory(prefix=".museum-09d-resume-", dir=ROOT) as temporary:
            root = Path(temporary) / "checkpoint"
            root.mkdir()
            _write_json(root / "build-manifest.json", {"artifact_content_hash": "sha256:" + "0" * 64})
            checkpoint = _artifact_checkpoint(root, "research")
            for stage in ("research", "media", "release"):
                journal["batches"][0]["stages"][stage] = {
                    "status": "committed",
                    "attempts": 1,
                    "checkpoint": checkpoint,
                    "error": None,
                }
            journal["batches"][1]["stages"]["research"] = {
                "status": "failed",
                "attempts": 1,
                "checkpoint": None,
                "error": {"type": "InjectedFailure", "message": "fixture"},
            }
            schedule = build_schedule(
                self.plan,
                journal,
                batch_ids=[item.batch_id for item in self.plan.batches],
                through="release",
                resume=True,
                from_batch=None,
                from_stage=None,
            )
            self.assertEqual(
                ("museum-09-batch-04", "research"),
                (schedule[0][0].batch_id, schedule[0][1]),
            )
            self.assertNotIn(
                "museum-09-batch-03",
                {batch.batch_id for batch, _stage in schedule},
            )

    def test_batch05_media_failure_resume_does_not_rebuild_research(self) -> None:
        journal = _initial_journal(self.plan, self.input_hash)
        with tempfile.TemporaryDirectory(prefix=".museum-09d-media-resume-", dir=ROOT) as temporary:
            root = Path(temporary) / "checkpoint"
            root.mkdir()
            _write_json(root / "build-manifest.json", {"artifact_content_hash": "sha256:" + "1" * 64})
            checkpoint = _artifact_checkpoint(root, "research")
            for batch in journal["batches"][:2]:
                for stage in ("research", "media", "release"):
                    batch["stages"][stage] = {
                        "status": "committed",
                        "attempts": 1,
                        "checkpoint": checkpoint,
                        "error": None,
                    }
            journal["batches"][2]["stages"]["research"] = {
                "status": "committed",
                "attempts": 1,
                "checkpoint": checkpoint,
                "error": None,
            }
            journal["batches"][2]["stages"]["media"] = {
                "status": "failed",
                "attempts": 1,
                "checkpoint": None,
                "error": {"type": "InjectedFailure", "message": "fixture"},
            }
            schedule = build_schedule(
                self.plan,
                journal,
                batch_ids=[item.batch_id for item in self.plan.batches],
                through="release",
                resume=True,
                from_batch=None,
                from_stage=None,
            )
            self.assertEqual(
                [("museum-09-batch-05", "media"), ("museum-09-batch-05", "release")],
                [(batch.batch_id, stage) for batch, stage in schedule],
            )

    def test_invalid_closure_and_forged_or_unplanned_batches_are_rejected(self) -> None:
        cases = []
        invalid_closure = copy.deepcopy(self.plan.document)
        invalid_closure["batches"][0]["input_closure_hash"] = "sha256:" + "0" * 64
        cases.append(invalid_closure)
        forged = copy.deepcopy(self.plan.document)
        forged["batches"][0]["batch_id"] = "museum-09-batch-99"
        cases.append(forged)
        unplanned = copy.deepcopy(self.plan.document)
        unplanned["batches"][-1]["batch_id"] = "museum-09-batch-06"
        cases.append(unplanned)
        with tempfile.TemporaryDirectory(prefix="museum-09d-invalid-plan-") as temporary:
            for index, document in enumerate(cases):
                path = Path(temporary) / f"case-{index}.json"
                _write_json(path, document)
                with self.assertRaises(ValueError):
                    load_wave_plan(path)

    def test_only_final_release_can_receive_deployment_eligibility(self) -> None:
        invalid = copy.deepcopy(self.plan.document)
        invalid["batches"][0]["deployment_eligible"] = True
        with tempfile.TemporaryDirectory(prefix="museum-09d-deploy-plan-") as temporary:
            path = Path(temporary) / "plan.json"
            _write_json(path, invalid)
            with self.assertRaisesRegex(ValueError, "only the final release"):
                load_wave_plan(path)

    def test_generic_v2_writer_contains_no_phase_date_reviewer_or_scope_constants(self) -> None:
        source = (
            ROOT / "museum_pipeline" / "art" / "expansion_wave_factory.py"
        ).read_text(encoding="utf-8")
        forbidden = [
            self.plan.legacy_adapter["template_phase_id"],
            self.plan.legacy_adapter["template_reviewer_id"],
            self.plan.legacy_adapter["template_actor_id"],
            *self.plan.legacy_adapter["template_scopes"],
            self.plan.phase_id,
            self.plan.reviewer_id,
            self.plan.authorization_scope,
        ]
        for value in forbidden:
            self.assertNotIn(value, source)
        self.assertIsNone(re.search(r"20\d{2}-\d{2}-\d{2}", source))

    def test_cli_exposes_required_recovery_and_deployment_controls(self) -> None:
        completed = subprocess.run(
            ["python", "scripts/run_museum_expansion_wave.py", "--help"],
            cwd=ROOT,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        )
        for option in (
            "--dry-run",
            "--resume",
            "--from-batch",
            "--from-stage",
            "--journal",
            "--no-deploy",
        ):
            self.assertIn(option, completed.stdout)

    def test_online_verifier_cli_is_directly_executable(self) -> None:
        completed = subprocess.run(
            ["python", "scripts/verify_museum_09d_wave_online.py", "--help"],
            cwd=ROOT,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        )
        self.assertIn("--base-url", completed.stdout)
        self.assertIn("--commit", completed.stdout)

    def test_generated_release_schemas_are_deterministic_and_version_bound(self) -> None:
        subprocess.run(
            ["python", "scripts/generate_expansion_release_schemas.py", "--check"],
            cwd=ROOT,
            check=True,
        )
        expected_counts = {"170": 160, "180": 209, "190": 258}
        for suffix, count in expected_counts.items():
            schema = json.loads(
                (
                    ROOT
                    / "schemas"
                    / "art"
                    / "release"
                    / f"artist-narrative-v{suffix}.schema.json"
                ).read_text(encoding="utf-8")
            )
            narratives = schema["properties"]["narratives"]
            self.assertEqual((count, count), (narratives["minItems"], narratives["maxItems"]))

    def test_web_contract_paths_are_exact_docs_only_and_descendants_fail_closed(self) -> None:
        paths = [
            "docs/qa/museum-09d-wave-01/web-preflight-audit.md",
            "docs/05_roadmap/museum-09d-wave-01-execution-contract.md",
            "docs/01_architecture/adr/ADR-0012-multi-batch-wave-release-and-single-deployment.md",
        ]
        result = classify_changes([Change(status="M", path=path) for path in paths])
        self.assertTrue(result["docs_only"])
        self.assertEqual("docs-only", result["impact_level"])
        self.assertFalse(result["deploy_required"])
        for path in paths:
            disguised = classify_changes([Change(status="M", path=path + "/descendant.md")])
            self.assertFalse(disguised["docs_only"])

    def test_generated_release_chain_counts_and_predecessors_are_exact(self) -> None:
        expected = [
            (160, 1502, "release:art-expansion-batch-02-1.6.0"),
            (209, 1987, "release:art-expansion-batch-03-1.7.0"),
            (258, 2471, "release:art-expansion-batch-04-1.8.0"),
        ]
        for batch, (artist_count, artwork_count, predecessor) in zip(
            self.plan.batches, expected, strict=True
        ):
            root = ROOT / batch.release_path
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            validation = json.loads(
                (root / "validation-summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(batch.release_id, manifest["id"])
            self.assertEqual(predecessor, manifest["predecessor"])
            self.assertEqual(artist_count, validation["counts"]["artists"])
            self.assertEqual(artwork_count, validation["counts"]["artworks"])
            self.assertEqual(artist_count, validation["child_facing_intro_count"])
            self.assertEqual(
                artist_count,
                validation["child_facing_intro_provenance_count"],
            )
            self.assertEqual(0, validation["duplicate_intro_count"])

    def test_object_level_media_review_is_complete_and_adds_no_bytes(self) -> None:
        for batch in self.plan.batches:
            root = ROOT / batch.media_path
            decisions = json.loads(
                (root / "object-media-decisions.json").read_text(encoding="utf-8")
            )["records"]
            self.assertEqual(batch.artwork_count, len(decisions))
            self.assertTrue(
                all(item["object_level_review_complete"] is True for item in decisions)
            )
            self.assertTrue(
                all(item["technical_media_locator_present"] is False for item in decisions)
            )
            self.assertTrue(
                all(
                    item["decision"] == "metadata_only_after_media_review"
                    for item in decisions
                )
            )
            self.assertEqual([], json.loads((root / "originals.json").read_text(encoding="utf-8"))["records"])
            self.assertEqual([], json.loads((root / "derivatives.json").read_text(encoding="utf-8"))["records"])

    def test_cross_batch_and_final_only_deployment_contracts_pass(self) -> None:
        cross_batch = json.loads(self.plan.cross_batch_report_path.read_text(encoding="utf-8"))
        marker = json.loads(self.plan.deployment_marker_path.read_text(encoding="utf-8"))
        self.assertEqual("pass", cross_batch["status"])
        self.assertEqual(147, cross_batch["counts"]["new_artists"])
        self.assertEqual(1454, cross_batch["counts"]["new_artworks"])
        self.assertEqual(147, cross_batch["counts"]["new_child_facing_intros"])
        self.assertEqual(0, cross_batch["counts"]["duplicate_intros"])
        self.assertEqual(0, cross_batch["intermediate_deployment_count"])
        self.assertEqual(self.plan.final_release_id, marker["release_id"])
        self.assertTrue(marker["deployment_eligible"])
        self.assertEqual(1, marker["expected_runtime_deployment_count"])
        self.assertEqual(0, marker["intermediate_deployment_count"])
        self.assertTrue(
            all(
                item["deployment_eligible"] is False
                for item in marker["intermediate_releases"]
            )
        )

    def test_canonical_journal_closes_all_nine_stages(self) -> None:
        journal = json.loads(self.plan.journal_path.read_text(encoding="utf-8"))
        self.assertEqual("release_chain_committed", journal["status"])
        stages = [
            state
            for batch in journal["batches"]
            for state in batch["stages"].values()
        ]
        self.assertEqual(9, len(stages))
        self.assertTrue(all(item["status"] == "committed" for item in stages))
        self.assertTrue(all(item["checkpoint"] for item in stages))


if __name__ == "__main__":
    unittest.main()
