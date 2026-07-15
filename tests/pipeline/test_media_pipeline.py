from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import canonical_sha256
from museum_pipeline.media.acquisition import _byte_record, _load_acquisition_evidence
from museum_pipeline.media.discovery import (
    build_discovery_record,
    commons_search_url,
    parse_commons_search,
)
from museum_pipeline.media.inputs import load_media_inputs
from museum_pipeline.media.cli import _emit
from museum_pipeline.media.planning import build_plan_record
from museum_pipeline.media.transport import MediaDownloadResult


class MediaPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_media_inputs()

    def test_sealed_inputs_are_exactly_the_m03c_baseline(self) -> None:
        self.assertEqual(12, len(self.inputs.artists))
        self.assertEqual(44, len(self.inputs.artworks))
        self.assertEqual(44, len(self.inputs.assessments))
        self.assertEqual(
            "sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86",
            self.inputs.manifest["content_hash"],
        )

    def test_cli_json_output_is_safe_on_strict_non_utf8_windows_streams(self) -> None:
        payload = {"ok": True, "summary": "Käthe Kollwitz 🙂", "artist": "Käthe Kollwitz"}
        for machine in (False, True):
            raw = io.BytesIO()
            stream = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
            with patch("museum_pipeline.media.cli.sys.stdout", stream):
                _emit(payload, machine)
                stream.flush()
            rendered = raw.getvalue().decode("gbk")
            json_text = rendered if machine else rendered.split("\n", 1)[1]
            self.assertEqual(payload, json.loads(json_text))

    def test_plan_record_closes_request_hash_and_network_controls(self) -> None:
        artwork = self.inputs.artworks[0]
        assessment = self.inputs.assessment_by_artwork[artwork["id"]]
        artist = self.inputs.artist_by_id[artwork["approved_artist_id"]]
        record = build_plan_record(artwork, assessment, artist, created_at="2026-07-15T00:00:00Z")
        self.assertEqual(1, record["concurrency"])
        self.assertTrue(record["download_media"])
        self.assertEqual("live", record["network_mode"])
        self.assertNotIn("Cookie", record.get("headers", {}))
        expected = canonical_sha256({key: value for key, value in record.items() if key != "request_hash"})
        self.assertEqual(expected, record["request_hash"])

    def test_met_discovery_requires_identity_rights_and_media_locator(self) -> None:
        artwork = next(item for item in self.inputs.artworks if item["id"] == "artwork:met-267426")
        assessment = self.inputs.assessment_by_artwork[artwork["id"]]
        artist = self.inputs.artist_by_id[artwork["approved_artist_id"]]
        request = build_plan_record(artwork, assessment, artist, created_at="2026-07-15T00:00:00Z")
        body = json.dumps(
            {
                "objectID": 267426,
                "accessionNumber": "1996.99.2",
                "artistDisplayName": "Julia Margaret Cameron",
                "title": "Julia Jackson",
                "objectDate": "1867",
                "repository": "Metropolitan Museum of Art, New York, NY",
                "objectURL": "https://www.metmuseum.org/art/collection/search/267426",
                "isPublicDomain": True,
                "primaryImage": "https://images.metmuseum.org/CRDImages/ph/original/DT1121.jpg",
                "primaryImageSmall": "https://images.metmuseum.org/CRDImages/ph/web-large/DT1121.jpg",
                "rightsAndReproduction": "",
                "creditLine": "Purchase, Joseph Pulitzer Bequest, 1996",
            }
        ).encode()
        record = build_discovery_record(request, body)
        self.assertTrue(record["identity_closure"])
        self.assertTrue(record["rights_closure"])
        self.assertEqual("DT1121.jpg", record["media"]["id"])

    def test_aic_copyright_notice_blocks_rights_closure(self) -> None:
        artwork = next(item for item in self.inputs.artworks if item["id"] == "artwork:aic-158971")
        assessment = self.inputs.assessment_by_artwork[artwork["id"]]
        artist = self.inputs.artist_by_id[artwork["approved_artist_id"]]
        request = build_plan_record(artwork, assessment, artist, created_at="2026-07-15T00:00:00Z")
        body = json.dumps(
            {
                "data": {
                    "id": 158971,
                    "main_reference_number": "2002.478",
                    "artist_display": "Käthe Kollwitz",
                    "title": "Memorial Sheet for Karl Liebknecht",
                    "date_display": "1919–20",
                    "api_link": "https://api.artic.edu/api/v1/artworks/158971",
                    "image_id": "b15d1fbc-828f-f224-fa79-bf3712705b16",
                    "is_public_domain": False,
                    "copyright_notice": "© Artists Rights Society / VG Bild-Kunst",
                    "credit_line": "Fund",
                }
            },
            ensure_ascii=False,
        ).encode()
        record = build_discovery_record(request, body)
        self.assertTrue(record["identity_closure"])
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])

    def test_commons_search_is_discovery_only_and_never_auto_promotes(self) -> None:
        url = commons_search_url("Flight Into Egypt", "Henry Ossawa Tanner")
        self.assertTrue(url.startswith("https://commons.wikimedia.org/w/api.php?"))
        body = json.dumps(
            {
                "query": {
                    "pages": [
                        {
                            "pageid": 7,
                            "title": "File:Candidate.jpg",
                            "imageinfo": [
                                {
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Candidate.jpg",
                                    "sha1": "abc",
                                    "thumburl": "https://upload.wikimedia.org/example.jpg",
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "Public domain"},
                                        "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/mark/1.0/"},
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        ).encode()
        candidate = parse_commons_search(body)[0]
        self.assertFalse(candidate["promotion_eligible"])
        self.assertIn("visual_identity_not_closed", candidate["block_reasons"])

    def test_persisted_resume_event_must_be_the_original_http_200_evidence(self) -> None:
        request = {"id": "media-request:test", "artwork_id": "artwork:test"}
        event = {
            "schema_version": "1.0.0",
            "id": "media-event:test-original",
            "entity_type": "media_acquisition_event",
            "branch_id": "art",
            "phase_id": "MUSEUM-03C",
            "executor": "automated_cross_validation_pipeline",
            "human_review_dependency": False,
            "request_id": request["id"],
            "artwork_id": request["artwork_id"],
            "event_type": "reused_existing_bytes",
            "request_url": "https://media.example/object.jpg",
            "final_url": "https://media.example/object.jpg",
            "redirect_chain": [],
            "resolved_public_ips": ["93.184.216.34"],
            "connected_peer_ip": "93.184.216.34",
            "status_code": None,
            "response_headers": {},
            "bytes_received": 17,
            "body_sha256": "sha256:" + "a" * 64,
            "error_code": None,
            "terminal": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "original-acquisition-event.json"
            path.write_text(json.dumps(event), encoding="utf-8")
            with self.assertRaises(PipelineError) as context:
                _load_acquisition_evidence(
                    path,
                    request=request,
                    source_url="https://media.example/object.jpg",
                    kind="original",
                )
        self.assertEqual("media_resume_evidence_mismatch", context.exception.code)

    def test_byte_record_never_synthesizes_http_200_for_unproven_result(self) -> None:
        result = MediaDownloadResult(
            status_code=None,
            final_url="https://media.example/object.jpg",
            redirect_chain=(),
            destination=Path("unused.jpg"),
            content_type="image/jpeg",
            etag=None,
            sha256="sha256:" + "a" * 64,
            file_size=17,
            bytes_downloaded=0,
            retry_count=0,
            response_headers={},
            resolved_public_ips=(),
            connected_peer_ip=None,
            hop_evidence=(),
            reused_existing=True,
        )
        with self.assertRaises(PipelineError) as context:
            _byte_record(
                {"id": "media-request:test", "artwork_id": "artwork:test", "source_id": "source:test"},
                result,
                {"display_width": 1, "display_height": 1, "phash": {"value": "phash64:0"}, "quality": {"flags": {}}},
                {"id": "media-event:test-original"},
                "2026-07-15T00:00:00Z",
            )
        self.assertEqual("media_acquisition_status_invalid", context.exception.code)


if __name__ == "__main__":
    unittest.main()
