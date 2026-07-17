from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from museum_pipeline.adapters._utils import candidate_claim
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.provenance import finalize_candidate, provenance_entry, provisional_candidate_id


class GettyTgnAdapter(SourceAdapter):
    source_id = "getty_tgn"
    adapter_name = "Getty TGN linked-data place adapter"
    adapter_version = "0.1.0"
    supported_record_types = ("tgn_place_record",)
    object_id_pattern = re.compile(r"^[0-9]{7}$")
    _id_pattern = re.compile(r"/tgn/([0-9]{7})$")
    _known_root = {
        "@context", "_label", "classified_as", "id", "identified_by", "inScheme",
        "part_of", "see_also", "subject_of", "type",
    }

    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        self.validate_object_id(object_id)
        if query_profile != "default":
            raise PipelineError("query_profile_invalid", "Getty TGN supports one per-record profile")
        headers = self.default_headers()
        headers["Accept"] = "application/ld+json, application/json;q=0.9"
        request = RequestSpec(
            "GET", self.configuration["endpoint_template"].format(object_id=object_id), headers, query_profile,
        )
        self.validate_request(request)
        return request

    def validate_response_contract(self, response: ResponseContract) -> Any:
        if response.status_code != 200:
            raise PipelineError("response_status_invalid", f"Getty TGN returned HTTP {response.status_code}")
        document = self.decode_json(response)
        if not isinstance(document, dict):
            raise PipelineError("contract_required_field_missing", "Getty TGN JSON must be an object")
        if document.get("type") != "Place" or not isinstance(document.get("id"), str):
            raise PipelineError("contract_required_field_missing", "Getty TGN record must identify a Place")
        source_ids = self.extract_source_object_ids(document)
        expected_id = urlsplit(response.final_url).path.rsplit("/", 1)[-1].removesuffix(".json")
        if source_ids != [expected_id]:
            raise PipelineError("contract_identity_mismatch", "Getty TGN response identity differs from the requested record")
        for field in ("identified_by", "classified_as", "part_of"):
            if field in document and not isinstance(document[field], list):
                raise PipelineError("contract_type_changed", f"Getty TGN field changed type: {field}")
        if not isinstance(document.get("_label"), str):
            raise PipelineError("contract_required_field_missing", "Getty TGN record has no preferred display label")
        return document

    def extract_source_object_ids(self, document: Any) -> list[str]:
        if not isinstance(document, dict) or not isinstance(document.get("id"), str):
            return []
        match = self._id_pattern.search(document["id"])
        return [match.group(1)] if match else []

    @staticmethod
    def _classification_labels(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            item["_label"] for item in value
            if isinstance(item, dict) and isinstance(item.get("_label"), str)
        ]

    @staticmethod
    def _language(value: Any) -> str:
        if not isinstance(value, list) or not value or not isinstance(value[0], dict):
            return "und"
        language = value[0].get("_label")
        return language if isinstance(language, str) and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language) else "und"

    @staticmethod
    def _coordinate(document: dict[str, Any]) -> tuple[list[float] | None, str | None]:
        for index, item in enumerate(document.get("identified_by", [])):
            if not isinstance(item, dict):
                continue
            classifications = " ".join(GettyTgnAdapter._classification_labels(item.get("classified_as"))).lower()
            if "geojson coordinate point" not in classifications or not isinstance(item.get("value"), str):
                continue
            try:
                value = json.loads(item["value"])
            except json.JSONDecodeError:
                raise PipelineError("coordinate_invalid", "Getty TGN coordinate is not valid GeoJSON JSON") from None
            if (
                not isinstance(value, list) or len(value) != 2
                or not all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in value)
                or not -180 <= value[0] <= 180 or not -90 <= value[1] <= 90
            ):
                raise PipelineError("coordinate_invalid", "Getty TGN coordinate is outside WGS84 bounds")
            return [float(value[0]), float(value[1])], f"/identified_by/{index}/value"
        return None, None

    def normalize(self, document: Any, *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        if not isinstance(document, dict):
            raise PipelineError("normalization_required_field_missing", "Getty TGN document is not an object")
        source_object_id = self.extract_source_object_ids(document)[0]
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        rule = self.rule("data")
        names: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        for index, item in enumerate(document.get("identified_by", [])):
            if not isinstance(item, dict) or item.get("type") != "Name" or not isinstance(item.get("content"), str):
                continue
            classifications = " ".join(self._classification_labels(item.get("classified_as"))).lower()
            name_type = "historical" if "historical term" in classifications else "preferred" if "preferred term" in classifications else "alternate"
            name = {"text": item["content"], "language": self._language(item.get("language")), "name_type": name_type}
            names.append(name)
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/names/{len(names) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=f"/identified_by/{index}/content", raw_value=item["content"], normalized_value=name,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                language=name["language"], transform_id="unicode_nfc_whitespace",
            ))
        if not names:
            names.append({"text": document["_label"], "language": "und", "name_type": "preferred"})

        coordinates, coordinate_locator = self._coordinate(document)
        if coordinates is not None and coordinate_locator is not None:
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer="/fields/coordinates",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=coordinate_locator, raw_value=json.dumps(coordinates, separators=(",", ":")),
                normalized_value=coordinates, rule_id=rule["rule_id"], content_class="data",
                observed_at=observed_at, transform_id="geojson_point_parse",
            ))
        broader = [
            {"id": item.get("id"), "label": item.get("_label")}
            for item in document.get("part_of", []) if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        fields = {
            "preferred_label": document["_label"],
            "names": names,
            "place_types": self._classification_labels(document.get("classified_as")),
            "broader": broader,
            "coordinates": coordinates,
            "coordinate_reference_system": "WGS84" if coordinates is not None else None,
        }
        provenance.extend([
            provenance_entry(
                candidate_id=candidate_id, field_pointer="/fields/preferred_label",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator="/_label", raw_value=document["_label"], normalized_value=document["_label"],
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="unicode_nfc_whitespace",
            ),
            provenance_entry(
                candidate_id=candidate_id, field_pointer="/fields/place_types",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator="/classified_as", raw_value=document.get("classified_as", []),
                normalized_value=fields["place_types"], rule_id=rule["rule_id"], content_class="data",
                observed_at=observed_at, transform_id="linked_art_type_labels",
            ),
            provenance_entry(
                candidate_id=candidate_id, field_pointer="/fields/broader",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator="/part_of", raw_value=document.get("part_of", []), normalized_value=broader,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="linked_art_place_hierarchy",
            ),
        ])
        if coordinates is not None and coordinate_locator is not None:
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer="/fields/coordinate_reference_system",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=coordinate_locator, raw_value="GeoJSON Coordinate Point", normalized_value="WGS84",
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="geojson_crs_contract",
            ))
        claims = [candidate_claim(
            candidate_id=candidate_id, predicate="place_identity", value={"tgn_id": source_object_id, "label": document["_label"]},
            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
            raw_locator="/id", source_tier=1, license_rule_id=rule["rule_id"],
        )]
        if coordinates is not None and coordinate_locator is not None:
            claims.append(candidate_claim(
                candidate_id=candidate_id, predicate="reference_coordinates", value=coordinates,
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=coordinate_locator, source_tier=1, license_rule_id=rule["rule_id"],
                metadata={"precision_warning": "TGN coordinates are approximate finding aids, not exact sites."},
            ))
        candidate = {
            "schema_version": "1.1.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": "place",
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": [], "conflicts": [], "contract_drift": self.detect_contract_drift(document),
            "quarantine": [], "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        rule_id = self.rule("data")["rule_id"]
        return {field: rule_id for field in fields}

    def extract_media_candidates(self, document: Any) -> list[dict[str, Any]]:
        return []

    def detect_contract_drift(self, document: Any) -> list[dict[str, Any]]:
        if not isinstance(document, dict):
            return [{"raw_locator": "/", "reason": "root_not_object"}]
        return [
            {"raw_locator": f"/{key}", "reason": "unmapped_upstream_field"}
            for key in sorted(set(document) - self._known_root)
        ]
