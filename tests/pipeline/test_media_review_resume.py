from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from museum_pipeline.canonical_json import write_canonical_json
import museum_pipeline.media.review as media_review


def _write(path: Path, value: object) -> None:
    write_canonical_json(path, value)


class MediaReviewResumeTests(unittest.TestCase):
    def test_cross_check_refuses_to_seal_before_discovery_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            _write(directory / "acquisition-request.json", {})
            inputs = SimpleNamespace(
                artworks=({"id": "artwork:test"},),
                assessment_by_artwork={"artwork:test": {}},
            )
            with (
                patch.object(media_review, "load_media_inputs", return_value=inputs),
                patch.object(media_review, "artwork_vault", return_value=directory),
                self.assertRaisesRegex(ValueError, "discovery is not terminal"),
            ):
                media_review.cross_check_all()
            self.assertFalse((directory / "identity-rights-cross-check.json").exists())

    def test_existing_cross_check_with_missing_quality_resumes_quality_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            _write(directory / "acquisition-request.json", {})
            _write(directory / "discovery.json", {"media": {"source_url": None}})
            _write(
                directory / "byte-record.json",
                {"id": "media-byte:test", "sha256": "sha256:" + "1" * 64, "phash": "phash:" + "1" * 16},
            )
            _write(
                directory / "identity-rights-cross-check.json",
                {"id": "media-cross-check:test", "closure_status": "pass"},
            )
            inputs = SimpleNamespace(
                artworks=({"id": "artwork:test"},),
                assessment_by_artwork={"artwork:test": {}},
            )
            cross = {"id": "media-cross-check:test", "closure_status": "pass", "checked_at": "2026-07-15T00:00:00Z"}
            quality = {"id": "media-quality:test", "assessed_at": "2026-07-15T00:00:00Z"}

            def store(path: Path, value: dict, _timestamp: str) -> bool:
                existed = path.exists()
                _write(path, value)
                return not existed

            with (
                patch.object(media_review, "load_media_inputs", return_value=inputs),
                patch.object(media_review, "artwork_vault", return_value=directory),
                patch.object(media_review, "_cross_check_record", return_value=cross),
                patch.object(media_review, "_quality_record", return_value=quality) as quality_builder,
                patch.object(media_review, "_store_derived", side_effect=store),
            ):
                result = media_review.cross_check_all()
            self.assertTrue(result["ok"])
            quality_builder.assert_called_once()
            self.assertTrue((directory / "quality-assessment.json").exists())

    def test_stale_failure_is_not_used_after_exact_bytes_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, value in (
                ("acquisition-request.json", {}),
                ("identity-rights-cross-check.json", {"id": "media-cross-check:test"}),
                ("byte-record.json", {"id": "media-byte:test"}),
                ("quality-assessment.json", {"id": "media-quality:test"}),
                ("acquisition-failure.json", {"error_code": "media_http_status"}),
            ):
                _write(directory / name, value)
            inputs = SimpleNamespace(artworks=({"id": "artwork:test"},))

            def store(path: Path, value: dict, _timestamp: str) -> bool:
                _write(path, value)
                return True

            with (
                patch.object(media_review, "load_media_inputs", return_value=inputs),
                patch.object(media_review, "artwork_vault", return_value=directory),
                patch.object(
                    media_review,
                    "_final_decision",
                    return_value=(
                        "approved_self_hosted",
                        ["identity_rights_bytes_quality_closed"],
                        {"identity": "pass", "rights": "pass", "bytes": "pass", "quality": "pass"},
                    ),
                ) as final_decision,
                patch.object(media_review, "_predicted_derivative_ids", return_value=["media-derivative:test-320w-jpeg"]),
                patch.object(media_review, "_store_derived", side_effect=store),
            ):
                result = media_review.assess_all()
            self.assertEqual(1, result["counts"]["approved_self_hosted"])
            self.assertIsNone(final_decision.call_args.args[4])


if __name__ == "__main__":
    unittest.main()
