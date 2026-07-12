from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from museum_pipeline.adapters._utils import candidate_claim, json_pointer_part
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.config import source_configuration
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.dates import incompatible_life_dates, normalize_wikidata_time
from museum_pipeline.normalization.external_ids import WIKIDATA_EXTERNAL_ID_PROPERTIES
from museum_pipeline.normalization.names import normalize_name, validate_language_tag
from museum_pipeline.normalization.provenance import finalize_candidate, provenance_entry, provisional_candidate_id
from museum_pipeline.normalization.rights import media_candidate


class WikidataAdapter(SourceAdapter):
    source_id = "wikidata"
    adapter_name = "Wikidata explicit entity adapter"
    supported_record_types = ("wikidata_item",)
    object_id_pattern = re.compile(r"^Q[1-9][0-9]{0,11}$")

    _entity_keys = {
        "pageid", "ns", "title", "lastrevid", "modified", "type", "id",
        "labels", "descriptions", "aliases", "claims", "sitelinks",
    }
    _entity_field_types = {
        "pageid": int, "ns": int, "title": str, "lastrevid": int, "modified": str,
        "type": str, "id": str, "labels": dict, "descriptions": dict, "aliases": dict,
        "claims": dict, "sitelinks": dict,
    }

    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        self.validate_object_id(object_id)
        if query_profile != "default":
            raise PipelineError("query_profile_invalid", "Wikidata supports only the explicit-entity profile")
        request = RequestSpec(
            method="GET",
            url=self.configuration["endpoint_template"].format(object_id=object_id),
            headers=self.default_headers(),
            query_profile=query_profile,
        )
        self.validate_request(request)
        return request

    def validate_response_contract(self, response: ResponseContract) -> dict[str, Any]:
        if response.status_code != 200:
            raise PipelineError("response_status_invalid", f"Wikidata returned HTTP {response.status_code}")
        document = self.decode_json(response)
        if not isinstance(document, dict) or not isinstance(document.get("entities"), dict) or not document["entities"]:
            raise PipelineError("contract_required_field_missing", "Wikidata response has no entities object")
        for entity_id, entity in document["entities"].items():
            if self.object_id_pattern.fullmatch(entity_id) is None or not isinstance(entity, dict):
                raise PipelineError("contract_type_changed", "Wikidata entity shape changed")
            if entity.get("id") != entity_id:
                raise PipelineError("contract_identity_mismatch", "Wikidata entity ID does not match its key")
            for field, expected_type in self._entity_field_types.items():
                if field in entity and (not isinstance(entity[field], expected_type) or (expected_type is int and isinstance(entity[field], bool))):
                    raise PipelineError("contract_type_changed", f"Wikidata {field} changed type")
            for field in ("labels", "aliases", "claims"):
                if not isinstance(entity.get(field), dict):
                    raise PipelineError("contract_type_changed", f"Wikidata {field} is no longer an object")
            for language, label in entity.get("labels", {}).items():
                if not isinstance(label, dict) or label.get("language") != language or not isinstance(label.get("value"), str):
                    raise PipelineError("contract_type_changed", "Wikidata label shape changed")
            for language, aliases in entity.get("aliases", {}).items():
                if not isinstance(aliases, list) or any(
                    not isinstance(alias, dict) or alias.get("language") != language or not isinstance(alias.get("value"), str)
                    for alias in aliases
                ):
                    raise PipelineError("contract_type_changed", "Wikidata alias shape changed")
            for property_id, statements in entity.get("claims", {}).items():
                if not isinstance(statements, list) or any(not isinstance(statement, dict) for statement in statements):
                    raise PipelineError("contract_type_changed", f"Wikidata claim list changed type: {property_id}")
                for statement in statements:
                    if not isinstance(statement.get("mainsnak"), dict):
                        raise PipelineError("contract_type_changed", f"Wikidata statement mainsnak changed type: {property_id}")
                    if statement.get("rank", "normal") not in {"preferred", "normal", "deprecated"}:
                        raise PipelineError("contract_type_changed", f"Wikidata statement rank changed: {property_id}")
                    if "references" in statement and not isinstance(statement["references"], list):
                        raise PipelineError("contract_type_changed", f"Wikidata references changed type: {property_id}")
                    if "qualifiers" in statement and not isinstance(statement["qualifiers"], dict):
                        raise PipelineError("contract_type_changed", f"Wikidata qualifiers changed type: {property_id}")
                    datavalue = statement["mainsnak"].get("datavalue")
                    if datavalue is not None and not isinstance(datavalue, dict):
                        raise PipelineError("contract_type_changed", f"Wikidata datavalue changed type: {property_id}")
        expected_id = urlsplit(response.final_url).path.rsplit("/", 1)[-1].removesuffix(".json")
        if set(document["entities"]) != {expected_id}:
            raise PipelineError("contract_identity_mismatch", "Wikidata response identity differs from the requested entity")
        return document

    def extract_source_object_ids(self, document: dict[str, Any]) -> list[str]:
        return sorted(document["entities"])

    @staticmethod
    def _statements(entity: dict[str, Any], property_id: str) -> list[tuple[int, dict[str, Any], Any]]:
        values: list[tuple[int, dict[str, Any], Any]] = []
        for index, statement in enumerate(entity.get("claims", {}).get(property_id, [])):
            if not isinstance(statement, dict):
                continue
            mainsnak = statement.get("mainsnak", {})
            data_value = mainsnak.get("datavalue", {}) if isinstance(mainsnak, dict) else {}
            if isinstance(data_value, dict) and "value" in data_value:
                values.append((index, statement, data_value["value"]))
        return values

    def normalize(self, document: dict[str, Any], *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        source_object_id = self.extract_source_object_ids(document)[0]
        entity = document["entities"][source_object_id]
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        data_rule = self.rule("data")
        fields: dict[str, Any] = {"names": [], "external_ids": {}, "birth_observations": [], "death_observations": []}
        provenance: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []

        for language, label in sorted(entity.get("labels", {}).items()):
            if not isinstance(label, dict) or not isinstance(label.get("value"), str):
                continue
            normalized = normalize_name(label["value"])
            validate_language_tag(language)
            name = {"text": normalized, "original_text": label["value"], "language": language, "script": None, "name_type": "preferred"}
            fields["names"].append(name)
            pointer = f"/entities/{source_object_id}/labels/{json_pointer_part(language)}/value"
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/names/{len(fields['names']) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=pointer, raw_value=label["value"], normalized_value=normalized,
                rule_id=data_rule["rule_id"], content_class="data", observed_at=observed_at,
                language=language, transform_id="unicode_nfc_whitespace",
            ))

        for language, aliases in sorted(entity.get("aliases", {}).items()):
            if not isinstance(aliases, list):
                continue
            for index, alias in enumerate(aliases):
                if not isinstance(alias, dict) or not isinstance(alias.get("value"), str):
                    continue
                normalized = normalize_name(alias["value"])
                validate_language_tag(language)
                name = {"text": normalized, "original_text": alias["value"], "language": language, "script": None, "name_type": "alternate"}
                fields["names"].append(name)
                pointer = f"/entities/{source_object_id}/aliases/{json_pointer_part(language)}/{index}/value"
                provenance.append(provenance_entry(
                    candidate_id=candidate_id, field_pointer=f"/fields/names/{len(fields['names']) - 1}",
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=pointer, raw_value=alias["value"], normalized_value=normalized,
                    rule_id=data_rule["rule_id"], content_class="data", observed_at=observed_at,
                    language=language, transform_id="unicode_nfc_whitespace",
                ))

        for property_id, name in WIKIDATA_EXTERNAL_ID_PROPERTIES.items():
            for index, statement, value in self._statements(entity, property_id):
                if not isinstance(value, str):
                    continue
                fields["external_ids"].setdefault(name, []).append(value)
                pointer = f"/entities/{source_object_id}/claims/{property_id}/{index}/mainsnak/datavalue/value"
                provenance.append(provenance_entry(
                    candidate_id=candidate_id, field_pointer=f"/fields/external_ids/{name}/{len(fields['external_ids'][name]) - 1}",
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=pointer, raw_value=value, normalized_value=value,
                    rule_id=data_rule["rule_id"], content_class="data", observed_at=observed_at,
                ))
                claims.append(candidate_claim(
                    candidate_id=candidate_id, predicate=f"external_id_{name}", value=value,
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=pointer, source_tier=3, license_rule_id=data_rule["rule_id"],
                    metadata=self._statement_metadata(statement),
                ))

        date_fields = (("P569", "birth_observations", "birth_date"), ("P570", "death_observations", "death_date"))
        for property_id, field_name, predicate in date_fields:
            for index, statement, value in self._statements(entity, property_id):
                if not isinstance(value, dict):
                    continue
                normalized_date = normalize_wikidata_time(value)
                fields[field_name].append({"source_display_text": value.get("time", ""), **normalized_date})
                pointer = f"/entities/{source_object_id}/claims/{property_id}/{index}/mainsnak/datavalue/value"
                provenance.append(provenance_entry(
                    candidate_id=candidate_id, field_pointer=f"/fields/{field_name}/{len(fields[field_name]) - 1}",
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=pointer, raw_value=value, normalized_value=normalized_date,
                    rule_id=data_rule["rule_id"], content_class="data", observed_at=observed_at,
                    transform_id="wikidata_time_precision",
                ))
                claims.append(candidate_claim(
                    candidate_id=candidate_id, predicate=predicate, value=normalized_date,
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=pointer, source_tier=3, license_rule_id=data_rule["rule_id"],
                    metadata=self._statement_metadata(statement),
                ))

        instance_ids = {
            value.get("id") for _, _, value in self._statements(entity, "P31") if isinstance(value, dict)
        }
        candidate_kind = "individual" if "Q5" in instance_ids else "unknown"
        conflicts: list[dict[str, Any]] = []
        birth = fields["birth_observations"][0] if fields["birth_observations"] else None
        death = fields["death_observations"][0] if fields["death_observations"] else None
        if incompatible_life_dates(birth, death):
            conflicts.append({"code": "birth_after_death", "severity": "hard", "status": "unresolved"})

        mapped_properties = set(WIKIDATA_EXTERNAL_ID_PROPERTIES) | {"P18", "P31", "P569", "P570"}
        quarantine = [{"raw_locator": f"/entities/{source_object_id}/claims/{property_id}", "reason": "unmapped_source_assertion"}
                      for property_id in sorted(set(entity.get("claims", {})) - mapped_properties)]
        candidate = {
            "schema_version": "1.0.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": candidate_kind,
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": self.extract_media_candidates(document), "conflicts": conflicts,
            "contract_drift": self.detect_contract_drift(document), "quarantine": quarantine,
            "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    @staticmethod
    def _statement_metadata(statement: dict[str, Any]) -> dict[str, Any]:
        references = statement.get("references")
        qualifiers = statement.get("qualifiers")
        return {
            "rank": statement.get("rank", "normal"),
            "qualifiers_present": isinstance(qualifiers, dict) and bool(qualifiers),
            "references_present": isinstance(references, list) and bool(references),
        }

    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        rule_id = self.rule("data")["rule_id"]
        return {field: rule_id for field in sorted(set(fields))}

    def extract_media_candidates(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for source_object_id in self.extract_source_object_ids(document):
            entity = document["entities"][source_object_id]
            for index, statement, value in self._statements(entity, "P18"):
                if isinstance(value, str):
                    result.append(media_candidate(
                        source_id=self.source_id, source_object_id=source_object_id,
                        source_locator=f"/entities/{source_object_id}/claims/P18/{index}/mainsnak/datavalue/value",
                        url_or_identifier=value,
                        hints={"commons_file_reference": True, "wikidata_license_inherited": False, **self._statement_metadata(statement)},
                        license_rule_id=self.rule("media")["rule_id"],
                    ))
        return result

    def detect_contract_drift(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        drift: list[dict[str, Any]] = []
        unknown_root = sorted(set(document) - {"entities"})
        for key in unknown_root:
            drift.append({"code": "unknown_root_field", "raw_locator": f"/{json_pointer_part(key)}"})
        for entity_id, entity in document.get("entities", {}).items():
            for key in sorted(set(entity) - self._entity_keys):
                drift.append({"code": "unknown_entity_field", "raw_locator": f"/entities/{entity_id}/{json_pointer_part(key)}"})
        return drift
