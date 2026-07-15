from __future__ import annotations

from pathlib import Path

from museum_pipeline.config import ROOT


PHASE_ID = "MUSEUM-03C"
PIPELINE_EXECUTOR = "automated_cross_validation_pipeline"
M03B_PACKAGE = ROOT / "data" / "reviewed" / "art" / "museum-03b" / "museum-03b-first-slate-v1" / "package-v1"
EXPECTED_M03B_PACKAGE_HASH = "sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86"
EXPECTED_M03B_GRAPH_HASH = "sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3"

MEDIA_VAULT = ROOT / "data" / "media-source" / "art" / "museum-03c"
REVIEWED_ROOT = ROOT / "data" / "reviewed" / "art" / "museum-03c"
LEDGER_PATH = REVIEWED_ROOT / "media-source-ledger.json"
BUNDLE_ROOT = REVIEWED_ROOT / "media-bundle-v1"

TARGET_WIDTHS = (320, 640, 960, 1600)
FINAL_DECISIONS = {
    "approved_self_hosted",
    "approved_external_delivery",
    "metadata_only_after_automated_review",
    "blocked_rights_conflict",
    "blocked_identity_conflict",
    "blocked_quality_failure",
    "blocked_source_unavailable",
}

SOURCE_POLICIES = {
    "source:met_open_access": {
        "short_id": "met_open_access",
        "metadata_host": "collectionapi.metmuseum.org",
        "media_hosts": ("images.metmuseum.org",),
        "metadata_url": "https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}",
        "minimum_interval_seconds": 0.25,
        "object_id_pattern": r"[1-9][0-9]*",
        "rights_field": "isPublicDomain",
        "institution": "The Metropolitan Museum of Art",
    },
    "source:aic_api": {
        "short_id": "aic_api",
        "metadata_host": "api.artic.edu",
        "media_hosts": ("www.artic.edu",),
        "metadata_url": (
            "https://api.artic.edu/api/v1/artworks/{object_id}?fields="
            "api_link,artist_display,copyright_notice,credit_line,date_display,department_title,"
            "id,image_id,is_public_domain,main_reference_number,medium_display,title"
        ),
        "minimum_interval_seconds": 1.0,
        "object_id_pattern": r"[1-9][0-9]*",
        "rights_field": "is_public_domain",
        "institution": "Art Institute of Chicago",
    },
    "source:cleveland_open_access": {
        "short_id": "cleveland_open_access",
        "metadata_host": "openaccess-api.clevelandart.org",
        "object_hosts": ("clevelandart.org",),
        "media_hosts": ("openaccess-cdn.clevelandart.org",),
        "metadata_url": "https://openaccess-api.clevelandart.org/api/artworks/{object_id}",
        "minimum_interval_seconds": 1.0,
        "object_id_pattern": r"[1-9][0-9]*",
        "rights_field": "share_license_status",
        "allowed_media_rights": ("CC0",),
        "media_rule_id": "cleveland_open_access:media:9f5808165c51",
        "rights_policy_url": "https://www.clevelandart.org/open-access",
        "institution": "Cleveland Museum of Art",
    },
    "source:rijksmuseum": {
        "short_id": "rijksmuseum",
        "metadata_host": "data.rijksmuseum.nl",
        "object_hosts": ("id.rijksmuseum.nl",),
        "media_hosts": ("iiif.micr.io",),
        "metadata_url": "https://data.rijksmuseum.nl/{object_id}?_profile=la-framed",
        "minimum_interval_seconds": 1.0,
        "object_id_pattern": r"[1-9][0-9]*",
        "rights_field": "visual_item.subject_to[].classified_as[].id",
        "allowed_media_rights": (
            "https://creativecommons.org/publicdomain/mark/1.0/",
            "https://creativecommons.org/publicdomain/zero/1.0/",
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        "media_rule_id": "rijksmuseum:media:9afa251862e4",
        "rights_policy_url": "https://data.rijksmuseum.nl/policy/information-and-data-policy",
        "institution": "Rijksmuseum",
    },
}

COMMONS_SEARCH_HOST = "commons.wikimedia.org"
MAX_METADATA_BYTES = 5 * 1024 * 1024
MAX_MEDIA_BYTES = 100 * 1024 * 1024
MAX_DECODE_PIXELS = 100_000_000


def artwork_slug(artwork_id: str) -> str:
    prefix = "artwork:"
    if not artwork_id.startswith(prefix):
        raise ValueError("M03C artwork IDs must use the artwork: prefix")
    slug = artwork_id[len(prefix):]
    if not slug or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in slug):
        raise ValueError("M03C artwork ID is not safe for a vault path")
    return slug


def artwork_vault(artwork_id: str) -> Path:
    return MEDIA_VAULT / artwork_slug(artwork_id)
