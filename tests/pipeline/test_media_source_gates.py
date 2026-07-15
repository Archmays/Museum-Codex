from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import sha256_bytes
from museum_pipeline.media.acquisition import (
    _resolve_rijks_metadata_chain,
    discover_all,
    media_transport,
)
from museum_pipeline.media.constants import SOURCE_POLICIES
from museum_pipeline.media.discovery import build_discovery_record, metadata_request_url, parse_official_metadata
from museum_pipeline.media.transport import MetadataFetchResult, MetadataFetchRequest, NetworkHopEvidence


def _json_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def _request(source_id: str, object_id: str, expected_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"media-request:test-{object_id}",
        "artwork_id": f"artwork:test-{object_id}",
        "source_id": source_id,
        "source_object_id": object_id,
        "expected_identity": expected_identity,
    }


class _SequenceMetadataTransport:
    def __init__(self, outcomes: list[dict[str, Any] | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[MetadataFetchRequest] = []

    def fetch_metadata(self, request: MetadataFetchRequest) -> MetadataFetchResult:
        self.requests.append(request)
        if not self.outcomes:
            raise AssertionError("unexpected metadata request")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        body = _json_bytes(outcome)
        public_ip = "93.184.216.34"
        return MetadataFetchResult(
            status_code=200,
            final_url=request.url,
            redirect_chain=(),
            response_headers={
                "content-type": "application/ld+json",
                "content-length": str(len(body)),
            },
            body=body,
            etag=None,
            retry_count=0,
            not_modified=False,
            resolved_public_ips=(public_ip,),
            connected_peer_ip=public_ip,
            hop_evidence=(
                NetworkHopEvidence(
                    url=request.url,
                    host="data.rijksmuseum.nl",
                    resolved_public_ips=(public_ip,),
                    connected_peer_ip=public_ip,
                    status_code=200,
                ),
            ),
        )


def _cleveland_document() -> dict[str, Any]:
    return {
        "data": {
            "id": 141444,
            "accession_number": "1964.88",
            "share_license_status": "CC0",
            "title": "Armor for Man and Horse with Völs-Colonna Arms",
            "creation_date": "c. 1575",
            "copyright": None,
            "url": "https://clevelandart.org/art/1964.88",
            "creditline": "John L. Severance Fund",
            "creators": [{"description": "Creator Example (Italian, active c. 1575)"}],
            "images": {
                "web": {
                    "url": "https://openaccess-cdn.clevelandart.org/1964.88/1964.88_web.jpg",
                },
                "print": {
                    "url": "https://openaccess-cdn.clevelandart.org/1964.88/1964.88_print.jpg",
                },
                "full": {
                    "url": "https://openaccess-cdn.clevelandart.org/1964.88/1964.88_full.tif",
                },
            },
        }
    }


def _cleveland_request() -> dict[str, Any]:
    return _request(
        "source:cleveland_open_access",
        "141444",
        {
            "official_object_id": "141444",
            "accession": "1964.88",
            "artist": "Creator Example",
            "title": "Armor for Man and Horse with Völs-Colonna Arms",
            "date": "1575",
            "institution": "Cleveland Museum of Art",
            "object_url": "https://clevelandart.org/art/1964.88",
        },
    )


def _rijks_en_language() -> list[dict[str, str]]:
    return [{"id": "http://vocab.getty.edu/aat/300388277", "type": "Language"}]


def _rijks_en_notation(value: str) -> list[dict[str, str]]:
    return [{"@language": "en", "@value": value}]


def _rijks_envelope() -> dict[str, Any]:
    visual_id = "https://id.rijksmuseum.nl/202107928"
    digital_id = "https://id.rijksmuseum.nl/500711199912110510799100"
    return {
        "object": {
            "id": "https://id.rijksmuseum.nl/200107928",
            "type": "HumanMadeObject",
            "identified_by": [
                {
                    "type": "Identifier",
                    "content": "SK-C-5",
                    "classified_as": [{"id": "https://id.rijksmuseum.nl/22015218", "type": "Type"}],
                },
                {
                    "type": "Name",
                    "content": "The Night Watch",
                    "classified_as": [
                        {"id": "http://vocab.getty.edu/aat/300417200", "type": "Type"}
                    ],
                    "language": _rijks_en_language(),
                },
            ],
            "produced_by": {
                "type": "Production",
                "timespan": {
                    "type": "TimeSpan",
                    "identified_by": [
                        {"type": "Name", "content": "1642", "language": _rijks_en_language()}
                    ],
                },
                "part": [
                    {
                        "type": "Production",
                        "carried_out_by": [
                            {
                                "id": "https://id.rijksmuseum.nl/2103429",
                                "type": "Person",
                                "notation": _rijks_en_notation("Rembrandt van Rijn"),
                            }
                        ],
                    }
                ],
            },
            "subject_of": [
                {
                    "id": "https://data.rijksmuseum.nl/200107928",
                    "type": "LinguisticObject",
                    "subject_to": [
                        {
                            "type": "Right",
                            "classified_as": [
                                {
                                    "id": "https://creativecommons.org/publicdomain/zero/1.0/",
                                    "type": "Type",
                                }
                            ],
                        }
                    ],
                }
            ],
            "referred_to_by": [
                {
                    "type": "LinguisticObject",
                    "content": "On loan from the City of Amsterdam",
                    "classified_as": [
                        {"id": "http://vocab.getty.edu/aat/300026687", "type": "Type"}
                    ],
                    "language": _rijks_en_language(),
                }
            ],
            "shows": [{"id": visual_id, "type": "VisualItem"}],
        },
        "visual_item": {
            "id": visual_id,
            "type": "VisualItem",
            "subject_to": [
                {
                    "type": "Right",
                    "classified_as": [
                        {
                            "id": "https://creativecommons.org/publicdomain/mark/1.0/",
                            "type": "Type",
                        }
                    ],
                }
            ],
            "digitally_shown_by": [{"id": digital_id, "type": "DigitalObject"}],
        },
        "digital_object": {
            "id": digital_id,
            "type": "DigitalObject",
            "access_point": [
                {
                    "id": "https://iiif.micr.io/PJEZO/full/max/0/default.jpg",
                    "type": "DigitalObject",
                }
            ],
        },
    }


def _rijks_request() -> dict[str, Any]:
    return _request(
        "source:rijksmuseum",
        "200107928",
        {
            "official_object_id": "200107928",
            "accession": "SK-C-5",
            "artist": "Rembrandt van Rijn",
            "title": "The Night Watch",
            "date": "1642",
            "institution": "Rijksmuseum",
            "object_url": "https://id.rijksmuseum.nl/200107928",
        },
    )


class MediaSourceGateTests(unittest.TestCase):
    def test_new_source_policies_bind_exact_endpoints_hosts_rules_and_throttles(self) -> None:
        cleveland = SOURCE_POLICIES["source:cleveland_open_access"]
        rijks = SOURCE_POLICIES["source:rijksmuseum"]
        self.assertEqual("openaccess-api.clevelandart.org", cleveland["metadata_host"])
        self.assertEqual(("clevelandart.org",), cleveland["object_hosts"])
        self.assertEqual(("openaccess-cdn.clevelandart.org",), cleveland["media_hosts"])
        self.assertEqual(("CC0",), cleveland["allowed_media_rights"])
        self.assertEqual("cleveland_open_access:media:9f5808165c51", cleveland["media_rule_id"])
        self.assertEqual("data.rijksmuseum.nl", rijks["metadata_host"])
        self.assertEqual(("id.rijksmuseum.nl",), rijks["object_hosts"])
        self.assertEqual(("iiif.micr.io",), rijks["media_hosts"])
        self.assertEqual("rijksmuseum:media:9afa251862e4", rijks["media_rule_id"])
        throttles = media_transport().policy.source_min_interval_seconds
        self.assertEqual(1.0, throttles["source:cleveland_open_access"])
        self.assertEqual(1.0, throttles["source:rijksmuseum"])

    def test_new_source_metadata_urls_are_exact_and_reject_path_injection(self) -> None:
        self.assertEqual(
            "https://openaccess-api.clevelandart.org/api/artworks/141444",
            metadata_request_url("source:cleveland_open_access", "141444"),
        )
        self.assertEqual(
            "https://data.rijksmuseum.nl/200107928?_profile=la-framed",
            metadata_request_url("source:rijksmuseum", "200107928"),
        )
        for source_id in (
            "source:met_open_access",
            "source:aic_api",
            "source:cleveland_open_access",
            "source:rijksmuseum",
        ):
            with self.subTest(source_id=source_id), self.assertRaises(ValueError):
                metadata_request_url(source_id, "../other")
        with self.assertRaises(ValueError):
            metadata_request_url("source:unregistered", "1")

    def test_rijks_live_resolver_fetches_and_records_the_exact_three_hop_chain(self) -> None:
        envelope = _rijks_envelope()
        transport = _SequenceMetadataTransport(
            [envelope["object"], envelope["visual_item"], envelope["digital_object"]]
        )
        persisted: list[dict[str, Any]] = []

        resolved = _resolve_rijks_metadata_chain(
            transport,
            _rijks_request(),
            persist_step=persisted.append,
        )

        expected_urls = [
            "https://data.rijksmuseum.nl/200107928?_profile=la-framed",
            "https://data.rijksmuseum.nl/202107928?_profile=la-framed",
            "https://data.rijksmuseum.nl/500711199912110510799100?_profile=la-framed",
        ]
        self.assertEqual(expected_urls, [request.url for request in transport.requests])
        self.assertTrue(
            all(
                request.trusted_hosts == frozenset({"data.rijksmuseum.nl"})
                and request.source_id == "source:rijksmuseum"
                for request in transport.requests
            )
        )
        self.assertEqual(3, len(persisted))
        self.assertEqual(["object", "visual_item", "digital_object"], [step["role"] for step in persisted])
        for step in persisted:
            self.assertEqual(step["response_sha256"], sha256_bytes(step["response_body"]))
            self.assertEqual(step["response_sha256"], step["event"]["body_sha256"])
            self.assertEqual(step["request_url"], step["event"]["request_url"])
            self.assertEqual(1, len(step["hop_evidence"]))

        record = build_discovery_record(
            _rijks_request(),
            resolved["body"],
            response_sha256=resolved["response_sha256"],
        )
        self.assertTrue(record["identity_closure"])
        self.assertTrue(record["rights_closure"])
        self.assertEqual("PJEZO", record["media"]["id"])

    def test_rijks_discover_persists_each_hop_and_the_closed_envelope(self) -> None:
        envelope = _rijks_envelope()
        transport = _SequenceMetadataTransport(
            [envelope["object"], envelope["visual_item"], envelope["digital_object"]]
        )
        with TemporaryDirectory() as temporary:
            vault = Path(temporary)
            directory = vault / "test-200107928"
            directory.mkdir()
            (directory / "acquisition-request.json").write_text(
                json.dumps(_rijks_request(), ensure_ascii=False),
                encoding="utf-8",
            )
            inputs = SimpleNamespace(artworks=[{"id": "artwork:test-200107928"}])
            with (
                patch("museum_pipeline.media.acquisition.load_media_inputs", return_value=inputs),
                patch("museum_pipeline.media.acquisition.artwork_vault", return_value=directory),
                patch("museum_pipeline.media.state.MEDIA_VAULT", vault),
            ):
                result = discover_all(live=True, transport=transport)

            self.assertTrue(result["ok"])
            self.assertEqual(1, result["discovered"])
            discovery = json.loads((directory / "discovery.json").read_text(encoding="utf-8"))
            self.assertEqual(3, len(discovery["metadata_chain"]))
            self.assertEqual(3, len(discovery["metadata_hops"]))
            self.assertEqual(
                ["object", "visual_item", "digital_object"],
                [step["role"] for step in discovery["metadata_chain"]],
            )
            for filename in (
                "official-metadata-response.json",
                "official-metadata-visual-item-response.json",
                "official-metadata-digital-object-response.json",
                "official-metadata-envelope.json",
                "metadata-acquisition-event.json",
                "metadata-visual-item-acquisition-event.json",
                "metadata-digital-object-acquisition-event.json",
            ):
                self.assertTrue((directory / filename).is_file(), filename)

    def test_rijks_live_resolver_rejects_wrong_host_or_pid_before_following_it(self) -> None:
        wrong_host = deepcopy(_rijks_envelope()["object"])
        wrong_host["shows"][0]["id"] = "https://images.example/202107928"
        wrong_pid = deepcopy(_rijks_envelope()["object"])
        wrong_pid["id"] = "https://id.rijksmuseum.nl/200000001"

        for document in (wrong_host, wrong_pid):
            with self.subTest(document=document):
                transport = _SequenceMetadataTransport([document])
                persisted: list[dict[str, Any]] = []
                with self.assertRaises(ValueError):
                    _resolve_rijks_metadata_chain(
                        transport,
                        _rijks_request(),
                        persist_step=persisted.append,
                    )
                self.assertEqual(1, len(transport.requests))
                self.assertEqual(1, len(persisted))

    def test_rijks_live_resolver_rejects_missing_or_multiple_chain_links(self) -> None:
        missing_visual = deepcopy(_rijks_envelope()["object"])
        missing_visual["shows"] = []
        multiple_visuals = deepcopy(_rijks_envelope()["object"])
        multiple_visuals["shows"].append(deepcopy(multiple_visuals["shows"][0]))

        for document in (missing_visual, multiple_visuals):
            with self.subTest(document=document):
                transport = _SequenceMetadataTransport([document])
                with self.assertRaises(ValueError):
                    _resolve_rijks_metadata_chain(transport, _rijks_request())
                self.assertEqual(1, len(transport.requests))

        envelope = _rijks_envelope()
        missing_digital = deepcopy(envelope["visual_item"])
        missing_digital["digitally_shown_by"] = []
        transport = _SequenceMetadataTransport([envelope["object"], missing_digital])
        with self.assertRaises(ValueError):
            _resolve_rijks_metadata_chain(transport, _rijks_request())
        self.assertEqual(2, len(transport.requests))

    def test_rijks_live_resolver_fails_closed_when_a_followup_source_is_unavailable(self) -> None:
        unavailable = PipelineError(
            "media_http_status",
            "Metadata server remained unavailable after bounded retries",
            exit_code=5,
        )
        transport = _SequenceMetadataTransport([_rijks_envelope()["object"], unavailable])
        persisted: list[dict[str, Any]] = []

        with self.assertRaises(PipelineError) as raised:
            _resolve_rijks_metadata_chain(
                transport,
                _rijks_request(),
                persist_step=persisted.append,
            )

        self.assertEqual("media_http_status", raised.exception.code)
        self.assertEqual(2, len(transport.requests))
        self.assertEqual(["object"], [step["role"] for step in persisted])

    def test_rijks_discover_records_followup_source_unavailable_without_a_discovery(self) -> None:
        unavailable = PipelineError(
            "media_http_status",
            "Metadata server remained unavailable after bounded retries",
            exit_code=5,
        )
        transport = _SequenceMetadataTransport([_rijks_envelope()["object"], unavailable])
        with TemporaryDirectory() as temporary:
            vault = Path(temporary)
            directory = vault / "test-200107928"
            directory.mkdir()
            (directory / "acquisition-request.json").write_text(
                json.dumps(_rijks_request(), ensure_ascii=False),
                encoding="utf-8",
            )
            inputs = SimpleNamespace(artworks=[{"id": "artwork:test-200107928"}])
            with (
                patch("museum_pipeline.media.acquisition.load_media_inputs", return_value=inputs),
                patch("museum_pipeline.media.acquisition.artwork_vault", return_value=directory),
                patch("museum_pipeline.media.state.MEDIA_VAULT", vault),
            ):
                result = discover_all(live=True, transport=transport)

            self.assertFalse(result["ok"])
            self.assertEqual(1, result["failed"])
            self.assertFalse((directory / "discovery.json").exists())
            self.assertTrue((directory / "official-metadata-response.json").is_file())
            failure = json.loads((directory / "discovery-failure.json").read_text(encoding="utf-8"))
            self.assertEqual("media_http_status", failure["error_code"])

    def test_cleveland_cc0_identity_rights_media_and_attribution_close(self) -> None:
        record = build_discovery_record(_cleveland_request(), _json_bytes(_cleveland_document()))
        self.assertTrue(record["identity_closure"])
        self.assertTrue(record["rights_closure"])
        self.assertEqual("1964.88_full.tif", record["media"]["id"])
        self.assertEqual(
            "https://openaccess-cdn.clevelandart.org/1964.88/1964.88_full.tif",
            record["media"]["source_url"],
        )
        self.assertEqual(
            "cleveland_open_access:media:9f5808165c51",
            record["rights"]["source_rule_id"],
        )
        self.assertEqual("John L. Severance Fund", record["rights"]["credit_line"])

    def test_cleveland_rights_conflicts_fail_closed(self) -> None:
        variants = []
        copyrighted = _cleveland_document()
        copyrighted["data"]["share_license_status"] = "Copyrighted"
        variants.append(copyrighted)
        copyright_notice = _cleveland_document()
        copyright_notice["data"]["copyright"] = "Copyright holder retained"
        variants.append(copyright_notice)
        no_attribution = _cleveland_document()
        no_attribution["data"]["creditline"] = None
        variants.append(no_attribution)
        for document in variants:
            with self.subTest(document=document):
                record = build_discovery_record(_cleveland_request(), _json_bytes(document))
                self.assertFalse(record["rights_closure"])
                self.assertIsNone(record["media"]["source_url"])

    def test_cleveland_untrusted_media_or_object_url_fails_closed(self) -> None:
        untrusted = _cleveland_document()
        untrusted["data"]["images"]["web"]["url"] = "https://images.example/1964.88_web.jpg"
        record = build_discovery_record(_cleveland_request(), _json_bytes(untrusted))
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])

        wrong_object_image = _cleveland_document()
        wrong_object_image["data"]["images"]["print"]["url"] = (
            "https://openaccess-cdn.clevelandart.org/other/other_print.jpg"
        )
        record = build_discovery_record(_cleveland_request(), _json_bytes(wrong_object_image))
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])

        mismatched_url = _cleveland_document()
        mismatched_url["data"]["url"] = "https://clevelandart.org/art/other"
        record = build_discovery_record(_cleveland_request(), _json_bytes(mismatched_url))
        self.assertFalse(record["identity_closure"])
        self.assertFalse(record["rights_closure"])

    def test_cleveland_malformed_envelope_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_official_metadata("source:cleveland_open_access", _json_bytes({"data": []}))

    def test_rijks_pid_chain_and_allowed_record_rights_close(self) -> None:
        allowed = (
            "https://creativecommons.org/publicdomain/mark/1.0/",
            "https://creativecommons.org/publicdomain/zero/1.0/",
            "https://creativecommons.org/licenses/by/4.0/",
        )
        for rights_url in allowed:
            with self.subTest(rights_url=rights_url):
                envelope = _rijks_envelope()
                envelope["visual_item"]["subject_to"][0]["classified_as"][0]["id"] = rights_url
                record = build_discovery_record(_rijks_request(), _json_bytes(envelope))
                self.assertTrue(record["identity_closure"])
                self.assertTrue(record["rights_closure"])
                self.assertEqual("PJEZO", record["media"]["id"])
                self.assertEqual(
                    "https://iiif.micr.io/PJEZO/full/max/0/default.jpg",
                    record["media"]["source_url"],
                )
                self.assertEqual("rijksmuseum:media:9afa251862e4", record["rights"]["source_rule_id"])
                self.assertEqual(
                    "Rijksmuseum — On loan from the City of Amsterdam",
                    record["rights"]["credit_line"],
                )
                self.assertEqual(
                    "https://creativecommons.org/publicdomain/zero/1.0/",
                    record["rights"]["object_record_rights_statement_url"],
                )

    def test_rijks_missing_unknown_or_conflicting_rights_fail_closed(self) -> None:
        missing = _rijks_envelope()
        missing["visual_item"]["subject_to"] = []
        unknown = _rijks_envelope()
        unknown["visual_item"]["subject_to"][0]["classified_as"][0]["id"] = (
            "https://creativecommons.org/licenses/by-nc/4.0/"
        )
        conflicting = _rijks_envelope()
        conflicting["digital_object"]["subject_to"] = [
            {
                "type": "Right",
                "classified_as": [
                    {
                        "id": "https://creativecommons.org/publicdomain/zero/1.0/",
                        "type": "Type",
                    }
                ],
            }
        ]
        ambiguous = _rijks_envelope()
        ambiguous["visual_item"]["subject_to"].append(
            deepcopy(ambiguous["visual_item"]["subject_to"][0])
        )
        missing_object_rights = _rijks_envelope()
        missing_object_rights["object"]["subject_of"] = []
        unknown_object_rights = _rijks_envelope()
        unknown_object_rights["object"]["subject_of"][0]["subject_to"][0]["classified_as"][0][
            "id"
        ] = "https://creativecommons.org/licenses/by-nc/4.0/"
        ambiguous_object_rights = _rijks_envelope()
        ambiguous_object_rights["object"]["subject_of"].append(
            deepcopy(ambiguous_object_rights["object"]["subject_of"][0])
        )
        for envelope in (
            missing,
            unknown,
            conflicting,
            ambiguous,
            missing_object_rights,
            unknown_object_rights,
            ambiguous_object_rights,
        ):
            with self.subTest(envelope=envelope):
                record = build_discovery_record(_rijks_request(), _json_bytes(envelope))
                self.assertFalse(record["rights_closure"])
                self.assertIsNone(record["media"]["source_url"])

    def test_rijks_requires_object_credit_and_never_synthesizes_attribution(self) -> None:
        no_credit = _rijks_envelope()
        no_credit["object"]["referred_to_by"] = []
        record = build_discovery_record(_rijks_request(), _json_bytes(no_credit))
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])
        self.assertIsNone(record["rights"]["credit_line"])
        self.assertIn("attribution_missing", record["rights"]["conflict_text"])

    def test_rijks_broken_chain_or_untrusted_iiif_fails_closed(self) -> None:
        broken_chain = _rijks_envelope()
        broken_chain["object"]["shows"][0]["id"] = "https://id.rijksmuseum.nl/202000001"
        record = build_discovery_record(_rijks_request(), _json_bytes(broken_chain))
        self.assertFalse(record["identity_closure"])
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])

        extra_visual = _rijks_envelope()
        extra_visual["object"]["shows"].append(
            {"id": "https://id.rijksmuseum.nl/202000001", "type": "VisualItem"}
        )
        record = build_discovery_record(_rijks_request(), _json_bytes(extra_visual))
        self.assertFalse(record["identity_closure"])
        self.assertFalse(record["rights_closure"])

        extra_digital = _rijks_envelope()
        extra_digital["visual_item"]["digitally_shown_by"].append(
            {"id": "https://id.rijksmuseum.nl/500700000000000000000000", "type": "DigitalObject"}
        )
        record = build_discovery_record(_rijks_request(), _json_bytes(extra_digital))
        self.assertFalse(record["identity_closure"])
        self.assertFalse(record["rights_closure"])

        untrusted = _rijks_envelope()
        untrusted["digital_object"]["access_point"][0]["id"] = (
            "https://images.example/PJEZO/full/max/0/default.jpg"
        )
        record = build_discovery_record(_rijks_request(), _json_bytes(untrusted))
        self.assertFalse(record["rights_closure"])
        self.assertIsNone(record["media"]["source_url"])

    def test_rijks_identity_classification_and_resolved_envelope_are_mandatory(self) -> None:
        wrong_class = _rijks_envelope()
        wrong_class["object"]["identified_by"][0]["classified_as"][0]["id"] = (
            "https://id.rijksmuseum.nl/22000000"
        )
        record = build_discovery_record(_rijks_request(), _json_bytes(wrong_class))
        self.assertFalse(record["identity_closure"])

        duplicate_object_number = _rijks_envelope()
        duplicate_object_number["object"]["identified_by"].append(
            deepcopy(duplicate_object_number["object"]["identified_by"][0])
        )
        record = build_discovery_record(_rijks_request(), _json_bytes(duplicate_object_number))
        self.assertFalse(record["identity_closure"])

        with self.assertRaises(ValueError):
            parse_official_metadata("source:rijksmuseum", _json_bytes({"object": {}}))


if __name__ == "__main__":
    unittest.main()
