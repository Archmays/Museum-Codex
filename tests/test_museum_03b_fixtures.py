from __future__ import annotations

import json
import unittest
from pathlib import Path

from museum_pipeline.art.fixtures import (
    INVALID_ROOT,
    VALID_ROOT,
    build_synthetic_batch,
    evaluate_art_batch_fixture,
    probe_legacy_contracts,
    validate_fixture_matrix,
    validate_synthetic_batch,
)


class Museum03BFixtureTests(unittest.TestCase):
    def test_base_batch_is_complete_and_entirely_synthetic(self) -> None:
        batch = build_synthetic_batch()
        self.assertEqual([], sorted(validate_synthetic_batch(batch)))
        self.assertEqual(12, len(batch["artists"]))
        self.assertEqual(44, len(batch["artworks"]))
        self.assertEqual(36, len(batch["relationships"]))
        self.assertEqual(44, len(batch["media_assessments"]))
        serialized = json.dumps(batch, ensure_ascii=False)
        for real_name in (
            "Dürer",
            "Goya",
            "van Gogh",
            "Cassatt",
            "Kollwitz",
            "Cameron",
            "Hokusai",
            "Utamaro",
            "Shen Zhou",
            "Ravi Varma",
            "Posada",
            "Tanner",
        ):
            self.assertNotIn(real_name, serialized)

    def test_every_valid_fixture_passes(self) -> None:
        paths = sorted(VALID_ROOT.glob("*.json"))
        self.assertEqual(4, len(paths))
        for path in paths:
            case = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.name):
                self.assertEqual(set(), evaluate_art_batch_fixture(case))

    def test_every_expected_invalid_fixture_fails_with_exact_declared_code(self) -> None:
        paths = sorted(INVALID_ROOT.glob("*.json"))
        self.assertEqual(69, len(paths))
        coverage: set[int] = set()
        count_variants: list[str] = []
        for path in paths:
            case = json.loads(path.read_text(encoding="utf-8"))
            coverage.add(case["case_number"])
            if case["case_number"] == 5:
                count_variants.append(case["behavior"])
            with self.subTest(path=path.name):
                self.assertEqual({case["expected_error"]}, evaluate_art_batch_fixture(case))
        self.assertEqual(set(range(1, 69)), coverage)
        self.assertEqual({"11 approved artists", "13 approved artists"}, set(count_variants))

    def test_matrix_validator_reports_all_numbered_behaviors(self) -> None:
        result = validate_fixture_matrix()
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(4, result["valid_fixtures"])
        self.assertEqual(69, result["invalid_fixtures"])
        self.assertEqual(68, result["numbered_behaviors"])

    def test_case_68_runs_real_legacy_validator_hooks(self) -> None:
        results = probe_legacy_contracts()
        self.assertEqual({"pipeline", "curation", "governance"}, set(results))
        self.assertIn("secret_in_url", results["pipeline"])
        self.assertIn("schema", results["curation"])
        self.assertIn("algorithmic_influence", results["governance"])
        case = json.loads((INVALID_ROOT / "68-legacy-regression.json").read_text(encoding="utf-8"))
        self.assertEqual({"legacy_fixture_regression_detected"}, evaluate_art_batch_fixture(case))

    def test_valid_unknown_date_preserves_unknown_precision(self) -> None:
        case_path = VALID_ROOT / "explicit-unknown-artwork-date.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        self.assertEqual(set(), evaluate_art_batch_fixture(case))


if __name__ == "__main__":
    unittest.main()
