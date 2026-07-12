from __future__ import annotations

from typing import Any

from museum_pipeline.normalization.names import normalize_name


def compare_candidates(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    hard_conflicts: list[dict[str, Any]] = []
    left_external = _external_ids(left)
    right_external = _external_ids(right)
    for scheme in sorted(set(left_external) & set(right_external)):
        overlap = sorted(left_external[scheme] & right_external[scheme])
        if overlap:
            signals.append({"signal_type": "exact_external_id", "strength": "strong", "scheme": scheme, "values": overlap})
    left_same_as = set(left.get("fields", {}).get("same_as", []))
    right_same_as = set(right.get("fields", {}).get("same_as", []))
    same_as_overlap = sorted(left_same_as & right_same_as)
    if same_as_overlap:
        signals.append({"signal_type": "source_same_as", "strength": "strong", "values": same_as_overlap})

    name_overlap = sorted(_names(left) & _names(right))
    if name_overlap:
        signals.append({"signal_type": "name_or_alias", "strength": "weak", "values": name_overlap})

    transliteration_overlap = sorted(
        (_transliterations(left) & _names(right)) | (_transliterations(right) & _names(left))
    )
    shared_scripts = sorted(_scripts(left) & _scripts(right))
    script_values = [*transliteration_overlap, *(f"script:{value}" for value in shared_scripts)]
    if script_values:
        signals.append({"signal_type": "script_or_transliteration", "strength": "weak", "values": sorted(set(script_values))})

    left_kind = left.get("candidate_kind")
    right_kind = right.get("candidate_kind")
    if left_kind != right_kind and left_kind != "unknown" and right_kind != "unknown":
        hard_conflicts.append({"conflict_type": "identity_kind_mismatch", "left": left_kind, "right": right_kind})

    left_birth = _date_years(left, "birth_observations")
    right_birth = _date_years(right, "birth_observations")
    left_death = _date_years(left, "death_observations")
    right_death = _date_years(right, "death_observations")
    life_overlap = [
        *(f"birth:{year}" for year in sorted(left_birth & right_birth)),
        *(f"death:{year}" for year in sorted(left_death & right_death)),
    ]
    if life_overlap:
        signals.append({"signal_type": "life_dates", "strength": "moderate", "values": life_overlap})
    if left_birth and right_birth and min(abs(a - b) for a in left_birth for b in right_birth) > 2:
        hard_conflicts.append({"conflict_type": "birth_date_conflict", "left": sorted(left_birth), "right": sorted(right_birth)})
    if left_death and right_death and min(abs(a - b) for a in left_death for b in right_death) > 2:
        hard_conflicts.append({"conflict_type": "death_date_conflict", "left": sorted(left_death), "right": sorted(right_death)})
    for candidate in (left, right):
        for conflict in candidate.get("conflicts", []):
            if conflict.get("severity") == "hard":
                hard_conflicts.append({"conflict_type": conflict.get("code", "candidate_hard_conflict"), "candidate_id": candidate.get("id")})

    place_period = sorted(
        {f"place:{item}" for item in _field_tokens(left, ("activity_places", "places")) & _field_tokens(right, ("activity_places", "places"))}
        | {f"period:{item}" for item in _field_tokens(left, ("activity_periods", "periods")) & _field_tokens(right, ("activity_periods", "periods"))}
    )
    if place_period:
        signals.append({"signal_type": "place_period", "strength": "moderate", "values": place_period})
    institutions = sorted(_field_tokens(left, ("institutions", "affiliations")) & _field_tokens(right, ("institutions", "affiliations")))
    if institutions:
        signals.append({"signal_type": "institution", "strength": "moderate", "values": institutions})
    collection_clues = sorted(
        _field_tokens(left, ("collection_clues", "work_clues", "accession_numbers"))
        & _field_tokens(right, ("collection_clues", "work_clues", "accession_numbers"))
    )
    if collection_clues:
        signals.append({"signal_type": "collection_clue", "strength": "weak", "values": collection_clues})
    return {"signals": signals, "hard_conflicts": hard_conflicts}


def special_identity_mapping_issues(source_kind: str, normalized_kind: str) -> list[str]:
    protected = {"anonymous", "workshop", "collective", "traditional_attribution", "conventional_identity"}
    if source_kind in protected and normalized_kind == "individual":
        return ["special_identity_coercion"]
    return []


def _external_ids(candidate: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    fields = candidate.get("fields", {})
    for scheme, values in fields.get("external_ids", {}).items():
        collection = values if isinstance(values, list) else [values]
        result[scheme] = {str(value) for value in collection if value not in {None, ""}}
    for field, scheme in (("artist_wikidata_url", "wikidata"), ("artist_ulan_url", "getty_ulan")):
        if fields.get(field):
            result.setdefault(scheme, set()).add(str(fields[field]).rstrip("/").split("/")[-1])
    return result


def _names(candidate: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in candidate.get("fields", {}).get("names", []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            result.add(normalize_name(item["text"]).casefold())
    creator = candidate.get("fields", {}).get("creator_display")
    if isinstance(creator, str) and creator.strip():
        result.add(normalize_name(creator).casefold())
    return result


def _transliterations(candidate: dict[str, Any]) -> set[str]:
    return {
        normalize_name(str(item["text"])).casefold()
        for item in candidate.get("fields", {}).get("names", [])
        if isinstance(item, dict) and item.get("name_type") == "transliteration" and isinstance(item.get("text"), str)
    }


def _scripts(candidate: dict[str, Any]) -> set[str]:
    return {
        str(item["script"])
        for item in candidate.get("fields", {}).get("names", [])
        if isinstance(item, dict) and isinstance(item.get("script"), str) and item["script"]
    }


def _date_years(candidate: dict[str, Any], field: str) -> set[int]:
    result: set[int] = set()
    for item in candidate.get("fields", {}).get(field, []):
        text = str(item.get("display_text", item.get("source_display_text", ""))) if isinstance(item, dict) else str(item)
        digits = text.lstrip("+-")[:4]
        if digits.isdigit():
            result.add(int(digits))
    event_type = "birth" if field.startswith("birth") else "death"
    for item in candidate.get("fields", {}).get("life_observations", []):
        if not isinstance(item, dict) or item.get("event_type") != event_type:
            continue
        text = str(item.get("display_text", item.get("source_display_text", "")))
        digits = text.lstrip("+-")[:4]
        if digits.isdigit():
            result.add(int(digits))
    return result


def _field_tokens(candidate: dict[str, Any], field_names: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    fields = candidate.get("fields", {})
    for field_name in field_names:
        values = fields.get(field_name, [])
        collection = values if isinstance(values, list) else [values]
        for value in collection:
            if isinstance(value, dict):
                token = value.get("id") or value.get("label") or value.get("text") or value.get("name")
            else:
                token = value
            if token not in {None, ""}:
                result.add(normalize_name(str(token)).casefold())
    return result
