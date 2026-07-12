from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from museum_pipeline.adapters._utils import candidate_claim, json_pointer_part, nested_literals
from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.errors import PipelineError
from museum_pipeline.normalization.names import normalize_name
from museum_pipeline.normalization.provenance import finalize_candidate, provenance_entry, provisional_candidate_id


class GettyUlanAdapter(SourceAdapter):
    source_id = "getty_ulan"
    adapter_name = "Getty ULAN linked-data record adapter"
    adapter_version = "0.1.1"
    supported_record_types = ("ulan_authority_record",)
    object_id_pattern = re.compile(r"^[0-9]{9}$")
    _id_pattern = re.compile(r"/ulan/([0-9]{9})(?:-agent)?$")
    _linked_art_known_root = {
        "@context", "_label", "born", "carried_out", "classified_as", "died", "equivalent",
        "id", "identified_by", "la:related_from_by", "rdfs:seeAlso", "referred_to_by",
        "skos:inScheme", "subject_of", "type",
    }

    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        self.validate_object_id(object_id)
        if query_profile != "default":
            raise PipelineError("query_profile_invalid", "Getty ULAN supports one per-record profile")
        headers = self.default_headers()
        headers["Accept"] = "application/ld+json, application/json;q=0.9"
        request = RequestSpec("GET", self.configuration["endpoint_template"].format(object_id=object_id), headers, query_profile)
        self.validate_request(request)
        return request

    @staticmethod
    def _nodes(document: Any) -> list[dict[str, Any]]:
        if isinstance(document, list):
            return [item for item in document if isinstance(item, dict)]
        if isinstance(document, dict) and isinstance(document.get("@graph"), list):
            return [item for item in document["@graph"] if isinstance(item, dict)]
        if isinstance(document, dict):
            return [document]
        return []

    def validate_response_contract(self, response: ResponseContract) -> Any:
        if response.status_code != 200:
            raise PipelineError("response_status_invalid", f"Getty ULAN returned HTTP {response.status_code}")
        document = self.decode_json(response)
        nodes = self._nodes(document)
        if not nodes:
            raise PipelineError("contract_required_field_missing", "Getty ULAN JSON-LD has no nodes")
        if any(
            ("@id" in node and not isinstance(node["@id"], str))
            or ("id" in node and not isinstance(node["id"], str))
            for node in nodes
        ):
            raise PipelineError("contract_type_changed", "Getty ULAN identity locator is no longer a string")
        if not self.extract_source_object_ids(document):
            raise PipelineError("contract_identity_missing", "Getty ULAN response has no canonical ULAN URI")
        expected_id = urlsplit(response.final_url).path.rsplit("/", 1)[-1].removesuffix(".json")
        if self.extract_source_object_ids(document) != [expected_id]:
            raise PipelineError("contract_identity_mismatch", "Getty ULAN response identity differs from the requested record")
        if isinstance(document, dict) and isinstance(document.get("id"), str):
            typed_fields = {
                "_label": str, "born": dict, "carried_out": list, "classified_as": list,
                "died": dict, "equivalent": list, "identified_by": list,
            }
            for field, expected in typed_fields.items():
                if field in document and not isinstance(document[field], expected):
                    raise PipelineError("contract_type_changed", f"Getty ULAN field changed type: {field}")
        return document

    def extract_source_object_ids(self, document: Any) -> list[str]:
        values: set[str] = set()
        for node in self._nodes(document):
            identifier = node.get("@id", node.get("id"))
            if isinstance(identifier, str):
                match = self._id_pattern.search(identifier)
                if match:
                    values.add(match.group(1))
        return sorted(values)

    def normalize(self, document: Any, *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        if isinstance(document, dict) and isinstance(document.get("id"), str):
            return self._normalize_linked_art(document, snapshot_id=snapshot_id, observed_at=observed_at)
        source_object_id = self.extract_source_object_ids(document)[0]
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        rule = self.rule("data")
        fields: dict[str, Any] = {
            "names": [], "roles": [], "classifications": [], "life_observations": [],
            "birth_observations": [], "death_observations": [], "activity_places": [],
            "activity_periods": [], "same_as": [],
        }
        provenance: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        mapped_pointers: set[str] = set()
        type_tokens: set[str] = set()

        for node_index, node in enumerate(self._nodes(document)):
            base = f"/{node_index}" if isinstance(document, list) else f"/@graph/{node_index}" if "@graph" in document else ""
            raw_type = node.get("@type")
            for _, text, _ in nested_literals(raw_type, f"{base}/@type"):
                type_tokens.add(text.lower())
            for key, value in sorted(node.items()):
                lowered = key.lower()
                pointer = f"{base}/{json_pointer_part(key)}"
                literals = nested_literals(value, pointer)
                if any(token in lowered for token in ("preflabel", "termdisplay", "_label")):
                    for raw_locator, text, language in literals:
                        normalized = normalize_name(text)
                        fields["names"].append({"text": normalized, "original_text": text, "language": language or "und", "script": None, "name_type": "preferred"})
                        mapped_pointers.add(raw_locator)
                        provenance.append(provenance_entry(
                            candidate_id=candidate_id, field_pointer=f"/fields/names/{len(fields['names']) - 1}",
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, raw_value=text, normalized_value=normalized,
                            rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                            language=language or "und", transform_id="unicode_nfc_whitespace",
                        ))
                elif "altlabel" in lowered:
                    for raw_locator, text, language in literals:
                        normalized = normalize_name(text)
                        fields["names"].append({"text": normalized, "original_text": text, "language": language or "und", "script": None, "name_type": "alternate"})
                        mapped_pointers.add(raw_locator)
                        provenance.append(provenance_entry(
                            candidate_id=candidate_id, field_pointer=f"/fields/names/{len(fields['names']) - 1}",
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, raw_value=text, normalized_value=normalized,
                            rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                            language=language or "und", transform_id="unicode_nfc_whitespace",
                        ))
                elif any(token in lowered for token in ("birth", "death", "eststart", "estend", "displaydate")):
                    for raw_locator, text, _ in literals:
                        observation = {"source_display_text": text, "precision": "uncertain", "range": None, "circa": False, "uncertain": True, "calendar": None}
                        fields["life_observations"].append(observation)
                        mapped_pointers.add(raw_locator)
                        provenance.append(provenance_entry(
                            candidate_id=candidate_id, field_pointer=f"/fields/life_observations/{len(fields['life_observations']) - 1}",
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, raw_value=text, normalized_value=observation,
                            rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                            transform_id="preserve_uncertain_date",
                        ))
                elif any(token in lowered for token in ("exactmatch", "sameas")):
                    for raw_locator, text, _ in literals:
                        fields["same_as"].append(text)
                        mapped_pointers.add(raw_locator)
                        provenance.append(provenance_entry(
                            candidate_id=candidate_id, field_pointer=f"/fields/same_as/{len(fields['same_as']) - 1}",
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, raw_value=text, normalized_value=text,
                            rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                        ))
                        claims.append(candidate_claim(
                            candidate_id=candidate_id, predicate="source_same_as", value=text,
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, source_tier=1, license_rule_id=rule["rule_id"],
                        ))
                elif "biography" in lowered or "role" in lowered:
                    for raw_locator, text, _ in literals:
                        fields["roles"].append(text)
                        mapped_pointers.add(raw_locator)
                        provenance.append(provenance_entry(
                            candidate_id=candidate_id, field_pointer=f"/fields/roles/{len(fields['roles']) - 1}",
                            source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                            raw_locator=raw_locator, raw_value=text, normalized_value=text,
                            rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                        ))

        candidate_kind = "unknown"
        joined_types = " ".join(sorted(type_tokens))
        if "personconcept" in joined_types or "person" in joined_types:
            candidate_kind = "individual"
        elif any(token in joined_types for token in ("groupconcept", "corporate", "organization", "firm", "studio")):
            candidate_kind = "corporate_body"
        if not fields["names"]:
            raise PipelineError("normalization_required_field_missing", "Getty ULAN record has no mapped name")

        quarantine: list[dict[str, Any]] = []
        for node_index, node in enumerate(self._nodes(document)):
            base = f"/{node_index}" if isinstance(document, list) else f"/@graph/{node_index}" if isinstance(document, dict) and "@graph" in document else ""
            for key in sorted(node):
                pointer = f"{base}/{json_pointer_part(key)}"
                if key not in {"@id", "@type"} and not any(item.startswith(pointer) for item in mapped_pointers):
                    quarantine.append({"raw_locator": pointer, "reason": "unmapped_jsonld_predicate"})

        candidate = {
            "schema_version": "1.0.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": candidate_kind,
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": [], "conflicts": [], "contract_drift": self.detect_contract_drift(document),
            "quarantine": quarantine, "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    def _normalize_linked_art(self, document: dict[str, Any], *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        source_object_id = self.extract_source_object_ids(document)[0]
        candidate_id = provisional_candidate_id(self.source_id, source_object_id)
        rule = self.rule("data")
        fields: dict[str, Any] = {
            "names": [], "roles": [], "classifications": [], "life_observations": [],
            "birth_observations": [], "death_observations": [], "activity_places": [],
            "activity_periods": [], "same_as": [],
        }
        provenance: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []

        def add_name(text: str, raw_locator: str, language: str, name_type: str) -> None:
            normalized = normalize_name(text)
            fields["names"].append({
                "text": normalized, "original_text": text, "language": language,
                "script": None, "name_type": name_type,
            })
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/names/{len(fields['names']) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=raw_locator, raw_value=text, normalized_value=normalized,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                language=language, transform_id="unicode_nfc_whitespace",
            ))

        if isinstance(document.get("_label"), str):
            add_name(document["_label"], "/_label", "und", "preferred")
        for index, identifier in enumerate(document.get("identified_by", [])):
            if not isinstance(identifier, dict) or not isinstance(identifier.get("content"), str):
                continue
            languages = identifier.get("language", [])
            language = "und"
            if isinstance(languages, list) and languages and isinstance(languages[0], dict):
                raw_language = languages[0].get("_label")
                if isinstance(raw_language, str) and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", raw_language):
                    language = raw_language
            classifications = " ".join(
                str(item.get("_label", "")).lower()
                for item in identifier.get("classified_as", []) if isinstance(item, dict)
            )
            name_type = "preferred" if "preferred" in classifications else "alternate"
            add_name(identifier["content"], f"/identified_by/{index}/content", language, name_type)

        raw_type = document.get("type")
        type_values = raw_type if isinstance(raw_type, list) else [raw_type]
        joined_types = " ".join(str(item).lower() for item in type_values if item is not None)
        candidate_kind = "individual" if "person" in joined_types else "corporate_body" if any(token in joined_types for token in ("group", "organization")) else "unknown"

        for date_key, predicate in (("born", "birth_date"), ("died", "death_date")):
            event = document.get(date_key)
            if not isinstance(event, dict) or not isinstance(event.get("timespan"), dict):
                continue
            timespan = event["timespan"]
            begin = timespan.get("begin_of_the_begin")
            end = timespan.get("end_of_the_end")
            if not isinstance(begin, str) and not isinstance(end, str):
                continue
            begin_text = begin or end
            end_text = end or begin
            same_year = isinstance(begin_text, str) and isinstance(end_text, str) and begin_text[:4] == end_text[:4]
            normalized_date = {
                "display_text": begin_text[:4] if same_year else f"{begin_text}–{end_text}",
                "precision": "year" if same_year else "range",
                "range": {"start": begin_text, "end": end_text},
                "circa": False, "uncertain": False, "calendar": "gregorian",
            }
            observation = {"event_type": date_key, "source_display_text": normalized_date["display_text"], **normalized_date}
            fields["life_observations"].append(observation)
            typed_field = "birth_observations" if date_key == "born" else "death_observations"
            fields[typed_field].append(observation)
            raw_locator = f"/{date_key}/timespan"
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/life_observations/{len(fields['life_observations']) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=raw_locator, raw_value=timespan, normalized_value=normalized_date,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="linked_art_timespan",
            ))
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/{typed_field}/{len(fields[typed_field]) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=raw_locator, raw_value=timespan, normalized_value=normalized_date,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                transform_id="linked_art_timespan",
            ))
            claims.append(candidate_claim(
                candidate_id=candidate_id, predicate=predicate, value=normalized_date,
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=raw_locator, source_tier=1, license_rule_id=rule["rule_id"],
            ))

        for activity_index, activity in enumerate(document.get("carried_out", [])):
            if not isinstance(activity, dict):
                continue
            for place_index, place in enumerate(activity.get("took_place_at", [])):
                if not isinstance(place, dict):
                    continue
                label = place.get("_label")
                identifier = place.get("id")
                if not isinstance(label, str) and not isinstance(identifier, str):
                    continue
                value = {"label": label, "id": identifier}
                fields["activity_places"].append(value)
                provenance.append(provenance_entry(
                    candidate_id=candidate_id, field_pointer=f"/fields/activity_places/{len(fields['activity_places']) - 1}",
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=f"/carried_out/{activity_index}/took_place_at/{place_index}", raw_value=place,
                    normalized_value=value, rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                ))
            timespan = activity.get("timespan")
            if isinstance(timespan, dict):
                start = timespan.get("begin_of_the_begin")
                end = timespan.get("end_of_the_end")
                if isinstance(start, str) or isinstance(end, str):
                    value = {"start": start, "end": end, "display_text": start if start == end else f"{start or '?'}–{end or '?'}"}
                    fields["activity_periods"].append(value)
                    provenance.append(provenance_entry(
                        candidate_id=candidate_id, field_pointer=f"/fields/activity_periods/{len(fields['activity_periods']) - 1}",
                        source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                        raw_locator=f"/carried_out/{activity_index}/timespan", raw_value=timespan,
                        normalized_value=value, rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
                        transform_id="linked_art_timespan",
                    ))

        for index, equivalent in enumerate(document.get("equivalent", [])):
            if not isinstance(equivalent, dict) or not isinstance(equivalent.get("id"), str):
                continue
            value = equivalent["id"]
            fields["same_as"].append(value)
            provenance.append(provenance_entry(
                candidate_id=candidate_id, field_pointer=f"/fields/same_as/{len(fields['same_as']) - 1}",
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=f"/equivalent/{index}/id", raw_value=value, normalized_value=value,
                rule_id=rule["rule_id"], content_class="data", observed_at=observed_at,
            ))
            claims.append(candidate_claim(
                candidate_id=candidate_id, predicate="source_same_as", value=value,
                source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                raw_locator=f"/equivalent/{index}/id", source_tier=1, license_rule_id=rule["rule_id"],
            ))

        for index, classification in enumerate(document.get("classified_as", [])):
            if not isinstance(classification, dict):
                continue
            label = classification.get("_label")
            if isinstance(label, str):
                categories = {
                    str(item.get("_label", "")).lower()
                    for item in classification.get("classified_as", []) if isinstance(item, dict)
                }
                target_field = "roles" if "roles" in categories else "classifications"
                fields[target_field].append({"label": label, "id": classification.get("id"), "categories": sorted(categories)})
                provenance.append(provenance_entry(
                    candidate_id=candidate_id, field_pointer=f"/fields/{target_field}/{len(fields[target_field]) - 1}",
                    source_id=self.source_id, source_object_id=source_object_id, snapshot_id=snapshot_id,
                    raw_locator=f"/classified_as/{index}", raw_value=classification,
                    normalized_value=fields[target_field][-1], rule_id=rule["rule_id"], content_class="data",
                    observed_at=observed_at,
                ))

        if not fields["names"]:
            raise PipelineError("normalization_required_field_missing", "Getty ULAN linked-art record has no mapped name")
        mapped_root = {"@context", "_label", "born", "carried_out", "classified_as", "died", "equivalent", "id", "identified_by", "type"}
        quarantine = [
            {"raw_locator": f"/{json_pointer_part(key)}", "reason": "known_unmapped_linked_art_branch"}
            for key in sorted(set(document) - mapped_root)
        ]
        for index, identifier in enumerate(document.get("identified_by", [])):
            if isinstance(identifier, dict):
                quarantine.extend(
                    {"raw_locator": f"/identified_by/{index}/{json_pointer_part(key)}", "reason": "unmapped_name_metadata"}
                    for key in sorted(set(identifier) - {"classified_as", "content", "language"})
                )
        candidate = {
            "schema_version": "1.0.0", "id": candidate_id, "entity_type": "normalized_candidate",
            "candidate_kind": candidate_kind,
            "source_records": [{"source_id": self.source_id, "source_object_id": source_object_id, "raw_snapshot_id": snapshot_id}],
            "fields": fields, "field_provenance": provenance, "candidate_claims": claims,
            "media_candidates": [], "conflicts": [], "contract_drift": self.detect_contract_drift(document),
            "quarantine": quarantine, "review_state": "candidate", "observed_at": observed_at, "publishable": False,
        }
        return finalize_candidate(candidate)

    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        rule_id = self.rule("data")["rule_id"]
        return {field: rule_id for field in sorted(set(fields))}

    def extract_media_candidates(self, document: Any) -> list[dict[str, Any]]:
        return []

    def detect_contract_drift(self, document: Any) -> list[dict[str, Any]]:
        drift: list[dict[str, Any]] = []
        if isinstance(document, dict) and isinstance(document.get("id"), str):
            drift.extend(
                {"code": "unknown_linked_art_root_field", "raw_locator": f"/{json_pointer_part(key)}"}
                for key in sorted(set(document) - self._linked_art_known_root)
            )
        for node_index, node in enumerate(self._nodes(document)):
            if "@id" not in node and "id" not in node:
                drift.append({"code": "jsonld_node_without_id", "raw_locator": f"/{node_index}"})
        return drift
