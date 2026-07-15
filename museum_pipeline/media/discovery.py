from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from museum_pipeline.hashing import sha256_bytes
from museum_pipeline.media.constants import COMMONS_SEARCH_HOST, SOURCE_POLICIES
from museum_pipeline.media.inputs import normalized_text, years


def metadata_request_url(source_id: str, object_id: str) -> str:
    return str(SOURCE_POLICIES[source_id]["metadata_url"]).format(object_id=object_id)


def parse_official_metadata(source_id: str, body: bytes) -> dict[str, Any]:
    document = json.loads(body.decode("utf-8"))
    if source_id == "source:met_open_access":
        return _parse_met(document)
    if source_id == "source:aic_api":
        return _parse_aic(document)
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
