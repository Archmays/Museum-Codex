from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlencode

from museum_pipeline.adapters import adapters_by_source, get_adapter
from museum_pipeline.adapters.base import RequestSpec, ResponseContract
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.dates import incompatible_life_dates, normalize_wikidata_time
from museum_pipeline.normalization.names import normalize_name, validate_language_tag
from museum_pipeline.source_registry import verify_sources
from museum_pipeline.validation.dispatch import validate_record


ROOT = Path(__file__).resolve().parents[2]
VALID = ROOT / "fixtures" / "pipeline" / "valid"
FIXTURES = {
    "wikidata": "adapter-wikidata-response.json",
    "getty_ulan": "adapter-getty-ulan-response.json",
    "met_open_access": "adapter-met-response.json",
    "aic_api": "adapter-aic-response.json",
}
OBJECT_IDS = {"wikidata": "Q42", "getty_ulan": "500115493", "met_open_access": "1", "aic_api": "27992"}


def response_for(source_id: str, document: object | None = None) -> ResponseContract:
    adapter = get_adapter(source_id)
    if document is None:
        body = (VALID / FIXTURES[source_id]).read_bytes()
    else:
        body = json.dumps(document, ensure_ascii=False).encode("utf-8")
    url = adapter.build_request(OBJECT_IDS[source_id]).url
    return ResponseContract(200, {"content-type": "application/json; charset=utf-8"}, body, url)


def normalized(source_id: str) -> dict:
    adapter = get_adapter(source_id)
    document = adapter.validate_response_contract(response_for(source_id))
    return adapter.normalize(document, snapshot_id=f"snapshot:{source_id}:fixture", observed_at="2026-07-12T00:00:00Z")


class AdapterTests(unittest.TestCase):
    def test_all_four_contract_records_use_canonical_schema(self) -> None:
        for source_id, adapter in adapters_by_source().items():
            with self.subTest(source_id=source_id):
                self.assertEqual([], validate_record(adapter.contract_record()))

    def test_all_four_default_requests_are_https_allowlisted_and_explicit(self) -> None:
        for source_id, adapter in adapters_by_source().items():
            with self.subTest(source_id=source_id):
                request = adapter.build_request(OBJECT_IDS[source_id])
                adapter.validate_request(request)
                self.assertTrue(request.url.startswith("https://"))
                self.assertIn("User-Agent", request.headers)

    def test_object_id_validation_is_source_specific(self) -> None:
        for source_id, adapter in adapters_by_source().items():
            with self.subTest(source_id=source_id), self.assertRaises(PipelineError):
                adapter.build_request("../not-an-id")

    def test_same_host_arbitrary_path_is_rejected(self) -> None:
        adapter = get_adapter("aic_api")
        request = RequestSpec("GET", "https://api.artic.edu/api/v1/artworks/search?fields=id,title", adapter.default_headers(), "default")
        with self.assertRaisesRegex(PipelineError, "path"):
            adapter.validate_request(request)

    def test_encoded_path_cannot_reach_unapproved_endpoint(self) -> None:
        adapter = get_adapter("aic_api")
        request = RequestSpec("GET", "https://api.artic.edu/api/v1/artworks/%73earch?fields=id,title", adapter.default_headers(), "default")
        with self.assertRaises(PipelineError) as context:
            adapter.validate_request(request)
        self.assertEqual("endpoint_path_not_allowed", context.exception.code)

    def test_query_parameter_injection_is_rejected(self) -> None:
        adapter = get_adapter("met_open_access")
        request = RequestSpec("GET", "https://collectionapi.metmuseum.org/public/collection/v1/objects/1?url=https://evil.example", adapter.default_headers(), "default")
        with self.assertRaises(PipelineError) as context:
            adapter.validate_request(request)
        self.assertEqual("query_parameter_not_allowed", context.exception.code)

    def test_response_identity_must_match_the_requested_object(self) -> None:
        wikidata = json.loads((VALID / FIXTURES["wikidata"]).read_text(encoding="utf-8"))
        entity = wikidata["entities"].pop("Q42")
        entity["id"] = "Q1"
        wikidata["entities"]["Q1"] = entity
        getty = json.loads((VALID / FIXTURES["getty_ulan"]).read_text(encoding="utf-8"))
        getty[0]["@id"] = "https://vocab.getty.edu/ulan/500000001"
        met = json.loads((VALID / FIXTURES["met_open_access"]).read_text(encoding="utf-8"))
        met["objectID"] = 2
        aic = json.loads((VALID / FIXTURES["aic_api"]).read_text(encoding="utf-8"))
        aic["data"]["id"] = 1
        for source_id, document in (("wikidata", wikidata), ("getty_ulan", getty), ("met_open_access", met), ("aic_api", aic)):
            with self.subTest(source_id=source_id), self.assertRaises(PipelineError) as raised:
                get_adapter(source_id).validate_response_contract(response_for(source_id, document))
            self.assertEqual("contract_identity_mismatch", raised.exception.code)

    def test_aic_request_field_order_extras_duplicates_and_profile_swaps_fail_closed(self) -> None:
        adapter = get_adapter("aic_api")
        base = "https://api.artic.edu/api/v1/artworks/27992"
        variants = [
            list(reversed(adapter.profile_fields("default"))),
            [*adapter.profile_fields("default"), "description"],
            adapter.profile_fields("default")[:-1],
        ]
        for fields in variants:
            request = RequestSpec("GET", f"{base}?{urlencode({'fields': ','.join(fields)})}", adapter.default_headers(), "default")
            with self.subTest(fields=fields), self.assertRaises(PipelineError) as raised:
                adapter.validate_request(request)
            self.assertEqual("aic_fields_invalid", raised.exception.code)
        duplicate = adapter.build_request("27992").url + "&fields=id"
        with self.assertRaises(PipelineError) as raised:
            adapter.validate_request(RequestSpec("GET", duplicate, adapter.default_headers(), "default"))
        self.assertEqual("aic_fields_invalid", raised.exception.code)

    def test_url_fragment_is_rejected_even_on_an_allowlisted_endpoint(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        with self.assertRaises(PipelineError) as raised:
            adapter.validate_request(RequestSpec(request.method, request.url + "#fragment", request.headers, request.query_profile))
        self.assertEqual("endpoint_not_allowed", raised.exception.code)

    def test_wikidata_contract_preserves_rank_reference_and_tier(self) -> None:
        candidate = normalized("wikidata")
        death = next(claim for claim in candidate["candidate_claims"] if claim["predicate"] == "death_date")
        self.assertEqual("preferred", death["source_assertion_metadata"]["rank"])
        self.assertTrue(death["source_assertion_metadata"]["references_present"])
        self.assertEqual(3, death["source_tier"])
        self.assertEqual("candidate", death["status"])
        self.assertFalse(candidate["publishable"])

    def test_wikidata_commons_reference_never_inherits_cc0(self) -> None:
        media = normalized("wikidata")["media_candidates"][0]
        self.assertEqual("unknown", media["rights_status"])
        self.assertTrue(media["development_only"])
        self.assertFalse(media["rights_hints"]["wikidata_license_inherited"])

    def test_getty_contract_uses_odc_by_rule_and_preserves_authority_type(self) -> None:
        adapter = get_adapter("getty_ulan")
        candidate = normalized("getty_ulan")
        self.assertEqual("individual", candidate["candidate_kind"])
        rule_id = adapter.map_license_rules(["names"])["names"]
        self.assertEqual("getty_ulan:data:eb25ddb4d400", rule_id)
        self.assertTrue(candidate["fields"]["same_as"])

    def test_current_getty_compacted_linked_art_fixture_is_supported_without_xml_fallback(self) -> None:
        adapter = get_adapter("getty_ulan")
        body = (ROOT / "fixtures" / "pipeline" / "recorded" / "getty_ulan" / "response.body").read_bytes()
        document = adapter.validate_response_contract(ResponseContract(
            200, {"content-type": "application/json"}, body, adapter.build_request("500115493").url,
        ))
        candidate = adapter.normalize(document, snapshot_id="snapshot:getty_ulan:fixture", observed_at="2026-07-12T00:00:00Z")
        self.assertEqual("individual", candidate["candidate_kind"])
        self.assertEqual("getty_ulan:data:eb25ddb4d400", candidate["field_provenance"][0]["license_rule_id"])
        self.assertEqual([], candidate["contract_drift"])

    def test_met_non_media_metadata_candidate_has_no_media(self) -> None:
        candidate = normalized("met_open_access")
        self.assertEqual("artwork", candidate["candidate_kind"])
        self.assertEqual([], candidate["media_candidates"])
        self.assertNotIn("identity_status", candidate["fields"])
        self.assertIn("constituent_assertions", candidate["fields"])

    def test_met_primary_image_is_only_unknown_media_hint(self) -> None:
        document = json.loads((VALID / FIXTURES["met_open_access"]).read_text(encoding="utf-8"))
        document["primaryImage"] = "https://images.metmuseum.org/fixture.jpg"
        document["isPublicDomain"] = True
        adapter = get_adapter("met_open_access")
        candidate = adapter.normalize(document, snapshot_id="snapshot:met:fixture", observed_at="2026-07-12T00:00:00Z")
        media = candidate["media_candidates"][0]
        self.assertEqual("unknown", media["rights_status"])
        self.assertFalse(media["rights_hints"]["primary_image_is_rights_proof"])
        self.assertEqual("met_open_access:media:1669574588c7", media["license_rule_id"])

    def test_aic_default_request_declares_exact_cc0_field_profile(self) -> None:
        adapter = get_adapter("aic_api")
        request = adapter.build_request("27992")
        self.assertIn("fields=", request.url)
        self.assertNotIn("description", request.url)
        mapping = adapter.map_license_rules(adapter.profile_fields("default"))
        self.assertEqual({"aic_api:data:75df7e022b4e"}, set(mapping.values()))

    def test_aic_description_profile_selects_cc_by_only_for_description(self) -> None:
        adapter = get_adapter("aic_api")
        fields = adapter.profile_fields("description")
        mapping = adapter.map_license_rules(fields)
        self.assertEqual("aic_api:data:230184c34ce7", mapping["description"])
        self.assertEqual("aic_api:data:75df7e022b4e", mapping["title"])

    def test_aic_description_response_propagates_cc_by_only_to_that_field(self) -> None:
        adapter = get_adapter("aic_api")
        document = json.loads((VALID / FIXTURES["aic_api"]).read_text(encoding="utf-8"))
        document["data"]["description"] = "Licensed field-level description."
        request = adapter.build_request("27992", query_profile="description")
        parsed = adapter.validate_response_contract(ResponseContract(
            200, {"content-type": "application/json"}, json.dumps(document, ensure_ascii=False).encode("utf-8"), request.url,
        ))
        candidate = adapter.normalize(parsed, snapshot_id="snapshot:aic_api:description", observed_at="2026-07-12T00:00:00Z")
        rules = {item["raw_locator"]: item["license_rule_id"] for item in candidate["field_provenance"]}
        self.assertEqual("aic_api:data:230184c34ce7", rules["/data/description"])
        self.assertEqual("aic_api:data:75df7e022b4e", rules["/data/title"])
        self.assertEqual([], validate_record(candidate))

    def test_aic_partial_or_extra_fields_fail_closed(self) -> None:
        adapter = get_adapter("aic_api")
        for fields in (["id", "title"], [*adapter.profile_fields("default"), "unexpected"], [*adapter.profile_fields("description"), "unexpected"]):
            with self.subTest(fields=fields):
                with self.assertRaises(PipelineError) as raised:
                    adapter.map_license_rules(fields)
                self.assertEqual("aic_fields_invalid", raised.exception.code)

    def test_aic_response_with_unrequested_field_fails_contract(self) -> None:
        document = json.loads((VALID / FIXTURES["aic_api"]).read_text(encoding="utf-8"))
        document["data"]["unexpected"] = "drift"
        with self.assertRaises(PipelineError) as context:
            get_adapter("aic_api").validate_response_contract(response_for("aic_api", document))
        self.assertEqual("contract_unexpected_field", context.exception.code)

    def test_aic_iiif_candidate_stays_unknown_even_when_public_domain_flag_is_true(self) -> None:
        media = normalized("aic_api")["media_candidates"][0]
        self.assertEqual("unknown", media["rights_status"])
        self.assertFalse(media["rights_hints"]["iiif_access_is_license"])
        self.assertTrue(media["rights_hints"]["object_level_rights_review_required"])
        self.assertEqual("aic_api:media:98cceb1965b8", media["license_rule_id"])

    def test_field_and_media_license_rule_tampering_is_rejected(self) -> None:
        candidate = normalized("aic_api")
        title = next(item for item in candidate["field_provenance"] if item["raw_locator"] == "/data/title")
        title["license_rule_id"] = "aic_api:data:230184c34ce7"
        candidate["media_candidates"][0]["license_rule_id"] = "aic_api:data:75df7e022b4e"
        codes = {issue.code for issue in validate_record(candidate)}
        self.assertIn("aic_license_rule_mismatch", codes)
        self.assertIn("license_content_class_mismatch", codes)

    def test_normalization_is_byte_deterministic(self) -> None:
        first = normalized("wikidata")
        second = normalized("wikidata")
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))

    def test_unknown_met_field_is_reported_as_drift(self) -> None:
        document = json.loads((VALID / FIXTURES["met_open_access"]).read_text(encoding="utf-8"))
        document["new_upstream_field"] = "not silently dropped"
        drift = get_adapter("met_open_access").detect_contract_drift(document)
        self.assertIn("/new_upstream_field", {item["raw_locator"] for item in drift})

    def test_unicode_normalization_preserves_text_semantics(self) -> None:
        self.assertEqual("Café", normalize_name("Cafe\u0301"))
        self.assertEqual("多 语", normalize_name("  多   语  "))

    def test_bcp47_validation_accepts_project_tags_and_rejects_malformed(self) -> None:
        for value in ("en", "zh-Hans", "zh-Hant", "fr"):
            self.assertEqual(value, validate_language_tag(value))
        with self.assertRaises(PipelineError):
            validate_language_tag("English")

    def test_wikidata_date_precision_does_not_invent_days(self) -> None:
        value = normalize_wikidata_time({"time": "+1900-00-00T00:00:00Z", "precision": 9, "calendarmodel": "Q1985727"})
        self.assertEqual("year", value["precision"])
        self.assertEqual("1900", value["display_text"])

    def test_birth_after_death_is_a_hard_compatibility_failure(self) -> None:
        self.assertTrue(incompatible_life_dates({"display_text": "2000"}, {"display_text": "1900"}))
        self.assertFalse(incompatible_life_dates({"display_text": "-0500"}, {"display_text": "-0400"}))

    def test_source_registry_and_license_hashes_are_closed(self) -> None:
        result = verify_sources()
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(4, len(result["reference_sources"]))


if __name__ == "__main__":
    unittest.main()
