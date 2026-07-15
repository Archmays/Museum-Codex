from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import museum_pipeline.media.bundle as media_bundle
from museum_pipeline.canonical_json import write_canonical_json
from museum_pipeline.hashing import canonical_sha256, sha256_file
from museum_pipeline.media.bundle import _verified_source_bytes, validate_bundle
from museum_pipeline.media.constants import BUNDLE_ROOT, LEDGER_PATH


class MediaBundleTests(unittest.TestCase):
    def _copy_bundle(self, temporary: str) -> tuple[Path, Path]:
        target = Path(temporary) / "media-bundle-v1"

        def copy_file(source: str, destination: str) -> str:
            if Path(source).suffix == ".json":
                return shutil.copy2(source, destination)
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)
            return destination

        shutil.copytree(BUNDLE_ROOT, target, copy_function=copy_file)
        ledger = Path(temporary) / "media-source-ledger.json"
        shutil.copy2(LEDGER_PATH, ledger)
        return target, ledger

    def _refresh_manifest(self, root: Path, *, relative: str | None = None) -> None:
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if relative is not None:
            target = root / relative
            entry = next(item for item in manifest["manifest_files"] if item["path"] == relative)
            entry["sha256"] = sha256_file(target)
            entry["bytes"] = target.stat().st_size
        manifest["content_hash"] = canonical_sha256(
            {key: value for key, value in manifest.items() if key != "content_hash"}
        )
        write_canonical_json(manifest_path, manifest)

    def _refresh_ledger(self, root: Path, ledger_path: Path, ledger: dict) -> None:
        ledger["content_hash"] = canonical_sha256(
            {key: value for key, value in ledger.items() if key != "content_hash"}
        )
        write_canonical_json(ledger_path, ledger)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["ledger_sha256"] = sha256_file(ledger_path)
        manifest["content_hash"] = canonical_sha256(
            {key: value for key, value in manifest.items() if key != "content_hash"}
        )
        write_canonical_json(manifest_path, manifest)

    def test_tracked_bundle_closes_without_original_vault(self) -> None:
        result = validate_bundle()
        self.assertTrue(result["ok"], result["issues"][:8])
        self.assertEqual(44, result["counts"]["artworks_reviewed"])
        self.assertEqual(242, result["counts"]["media_files"])
        self.assertEqual(35_907_176, result["counts"]["media_bytes"])

    def test_ledger_has_exact_44_terminal_decisions_and_actual_byte_counts(self) -> None:
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        self.assertEqual(44, len(ledger["entries"]))
        self.assertEqual(
            {
                "approved_external_delivery": 0,
                "approved_self_hosted": 31,
                "blocked_identity_conflict": 0,
                "blocked_quality_failure": 0,
                "blocked_rights_conflict": 2,
                "blocked_source_unavailable": 4,
                "metadata_only_after_automated_review": 7,
            },
            ledger["counts"],
        )
        self.assertEqual(31, ledger["original_downloads"])
        self.assertEqual(75_611_836, ledger["original_bytes"])
        self.assertEqual(242, ledger["derivative_count"])
        self.assertEqual(35_907_176, ledger["derivative_bytes"])

    def test_public_bundle_manifest_contains_only_approved_derivatives(self) -> None:
        manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
        media_entries = [item for item in manifest["manifest_files"] if item["record_type"] == "media"]
        self.assertEqual(242, len(media_entries))
        self.assertEqual(set(manifest["approved_media_ids"]), {item["record_ids"][0] for item in media_entries})
        self.assertFalse(any("original" in item["path"] or "media-source" in item["path"] for item in media_entries))
        self.assertTrue(all(item["path"].startswith("assets/") for item in media_entries))

    def test_physical_validator_rejects_a_hash_drift_without_changing_files(self) -> None:
        original = sha256_file

        def drift(path: Path, *, prefixed: bool = True) -> str:
            value = original(path, prefixed=prefixed)
            if Path(path).name == "320w.jpg" and "assets" in Path(path).parts:
                return "sha256:" + "0" * 64 if prefixed else "0" * 64
            return value

        with patch.object(media_bundle, "sha256_file", side_effect=drift):
            result = validate_bundle()
        self.assertFalse(result["ok"])
        self.assertTrue(any(issue.startswith("hash_mismatch:assets/") for issue in result["issues"]))

    def test_source_bytes_changed_after_review_are_rejected_before_derivation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "original.jpg"
            source.write_bytes(b"reviewed bytes")
            record = {
                "artwork_id": "artwork:test",
                "byte_length": source.stat().st_size,
                "sha256": sha256_file(source),
            }
            source.write_bytes(b"tampered bytes")
            with self.assertRaisesRegex(ValueError, "source bytes drifted"):
                _verified_source_bytes(source, record)

    def test_validator_rejects_schema_valid_rights_document_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            relative = "attributions.json"
            document = json.loads((root / relative).read_text(encoding="utf-8"))
            document["assets"][0]["license_url"] = "https://example.com/wrong-license"
            write_canonical_json(root / relative, document)
            self._refresh_manifest(root, relative=relative)
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        self.assertTrue(any(issue.startswith("attribution_rights_mismatch:") for issue in result["issues"]))

    def test_validator_rejects_rehashed_attribution_changes_statement_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            relative = "attributions.json"
            document = json.loads((root / relative).read_text(encoding="utf-8"))
            media_id = document["assets"][0]["asset_id"]
            document["assets"][0]["changes_statement"] = (
                "AI inpainting and generative fill were used, with watermark removal."
            )
            write_canonical_json(root / relative, document)
            self._refresh_manifest(root, relative=relative)
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        self.assertIn(f"attribution_changes_statement_mismatch:{media_id}", result["issues"])

    def test_validator_rejects_rehashed_transform_step_and_processor_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            relative = "derivative-records.json"
            derivatives = json.loads((root / relative).read_text(encoding="utf-8"))
            without_icc = next(item for item in derivatives if "icc_normalization" not in item["transform_steps"])
            with_icc = next(item for item in derivatives if "icc_normalization" in item["transform_steps"])
            version_drift = next(item for item in derivatives if item["id"] not in {without_icc["id"], with_icc["id"]})
            without_icc["transform_steps"].append("icc_normalization")
            without_icc["transform_steps"].sort()
            with_icc["transform_steps"].remove("icc_normalization")
            version_drift["transform_version"] = "999.0.0"
            write_canonical_json(root / relative, derivatives)
            self._refresh_manifest(root, relative=relative)
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        for derivative in (without_icc, with_icc, version_drift):
            self.assertIn(f"derivative_transform_closure_mismatch:{derivative['id']}", result["issues"])

    def test_validator_returns_structured_failure_for_manifest_entry_missing_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["manifest_files"] if item["record_type"] == "media")
            relative = entry["path"]
            del entry["bytes"]
            manifest["content_hash"] = canonical_sha256(
                {key: value for key, value in manifest.items() if key != "content_hash"}
            )
            write_canonical_json(manifest_path, manifest)
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        self.assertIn(f"manifest_entry_bytes_invalid:{relative}", result["issues"])

    def test_validator_rejects_canonical_source_rule_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            relative = "source-rules-snapshot.json"
            document = json.loads((root / relative).read_text(encoding="utf-8"))
            source = document["sources"][0]
            source["license_rules"][0]["rule_id"] = "tampered_media_rule"
            source["license_rules_snapshot_hash"] = canonical_sha256(source["license_rules"])
            write_canonical_json(root / relative, document)
            self._refresh_manifest(root, relative=relative)
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        self.assertIn("source_rules_canonical_binding_mismatch", result["issues"])

    def test_validator_rejects_well_formed_m03b_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger_path = self._copy_bundle(temporary)
            wrong_hash = "sha256:" + "0" * 64
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["m03b_package_hash"] = wrong_hash
            ledger["m03b_graph_hash"] = wrong_hash
            self._refresh_ledger(root, ledger_path, ledger)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["m03b_package_hash"] = wrong_hash
            manifest["m03b_graph_hash"] = wrong_hash
            manifest["content_hash"] = canonical_sha256(
                {key: value for key, value in manifest.items() if key != "content_hash"}
            )
            write_canonical_json(manifest_path, manifest)
            result = validate_bundle(root, ledger_path)
        self.assertFalse(result["ok"])
        self.assertIn("manifest_m03b_package_hash_mismatch", result["issues"])
        self.assertIn("ledger_m03b_graph_hash_mismatch", result["issues"])

    def test_validator_rejects_parent_and_review_reference_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger = self._copy_bundle(temporary)
            bytes_records = json.loads((root / "byte-records.json").read_text(encoding="utf-8"))
            derivatives = json.loads((root / "derivative-records.json").read_text(encoding="utf-8"))
            derivatives[0]["parent_byte_record_id"] = bytes_records[1]["id"]
            derivatives[0]["source_sha256"] = bytes_records[1]["sha256"]
            write_canonical_json(root / "derivative-records.json", derivatives)
            self._refresh_manifest(root, relative="derivative-records.json")
            reviews = json.loads((root / "automated-reviews.json").read_text(encoding="utf-8"))
            reviews[0]["cross_check_id"] = reviews[1]["cross_check_id"]
            write_canonical_json(root / "automated-reviews.json", reviews)
            self._refresh_manifest(root, relative="automated-reviews.json")
            result = validate_bundle(root, ledger)
        self.assertFalse(result["ok"])
        self.assertTrue(any(issue.startswith("derivative_parent_reference_mismatch:") for issue in result["issues"]))
        self.assertTrue(any(issue.startswith("review_reference_mismatch:") for issue in result["issues"]))

    def test_validator_rejects_rehashed_derived_count_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=BUNDLE_ROOT.parent) as temporary:
            root, ledger_path = self._copy_bundle(temporary)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["original_bytes"] += 1
            self._refresh_ledger(root, ledger_path, ledger)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["counts"]["media_bytes"] += 1
            manifest["content_hash"] = canonical_sha256(
                {key: value for key, value in manifest.items() if key != "content_hash"}
            )
            write_canonical_json(manifest_path, manifest)
            result = validate_bundle(root, ledger_path)
        self.assertFalse(result["ok"])
        self.assertIn("ledger_derived_count_mismatch:original_bytes", result["issues"])
        self.assertIn("manifest_derived_counts_mismatch", result["issues"])


if __name__ == "__main__":
    unittest.main()
