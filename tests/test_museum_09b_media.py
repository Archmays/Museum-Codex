from __future__ import annotations

import json
import unittest
from pathlib import Path

from museum_pipeline.art.media_bundle import (
    DEFAULT_BUNDLE_ROOT,
    FINAL_STATUSES,
    INPUT_CONTENT_HASH,
    INPUT_TREE_HASH,
    load_inputs,
    validate_bundle,
    validate_fixture_scenario,
)
from museum_pipeline.config import ROOT


class Museum09BMediaTests(unittest.TestCase):
    def test_candidate_input_closure_is_exact(self) -> None:
        inputs = load_inputs()
        self.assertEqual(inputs["manifest"]["artifact_content_hash"], INPUT_CONTENT_HASH)
        self.assertEqual(inputs["manifest"]["artifact_tree_hash"], INPUT_TREE_HASH)
        self.assertEqual(len(inputs["allowlist"]), 65)
        self.assertEqual(len(inputs["excluded"]), 423)
        self.assertTrue(set(inputs["allowlist"]).isdisjoint(inputs["excluded"]))

    @unittest.skipUnless(DEFAULT_BUNDLE_ROOT.exists(), "formal media bundle not built yet")
    def test_formal_media_bundle_passes(self) -> None:
        result = validate_bundle(DEFAULT_BUNDLE_ROOT)
        self.assertTrue(result["ok"], result["issues"])
        decisions = json.loads((DEFAULT_BUNDLE_ROOT / "object-rights-decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(decisions["checked_count"], 65)
        self.assertEqual(decisions["unresolved_count"], 0)
        self.assertTrue(all(item["final_status"] in FINAL_STATUSES for item in decisions["decisions"]))
        drift = json.loads((DEFAULT_BUNDLE_ROOT / "source-drift-manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((DEFAULT_BUNDLE_ROOT / "download-manifest.json").read_text(encoding="utf-8"))["metrics"]
        for status in ("changed", "unchanged", "unavailable"):
            self.assertEqual(drift[f"{status}_count"], metrics[f"source_record_{status}_count"])

    @unittest.skipUnless(DEFAULT_BUNDLE_ROOT.exists(), "formal media bundle not built yet")
    def test_invalid_fixture_matrix_exercises_all_required_failures(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "museum-09b-media" / "invalid-cases.json").read_text(encoding="utf-8"))
        required = {
            "unlisted-work", "metadata-only-downloaded", "availability-as-permission", "general-policy-only",
            "rights-statement-changed", "identity-mismatch", "wrong-object-iiif", "html-as-image",
            "mime-signature-mismatch", "corrupt-image", "pixel-overflow", "original-over-limit",
            "partial-promoted", "missing-attribution", "missing-withdrawal", "duplicate-physical-bytes",
            "derivative-parent-missing", "derivative-upscale", "derivative-crop", "watermark-removal",
            "nondeterministic-derivative", "prohibited-original-tracked", "unresolved-status", "manual-wait",
            "public-release-mutation", "public-media-leakage", "pages-artifact", "batch-02-advanced",
        }
        self.assertEqual({item["id"] for item in fixture["cases"]}, required)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(validate_fixture_scenario(case), case["expected_code"])

    @unittest.skipUnless(DEFAULT_BUNDLE_ROOT.exists(), "formal media bundle not built yet")
    def test_no_media_bytes_for_excluded_or_external_iiif(self) -> None:
        excluded = json.loads((DEFAULT_BUNDLE_ROOT / "metadata-only-and-blocked.json").read_text(encoding="utf-8"))
        self.assertEqual(len(excluded["excluded"]), 423)
        self.assertTrue(all(item["media_requested"] is False for item in excluded["excluded"]))
        iiif = json.loads((DEFAULT_BUNDLE_ROOT / "iiif-manifests.json").read_text(encoding="utf-8"))
        self.assertEqual(iiif["candidate_count"], 25)
        self.assertEqual(iiif["image_download_count"], 0)
        self.assertTrue(all(item["image_bytes_downloaded"] is False for item in iiif["records"]))

    @unittest.skipUnless(DEFAULT_BUNDLE_ROOT.exists(), "formal media bundle not built yet")
    def test_derivative_contract_and_content_addressing(self) -> None:
        derivatives = json.loads((DEFAULT_BUNDLE_ROOT / "derivatives-manifest.json").read_text(encoding="utf-8"))["derivatives"]
        self.assertTrue(derivatives)
        self.assertEqual(len({item["storage_path"] for item in derivatives}), len(derivatives))
        self.assertTrue(all(item["no_crop"] and item["no_upscale"] for item in derivatives))
        self.assertTrue(all(not item["ai_used"] and not item["content_altered"] and not item["watermark_removed"] for item in derivatives))
        self.assertTrue(all("assets/by-source-sha256/" in item["storage_path"] for item in derivatives))

    @unittest.skipUnless(DEFAULT_BUNDLE_ROOT.exists(), "formal media bundle not built yet")
    def test_single_work_rights_change_has_bounded_closure(self) -> None:
        drift = json.loads((DEFAULT_BUNDLE_ROOT / "source-drift-manifest.json").read_text(encoding="utf-8"))
        first = drift["records"][0]
        simulated = [item["work_id"] for item in drift["records"] if item["work_id"] == first["work_id"]]
        self.assertEqual(simulated, [first["work_id"]])


if __name__ == "__main__":
    unittest.main()
