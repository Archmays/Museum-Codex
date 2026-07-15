from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from museum_pipeline.hashing import sha256_bytes
from museum_pipeline.media.constants import COMMONS_SEARCH_HOST, SOURCE_POLICIES
from museum_pipeline.media.inputs import normalized_text, years


_RIJKS_OBJECT_NUMBER_CLASS = "https://id.rijksmuseum.nl/22015218"
_RIJKS_PRIMARY_TITLE_CLASS = "http://vocab.getty.edu/aat/300417200"
_RIJKS_CREDIT_LINE_CLASS = "http://vocab.getty.edu/aat/300026687"
_RIJKS_ENGLISH_LANGUAGE = "http://vocab.getty.edu/aat/300388277"
_RIJKS_MEDIA_RIGHTS = {
    "https://creativecommons.org/publicdomain/mark/1.0/": "public_domain_mark",
    "https://creativecommons.org/publicdomain/zero/1.0/": "cc0",
    "https://creativecommons.org/licenses/by/4.0/": "cc_by_4_0",
}
_RIJKS_CHAIN_STEPS = {
    "object": ("HumanMadeObject", "shows", "VisualItem"),
    "visual_item": ("VisualItem", "digitally_shown_by", "DigitalObject"),
    "digital_object": ("DigitalObject", None, None),
}


def metadata_request_url(source_id: str, object_id: str) -> str:
    policy = SOURCE_POLICIES.get(source_id)
    if policy is None:
        raise ValueError(f"unsupported M03C source: {source_id}")
    pattern = policy.get("object_id_pattern")
    if pattern and re.fullmatch(str(pattern), str(object_id)) is None:
        raise ValueError(f"invalid M03C object ID for {source_id}")
    return str(policy["metadata_url"]).format(object_id=object_id)


def rijks_object_pid(object_id: str) -> str:
    policy = SOURCE_POLICIES["source:rijksmuseum"]
    if re.fullmatch(str(policy["object_id_pattern"]), str(object_id)) is None:
        raise ValueError("invalid Rijksmuseum object ID")
    return f"https://{policy['object_hosts'][0]}/{object_id}"


def rijks_resolver_url(pid: str) -> str:
    policy = SOURCE_POLICIES["source:rijksmuseum"]
    identifier = _canonical_rijks_identifier(pid, policy["object_hosts"][0])
    if identifier is None:
        raise ValueError("Rijksmuseum chain contains a non-canonical PID")
    return f"https://{policy['metadata_host']}/{identifier}?_profile=la-framed"


def validate_rijks_chain_step(
    body: bytes,
    *,
    role: str,
    expected_pid: str,
) -> tuple[dict[str, Any], str | None]:
    specification = _RIJKS_CHAIN_STEPS.get(role)
    if specification is None:
        raise ValueError(f"unsupported Rijksmuseum chain role: {role}")
    document = json.loads(body.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Rijksmuseum resolver response must be a JSON object")

    expected_type, link_field, linked_type = specification
    actual_pid = str(document.get("id") or "")
    if actual_pid != expected_pid:
        raise ValueError(f"Rijksmuseum {role} response PID does not match the requested PID")
    rijks_resolver_url(actual_pid)
    if document.get("type") != expected_type:
        raise ValueError(f"Rijksmuseum {role} response has the wrong entity type")
    if link_field is None:
        return document, None

    links = document.get(link_field)
    if not isinstance(links, list) or len(links) != 1 or not isinstance(links[0], dict):
        raise ValueError(f"Rijksmuseum {role} response requires exactly one {link_field} link")
    link = links[0]
    next_pid = str(link.get("id") or "")
    if link.get("type") != linked_type:
        raise ValueError(f"Rijksmuseum {role} response has the wrong linked entity type")
    rijks_resolver_url(next_pid)
    return document, next_pid


def parse_official_metadata(source_id: str, body: bytes) -> dict[str, Any]:
    document = json.loads(body.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Official metadata response must be a JSON object")
    if source_id == "source:met_open_access":
        return _parse_met(document)
    if source_id == "source:aic_api":
        return _parse_aic(document)
    if source_id == "source:cleveland_open_access":
        return _parse_cleveland(document)
    if source_id == "source:rijksmuseum":
        return _parse_rijks(document)
    raise ValueError(f"unsupported M03C source: {source_id}")


def identity_comparison(expected: dict[str, Any], observed: dict[str, Any]) -> dict[str, bool]:
    expected_title = normalized_text(expected.get("title"))
    observed_title = normalized_text(observed.get("title"))
    expected_artist = normalized_text(expected.get("artist"))
    observed_artist = normalized_text(observed.get("artist"))
    expected_years = years(expected.get("date"))
    observed_years = years(observed.get("date"))
    return {
        "official_object_id_match": str(observed.get("official_object_id")) == str(expected.get("official_object_id")),
        "accession_match": normalized_text(observed.get("accession")) == normalized_text(expected.get("accession")),
        "artist_match": bool(expected_artist and (expected_artist in observed_artist or observed_artist in expected_artist)),
        "title_match": bool(expected_title and expected_title == observed_title),
        "date_match": bool(not expected_years or expected_years <= observed_years),
        "institution_match": bool(observed.get("institution_verified")),
        "object_url_match": bool(observed.get("object_url") and observed.get("canonical_object_url_verified")),
        "source_identity_match": bool(observed.get("source_identity_verified")),
    }


def commons_search_url(title: str, artist: str) -> str:
    query = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrlimit": "3",
            "gsrsearch": f'filetype:bitmap "{title}" "{artist}"',
            "prop": "imageinfo",
            "iiprop": "url|sha1|extmetadata",
            "iiurlwidth": "320",
        }
    )
    return f"https://{COMMONS_SEARCH_HOST}/w/api.php?{query}"


def parse_commons_search(body: bytes) -> list[dict[str, Any]]:
    document = json.loads(body.decode("utf-8"))
    pages = ((document.get("query") or {}).get("pages") or []) if isinstance(document, dict) else []
    candidates: list[dict[str, Any]] = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        metadata = info.get("extmetadata") or {}
        value = lambda key: (metadata.get(key) or {}).get("value")  # noqa: E731
        candidates.append(
            {
                "page_id": page.get("pageid"),
                "title": page.get("title"),
                "description_url": info.get("descriptionurl"),
                "revision_sha1": info.get("sha1"),
                "license_short_name": value("LicenseShortName"),
                "license_url": value("LicenseUrl"),
                "artist": value("Artist"),
                "credit": value("Credit"),
                "usage_terms": value("UsageTerms"),
                "preview_url": info.get("thumburl"),
                "promotion_eligible": False,
                "block_reasons": [
                    "no_registered_production_source_contract",
                    "official_museum_object_corroboration_not_closed",
                    "visual_identity_not_closed",
                    "permanent_revision_and_dispute_status_not_closed",
                ],
            }
        )
    return candidates


def build_discovery_record(
    request: dict[str, Any],
    response_body: bytes,
    *,
    response_sha256: str | None = None,
) -> dict[str, Any]:
    observed = parse_official_metadata(request["source_id"], response_body)
    comparison = identity_comparison(request["expected_identity"], observed["identity"])
    rights = observed["rights"]
    return {
        "artwork_id": request["artwork_id"],
        "request_id": request["id"],
        "source_id": request["source_id"],
        "source_object_id": request["source_object_id"],
        "metadata_url": metadata_request_url(request["source_id"], request["source_object_id"]),
        "metadata_response_sha256": response_sha256 or sha256_bytes(response_body),
        "observed_identity": observed["identity"],
        "identity_matches": comparison,
        "identity_closure": all(comparison.values()),
        "rights": rights,
        "rights_closure": bool(rights["object_open"] and rights["media_locator"] and not rights["conflict"]),
        "media": {
            "id": rights["media_id"],
            "source_url": rights["media_locator"],
            "preview_url": rights["preview_locator"],
            "trusted_hosts": sorted(SOURCE_POLICIES[request["source_id"]]["media_hosts"]),
        },
    }


def _parse_met(document: dict[str, Any]) -> dict[str, Any]:
    object_id = str(document.get("objectID") or "")
    public_url = str(document.get("objectURL") or "")
    primary = str(document.get("primaryImage") or "") or None
    preview = str(document.get("primaryImageSmall") or "") or None
    public_domain = document.get("isPublicDomain") is True
    rights_text = str(document.get("rightsAndReproduction") or "").strip()
    return {
        "identity": {
            "official_object_id": object_id,
            "accession": document.get("accessionNumber"),
            "artist": document.get("artistDisplayName"),
            "title": document.get("title"),
            "date": document.get("objectDate"),
            "institution": "The Metropolitan Museum of Art",
            "institution_verified": str(document.get("repository") or "").startswith("Metropolitan Museum"),
            "object_url": public_url,
            "canonical_object_url_verified": public_url.startswith("https://www.metmuseum.org/art/collection/search/"),
            "source_identity": "source:met_open_access",
            "source_identity_verified": True,
        },
        "rights": {
            "object_open": public_domain,
            "conflict": bool(rights_text),
            "conflict_text": rights_text or None,
            "media_id": primary.rsplit("/", 1)[-1] if primary else None,
            "media_locator": primary,
            "preview_locator": preview,
            "credit_line": document.get("creditLine"),
            "live_rights_status": "public_domain" if public_domain else "not_public_domain",
        },
    }


def _parse_aic(document: dict[str, Any]) -> dict[str, Any]:
    data = document.get("data") if isinstance(document, dict) else None
    if not isinstance(data, dict):
        raise ValueError("AIC response does not contain an artwork data object")
    object_id = str(data.get("id") or "")
    image_id = str(data.get("image_id") or "") or None
    public_domain = data.get("is_public_domain") is True
    copyright_notice = str(data.get("copyright_notice") or "").strip()
    base = f"https://www.artic.edu/iiif/2/{image_id}" if image_id else None
    return {
        "identity": {
            "official_object_id": object_id,
            "accession": data.get("main_reference_number"),
            "artist": data.get("artist_display"),
            "title": data.get("title"),
            "date": data.get("date_display"),
            "institution": "Art Institute of Chicago",
            "institution_verified": str(data.get("api_link") or "").startswith("https://api.artic.edu/api/v1/artworks/"),
            "object_url": data.get("api_link"),
            "canonical_object_url_verified": str(data.get("api_link") or "").endswith(f"/{object_id}"),
            "source_identity": "source:aic_api",
            "source_identity_verified": True,
        },
        "rights": {
            "object_open": public_domain,
            "conflict": bool(copyright_notice),
            "conflict_text": copyright_notice or None,
            "media_id": image_id,
            "media_locator": f"{base}/full/full/0/default.jpg" if base and public_domain else None,
            "preview_locator": f"{base}/full/320,/0/default.jpg" if base and public_domain else None,
            "credit_line": data.get("credit_line"),
            "live_rights_status": "public_domain" if public_domain else "copyright_or_restricted",
        },
    }


def _parse_cleveland(document: dict[str, Any]) -> dict[str, Any]:
    data = document.get("data")
    if not isinstance(data, dict):
        raise ValueError("Cleveland response does not contain an artwork data object")

    policy = SOURCE_POLICIES["source:cleveland_open_access"]
    object_id = str(data.get("id") or "")
    accession = str(data.get("accession_number") or "").strip()
    public_url = str(data.get("url") or "").strip()
    canonical_url = bool(
        accession
        and _trusted_https_url(public_url, policy["object_hosts"][0])
        and urlsplit(public_url).path == f"/art/{accession}"
    )
    source_identity = bool(re.fullmatch(r"[1-9][0-9]*", object_id)) and canonical_url

    creators = []
    for creator in _mapping_list(data.get("creators")):
        description = str(creator.get("description") or "").strip()
        if description and description not in creators:
            creators.append(description)

    images = data.get("images") if isinstance(data.get("images"), dict) else {}
    verified_images: dict[str, str] = {}
    invalid_image_url = False
    for profile in ("full", "print", "web"):
        profile_record = images.get(profile)
        if profile_record is None:
            continue
        if not isinstance(profile_record, dict):
            invalid_image_url = True
            continue
        image = profile_record
        locator = str(image.get("url") or "").strip()
        if not locator:
            continue
        if _valid_cleveland_media_url(
            locator,
            host=policy["media_hosts"][0],
            accession=accession,
            profile=profile,
        ):
            verified_images[profile] = locator
        else:
            invalid_image_url = True

    source_url = next((verified_images[key] for key in ("full", "print", "web") if key in verified_images), None)
    preview_url = verified_images.get("web") or source_url
    status = data.get("share_license_status")
    copyright_text = str(data.get("copyright") or "").strip()
    credit_line = str(data.get("creditline") or "").strip()
    conflict_reasons = []
    rights_open = status in policy["allowed_media_rights"]
    if not rights_open:
        conflict_reasons.append("share_license_status_not_cc0")
    if copyright_text:
        conflict_reasons.append("object_copyright_conflict")
    if invalid_image_url:
        conflict_reasons.append("untrusted_media_host")
    if not credit_line:
        conflict_reasons.append("attribution_missing")
    eligible = bool(source_identity and source_url and not conflict_reasons)

    return {
        "identity": {
            "official_object_id": object_id,
            "accession": accession,
            "artist": "; ".join(creators),
            "title": data.get("title"),
            "date": data.get("creation_date"),
            "institution": policy["institution"],
            "institution_verified": source_identity,
            "object_url": public_url,
            "canonical_object_url_verified": canonical_url,
            "source_identity": "source:cleveland_open_access",
            "source_identity_verified": source_identity,
        },
        "rights": {
            "object_open": rights_open,
            "conflict": bool(conflict_reasons),
            "conflict_text": ";".join(conflict_reasons) or None,
            "media_id": _url_basename(source_url) if eligible else None,
            "media_locator": source_url if eligible else None,
            "preview_locator": preview_url if eligible else None,
            "credit_line": credit_line or None,
            "live_rights_status": "cc0" if rights_open else "copyright_or_restricted",
            "source_rule_id": policy["media_rule_id"],
            "rights_statement_url": policy["rights_policy_url"],
            "attribution_required": True,
        },
    }


def _parse_rijks(document: dict[str, Any]) -> dict[str, Any]:
    artwork = document.get("object")
    visual_item = document.get("visual_item")
    digital_object = document.get("digital_object")
    if not all(isinstance(item, dict) for item in (artwork, visual_item, digital_object)):
        raise ValueError("Rijksmuseum media review requires object, visual_item, and digital_object records")

    policy = SOURCE_POLICIES["source:rijksmuseum"]
    object_pid = str(artwork.get("id") or "")
    visual_pid = str(visual_item.get("id") or "")
    digital_pid = str(digital_object.get("id") or "")
    object_id = _canonical_rijks_identifier(object_pid, policy["object_hosts"][0])
    visual_id = _canonical_rijks_identifier(visual_pid, policy["object_hosts"][0])
    digital_id = _canonical_rijks_identifier(digital_pid, policy["object_hosts"][0])
    shown_records = artwork.get("shows")
    digital_records = visual_item.get("digitally_shown_by")
    chain_verified = bool(
        object_id
        and visual_id
        and digital_id
        and artwork.get("type") == "HumanMadeObject"
        and visual_item.get("type") == "VisualItem"
        and digital_object.get("type") == "DigitalObject"
        and isinstance(shown_records, list)
        and len(shown_records) == 1
        and isinstance(shown_records[0], dict)
        and shown_records[0].get("id") == visual_pid
        and shown_records[0].get("type") == "VisualItem"
        and isinstance(digital_records, list)
        and len(digital_records) == 1
        and isinstance(digital_records[0], dict)
        and digital_records[0].get("id") == digital_pid
        and digital_records[0].get("type") == "DigitalObject"
    )

    identified_by = _mapping_list(artwork.get("identified_by"))
    object_number_records = [
        item
        for item in identified_by
        if item.get("type") == "Identifier" and _has_classification(item, _RIJKS_OBJECT_NUMBER_CLASS)
    ]
    accession = (
        str(object_number_records[0].get("content") or "").strip()
        if len(object_number_records) == 1
        else ""
    )
    title_records = [
        item
        for item in identified_by
        if item.get("type") == "Name" and _has_classification(item, _RIJKS_PRIMARY_TITLE_CLASS)
    ]
    title = _preferred_content(title_records)

    production = artwork.get("produced_by") if isinstance(artwork.get("produced_by"), dict) else {}
    creator_names = []
    for part in _mapping_list(production.get("part")):
        for creator in _mapping_list(part.get("carried_out_by")):
            name = _preferred_notation(_mapping_list(creator.get("notation")))
            if name and name not in creator_names:
                creator_names.append(name)
    timespan = production.get("timespan") if isinstance(production.get("timespan"), dict) else {}
    date = _preferred_content(_mapping_list(timespan.get("identified_by")))
    if not date:
        date = str(timespan.get("begin_of_the_begin") or "")[:4]

    record_rights_id = f"https://{policy['metadata_host']}/{object_id}" if object_id else ""
    record_rights_records = [
        item
        for item in _mapping_list(artwork.get("subject_of"))
        if item.get("type") == "LinguisticObject" and item.get("id") == record_rights_id
    ]
    record_rights_url = (
        _single_rights_identifier(record_rights_records[0]) if len(record_rights_records) == 1 else None
    )
    record_rights_open = record_rights_url in policy["allowed_media_rights"]

    media_rights_url = _single_rights_identifier(visual_item)
    media_rights_open = media_rights_url in policy["allowed_media_rights"]
    digital_subjects = digital_object.get("subject_to")
    digital_rights = _single_rights_identifier(digital_object)
    digital_conflict = digital_subjects not in (None, []) and digital_rights != media_rights_url

    credit_records = [
        item
        for item in _mapping_list(artwork.get("referred_to_by"))
        if item.get("type") == "LinguisticObject" and _has_classification(item, _RIJKS_CREDIT_LINE_CLASS)
    ]
    object_credit = _english_content(credit_records)

    access_points = _mapping_list(digital_object.get("access_point"))
    media_url = str(access_points[0].get("id") or "") if len(access_points) == 1 else ""
    media_verified = bool(
        len(access_points) == 1
        and access_points[0].get("type") == "DigitalObject"
        and _valid_rijks_iiif_url(media_url, policy["media_hosts"][0])
    )
    conflict_reasons = []
    if not record_rights_open:
        conflict_reasons.append("unapproved_or_missing_object_record_rights")
    if not media_rights_open:
        conflict_reasons.append("unapproved_or_missing_media_rights")
    if digital_conflict:
        conflict_reasons.append("digital_object_rights_conflict")
    if access_points and not media_verified:
        conflict_reasons.append("untrusted_or_invalid_iiif_access_point")
    if not object_credit:
        conflict_reasons.append("attribution_missing")
    eligible = bool(
        chain_verified
        and media_verified
        and record_rights_open
        and media_rights_open
        and object_credit
        and not conflict_reasons
    )

    return {
        "identity": {
            "official_object_id": object_id or "",
            "accession": accession,
            "artist": "; ".join(creator_names),
            "title": title,
            "date": date,
            "institution": policy["institution"],
            "institution_verified": chain_verified,
            "object_url": object_pid,
            "canonical_object_url_verified": bool(object_id),
            "source_identity": "source:rijksmuseum",
            "source_identity_verified": chain_verified,
        },
        "rights": {
            "object_open": bool(record_rights_open and media_rights_open),
            "conflict": bool(conflict_reasons),
            "conflict_text": ";".join(conflict_reasons) or None,
            "media_id": _rijks_media_id(media_url) if eligible else None,
            "media_locator": media_url if eligible else None,
            "preview_locator": media_url if eligible else None,
            "credit_line": f"Rijksmuseum — {object_credit}" if object_credit else None,
            "object_credit_line": object_credit or None,
            "attribution_source": "object.referred_to_by[AAT:300026687][en]" if object_credit else None,
            "live_rights_status": _RIJKS_MEDIA_RIGHTS.get(media_rights_url, "unknown_or_restricted"),
            "source_rule_id": policy["media_rule_id"],
            "rights_statement_url": media_rights_url,
            "object_record_rights_statement_url": record_rights_url,
            "rights_policy_url": policy["rights_policy_url"],
            "attribution_required": True,
        },
    }


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _has_classification(record: dict[str, Any], identifier: str) -> bool:
    return any(str(item.get("id") or "") == identifier for item in _mapping_list(record.get("classified_as")))


def _is_english(record: dict[str, Any]) -> bool:
    return any(str(item.get("id") or "") == _RIJKS_ENGLISH_LANGUAGE for item in _mapping_list(record.get("language")))


def _preferred_content(records: list[dict[str, Any]]) -> str:
    for record in [*filter(_is_english, records), *filter(lambda item: not _is_english(item), records)]:
        value = str(record.get("content") or "").strip()
        if value:
            return value
    return ""


def _english_content(records: list[dict[str, Any]]) -> str:
    for record in records:
        if _is_english(record):
            value = str(record.get("content") or "").strip()
            if value:
                return value
    return ""


def _preferred_notation(records: list[dict[str, Any]]) -> str:
    for language in ("en", None):
        for record in records:
            if language is not None and record.get("@language") != language:
                continue
            value = str(record.get("@value") or "").strip()
            if value:
                return value
    return ""


def _single_rights_identifier(record: dict[str, Any]) -> str | None:
    rights = record.get("subject_to")
    if not isinstance(rights, list) or len(rights) != 1 or not isinstance(rights[0], dict):
        return None
    right = rights[0]
    classifications = right.get("classified_as")
    if right.get("type") != "Right" or not isinstance(classifications, list) or len(classifications) != 1:
        return None
    classification = classifications[0]
    if not isinstance(classification, dict):
        return None
    identifier = str(classification.get("id") or "").strip()
    return identifier or None


def _trusted_https_url(value: str, host: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == host
        and port in (None, 443)
        and not parsed.username
        and not parsed.password
        and parsed.path.startswith("/")
        and not parsed.query
        and not parsed.fragment
    )


def _canonical_rijks_identifier(value: str, host: str) -> str | None:
    if not _trusted_https_url(value, host):
        return None
    match = re.fullmatch(r"/([1-9][0-9]*)", urlsplit(value).path)
    return match.group(1) if match else None


def _valid_cleveland_media_url(value: str, *, host: str, accession: str, profile: str) -> bool:
    if not accession or not _trusted_https_url(value, host):
        return False
    parts = [part for part in urlsplit(value).path.split("/") if part]
    return bool(
        len(parts) == 2
        and parts[0] == accession
        and re.fullmatch(
            rf"{re.escape(accession)}_{re.escape(profile)}\.(?:jpe?g|png|tiff?|webp)",
            parts[1],
            flags=re.IGNORECASE,
        )
    )


def _valid_rijks_iiif_url(value: str, host: str) -> bool:
    if not _trusted_https_url(value, host):
        return False
    return re.fullmatch(
        r"/[A-Za-z0-9_-]+/full/(?:max|full)/0/default\.(?:jpe?g|png|tiff?|webp)",
        urlsplit(value).path,
        flags=re.IGNORECASE,
    ) is not None


def _url_basename(value: str | None) -> str | None:
    return urlsplit(value).path.rsplit("/", 1)[-1] if value else None


def _rijks_media_id(value: str) -> str | None:
    parts = [part for part in urlsplit(value).path.split("/") if part]
    return parts[0] if parts else None
