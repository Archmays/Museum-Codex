from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from museum_pipeline.adapters._utils import candidate_claim, json_pointer_part
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.provenance import finalize_candidate, provenance_entry, provisional_candidate_id
from museum_pipeline.normalization.rights import media_candidate


class AicAdapter(SourceAdapter):
    source_id = "aic_api"
    adapter_name = "Art Institute of Chicago artwork fields adapter"
    supported_record_types = ("collection_object",)
    object_id_pattern = re.compile(r"^[1-9][0-9]{0,9}$")

    def profile_fields(self, query_profile: str) -> list[str]:
        profiles = self.configuration.get("query_profiles", {})
        if query_profile not in profiles:
            raise PipelineError("query_profile_invalid", "Unknown AIC query profile")
        return list(profiles[query_profile])

    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        self.validate_object_id(object_id)
        fields = self.profile_fields(query_profile)
        base = self.configuration["endpoint_template"].format(object_id=object_id)
        url = f"{base}?{urlencode({'fields': ','.join(fields)})}"
        headers = self.default_headers()
        headers["AIC-User-Agent"] = headers["User-Agent"]
        request = RequestSpec("GET", url, headers, query_profile)
        self.validate_request(request)
        return request

    def validate_request(self, request: RequestSpec) -> None:
        super().validate_request(request)
        pairs = parse_qsl(request.url.split("?", 1)[1] if "?" in request.url else "", keep_blank_values=True)
        if len(pairs) != 1 or pairs[0][0] != "fields":
            raise PipelineError("aic_fields_invalid", "AIC requests require exactly one explicit fields parameter")
        expected = self.profile_fields(request.query_profile)
        observed = pairs[0][1].split(",") if pairs[0][1] else []
        if observed != expected:
            raise PipelineError("aic_fields_invalid", "AIC request fields must exactly match the selected approved profile")

    def validate_response_contract(self, response: ResponseContract) -> dict[str, Any]:
        if response.status_code != 200:
            raise PipelineError("response_status_invalid", f"AIC returned HTTP {response.status_code}")
        document = self.decode_json(response)
        if not isinstance(document, dict) or not isinstance(document.get("data"), dict):
            raise PipelineError("contract_required_field_missing", "AIC response has no data object")
        if not isinstance(document.get("info"), dict) or not isinstance(document.get("config"), dict):
            raise PipelineError("contract_required_field_missing", "AIC response lacks info/config contract blocks")
        data = document["data"]
        query_pairs = parse_qsl(urlsplit(response.final_url).query, keep_blank_values=True)
        if len(query_pairs) != 1 or query_pairs[0][0] != "fields":
            raise PipelineError("aic_fields_invalid", "AIC response is not tied to one explicit fields request")
        response_fields = query_pairs[0][1].split(",") if query_pairs[0][1] else []
        profiles = [name for name in ("default", "description") if response_fields == self.profile_fields(name)]
        if len(profiles) != 1:
            raise PipelineError("aic_fields_invalid", "AIC response request fields do not match an approved profile")
        profile = profiles[0]
        expected_fields = set(self.profile_fields(profile))
        missing = expected_fields - set(data)
        if missing:
            raise PipelineError("contract_required_field_missing", f"AIC response omitted requested fields: {', '.join(sorted(missing))}")
        extra = set(data) - expected_fields
        if extra:
            raise PipelineError("contract_unexpected_field", f"AIC response added unapproved fields: {', '.join(sorted(extra))}")
        if not isinstance(data.get("id"), int) or isinstance(data.get("id"), bool):
            raise PipelineError("contract_type_changed", "AIC id is no longer an integer")
        if not isinstance(data.get("is_public_domain"), bool):
            raise PipelineError("contract_type_changed", "AIC is_public_domain is no longer boolean")
        for field in expected_fields - {"id", "is_public_domain"}:
            if data[field] is not None and not isinstance(data[field], str):
                raise PipelineError("contract_type_changed", f"AIC field changed type: {field}")
        expected_id = urlsplit(response.final_url).path.rsplit("/", 1)[-1]
        if str(data["id"]) != expected_id:
            raise PipelineError("contract_identity_mismatch", "AIC response identity differs from the requested object")
        return document

    def extract_source_object_ids(self, document: dict[str, Any]) -> list[str]:
        return [str(document["data"]["id"])]

    def normalize(self, document: dict[str, Any], *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        data = document["data"]
        source_object_id = str(data["id"])
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        fields: dict[str, Any] = {}
        provenance: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        license_map = self.map_license_rules(list(data))
        for field in sorted(data):
            if field == "image_id":
                continue
            value = data[field]
            fields[field] = value
            pointer = f"/data/{json_pointer_part(field)}"
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/{json_pointer_part(field)}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=pointer, raw_value=value, normalized_value=value,
                rule_id=license_map[field], content_class="data", observed_at=observed_at,
            ))
            claims.append(candidate_claim(
                candidate_id=candidate_id, predicate=f"source_{field}", value=value,
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=pointer, source_tier=1, license_rule_id=license_map[field],
            ))
        candidate = {
            "schema_version": "1.0.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": "artwork",
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": self.extract_media_candidates(document), "conflicts": [],
            "contract_drift": self.detect_contract_drift(document), "quarantine": [],
            "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        observed = set(fields)
        approved = {frozenset(self.profile_fields("default")), frozenset(self.profile_fields("description"))}
        if frozenset(observed) not in approved:
            raise PipelineError("aic_fields_invalid", "AIC fields must exactly derive from an approved explicit profile")
        cc0 = self.rule("data")["rule_id"]
        cc_by = self.rule("data", field="description")["rule_id"]
        return {field: (cc_by if field == "description" else cc0) for field in sorted(observed)}

    def extract_media_candidates(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        data = document["data"]
        image_id = data.get("image_id")
        if not isinstance(image_id, str) or not image_id:
            return []
        return [media_candidate(
            source_id=self.source_id, source_object_id=str(data["id"]), source_locator="/data/image_id",
            url_or_identifier=image_id,
            hints={"is_public_domain": data.get("is_public_domain"), "copyright_notice": data.get("copyright_notice"),
                   "credit_line": data.get("credit_line"), "iiif_access_is_license": False,
                   "object_level_rights_review_required": True},
            license_rule_id=self.rule("media")["rule_id"],
        )]

    def detect_contract_drift(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        data = document.get("data", {})
        allowed = set(self.profile_fields("description"))
        drift = [{"code": "unknown_source_field", "raw_locator": f"/data/{json_pointer_part(field)}"}
                 for field in sorted(set(data) - allowed)]
        for root_field in sorted(set(document) - {"data", "info", "config"}):
            drift.append({"code": "unknown_root_field", "raw_locator": f"/{json_pointer_part(root_field)}"})
        return drift
