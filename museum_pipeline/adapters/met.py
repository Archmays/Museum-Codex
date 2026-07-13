from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from museum_pipeline.adapters._utils import candidate_claim, json_pointer_part
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.provenance import finalize_candidate, provenance_entry, provisional_candidate_id
from museum_pipeline.normalization.rights import media_candidate


class MetOpenAccessAdapter(SourceAdapter):
    source_id = "met_open_access"
    adapter_name = "The Met Open Access object adapter"
    supported_record_types = ("collection_object",)
    object_id_pattern = re.compile(r"^[1-9][0-9]{0,8}$")
    _required_types = {
        "objectID": int, "isPublicDomain": bool, "accessionNumber": str, "objectURL": str,
        "title": str, "artistDisplayName": str, "objectDate": str, "medium": str, "department": str,
        "primaryImage": str,
    }
    _optional_contract_types = {
        "primaryImageSmall": str,
        "additionalImages": list,
        "constituents": (list, type(None)),
        "artistWikidata_URL": str,
        "artistULAN_URL": str,
        "objectWikidata_URL": str,
        "rightsAndReproduction": str,
    }
    _known_fields = {
        "objectID", "isHighlight", "accessionNumber", "accessionYear", "isPublicDomain", "primaryImage",
        "primaryImageSmall", "additionalImages", "constituents", "department", "objectName", "title", "culture",
        "period", "dynasty", "reign", "portfolio", "artistRole", "artistPrefix", "artistDisplayName",
        "artistDisplayBio", "artistSuffix", "artistAlphaSort", "artistNationality", "artistBeginDate", "artistEndDate",
        "artistGender", "artistWikidata_URL", "artistULAN_URL", "objectDate", "objectBeginDate", "objectEndDate",
        "medium", "dimensions", "measurements", "creditLine", "geographyType", "city", "state", "county",
        "country", "region", "subregion", "locale", "locus", "excavation", "river", "classification", "rightsAndReproduction",
        "linkResource", "metadataDate", "repository", "objectURL", "tags", "objectWikidata_URL", "isTimelineWork", "GalleryNumber",
    }

    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        self.validate_object_id(object_id)
        if query_profile != "default":
            raise PipelineError("query_profile_invalid", "The Met adapter supports one object profile")
        request = RequestSpec("GET", self.configuration["endpoint_template"].format(object_id=object_id), self.default_headers(), query_profile)
        self.validate_request(request)
        return request

    def validate_response_contract(self, response: ResponseContract) -> dict[str, Any]:
        if response.status_code != 200:
            raise PipelineError("response_status_invalid", f"The Met returned HTTP {response.status_code}")
        document = self.decode_json(response)
        if not isinstance(document, dict):
            raise PipelineError("contract_type_changed", "The Met object response is no longer an object")
        for field, expected_type in self._required_types.items():
            if field not in document:
                raise PipelineError("contract_required_field_missing", f"The Met field is missing: {field}")
            if not isinstance(document[field], expected_type) or (expected_type is int and isinstance(document[field], bool)):
                raise PipelineError("contract_type_changed", f"The Met field changed type: {field}")
        for field, expected_type in self._optional_contract_types.items():
            if field in document and not isinstance(document[field], expected_type):
                raise PipelineError("contract_type_changed", f"The Met field changed type: {field}")
        if any(not isinstance(item, str) for item in document.get("additionalImages", [])):
            raise PipelineError("contract_type_changed", "The Met additionalImages entries must remain strings")
        if any(not isinstance(item, dict) for item in (document.get("constituents") or [])):
            raise PipelineError("contract_type_changed", "The Met constituents entries must remain objects")
        expected_id = urlsplit(response.final_url).path.rsplit("/", 1)[-1]
        if str(document["objectID"]) != expected_id:
            raise PipelineError("contract_identity_mismatch", "The Met response identity differs from the requested object")
        return document

    def extract_source_object_ids(self, document: dict[str, Any]) -> list[str]:
        return [str(document["objectID"])]

    def normalize(self, document: dict[str, Any], *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        source_object_id = str(document["objectID"])
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        rule = self.rule("data")
        field_map = {
            "object_id": "objectID", "collection_url": "objectURL", "accession_number": "accessionNumber",
            "title": "title", "creator_display": "artistDisplayName", "date_display": "objectDate",
            "medium": "medium", "department": "department", "object_wikidata_url": "objectWikidata_URL",
            "artist_wikidata_url": "artistWikidata_URL", "artist_ulan_url": "artistULAN_URL",
            "is_public_domain": "isPublicDomain", "rights_and_reproduction": "rightsAndReproduction",
            "constituent_assertions": "constituents",
        }
        fields: dict[str, Any] = {}
        provenance: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        for normalized_name, source_name in field_map.items():
            if source_name not in document:
                continue
            raw_value = document[source_name]
            value = [] if source_name == "constituents" and raw_value is None else raw_value
            fields[normalized_name] = value
            pointer = f"/{json_pointer_part(source_name)}"
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/{normalized_name}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=pointer, raw_value=raw_value, normalized_value=value,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="null_to_empty_array" if source_name == "constituents" and raw_value is None else "identity",
            ))
            claims.append(candidate_claim(
                candidate_id=candidate_id, predicate=f"source_{normalized_name}", value=value,
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=pointer, source_tier=1, license_rule_id=rule["rule_id"],
            ))
        candidate = {
            "schema_version": "1.0.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": "artwork",
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": self.extract_media_candidates(document), "conflicts": [],
            "contract_drift": self.detect_contract_drift(document),
            "quarantine": [{"raw_locator": f"/{json_pointer_part(name)}", "reason": "unmapped_source_field"}
                           for name in sorted(set(document) - set(field_map.values()) - {"primaryImage", "primaryImageSmall", "additionalImages"})],
            "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        rule_id = self.rule("data")["rule_id"]
        return {field: rule_id for field in sorted(set(fields))}

    def extract_media_candidates(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        locators: list[tuple[str, str]] = []
        for field in ("primaryImage", "primaryImageSmall"):
            value = document.get(field)
            if isinstance(value, str) and value:
                locators.append((f"/{field}", value))
        for index, value in enumerate(document.get("additionalImages", [])):
            if isinstance(value, str) and value:
                locators.append((f"/additionalImages/{index}", value))
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for locator, url in locators:
            if url in seen:
                continue
            seen.add(url)
            result.append(media_candidate(
                source_id=self.source_id, source_object_id=str(document["objectID"]), source_locator=locator,
                url_or_identifier=url,
                hints={"isPublicDomain": document.get("isPublicDomain"), "primary_image_is_rights_proof": False,
                       "object_level_oa_candidate": document.get("isPublicDomain") is True},
                license_rule_id=self.rule("media")["rule_id"],
            ))
        return result

    def detect_contract_drift(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"code": "unknown_source_field", "raw_locator": f"/{json_pointer_part(field)}"}
                for field in sorted(set(document) - self._known_fields)]
