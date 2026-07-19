from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from museum_pipeline.canonical_json import canonical_json_bytes, write_canonical_json
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import sha256_file
from scripts.generate_release_integrity_ledger import physical_tree
from scripts.validate_governance_foundation import release_content_hash


PHASE_ID = "MUSEUM-09A"
BUILT_AT = "2026-07-19T18:00:00+08:00"
BASELINE_COMMIT = "d16817943ed404bf47ed222ebd2800438dd00602"
INPUT_RELEASE_ID = "release:art-v1-candidate-1.4.0"
INPUT_RELEASE_CONTENT_HASH = "sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202"
INPUT_RELEASE_MANIFEST_SHA256 = "sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114"
INPUT_RELEASE_TREE_SHA256 = "sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1"

RAW_ROOT = ROOT / "data" / "raw" / "museum-09a"
EXISTING_ROOT = (
    ROOT
    / "data"
    / "reviewed"
    / "art"
    / "museum-03b"
    / "museum-03b-first-slate-v1"
    / "package-v1"
)
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "reviewed"
    / "art"
    / "museum-09a"
    / "global-expansion-universe-v1"
)
DEFAULT_BATCH_REGISTRY = ROOT / "governance" / "museum-09-batch-registry.json"
PUBLIC_RELEASE = ROOT / "public" / "releases" / "art-v1-candidate-1.4.0"
SHARD_MAX_BYTES = 5 * 1024 * 1024
SHARDED_DOCUMENTS = {
    "normalized-candidates.json": {
        "collection_field": "candidates",
        "count_field": "candidate_count",
        "chunk_size": 1_750,
    },
    "deceased-evidence.json": {
        "collection_field": "records",
        "count_field": "evidence_count",
        "chunk_size": 3_500,
    },
    "candidate-artworks.json": {
        "collection_field": "artworks",
        "count_field": "artwork_count",
        "chunk_size": 2_250,
    },
    "target-artworks.json": {
        "collection_field": "artworks",
        "count_field": "artwork_count",
        "chunk_size": 2_500,
    },
}

REGION_QUOTAS = {
    "europe": 170,
    "east-asia": 65,
    "africa": 40,
    "latin-america-caribbean": 55,
    "north-america": 75,
    "south-asia": 30,
    "southeast-asia": 25,
    "west-central-asia": 25,
    "oceania": 15,
}
REGION_GUARDRAILS = {
    "europe": {"maximum": 175},
    "east-asia": {"minimum": 50},
    "africa": {"minimum": 40},
    "latin-america-caribbean": {"minimum": 40},
    "north-america": {"minimum": 40},
    "south-asia": {"minimum": 30},
    "southeast-asia": {"minimum": 20},
    "west-central-asia": {"minimum": 20},
    "oceania": {"minimum": 10},
}
EXISTING_COVERAGE = {
    "artist:albrecht-durer": "europe",
    "artist:francisco-de-goya": "europe",
    "artist:henry-ossawa-tanner": "north-america",
    "artist:jose-guadalupe-posada": "latin-america-caribbean",
    "artist:julia-margaret-cameron": "south-asia",
    "artist:kathe-kollwitz": "europe",
    "artist:katsushika-hokusai": "east-asia",
    "artist:kitagawa-utamaro": "east-asia",
    "artist:mary-cassatt": "north-america",
    "artist:raja-ravi-varma": "south-asia",
    "artist:shen-zhou": "east-asia",
    "artist:vincent-van-gogh": "europe",
}

SOURCE_PROFILES: dict[str, dict[str, Any]] = {
    "aic_api": {
        "title": "Art Institute of Chicago",
        "institution": "Art Institute of Chicago",
        "official_entry": "https://api.artic.edu/docs/",
        "metadata_license": "CC0-1.0 except excluded description field",
        "media_license": "object-specific; no media acquired in MUSEUM-09A",
        "rate_limit": "anonymous 60 requests/minute; bulk dump used",
        "api_key_required": False,
        "snapshot_or_bulk": "official monthly data dump",
        "identifier_stability": "numeric artwork and agent IDs",
        "attribution": "Art Institute of Chicago",
        "correction_route": "official collection feedback and API issue routes",
        "terms": "https://www.artic.edu/terms",
        "source_rule_id": "aic_api:data:75df7e022b4e",
    },
    "cleveland_open_access": {
        "title": "Cleveland Museum of Art Open Access",
        "institution": "Cleveland Museum of Art",
        "official_entry": "https://www.clevelandart.org/open-access-api",
        "metadata_license": "CC0-1.0",
        "media_license": "only object records explicitly marked CC0; no media acquired",
        "rate_limit": "not stated; bulk CSV used",
        "api_key_required": False,
        "snapshot_or_bulk": "official CSV dump",
        "identifier_stability": "numeric object ID and accession number",
        "attribution": "Cleveland Museum of Art",
        "correction_route": "official collection record contact route",
        "terms": "https://www.clevelandart.org/terms-and-conditions",
        "source_rule_id": "cleveland_open_access:data:818c1d328e7d",
    },
    "british_museum_collection": {
        "title": "British Museum Collections Online",
        "institution": "The British Museum",
        "official_entry": "https://www.britishmuseum.org/collection",
        "metadata_license": "RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION for internal candidate metadata",
        "media_license": "separate object-specific review; no media acquired",
        "rate_limit": "not stated; one fixed official record used",
        "api_key_required": False,
        "snapshot_or_bulk": "fixed official artist/object metadata snapshot",
        "identifier_stability": "museum registration number and biography ID",
        "attribution": "The British Museum",
        "correction_route": "official collection feedback route",
        "terms": "https://www.britishmuseum.org/terms-use",
        "source_rule_id": "museum09a:british_museum_collection:metadata:pass-by-user-authorization",
    },
    "cooper_hewitt_open_data": {
        "title": "Cooper Hewitt Collection Data",
        "institution": "Cooper Hewitt, Smithsonian Design Museum",
        "official_entry": "https://github.com/cooperhewitt/collection",
        "metadata_license": "CC0 project data",
        "media_license": "separate object-specific review; no media acquired",
        "rate_limit": "GitHub platform limits; bulk CSV used",
        "api_key_required": False,
        "snapshot_or_bulk": "official repository CSV snapshot",
        "identifier_stability": "collection object and person IDs",
        "attribution": "Cooper Hewitt, Smithsonian Design Museum",
        "correction_route": "official repository issue route",
        "terms": "https://www.si.edu/termsofuse",
        "source_rule_id": "museum09a:cooper_hewitt_open_data:metadata:pass-by-user-authorization",
    },
    "met_open_access": {
        "title": "The Metropolitan Museum of Art Open Access",
        "institution": "The Metropolitan Museum of Art",
        "official_entry": "https://metmuseum.github.io/",
        "metadata_license": "CC0-1.0",
        "media_license": "object-level Open Access designation only; no media acquired",
        "rate_limit": "bulk CSV preferred; API maximum 80 requests/second",
        "api_key_required": False,
        "snapshot_or_bulk": "official CSV snapshot",
        "identifier_stability": "numeric Object ID and Constituent ID",
        "attribution": "The Metropolitan Museum of Art",
        "correction_route": "official collection feedback route",
        "terms": "https://www.metmuseum.org/hubs/open-access",
        "source_rule_id": "met_open_access:data:8924a3c83dc7",
    },
    "mia_open_access": {
        "title": "Minneapolis Institute of Art Collection Data",
        "institution": "Minneapolis Institute of Art",
        "official_entry": "https://github.com/artsmia/collection",
        "metadata_license": "official repository open-data license",
        "media_license": "object-specific rights field; no media acquired",
        "rate_limit": "GitHub platform limits; fixed repository snapshot used",
        "api_key_required": False,
        "snapshot_or_bulk": "official repository snapshot",
        "identifier_stability": "numeric object ID and accession number",
        "attribution": "Minneapolis Institute of Art",
        "correction_route": "official collection and repository issue routes",
        "terms": "https://github.com/artsmia/collection/blob/master/LICENSE",
        "source_rule_id": "museum09a:mia_open_access:metadata:pass-by-user-authorization",
    },
    "moma_open_data": {
        "title": "Museum of Modern Art Collection Data",
        "institution": "The Museum of Modern Art",
        "official_entry": "https://github.com/MuseumofModernArt/collection",
        "metadata_license": "CC0 project data",
        "media_license": "not conveyed by dataset; no media acquired",
        "rate_limit": "GitHub platform limits; bulk CSV used",
        "api_key_required": False,
        "snapshot_or_bulk": "official repository CSV snapshot",
        "identifier_stability": "ConstituentID and ObjectID",
        "attribution": "The Museum of Modern Art",
        "correction_route": "official repository issue route",
        "terms": "https://github.com/MuseumofModernArt/collection",
        "source_rule_id": "museum09a:moma_open_data:metadata:pass-by-user-authorization",
    },
    "national_gallery_singapore": {
        "title": "National Gallery Singapore Collection Search",
        "institution": "National Gallery Singapore",
        "official_entry": "https://www.nationalgallery.sg/sg/en/our-collections.html",
        "metadata_license": "RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION for internal candidate metadata",
        "media_license": "object-specific future review; no media acquired",
        "rate_limit": "public search service limits not stated; cached requests only",
        "api_key_required": False,
        "snapshot_or_bulk": "cached official public-search responses with content hashes",
        "identifier_stability": "ArtPlus object ID and artist content-fragment ID",
        "attribution": "National Gallery Singapore",
        "correction_route": "official collection contact route",
        "terms": "https://www.nationalgallery.sg/sg/en/terms-of-use.html",
        "source_rule_id": "museum09a:national_gallery_singapore:metadata:pass-by-user-authorization",
    },
    "nga_open_data": {
        "title": "National Gallery of Art Open Data",
        "institution": "National Gallery of Art, Washington",
        "official_entry": "https://github.com/NationalGalleryOfArt/opendata",
        "metadata_license": "CC0-1.0",
        "media_license": "object-page Open Access designation only; no media acquired",
        "rate_limit": "GitHub platform limits; bulk CSV used",
        "api_key_required": False,
        "snapshot_or_bulk": "official CSV snapshot",
        "identifier_stability": "constituentid, objectid, UUID, accession number",
        "attribution": "National Gallery of Art, Washington",
        "correction_route": "official collection and repository routes",
        "terms": "https://www.nga.gov/terms-and-notices",
        "source_rule_id": "nga_open_data:data:8afdbf28a3ed",
    },
    "smithsonian_open_access": {
        "title": "Smithsonian Open Access",
        "institution": "Smithsonian Institution",
        "official_entry": "https://www.si.edu/openaccess/devtools",
        "metadata_license": "CC0 when marked and basic metadata under official Open Access terms",
        "media_license": "explicit object-level CC0 only; no media acquired",
        "rate_limit": "bulk snapshot used; no live API key dependency",
        "api_key_required": False,
        "snapshot_or_bulk": "official Open Access bulk shards",
        "identifier_stability": "Smithsonian record ID",
        "attribution": "Smithsonian Institution",
        "correction_route": "official Open Access feedback route",
        "terms": "https://www.si.edu/termsofuse",
        "source_rule_id": "smithsonian_open_access:data:592849901d36",
    },
    "tate_open_data": {
        "title": "Tate Collection Data",
        "institution": "Tate",
        "official_entry": "https://github.com/tategallery/collection",
        "metadata_license": "CC0 project data",
        "media_license": "not conveyed by dataset; no media acquired",
        "rate_limit": "GitHub platform limits; bulk CSV used",
        "api_key_required": False,
        "snapshot_or_bulk": "official repository CSV snapshot",
        "identifier_stability": "artist ID and artwork accession number",
        "attribution": "Tate",
        "correction_route": "official repository and collection routes",
        "terms": "https://www.tate.org.uk/about-us/policies-and-procedures/website-terms-use",
        "source_rule_id": "museum09a:tate_open_data:metadata:pass-by-user-authorization",
    },
    "vam_collections": {
        "title": "Victoria and Albert Museum Collections API",
        "institution": "Victoria and Albert Museum",
        "official_entry": "https://developers.vam.ac.uk/",
        "metadata_license": "official collection API terms; internal metadata use",
        "media_license": "object-specific future review; no media acquired",
        "rate_limit": "not stated; cached search responses only",
        "api_key_required": False,
        "snapshot_or_bulk": "cached official API responses",
        "identifier_stability": "system number and object URL",
        "attribution": "Victoria and Albert Museum",
        "correction_route": "official collection feedback route",
        "terms": "https://www.vam.ac.uk/info/va-websites-terms-conditions",
        "source_rule_id": "museum09a:vam_collections:metadata:pass-by-user-authorization",
    },
}

CROSS_SOURCE_MAP = {
    "moma": "moma_open_data",
    "met": "met_open_access",
    "cleveland": "cleveland_open_access",
    "smithsonian_fsg": "smithsonian_open_access",
    "vam": "vam_collections",
    "cooper_hewitt": "cooper_hewitt_open_data",
    "tate": "tate_open_data",
}

NON_PERSON_TERMS = {
    "anonymous",
    "architects",
    "association",
    "atelier",
    "bureau",
    "circle",
    "collective",
    "committee",
    "company",
    "corporation",
    "department",
    "designers",
    "dynasty",
    "factory",
    "firm",
    "foundation",
    "group",
    "inc",
    "ltd",
    "manufacturer",
    "office",
    "school",
    "studio",
    "team",
    "traditional",
    "unknown",
    "workshop",
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def normalize_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    folded = re.sub(r"[^\w]+", " ", folded, flags=re.UNICODE)
    return " ".join(folded.split())


def _name_forms(value: str) -> set[str]:
    result = {normalize_name(value)}
    if "," in value:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if len(parts) == 2:
            result.add(normalize_name(f"{parts[1]} {parts[0]}"))
    return {item for item in result if item}


def names_equivalent(left: str, right: str) -> bool:
    return bool(_name_forms(left) & _name_forms(right))


def _slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^a-zA-Z0-9]+", "-", folded.casefold()).strip("-")
    if folded:
        return folded[:80]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _year(value: Any) -> int | None:
    text = str(value or "").strip()
    matches = re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", text)
    if not matches:
        return None
    year = int(matches[-1])
    return year if year > 0 else None


def _is_person_name(name: str) -> bool:
    normalized = normalize_name(name)
    if not normalized or len(normalized) < 2:
        return False
    tokens = set(normalized.split())
    return not bool(tokens & NON_PERSON_TERMS)


def _pipe_first(value: str) -> str:
    return value.split("|", 1)[0].strip()


def _region_from_text(value: str) -> str | None:
    text = normalize_name(value)
    groups = {
        "africa": (
            "alger", "angola", "angolan", "benin", "botswana", "botswanan", "burkina",
            "burkinabe", "burundi", "burundian", "cameroon", "cameroonian",
            "cape verde", "cape verdean", "central african", "chad", "chadian", "congo",
            "congolese", "djibouti", "djiboutian", "egypt", "egyptian",
            "equatorial guinea", "equatoguinean", "eritrea", "eritrean", "eswatini",
            "ethiopia", "ethiopian", "gabon", "gabonese", "gambia", "gambian", "ghana",
            "ghanaian", "guinea", "guinean", "ivory coast", "ivorian", "kenya",
            "kenyan", "lesotho", "basotho", "liberia", "liberian", "libya", "libyan",
            "madagascar", "malagasy", "malawi", "malawian", "mali", "malian",
            "mauritania", "mauritanian", "mauritius", "mauritian", "morocco",
            "moroccan", "mozambique", "mozambican", "namibia", "namibian", "niger",
            "nigerien", "nigeria", "nigerian", "rwanda", "rwandan", "senegal",
            "senegalese", "seychelles", "seychellois", "sierra leone",
            "sierra leonean", "somalia", "somali", "south africa", "south african",
            "sudan", "sudanese", "tanzania", "tanzanian", "togo", "togolese", "tunisia",
            "tunisian", "uganda", "ugandan", "zambia", "zambian", "zimbabwe",
            "zimbabwean", "african",
        ),
        "east-asia": (
            "china", "chinese", "hong kong", "japan", "japanese", "korea", "korean",
            "macau", "mongolia", "mongolian", "taiwan", "taiwanese",
        ),
        "latin-america-caribbean": (
            "antigua", "argentin", "bahamas", "barbados", "belize", "bolivia", "brazil",
            "chile", "colombia", "costa rica", "cuba", "dominica", "dominican",
            "ecuador", "el salvador", "grenada", "guatemala", "guyana", "haiti",
            "honduras", "jamaica", "mexic", "nicaragua", "panama", "paraguay", "peru",
            "puerto ric", "saint lucia", "suriname", "trinidad", "uruguay", "venezuel",
        ),
        "north-america": (
            "american", "canada", "canadian", "united states",
        ),
        "oceania": (
            "australia", "australian", "fiji", "kiribati", "maori", "micronesia",
            "nauru", "new zealand", "papua new guinea", "samoa", "solomon", "tonga",
            "tuvalu", "vanuatu",
        ),
        "south-asia": (
            "afghanistan", "bangladesh", "bangladeshi", "bhutan", "india", "indian",
            "maldives", "nepal", "nepalese", "pakistan", "pakistani", "sri lanka",
            "sri lankan",
        ),
        "southeast-asia": (
            "brunei", "cambodia", "indonesia", "indonesian", "laos", "malaysia",
            "malaysian", "myanmar", "burma", "philippine", "singapore", "singaporean",
            "thailand", "thai", "timor", "vietnam", "vietnamese",
        ),
        "west-central-asia": (
            "armenia", "armenian", "azerbaijan", "bahrain", "cyprus", "georgia",
            "iran", "iranian", "iraq", "iraqi", "israel", "israeli", "jordan",
            "kazakh", "kuwait", "kyrgyz", "leban", "oman", "palestin", "qatar",
            "saudi", "syria", "syrian", "tajik", "turkey", "turkish", "turkmen",
            "united arab emirates", "uzbek", "yemen",
        ),
        "europe": (
            "alban", "austria", "austrian", "belarus", "belg", "bosnia", "britain",
            "british", "bulgaria", "croatia", "croatian", "czech", "denmark", "danish",
            "dutch", "england", "english", "eston", "finland", "finnish", "france",
            "french", "german", "germany", "greece", "greek", "hungar", "iceland",
            "ireland", "irish", "ital", "latvia", "lithuan", "luxembourg", "moldov",
            "montenegro", "netherlands", "north macedonia", "norway", "norwegian",
            "poland", "polish", "portugal", "portuguese", "romania", "romanian",
            "russia", "russian", "scotland", "scottish", "serbia", "serbian",
            "slovak", "sloven", "spain", "spanish", "sweden", "swedish",
            "switzerland", "swiss", "ukrain", "wales", "welsh", "yugoslav",
        ),
    }
    prefix_needles = {
        "alger", "argentin", "belg", "bulgaria", "chile", "colombia", "croatia",
        "eston", "hungar", "ital", "latvia", "leban", "lithuan", "moldov",
        "nepal", "palestin", "philippine", "portugal", "romania", "russia",
        "serbia", "slovak", "sloven", "syria", "taiwan", "ukrain", "venezuel",
    }
    for region, needles in groups.items():
        if any(
            re.search(
                rf"(?<!\w){re.escape(needle)}"
                + (r"\w*" if needle in prefix_needles else r"(?!\w)"),
                text,
            )
            for needle in needles
        ):
            return region
    return None


def _period(birth: int | None, death: int) -> str:
    pivot = birth if birth is not None else death
    if pivot < 1400:
        return "before-1400"
    if pivot <= 1599:
        return "1400-1599"
    if pivot <= 1799:
        return "1600-1799"
    if pivot <= 1899:
        return "1800-1899"
    if pivot <= 1949:
        return "1900-1949"
    return "1950-onward"


def _medium_tags(value: str) -> list[str]:
    text = normalize_name(value)
    mapping = {
        "architecture-design": ("architect", "design", "furniture", "model"),
        "ceramics": ("ceramic", "porcelain", "pottery", "stoneware", "earthenware"),
        "decorative-arts": ("glass", "jewelry", "silver", "metalwork", "decorative"),
        "drawing": ("drawing", "graphite", "charcoal", "chalk", "pencil", "ink"),
        "mixed-installation-performance-documentation": (
            "installation", "performance", "mixed media", "assemblage", "video",
        ),
        "painting": ("oil", "paint", "tempera", "gouache", "watercolor", "watercolour"),
        "photography": ("photograph", "gelatin silver", "albumen", "photogravure"),
        "printmaking": (
            "print", "etching", "engraving", "lithograph", "woodcut", "screenprint",
            "linocut", "aquatint",
        ),
        "sculpture": ("sculpture", "bronze", "marble", "carved", "plaster", "wood"),
        "textile-fiber": ("textile", "fiber", "fibre", "fabric", "tapestry", "weaving"),
    }
    result = [tag for tag, needles in mapping.items() if any(needle in text for needle in needles)]
    return result or ["other-documented-medium"]


class Universe:
    def __init__(self) -> None:
        self.artists: dict[str, dict[str, Any]] = {}
        self.index: dict[str, str] = {}
        self.raw_source_counts: Counter[str] = Counter()
        self.raw_seen: set[tuple[str, str]] = set()
        self.rejection_counts: Counter[str] = Counter()

    def _keys(
        self,
        *,
        name: str,
        death: int,
        ulan: str | None,
        wikidata: str | None,
    ) -> list[str]:
        keys = [f"name-death:{form}:{death}" for form in sorted(_name_forms(name))]
        if ulan:
            keys.insert(0, f"ulan:{ulan}")
        if wikidata:
            keys.insert(0, f"wikidata:{wikidata}")
        return keys

    def add_artist(
        self,
        *,
        source_id: str,
        source_artist_id: str,
        name: str,
        birth: int | None,
        death: int | None,
        ulan: str | None = None,
        wikidata: str | None = None,
        region: str | None = None,
        coverage_basis: str | None = None,
        official_death: bool,
        evidence_locator: str,
        aliases: Iterable[str] = (),
        legacy_id: str | None = None,
    ) -> str | None:
        raw_key = (source_id, str(source_artist_id))
        if raw_key not in self.raw_seen:
            self.raw_seen.add(raw_key)
            self.raw_source_counts[source_id] += 1
        if death is None:
            self.rejection_counts["unknown_death"] += 1
            return None
        if not _is_person_name(name):
            self.rejection_counts["non_person_or_empty_name"] += 1
            return None
        keys = self._keys(name=name, death=death, ulan=ulan, wikidata=wikidata)
        matches = sorted({self.index[key] for key in keys if key in self.index})
        if legacy_id:
            stable_id = legacy_id
        elif matches:
            stable_id = matches[0]
        else:
            stable_id = f"artist:m09a-{source_id}-{_slug(source_artist_id)}"
        if stable_id not in self.artists:
            self.artists[stable_id] = {
                "id": stable_id,
                "preferred_name": name.strip(),
                "aliases": set(),
                "birth_year": birth,
                "death_year": death,
                "external_ids": {},
                "source_identities": {},
                "deceased_evidence": [],
                "regions": set(),
                "coverage_bases": {},
                "works": {},
                "legacy_existing": bool(legacy_id),
                "conflict_notes": [],
            }
        artist = self.artists[stable_id]
        for other_id in matches:
            if other_id == stable_id or other_id not in self.artists:
                continue
            self._merge(stable_id, other_id)
            artist = self.artists[stable_id]
        if artist["death_year"] != death:
            artist["conflict_notes"].append(
                f"death-year conflict retained for later blocking: {artist['death_year']} vs {death}"
            )
        if birth is not None and artist["birth_year"] is None:
            artist["birth_year"] = birth
        artist["aliases"].update(item.strip() for item in aliases if item and item.strip() != name.strip())
        artist["source_identities"][source_id] = str(source_artist_id)
        if ulan:
            artist["external_ids"]["ulan"] = str(ulan)
        if wikidata:
            artist["external_ids"]["wikidata"] = str(wikidata)
        if region:
            artist["regions"].add(region)
            artist["coverage_bases"][region] = coverage_basis or f"{source_id}:documented_geography"
        evidence = {
            "source_id": source_id,
            "source_artist_id": str(source_artist_id),
            "locator": evidence_locator,
            "death_year": death,
            "precision": "year",
            "formal_official_source": official_death,
        }
        evidence_identity = (
            evidence["source_id"],
            evidence["source_artist_id"],
            evidence["death_year"],
            evidence["formal_official_source"],
        )
        if not any(
            (
                item["source_id"],
                item["source_artist_id"],
                item["death_year"],
                item["formal_official_source"],
            )
            == evidence_identity
            for item in artist["deceased_evidence"]
        ):
            artist["deceased_evidence"].append(evidence)
        for key in keys:
            self.index[key] = stable_id
        return stable_id

    def _merge(self, target_id: str, source_id: str) -> None:
        target = self.artists[target_id]
        source = self.artists.pop(source_id)
        target["aliases"].add(source["preferred_name"])
        target["aliases"].update(source["aliases"])
        target["external_ids"].update(source["external_ids"])
        target["source_identities"].update(source["source_identities"])
        evidence_identities = {
            (
                item["source_id"],
                item["source_artist_id"],
                item["death_year"],
                item["formal_official_source"],
            )
            for item in target["deceased_evidence"]
        }
        for item in source["deceased_evidence"]:
            identity = (
                item["source_id"],
                item["source_artist_id"],
                item["death_year"],
                item["formal_official_source"],
            )
            if identity not in evidence_identities:
                target["deceased_evidence"].append(item)
                evidence_identities.add(identity)
        target["regions"].update(source["regions"])
        target["coverage_bases"].update(source["coverage_bases"])
        target["works"].update(source["works"])
        target["legacy_existing"] = target["legacy_existing"] or source["legacy_existing"]
        target["conflict_notes"].extend(source["conflict_notes"])
        for key, value in list(self.index.items()):
            if value == source_id:
                self.index[key] = target_id

    def add_work(
        self,
        artist_id: str | None,
        *,
        source_id: str,
        object_id: str,
        title: str,
        date: str,
        medium: str,
        dimensions: str | None,
        url: str,
        attribution: str,
        accession_number: str | None = None,
        legacy_id: str | None = None,
    ) -> None:
        if artist_id is None or artist_id not in self.artists or not str(object_id).strip():
            return
        artist = self.artists[artist_id]
        source_object_id = str(object_id).strip()
        key = f"{source_id}:{source_object_id}"
        if key in artist["works"]:
            return
        if sum(1 for item in artist["works"].values() if item["source_id"] == source_id) >= 40:
            return
        title = str(title or "Untitled").strip() or "Untitled"
        date = str(date or "date not stated").strip() or "date not stated"
        medium = str(medium or "medium not stated").strip() or "medium not stated"
        duplicate_basis = [
            artist_id,
            normalize_name(title),
            normalize_name(date),
            normalize_name(medium),
        ]
        work_id = legacy_id or f"candidate-work:{source_id}:{_slug(source_object_id)}"
        artist["works"][key] = {
            "id": work_id,
            "source_id": source_id,
            "source_object_id": source_object_id,
            "artist_id": artist_id,
            "title": title,
            "title_language": "source-language-undetermined",
            "date_display": date,
            "date_precision": "source-display",
            "medium": medium,
            "medium_tags": _medium_tags(medium),
            "dimensions": dimensions.strip() if isinstance(dimensions, str) and dimensions.strip() else None,
            "holding_institution": SOURCE_PROFILES[source_id]["institution"],
            "source_url": url,
            "metadata_license": SOURCE_PROFILES[source_id]["metadata_license"],
            "media_availability": "not_assessed_no_download",
            "attribution_qualifier": attribution,
            "accession_number": accession_number or None,
            "evidence": {
                "claim": f"{artist_id} is named by the official record as {attribution}",
                "evidence_locator": f"{source_id}:{source_object_id}",
                "source_id": source_id,
            },
            "duplicate_cluster_id": f"work-duplicate:{_canonical_hash(duplicate_basis).split(':', 1)[1][:20]}",
            "status": "metadata_verified",
            "candidate_batch": None,
            "rights_media_future_review_hint": "metadata-first; object media requires separate M09B+ review",
            "legacy_existing": bool(legacy_id),
        }


def _load_existing(universe: Universe) -> tuple[list[str], list[str]]:
    artists = _json(EXISTING_ROOT / "artists.json")
    works = _json(EXISTING_ROOT / "artworks.json")
    existing_artist_ids: list[str] = []
    for record in artists:
        name = record["labels"].get("en") or next(iter(record["labels"].values()))
        birth = _year(record["life_dates"]["birth"]["display_value"])
        death = _year(record["life_dates"]["death"]["display_value"])
        artist_id = universe.add_artist(
            source_id="met_open_access",
            source_artist_id=record["external_ids"].get("ulan") or record["id"],
            name=name,
            birth=birth,
            death=death,
            ulan=record["external_ids"].get("ulan"),
            wikidata=record["external_ids"].get("wikidata"),
            region=EXISTING_COVERAGE[record["id"]],
            coverage_basis=f"MUSEUM-03B reviewed Claim-Evidence-Source closure for {record['id']}",
            official_death=True,
            evidence_locator=f"{record['id']}.life_dates.death",
            aliases=[item["text"] for item in record.get("aliases", [])],
            legacy_id=record["id"],
        )
        if artist_id:
            existing_artist_ids.append(artist_id)
    existing_work_ids: list[str] = []
    for record in works:
        source_id = {
            "source:met_open_access": "met_open_access",
            "source:aic_api": "aic_api",
        }.get(record["source_ids"][0], "met_open_access")
        object_record = record.get("official_object_record", {})
        universe.add_work(
            record["approved_artist_id"],
            source_id=source_id,
            object_id=object_record.get("source_object_id") or record["id"],
            title=record["labels"].get("en") or next(iter(record["labels"].values())),
            date=record.get("creation_span", {}).get("description", "date not stated"),
            medium=", ".join(record.get("technique_ids", [])) or ", ".join(record.get("material_ids", [])),
            dimensions=None,
            url=object_record.get("official_object_url", ""),
            attribution=record.get("creator_attributions", [{}])[0].get(
                "attribution_type", "named_creator"
            ),
            accession_number=record.get("accession_number"),
            legacy_id=record["id"],
        )
        existing_work_ids.append(record["id"])
    return sorted(existing_artist_ids), sorted(existing_work_ids)


def _load_british_museum_fixed(universe: Universe) -> None:
    document = _json(RAW_ROOT / "british-museum-ravi-varma.json")
    artist = document["artist"]
    artist_id = universe.add_artist(
        source_id="british_museum_collection",
        source_artist_id=artist["source_artist_id"],
        name=artist["name"],
        birth=artist["birth_year"],
        death=artist["death_year"],
        region="south-asia",
        coverage_basis="British Museum official artist record identifies the artist as Indian",
        official_death=True,
        evidence_locator="british-museum-ravi-varma.json#artist",
    )
    for work in document["objects"]:
        universe.add_work(
            artist_id,
            source_id="british_museum_collection",
            object_id=work["source_object_id"],
            title=work["title"],
            date=work["date"],
            medium=work["medium"],
            dimensions=None,
            url=work["source_url"],
            attribution=work["attribution"],
            accession_number=work["source_object_id"],
        )


def _load_moma(universe: Universe) -> None:
    artists: dict[str, dict[str, Any]] = {}
    with (RAW_ROOT / "moma-artists.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            death = _year(row.get("EndDate"))
            name = row.get("DisplayName", "").strip()
            if death is None or not _is_person_name(name):
                continue
            region = _region_from_text(row.get("Nationality", ""))
            artist_id = universe.add_artist(
                source_id="moma_open_data",
                source_artist_id=row["ConstituentID"],
                name=name,
                birth=_year(row.get("BeginDate")),
                death=death,
                ulan=row.get("ULAN") or None,
                wikidata=row.get("Wiki QID") or None,
                region=region,
                coverage_basis=f"MoMA official Nationality field: {row.get('Nationality') or 'not stated'}",
                official_death=True,
                evidence_locator=f"moma-artists.csv#ConstituentID={row['ConstituentID']}",
            )
            if artist_id:
                artists[row["ConstituentID"]] = {"id": artist_id, "name": name}
    with (RAW_ROOT / "moma-artworks.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ids = [item.strip() for item in row.get("ConstituentID", "").strip("[]").split(",") if item.strip()]
            if len(ids) != 1 or ids[0] not in artists:
                continue
            artist = artists[ids[0]]
            if not names_equivalent(row.get("Artist", ""), artist["name"]):
                continue
            universe.add_work(
                artist["id"],
                source_id="moma_open_data",
                object_id=row["ObjectID"],
                title=row.get("Title", ""),
                date=row.get("Date", ""),
                medium=row.get("Medium", ""),
                dimensions=row.get("Dimensions"),
                url=row.get("URL", ""),
                attribution="named_creator_single",
                accession_number=row.get("AccessionNumber"),
            )


def _load_met(universe: Universe) -> None:
    path = RAW_ROOT / "met-objects.csv"
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            constituent = row.get("Constituent ID", "").strip()
            name = row.get("Artist Display Name", "").strip()
            if not constituent or "|" in constituent or "|" in name or not _is_person_name(name):
                continue
            death = _year(row.get("Artist End Date"))
            if death is None:
                continue
            ulan_match = re.search(r"/([0-9]+)\s*$", row.get("Artist ULAN URL", ""))
            qid_match = re.search(r"/(Q[0-9]+)\s*$", row.get("Artist Wikidata URL", ""))
            region = _region_from_text(
                " ".join([row.get("Artist Nationality", ""), row.get("Artist Display Bio", "")])
            )
            artist_id = universe.add_artist(
                source_id="met_open_access",
                source_artist_id=constituent,
                name=name,
                birth=_year(row.get("Artist Begin Date")),
                death=death,
                ulan=ulan_match.group(1) if ulan_match else None,
                wikidata=qid_match.group(1) if qid_match else None,
                region=region,
                coverage_basis=(
                    "The Met official Artist Nationality/Bio fields: "
                    + (row.get("Artist Nationality") or row.get("Artist Display Bio") or "not stated")
                ),
                official_death=True,
                evidence_locator=f"met-objects.csv#ConstituentID={constituent}",
            )
            prefix = row.get("Artist Prefix", "").strip()
            if prefix:
                continue
            universe.add_work(
                artist_id,
                source_id="met_open_access",
                object_id=row["Object ID"],
                title=row.get("Title") or row.get("Object Name", ""),
                date=row.get("Object Date", ""),
                medium=row.get("Medium", ""),
                dimensions=row.get("Dimensions"),
                url=f"https://www.metmuseum.org/art/collection/search/{row['Object ID']}",
                attribution=f"named_{normalize_name(row.get('Artist Role') or 'creator').replace(' ', '_')}",
                accession_number=row.get("Object Number"),
            )


def _load_tate(universe: Universe) -> None:
    artists: dict[str, dict[str, Any]] = {}
    with (RAW_ROOT / "tate-artists.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            death = _year(row.get("yearOfDeath"))
            name = row.get("name", "").strip()
            if death is None or not _is_person_name(name):
                continue
            region = _region_from_text(row.get("placeOfBirth", ""))
            artist_id = universe.add_artist(
                source_id="tate_open_data",
                source_artist_id=row["id"],
                name=name,
                birth=_year(row.get("yearOfBirth")),
                death=death,
                region=region,
                coverage_basis=f"Tate official placeOfBirth field: {row.get('placeOfBirth') or 'not stated'}",
                official_death=True,
                evidence_locator=f"tate-artists.csv#id={row['id']}",
            )
            if artist_id:
                artists[row["id"]] = {"id": artist_id, "name": name}
    with (RAW_ROOT / "tate-artworks.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source_artist_id = row.get("artistId", "")
            if (
                source_artist_id not in artists
                or normalize_name(row.get("artistRole", "")) != "artist"
            ):
                continue
            universe.add_work(
                artists[source_artist_id]["id"],
                source_id="tate_open_data",
                object_id=row.get("accession_number") or row["id"],
                title=row.get("title", ""),
                date=row.get("dateText", ""),
                medium=row.get("medium", ""),
                dimensions=row.get("dimensions"),
                url=row.get("url", ""),
                attribution="named_artist",
                accession_number=row.get("accession_number"),
            )


def _load_nga(universe: Universe) -> None:
    artists: dict[str, dict[str, Any]] = {}
    with (RAW_ROOT / "nga-constituents.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if normalize_name(row.get("constituenttype", "")) != "individual":
                continue
            death = _year(row.get("endyear"))
            name = row.get("forwarddisplayname", "").strip()
            if death is None or not _is_person_name(name):
                continue
            region = _region_from_text(
                " ".join([row.get("nationality", ""), row.get("visualbrowsernationality", "")])
            )
            artist_id = universe.add_artist(
                source_id="nga_open_data",
                source_artist_id=row["constituentid"],
                name=name,
                birth=_year(row.get("beginyear")),
                death=death,
                ulan=row.get("ulanid") or None,
                wikidata=row.get("wikidataid") or None,
                region=region,
                coverage_basis=f"NGA official nationality field: {row.get('nationality') or 'not stated'}",
                official_death=True,
                evidence_locator=f"nga-constituents.csv#constituentid={row['constituentid']}",
            )
            if artist_id:
                artists[row["constituentid"]] = {"id": artist_id, "name": name}
    object_artist: dict[str, str] = {}
    with (RAW_ROOT / "nga-objects-constituents.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            if (
                normalize_name(row.get("roletype", "")) == "artist"
                and row.get("constituentid") in artists
                and row.get("objectid") not in object_artist
            ):
                object_artist[row["objectid"]] = artists[row["constituentid"]]["id"]
    with (RAW_ROOT / "nga-objects.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            artist_id = object_artist.get(row["objectid"])
            if not artist_id:
                continue
            universe.add_work(
                artist_id,
                source_id="nga_open_data",
                object_id=row["objectid"],
                title=row.get("title", ""),
                date=row.get("displaydate", ""),
                medium=row.get("medium", ""),
                dimensions=row.get("dimensions"),
                url=f"https://www.nga.gov/artworks/{row['objectid']}",
                attribution="named_artist",
                accession_number=row.get("accessionnum"),
            )


def _load_aic(universe: Universe) -> None:
    agents = _json(RAW_ROOT / "aic-agents-index.json")
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in agents:
        death = _year(row.get("death"))
        name = str(row.get("title") or "").strip()
        if not row.get("is_artist") or death is None or not _is_person_name(name):
            continue
        by_name[normalize_name(name)].append(row)
    artist_ids: dict[str, str] = {}
    for normalized, rows in sorted(by_name.items()):
        if not normalized or len(rows) != 1:
            continue
        row = rows[0]
        artist_id = universe.add_artist(
            source_id="aic_api",
            source_artist_id=str(row["id"]),
            name=row["title"],
            birth=_year(row.get("birth")),
            death=_year(row.get("death")),
            ulan=str(row.get("ulan") or "") or None,
            region=None,
            coverage_basis=None,
            official_death=True,
            evidence_locator=f"AIC agents/{row['id']}.json",
        )
        if artist_id:
            artist_ids[normalized] = artist_id
    path = RAW_ROOT / "artic-api-data" / "getting-started" / "allArtworks.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            artist_id = artist_ids.get(normalize_name(str(row.get("artist_title") or "")))
            if not artist_id:
                continue
            universe.add_work(
                artist_id,
                source_id="aic_api",
                object_id=str(row["id"]),
                title=str(row.get("title") or ""),
                date="date not included in compact bulk index",
                medium=str(row.get("department_title") or "medium not included in compact bulk index"),
                dimensions=None,
                url=f"https://www.artic.edu/artworks/{row['id']}",
                attribution="named_artist",
                accession_number=str(row.get("main_reference_number") or "") or None,
            )


_CLEVELAND_CREATOR = re.compile(
    r"^(?P<name>.+?) \((?P<bio>.+?),\s*(?:c\.\s*)?(?P<birth>[0-9]{4})"
    r"\s*[–-]\s*(?:c\.\s*)?(?P<death>[0-9]{4})\),\s*"
    r"(?P<role>artist|carver|sculptor|designer|photographer|maker|weaver|painter|"
    r"ceramist|engraver|printmaker)$",
    re.IGNORECASE,
)


def _load_cleveland(universe: Universe) -> None:
    with (RAW_ROOT / "cleveland-artworks.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            creator = row.get("creators", "").strip()
            if "\n" in creator:
                continue
            match = _CLEVELAND_CREATOR.match(creator)
            if not match:
                continue
            name = match.group("name").strip()
            death = int(match.group("death"))
            region = _region_from_text(match.group("bio"))
            artist_id = universe.add_artist(
                source_id="cleveland_open_access",
                source_artist_id=f"{normalize_name(name)}-{death}",
                name=name,
                birth=int(match.group("birth")),
                death=death,
                region=region,
                coverage_basis=f"Cleveland official creator biography: {match.group('bio')}",
                official_death=True,
                evidence_locator=f"cleveland-artworks.csv#id={row['id']}.creators",
            )
            universe.add_work(
                artist_id,
                source_id="cleveland_open_access",
                object_id=row["id"],
                title=row.get("title", ""),
                date=row.get("creation_date", ""),
                medium=row.get("technique", ""),
                dimensions=row.get("measurements"),
                url=row.get("url", ""),
                attribution=f"named_{normalize_name(match.group('role')).replace(' ', '_')}",
                accession_number=row.get("accession_number"),
            )


def _load_mia(universe: Universe) -> None:
    repository = RAW_ROOT / "artsmia-collection"
    african_terms = (
        "African|South African|Nigerian|Ghanaian|Ethiopian|Mozambican|Zimbabwean|"
        "Kenyan|Malian|Senegalese|Congolese|Cameroonian|Ugandan|Sudanese|Egyptian|"
        "Moroccan|Algerian|Tunisian"
    )
    completed = subprocess.run(
        [
            "git",
            "grep",
            "-l",
            "-E",
            rf'"nationality": "({african_terms})"',
            "--",
            "objects",
        ],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    role_prefix = re.compile(
        r"^(?:artist|photographer|sculptor|designer|carver|maker|weaver|painter):\s*",
        re.IGNORECASE,
    )
    for relative in completed.stdout.splitlines():
        path = repository / relative
        try:
            row = _json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        raw_name = str(row.get("artist") or "").strip()
        if not raw_name or ";" in raw_name or raw_name.casefold().startswith(("unknown", "anonymous")):
            continue
        name = role_prefix.sub("", raw_name).strip()
        birth_death = [
            int(item)
            for item in re.findall(
                r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)",
                str(row.get("life_date") or ""),
            )
        ]
        if len(birth_death) < 2 or not _is_person_name(name):
            continue
        region = _region_from_text(
            " ".join([str(row.get("nationality") or ""), str(row.get("life_date") or "")])
        )
        if region != "africa":
            continue
        object_id = str(row.get("id") or Path(relative).stem)
        artist_id = universe.add_artist(
            source_id="mia_open_access",
            source_artist_id=f"{normalize_name(name)}-{birth_death[-1]}",
            name=name,
            birth=birth_death[0],
            death=birth_death[-1],
            region=region,
            coverage_basis=(
                "MIA official nationality/life-date fields: "
                + str(row.get("nationality") or row.get("life_date") or "not stated")
            ),
            official_death=True,
            evidence_locator=f"artsmia-collection/{relative}#life_date",
        )
        universe.add_work(
            artist_id,
            source_id="mia_open_access",
            object_id=object_id,
            title=str(row.get("title") or ""),
            date=str(row.get("dated") or ""),
            medium=str(row.get("medium") or row.get("object_name") or ""),
            dimensions=str(row.get("dimension") or "") or None,
            url=f"https://collections.artsmia.org/art/{object_id}",
            attribution="named_artist",
            accession_number=str(row.get("accession_number") or "") or None,
        )


def _ngs_years(value: str) -> tuple[int | None, int | None]:
    years = [
        int(item)
        for item in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", value or "")
    ]
    if len(years) < 2:
        return None, None
    return years[0], years[-1]


def _load_ngs(universe: Universe) -> None:
    for path in sorted((RAW_ROOT / "ngs-facet-search").glob("*.json")):
        document = _json(path)
        query_name = document["query_name"].strip()
        exact_hits: list[tuple[dict[str, Any], dict[str, Any]]] = []
        artist_record: dict[str, Any] | None = None
        for hit in document["response"].get("hits", []):
            for artist in hit.get("metadata", {}).get("artistCfs", []):
                if names_equivalent(artist.get("availableName", ""), query_name):
                    artist_record = artist
                    exact_hits.append((hit, artist))
                    break
        if artist_record is None or len(exact_hits) < 3:
            continue
        birth, death = _ngs_years(str(artist_record.get("perDatingTxt") or ""))
        if death is None:
            continue
        geography = " ".join(
            str(artist_record.get(key) or "")
            for key in ("perCountryBirthVoc", "perCountryDeathVoc")
        )
        region = _region_from_text(geography)
        artist_id = universe.add_artist(
            source_id="national_gallery_singapore",
            source_artist_id=str(artist_record["id"]),
            name=artist_record.get("perNameTxt") or query_name,
            birth=birth,
            death=death,
            region=region,
            coverage_basis=(
                "National Gallery Singapore official artist birth/death country fields: "
                + (geography.strip() or "not stated")
            ),
            official_death=True,
            evidence_locator=f"{path.name}#artistCfs/{artist_record['id']}/perDatingTxt",
            aliases=[
                item.get("nameTxt", "")
                for item in artist_record.get("perNameOtherGrp", [])
                if item.get("nameTxt")
            ],
        )
        for hit, _artist in exact_hits:
            metadata = hit.get("metadata", {})
            universe.add_work(
                artist_id,
                source_id="national_gallery_singapore",
                object_id=str(metadata.get("artPlusId") or hit.get("objectID") or hit.get("path")),
                title=hit.get("title", ""),
                date=str(metadata.get("dateTxt") or metadata.get("objectDateTxt") or "date not stated"),
                medium=str(
                    metadata.get("mediumTxt")
                    or metadata.get("materialsAndTechniquesTxt")
                    or metadata.get("objectTypeVoc")
                    or "medium not stated"
                ),
                dimensions=str(metadata.get("publishedDimension") or "") or None,
                url=(
                    "https://www.nationalgallery.sg"
                    + str(hit.get("url") or hit.get("path") or "")
                ),
                attribution="named_artist",
                accession_number=str(metadata.get("accessionNumber") or "") or None,
            )


def _load_cross_source(universe: Universe) -> None:
    document = _json(RAW_ROOT / "cross-source-candidates.json")
    for row in document["artists"]:
        death = _year(row.get("death"))
        birth = _year(row.get("birth"))
        regions = [region for region in row.get("regions", []) if region in REGION_QUOTAS]
        primary_region = regions[0] if regions else None
        artist_id = universe.add_artist(
            source_id="wikidata_discovery",
            source_artist_id=row["qid"],
            name=row["name"],
            birth=birth,
            death=death,
            ulan=row.get("ulan") or None,
            wikidata=row.get("qid") or None,
            region=primary_region,
            coverage_basis=(
                "Wikidata discovery geography; target eligibility still requires an official "
                "collection/authority death record"
            ),
            official_death=False,
            evidence_locator=f"cross-source-candidates.json#{row['qid']}",
        )
        if artist_id is None:
            continue
        for extra_region in regions[1:]:
            universe.artists[artist_id]["regions"].add(extra_region)
            universe.artists[artist_id]["coverage_bases"][extra_region] = (
                "Wikidata discovery geography; not used alone for target eligibility"
            )
        for work in row.get("works", []):
            source_id = CROSS_SOURCE_MAP.get(work.get("source"))
            if source_id not in SOURCE_PROFILES:
                continue
            maker = str(work.get("maker") or "")
            if not names_equivalent(maker, row["name"]):
                universe.rejection_counts["ambiguous_name_work_mapping"] += 1
                continue
            universe.add_work(
                artist_id,
                source_id=source_id,
                object_id=str(work.get("object_id") or ""),
                title=str(work.get("title") or ""),
                date=str(work.get("date") or ""),
                medium=str(work.get("medium") or ""),
                dimensions=None,
                url=str(work.get("url") or ""),
                attribution="exact_name_mapped_creator",
            )


def _load_documented_birthplace_crosswalks(universe: Universe) -> None:
    inputs = (
        ("wikidata-artists-africa-birthplace.json", "africa"),
        ("wikidata-artists-south-asia-birthplace.json", "south-asia"),
    )
    for filename, region in inputs:
        document = _json(RAW_ROOT / filename)
        for binding in document.get("results", {}).get("bindings", []):
            name = binding.get("itemLabel", {}).get("value", "")
            qid = binding.get("item", {}).get("value", "").rsplit("/", 1)[-1]
            ulan = binding.get("ulan", {}).get("value") or None
            country = binding.get("countryLabel", {}).get("value", "not stated")
            universe.add_artist(
                source_id="wikidata_discovery",
                source_artist_id=qid,
                name=name,
                birth=_year(binding.get("dob", {}).get("value")),
                death=_year(binding.get("dod", {}).get("value")),
                ulan=ulan,
                wikidata=qid,
                region=region,
                coverage_basis=(
                    f"documented birthplace in {country}; research-routing label only, "
                    "not nationality, ethnicity, or cultural identity"
                ),
                official_death=False,
                evidence_locator=f"{filename}#{qid}",
            )


def _load_documented_region_crosswalks(universe: Universe) -> None:
    inputs = (
        ("wikidata-artists-africa.json", "africa"),
        ("wikidata-artists-east-asia.json", "east-asia"),
        ("wikidata-artists-latin-america-caribbean.json", "latin-america-caribbean"),
        ("wikidata-artists-oceania.json", "oceania"),
        ("wikidata-artists-south-asia.json", "south-asia"),
        ("wikidata-artists-southeast-asia.json", "southeast-asia"),
        ("wikidata-artists-west-central-asia.json", "west-central-asia"),
    )
    for filename, region in inputs:
        document = _json(RAW_ROOT / filename)
        for binding in document.get("results", {}).get("bindings", []):
            name = binding.get("itemLabel", {}).get("value", "")
            qid = binding.get("item", {}).get("value", "").rsplit("/", 1)[-1]
            ulan = binding.get("ulan", {}).get("value") or None
            country = binding.get("countryLabel", {}).get("value", "not stated")
            universe.add_artist(
                source_id="wikidata_discovery",
                source_artist_id=qid,
                name=name,
                birth=_year(binding.get("dob", {}).get("value")),
                death=_year(binding.get("dod", {}).get("value")),
                ulan=ulan,
                wikidata=qid,
                region=region,
                coverage_basis=(
                    f"documented country/region association in {country}; "
                    "research-routing label only and not a sensitive-identity inference"
                ),
                official_death=False,
                evidence_locator=f"{filename}#{qid}",
            )


def _input_paths() -> list[Path]:
    paths = [
        RAW_ROOT / "aic-agents-index.json",
        RAW_ROOT / "artic-api-data" / "getting-started" / "allArtworks.jsonl",
        RAW_ROOT / "british-museum-ravi-varma.json",
        RAW_ROOT / "cleveland-artworks.csv",
        RAW_ROOT / "cross-source-candidates.json",
        RAW_ROOT / "met-objects.csv",
        RAW_ROOT / "moma-artists.csv",
        RAW_ROOT / "moma-artworks.csv",
        RAW_ROOT / "nga-constituents.csv",
        RAW_ROOT / "nga-objects-constituents.csv",
        RAW_ROOT / "nga-objects.csv",
        RAW_ROOT / "tate-artists.csv",
        RAW_ROOT / "tate-artworks.csv",
        RAW_ROOT / "wikidata-artists-africa-birthplace.json",
        RAW_ROOT / "wikidata-artists-africa.json",
        RAW_ROOT / "wikidata-artists-east-asia.json",
        RAW_ROOT / "wikidata-artists-latin-america-caribbean.json",
        RAW_ROOT / "wikidata-artists-oceania.json",
        RAW_ROOT / "wikidata-artists-south-asia-birthplace.json",
        RAW_ROOT / "wikidata-artists-south-asia.json",
        RAW_ROOT / "wikidata-artists-southeast-asia.json",
        RAW_ROOT / "wikidata-artists-west-central-asia.json",
        EXISTING_ROOT / "artists.json",
        EXISTING_ROOT / "artworks.json",
    ]
    paths.extend(sorted((RAW_ROOT / "ngs-facet-search").glob("*.json")))
    return paths


def _input_manifest() -> tuple[list[dict[str, Any]], str]:
    records = []
    for path in _input_paths():
        if not path.is_file():
            raise FileNotFoundError(f"required MUSEUM-09A cache input missing: {path}")
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    mia_repository = RAW_ROOT / "artsmia-collection"
    mia_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=mia_repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    records.append(
        {
            "path": "data/raw/museum-09a/artsmia-collection",
            "snapshot_kind": "official_git_commit",
            "git_commit": mia_commit,
            "tracked_file_count": int(
                subprocess.run(
                    ["git", "ls-files"],
                    cwd=mia_repository,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                ).stdout.count("\n")
            ),
        }
    )
    return records, _canonical_hash(records)


def discover_universe() -> tuple[Universe, list[str], list[str]]:
    universe = Universe()
    existing_artist_ids, existing_work_ids = _load_existing(universe)
    _load_british_museum_fixed(universe)
    _load_moma(universe)
    _load_met(universe)
    _load_tate(universe)
    _load_nga(universe)
    _load_aic(universe)
    _load_cleveland(universe)
    _load_mia(universe)
    _load_ngs(universe)
    _load_cross_source(universe)
    _load_documented_birthplace_crosswalks(universe)
    _load_documented_region_crosswalks(universe)
    return universe, existing_artist_ids, existing_work_ids


def _eligible(artist: dict[str, Any]) -> bool:
    official_death = any(item["formal_official_source"] for item in artist["deceased_evidence"])
    official_sources = {
        item
        for item in artist["source_identities"]
        if item in SOURCE_PROFILES
    }
    return (
        official_death
        and bool(official_sources)
        and not artist["conflict_notes"]
        and artist["death_year"] <= 2026
        and (
            artist["birth_year"] is None
            or 10 <= artist["death_year"] - artist["birth_year"] <= 150
        )
        and _artist_work_capacity(artist) >= 3
        and bool(artist["regions"])
    )


def _artist_work_capacity(artist: dict[str, Any]) -> int:
    return len(
        {
            work["duplicate_cluster_id"]
            for work in artist["works"].values()
        }
    )


def _artist_sort_key(artist: dict[str, Any], region: str) -> tuple[Any, ...]:
    official_sources = {
        work["source_id"] for work in artist["works"].values() if work["source_id"] in SOURCE_PROFILES
    }
    capacity = _artist_work_capacity(artist)
    return (
        0 if len(official_sources) >= 2 else 1,
        0 if capacity >= 15 else 1,
        0 if "ulan" in artist["external_ids"] else 1,
        artist["coverage_bases"].get(region, ""),
        artist["id"],
    )


def select_artists(
    universe: Universe,
    existing_artist_ids: list[str],
) -> tuple[list[str], list[str], dict[str, str], list[str]]:
    selected = list(existing_artist_ids)
    assignments = {artist_id: EXISTING_COVERAGE[artist_id] for artist_id in selected}
    for region, quota in REGION_QUOTAS.items():
        needed = quota - sum(1 for value in assignments.values() if value == region)
        candidates = [
            artist
            for artist in universe.artists.values()
            if artist["id"] not in assignments and _eligible(artist) and region in artist["regions"]
        ]
        candidates.sort(key=lambda artist: _artist_sort_key(artist, region))
        if len(candidates) < needed:
            raise ValueError(f"coverage bucket {region} has {len(candidates)} candidates for {needed} slots")
        for artist in candidates[:needed]:
            selected.append(artist["id"])
            assignments[artist["id"]] = region
    if len(selected) != 500 or len(set(selected)) != 500:
        raise ValueError(f"program target artist count is {len(selected)}, expected 500")

    remaining_by_region: dict[str, list[str]] = {}
    for region in REGION_QUOTAS:
        remaining_by_region[region] = [
            artist["id"]
            for artist in sorted(
                (
                    artist
                    for artist in universe.artists.values()
                    if artist["id"] not in assignments
                    and _eligible(artist)
                    and region in artist["regions"]
                ),
                key=lambda artist: _artist_sort_key(artist, region),
            )
        ]
    reserve: list[str] = []
    while len(reserve) < 120:
        progress = False
        for region in REGION_QUOTAS:
            while remaining_by_region[region] and remaining_by_region[region][0] in reserve:
                remaining_by_region[region].pop(0)
            if remaining_by_region[region]:
                reserve.append(remaining_by_region[region].pop(0))
                progress = True
                if len(reserve) == 120:
                    break
        if not progress:
            raise ValueError("fewer than 120 deterministic reserve artists")
    rejected = sorted(
        artist_id
        for artist_id, artist in universe.artists.items()
        if artist_id not in assignments and artist_id not in reserve and _eligible(artist)
    )
    return selected, reserve, assignments, rejected


def _flatten_works(
    universe: Universe,
    artist_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    works: dict[str, dict[str, Any]] = {}
    for artist_id in artist_ids:
        for work in universe.artists[artist_id]["works"].values():
            item = deepcopy(work)
            item["artist_id"] = artist_id
            if item["id"] in works and works[item["id"]]["artist_id"] != artist_id:
                raise ValueError(f"work ID attributed to multiple artists: {item['id']}")
            works[item["id"]] = item
    return works


def _select_gallery(
    universe: Universe,
    target_ids: list[str],
    existing_ids: list[str],
) -> set[str]:
    gallery = {
        artist_id
        for artist_id in existing_ids
        if _artist_work_capacity(universe.artists[artist_id]) >= 8
    }
    candidates = sorted(
        (
            universe.artists[artist_id]
            for artist_id in target_ids
            if artist_id not in gallery
            and _artist_work_capacity(universe.artists[artist_id]) >= 8
        ),
        key=lambda artist: (
            0 if len({work["source_id"] for work in artist["works"].values()}) >= 2 else 1,
            0 if _artist_work_capacity(artist) >= 15 else 1,
            artist["id"],
        ),
    )
    gallery.update(artist["id"] for artist in candidates[: 125 - len(gallery)])
    if len(gallery) != 125:
        raise ValueError(f"gallery tier count is {len(gallery)}, expected 125")
    return gallery


def _work_targets_per_artist(
    universe: Universe,
    target_ids: list[str],
    gallery: set[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for artist_id in target_ids:
        minimum = 8 if artist_id in gallery else 3
        capacity = min(
            15 if artist_id in gallery else 10,
            _artist_work_capacity(universe.artists[artist_id]),
        )
        if capacity < minimum:
            raise ValueError(f"{artist_id} has capacity {capacity}, below tier minimum {minimum}")
        counts[artist_id] = minimum
    remaining = 5000 - sum(counts.values())
    opportunities: list[tuple[Any, ...]] = []
    for artist_id in target_ids:
        artist = universe.artists[artist_id]
        sources = {work["source_id"] for work in artist["works"].values()}
        cap = min(
            15 if artist_id in gallery else 10,
            _artist_work_capacity(artist),
        )
        for slot in range(counts[artist_id] + 1, cap + 1):
            opportunities.append(
                (
                    0 if len(sources) >= 2 else 1,
                    0 if artist_id in gallery else 1,
                    slot,
                    artist_id,
                )
            )
    opportunities.sort()
    if len(opportunities) < remaining:
        raise ValueError("target artist work capacities cannot reach 5,000")
    for _source_diversity, _tier, _slot, artist_id in opportunities[:remaining]:
        counts[artist_id] += 1
    return counts


def select_target_works(
    universe: Universe,
    target_ids: list[str],
    existing_work_ids: list[str],
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    all_works = _flatten_works(universe, target_ids)
    selected: dict[str, dict[str, Any]] = {
        work_id: deepcopy(all_works[work_id]) for work_id in existing_work_ids
    }
    selected_by_artist = Counter(work["artist_id"] for work in selected.values())
    source_counts = Counter(work["source_id"] for work in selected.values())
    duplicate_clusters = {work["duplicate_cluster_id"] for work in selected.values()}
    source_cap = 1500
    candidates_by_artist: dict[str, list[dict[str, Any]]] = {}
    for artist_id in target_ids:
        candidates_by_artist[artist_id] = []
        for work in universe.artists[artist_id]["works"].values():
            if work["id"] in selected:
                continue
            item = deepcopy(work)
            item["artist_id"] = artist_id
            candidates_by_artist[artist_id].append(item)
        candidates_by_artist[artist_id].sort(
            key=lambda work: (work["source_id"], work["id"])
        )
    while sum(selected_by_artist.values()) < 5000:
        progress = False
        for artist_id in sorted(target_ids):
            if selected_by_artist[artist_id] >= counts[artist_id]:
                continue
            candidates = [
                work
                for work in candidates_by_artist[artist_id]
                if work["id"] not in selected
                and work["duplicate_cluster_id"] not in duplicate_clusters
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda work: (
                    source_counts[work["source_id"]],
                    work["source_id"],
                    work["id"],
                )
            )
            work = candidates[0]
            selected[work["id"]] = work
            selected_by_artist[artist_id] += 1
            source_counts[work["source_id"]] += 1
            duplicate_clusters.add(work["duplicate_cluster_id"])
            progress = True
        if not progress:
            deficits = {
                artist_id: counts[artist_id] - selected_by_artist[artist_id]
                for artist_id in target_ids
                if selected_by_artist[artist_id] < counts[artist_id]
            }
            raise ValueError(
                "cannot close 5,000 target works under duplicate/source caps: "
                + json.dumps(dict(list(deficits.items())[:20]), sort_keys=True)
            )
    while any(count > source_cap for count in source_counts.values()):
        over_source = min(
            source_id for source_id, count in source_counts.items() if count > source_cap
        )
        swapped = False
        for old_work in sorted(
            (
                work
                for work in selected.values()
                if work["source_id"] == over_source and not work["legacy_existing"]
            ),
            key=lambda work: (work["artist_id"], work["id"]),
        ):
            alternatives = [
                work
                for work in candidates_by_artist[old_work["artist_id"]]
                if work["id"] not in selected
                and work["source_id"] != over_source
                and source_counts[work["source_id"]] < source_cap
                and work["duplicate_cluster_id"] not in duplicate_clusters
            ]
            if not alternatives:
                continue
            alternatives.sort(
                key=lambda work: (
                    source_counts[work["source_id"]],
                    work["source_id"],
                    work["id"],
                )
            )
            new_work = alternatives[0]
            del selected[old_work["id"]]
            selected[new_work["id"]] = new_work
            source_counts[over_source] -= 1
            source_counts[new_work["source_id"]] += 1
            duplicate_clusters.remove(old_work["duplicate_cluster_id"])
            duplicate_clusters.add(new_work["duplicate_cluster_id"])
            swapped = True
            break
        if not swapped:
            raise ValueError(f"cannot rebalance target works below source cap for {over_source}")
    if len(selected) != 5000:
        raise ValueError(f"target work count is {len(selected)}, expected 5,000")
    return [selected[work_id] for work_id in sorted(selected)]


def _candidate_work_set(
    universe: Universe,
    target_ids: list[str],
    reserve_ids: list[str],
    rejected_ids: list[str],
    target_works: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    works = {work["id"]: deepcopy(work) for work in target_works}
    ordered_artists = [*target_ids, *reserve_ids, *rejected_ids]
    for artist_id in ordered_artists:
        for work in sorted(universe.artists[artist_id]["works"].values(), key=lambda item: item["id"]):
            if work["id"] in works:
                continue
            works[work["id"]] = deepcopy(work)
            if len(works) >= 9000:
                break
        if len(works) >= 9000:
            break
    if len(works) < 7500:
        raise ValueError(f"candidate work count is only {len(works)}")
    return [works[work_id] for work_id in sorted(works)]


def _assign_batches(
    target_ids: list[str],
    existing_ids: list[str],
    target_works: list[dict[str, Any]],
    assignments: dict[str, str],
    gallery: set[str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    new_ids = [artist_id for artist_id in target_ids if artist_id not in set(existing_ids)]
    work_counts = Counter(work["artist_id"] for work in target_works)
    capacities = [50, 49, 49, 49, 49, 49, 49, 48, 48, 48]
    batches = [
        {
            "id": f"museum-09-batch-{index + 1:02d}",
            "phase": f"MUSEUM-09{chr(ord('B') + index)}",
            "artist_ids": [],
            "work_count": 0,
            "coverage_delta": Counter(),
            "gallery_count": 0,
        }
        for index in range(10)
    ]
    ordered = sorted(
        new_ids,
        key=lambda artist_id: (
            -work_counts[artist_id],
            assignments[artist_id],
            artist_id,
        ),
    )
    for artist_id in ordered:
        available = [
            (index, batch)
            for index, batch in enumerate(batches)
            if len(batch["artist_ids"]) < capacities[index]
        ]
        if not available:
            raise ValueError("batch capacity exhausted before all artists were assigned")
        index, batch = min(
            available,
            key=lambda pair: (
                pair[1]["work_count"],
                pair[1]["coverage_delta"][assignments[artist_id]],
                len(pair[1]["artist_ids"]),
                pair[0],
            ),
        )
        batch["artist_ids"].append(artist_id)
        batch["work_count"] += work_counts[artist_id]
        batch["coverage_delta"][assignments[artist_id]] += 1
        batch["gallery_count"] += int(artist_id in gallery)
    artist_batch: dict[str, str] = {}
    snapshots: list[dict[str, Any]] = []
    for index, batch in enumerate(batches):
        artist_ids = sorted(batch["artist_ids"])
        for artist_id in artist_ids:
            artist_batch[artist_id] = batch["id"]
        input_closure = {
            "artist_ids": artist_ids,
            "work_ids": sorted(
                work["id"] for work in target_works if work["artist_id"] in set(artist_ids)
            ),
        }
        snapshots.append(
            {
                "id": batch["id"],
                "sequence": index + 1,
                "planned_phase": batch["phase"],
                "status": "registered_not_started",
                "artist_count": len(artist_ids),
                "work_count": batch["work_count"],
                "artist_ids": artist_ids,
                "coverage_delta": dict(sorted(batch["coverage_delta"].items())),
                "gallery_tier_count": batch["gallery_count"],
                "collection_tier_count": len(artist_ids) - batch["gallery_count"],
                "input_closure_hash": _canonical_hash(input_closure),
                "source_set": sorted(
                    {
                        work["source_id"]
                        for work in target_works
                        if work["artist_id"] in set(artist_ids)
                    }
                ),
                "workload": "identity, deceased, attribution, claim-evidence-source, and media-feasibility closure",
                "risks": ["source correction", "identity conflict", "object attribution conflict"],
                "dependencies": ["MUSEUM-09A candidate package", "MUSEUM-08 immutable release"],
            }
        )
    if [len(batch["artist_ids"]) for batch in snapshots] != capacities:
        raise ValueError("batch artist capacities are not exact")
    return artist_batch, snapshots


def _artist_document(
    artist: dict[str, Any],
    *,
    status: str,
    primary_bucket: str | None,
    tier: str,
    reserve_order: int | None,
    batch: str | None,
) -> dict[str, Any]:
    source_ids = sorted(source_id for source_id in artist["source_identities"] if source_id in SOURCE_PROFILES)
    media_tags = Counter(
        tag for work in artist["works"].values() for tag in work["medium_tags"]
    )
    proven = [
        "preferred name is copied from a named source record",
        "death year is supported by at least one official source record",
        "at least three official collection object mappings are retained",
    ]
    not_proven = [
        "sensitive identity attributes not explicitly represented by source records",
        "historical influence, migration, diaspora, and cultural affiliation unless separately evidenced",
        "media reuse permission; media availability is not permission",
    ]
    return {
        "id": artist["id"],
        "entity_type": "artist_expansion_candidate",
        "artist_kind": "individual",
        "preferred_name": artist["preferred_name"],
        "aliases": sorted(artist["aliases"]),
        "birth": {"year": artist["birth_year"], "precision": "year" if artist["birth_year"] else "unknown"},
        "death": {"year": artist["death_year"], "precision": "year"},
        "deceased_status": "confirmed_deceased",
        "deceased_verification_evidence_ids": sorted(
            f"deceased-evidence:{artist['id'].split(':', 1)[1]}:{index + 1}"
            for index, item in enumerate(artist["deceased_evidence"])
            if item["formal_official_source"]
        ),
        "external_ids": dict(sorted(artist["external_ids"].items())),
        "source_identities": [
            {"source_id": source_id, "source_artist_id": artist["source_identities"][source_id]}
            for source_id in source_ids
        ],
        "duplicate_cluster_id": f"artist-duplicate:{_canonical_hash([artist['preferred_name'], artist['death_year']]).split(':', 1)[1][:20]}",
        "primary_coverage_bucket": primary_bucket,
        "primary_coverage_basis": artist["coverage_bases"].get(primary_bucket) if primary_bucket else None,
        "secondary_region_context_tags": sorted(
            region for region in artist["regions"] if region != primary_bucket
        ),
        "historical_period": _period(artist["birth_year"], artist["death_year"]),
        "documented_media_practice_tags": [
            item for item, _count in sorted(media_tags.items(), key=lambda pair: (-pair[1], pair[0]))
        ],
        "content_depth_tier": tier,
        "status": status,
        "status_history": [
            {
                "at": BUILT_AT,
                "from": "discovered",
                "to": "identity_normalized",
                "reason": "deterministic authority/name-life-date dedupe",
            },
            {
                "at": BUILT_AT,
                "from": "identity_normalized",
                "to": "deceased_verified",
                "reason": "official source death record closed",
            },
            {
                "at": BUILT_AT,
                "from": "deceased_verified",
                "to": status,
                "reason": (
                    "coverage/readiness/stable-ID selection"
                    if status == "program_target"
                    else "deterministic reserve order"
                    if status == "reserve"
                    else "eligible but outside current target and reserve closure"
                ),
            },
        ],
        "what_is_proven": proven,
        "what_is_not_proven": not_proven,
        "conflict_notes": artist["conflict_notes"],
        "reserve_order": reserve_order,
        "candidate_batch": batch,
        "legacy_existing": artist["legacy_existing"],
        "selection_reason_codes": (
            ["legacy_baseline_retained", "hard_gates_pass"]
            if artist["legacy_existing"]
            else ["hard_gates_pass", "coverage_bucket_contribution", "batch_executable"]
            if status == "program_target"
            else ["hard_gates_pass", "ordered_replacement_candidate"]
            if status == "reserve"
            else ["hard_gates_pass", "coverage_capacity_saturated"]
        ),
    }


def _source_audit(input_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hashes_by_name = {
        Path(item["path"]).name: item.get("sha256") or f"git:{item.get('git_commit')}"
        for item in input_records
    }
    records = []
    for source_id, profile in sorted(SOURCE_PROFILES.items()):
        record = {
            "source_id": source_id,
            **profile,
            "adapter_version": "museum-09a-offline-cache-v1",
            "fixture_or_snapshot_hash": next(
                (
                    value
                    for name, value in hashes_by_name.items()
                    if source_id.split("_", 1)[0] in name
                ),
                "recorded-in-discovery-input-closure",
            ),
            "provenance": "official bulk data or cached official collection response",
            "robots_and_terms_behavior": "no media crawl; cached metadata only; fail closed on missing cache",
            "fail_closed_behavior": (
                "missing source identity, death evidence, attribution, or object ID prevents target status"
            ),
            "rights_status": "PASS_BY_USER_AUTHORIZATION",
        }
        records.append(record)
    return records


def _write_sharded_document(
    output: Path,
    relative: str,
    document: dict[str, Any],
    *,
    collection_field: str,
    count_field: str,
    chunk_size: int,
) -> list[str]:
    records = document[collection_field]
    shard_directory = Path(relative).with_suffix("")
    absolute_directory = output / shard_directory
    if absolute_directory.exists():
        shutil.rmtree(absolute_directory)
    absolute_directory.mkdir(parents=True)
    shard_entries: list[dict[str, Any]] = []
    written: list[str] = []
    for index, offset in enumerate(range(0, len(records), chunk_size), start=1):
        chunk = records[offset : offset + chunk_size]
        shard_relative = (shard_directory / f"part-{index:04d}.json").as_posix()
        shard_document = {
            "schema_version": document["schema_version"],
            "phase_id": document["phase_id"],
            count_field: len(chunk),
            collection_field: chunk,
        }
        shard_path = output / shard_relative
        write_canonical_json(shard_path, shard_document)
        byte_count = shard_path.stat().st_size
        if byte_count >= SHARD_MAX_BYTES:
            raise ValueError(f"MUSEUM-09A shard exceeds repository limit: {shard_relative}={byte_count}")
        shard_entries.append(
            {
                "path": shard_relative,
                "record_count": len(chunk),
                "bytes": byte_count,
                "sha256": sha256_file(shard_path),
                "first_id": chunk[0]["id"],
                "last_id": chunk[-1]["id"],
            }
        )
        written.append(shard_relative)
    manifest = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "entity_type": "sharded_collection_manifest",
        "collection_field": collection_field,
        "document_count_field": count_field,
        "record_count": len(records),
        "shard_count": len(shard_entries),
        "ordering": "stable_id_ascending",
        "records_hash": _canonical_hash(records),
        "shards": shard_entries,
    }
    write_canonical_json(output / relative, manifest)
    return [relative, *written]


def _read_sharded_document(
    package_root: Path,
    relative: str,
    manifest: dict[str, Any],
    *,
    collection_field: str,
    count_field: str,
    chunk_size: int,
    fail: Any,
) -> dict[str, Any]:
    schema_path = ROOT / "schemas" / "art" / "expansion" / "sharded-collection.schema.json"
    schema = _json(schema_path)
    Draft202012Validator.check_schema(schema)
    for error in sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path)
        fail("shard_manifest_schema", error.message, f"{relative}:{location}")
    if (
        manifest.get("collection_field") != collection_field
        or manifest.get("document_count_field") != count_field
    ):
        fail("shard_manifest_contract", "collection/count field mismatch", relative)
    records: list[dict[str, Any]] = []
    declared_paths: list[str] = []
    root_resolved = package_root.resolve()
    for shard in manifest.get("shards", []):
        shard_relative = shard.get("path", "")
        declared_paths.append(shard_relative)
        shard_path = (package_root / shard_relative).resolve()
        if not shard_path.is_relative_to(root_resolved):
            fail("shard_path_escape", shard_relative, relative)
            continue
        try:
            shard_document = _json(shard_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            fail("shard_unreadable", str(error), shard_relative)
            continue
        if shard_path.stat().st_size != shard.get("bytes") or sha256_file(shard_path) != shard.get("sha256"):
            fail("shard_hash_drift", shard_relative, shard_relative)
        if shard_path.stat().st_size >= SHARD_MAX_BYTES:
            fail("shard_file_size", shard_relative, shard_relative)
        chunk = shard_document.get(collection_field)
        if (
            shard_document.get("schema_version") != "1.0.0"
            or shard_document.get("phase_id") != PHASE_ID
            or not isinstance(chunk, list)
            or shard_document.get(count_field) != len(chunk)
            or shard.get("record_count") != len(chunk)
        ):
            fail("shard_count_drift", shard_relative, shard_relative)
            continue
        if chunk and (
            shard.get("first_id") != chunk[0].get("id")
            or shard.get("last_id") != chunk[-1].get("id")
        ):
            fail("shard_boundary_drift", shard_relative, shard_relative)
        records.extend(chunk)
    if declared_paths != sorted(declared_paths):
        fail("shard_order", "shard paths must be sorted", relative)
    shard_directory = package_root / Path(relative).with_suffix("")
    actual_paths = (
        sorted(path.relative_to(package_root).as_posix() for path in shard_directory.rglob("*.json"))
        if shard_directory.is_dir()
        else []
    )
    if actual_paths != declared_paths:
        fail("shard_physical_closure", "declared and physical shard paths differ", relative)
    if manifest.get("record_count") != len(records):
        fail("shard_total_count", "manifest record count differs from shards", relative)
    if manifest.get("records_hash") != _canonical_hash(records):
        fail("shard_records_hash", "combined record hash differs", relative)
    return {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        count_field: len(records),
        collection_field: records,
    }


def _write_documents(
    output: Path,
    universe: Universe,
    existing_artist_ids: list[str],
    existing_work_ids: list[str],
    *,
    deterministic_rebuild_status: str,
) -> dict[str, Any]:
    input_records, input_hash = _input_manifest()
    target_ids, reserve_ids, assignments, rejected_ids = select_artists(
        universe, existing_artist_ids
    )
    gallery = _select_gallery(universe, target_ids, existing_artist_ids)
    target_counts = _work_targets_per_artist(universe, target_ids, gallery)
    target_works = select_target_works(
        universe, target_ids, existing_work_ids, target_counts
    )
    artist_batch, batches = _assign_batches(
        target_ids, existing_artist_ids, target_works, assignments, gallery
    )
    target_work_ids = {work["id"] for work in target_works}
    existing_artist_id_set = set(existing_artist_ids)
    for work in target_works:
        work["status"] = "program_target"
        work["candidate_batch"] = (
            "legacy-baseline"
            if work["legacy_existing"]
            else "legacy-target-supplement"
            if work["artist_id"] in existing_artist_id_set
            else artist_batch[work["artist_id"]]
        )
    candidate_works = _candidate_work_set(
        universe, target_ids, reserve_ids, rejected_ids, target_works
    )
    for work in candidate_works:
        if work["id"] in target_work_ids:
            target = next(item for item in target_works if item["id"] == work["id"])
            work.update(target)
        elif work["artist_id"] in reserve_ids:
            work["status"] = "reserve"
        else:
            work["status"] = "metadata_verified"

    eligible_ids = sorted(
        artist_id for artist_id, artist in universe.artists.items() if _eligible(artist)
    )
    reserve_order = {artist_id: index + 1 for index, artist_id in enumerate(reserve_ids)}
    artist_documents = []
    for artist_id in eligible_ids:
        status = (
            "program_target"
            if artist_id in assignments
            else "reserve"
            if artist_id in reserve_order
            else "rejected"
        )
        primary = assignments.get(artist_id)
        if primary is None:
            primary = sorted(universe.artists[artist_id]["regions"])[0]
        tier = (
            "gallery"
            if artist_id in gallery
            else "collection"
            if status == "program_target"
            else "discovery-only"
        )
        artist_documents.append(
            _artist_document(
                universe.artists[artist_id],
                status=status,
                primary_bucket=primary,
                tier=tier,
                reserve_order=reserve_order.get(artist_id),
                batch=artist_batch.get(artist_id),
            )
        )

    deceased_evidence = []
    for artist_id in eligible_ids:
        artist = universe.artists[artist_id]
        index = 0
        for evidence in artist["deceased_evidence"]:
            if not evidence["formal_official_source"]:
                continue
            index += 1
            deceased_evidence.append(
                {
                    "id": f"deceased-evidence:{artist_id.split(':', 1)[1]}:{index}",
                    "artist_id": artist_id,
                    **evidence,
                    "claim": f"{artist['preferred_name']} died in {artist['death_year']}",
                    "evidence_type": "official_source_record",
                    "status": "verified",
                }
            )
    duplicate_clusters = [
        {
            "id": document["duplicate_cluster_id"],
            "kind": "artist_identity",
            "canonical_artist_id": document["id"],
            "source_identities": document["source_identities"],
            "disposition": "merged_by_authority_or_name_life_date",
        }
        for document in artist_documents
        if len(document["source_identities"]) > 1
    ]
    duplicate_clusters.extend(
        {
            "id": cluster_id,
            "kind": "candidate_work",
            "member_ids": sorted(work["id"] for work in members),
            "disposition": "one member maximum eligible for program target",
        }
        for cluster_id, members in sorted(
            (
                (cluster_id, members)
                for cluster_id, members in _group_by(
                    candidate_works, lambda work: work["duplicate_cluster_id"]
                ).items()
                if len(members) > 1
            ),
            key=lambda pair: pair[0],
        )
    )
    target_artists = [
        document for document in artist_documents if document["status"] == "program_target"
    ]
    source_target_counts = Counter(work["source_id"] for work in target_works)
    source_candidate_counts = Counter(work["source_id"] for work in candidate_works)
    source_artist_counts = Counter(
        source["source_id"]
        for artist in target_artists
        for source in artist["source_identities"]
    )
    source_contribution = []
    for source_id in sorted(SOURCE_PROFILES):
        source_contribution.append(
            {
                "source_id": source_id,
                "target_artist_identity_count": source_artist_counts[source_id],
                "candidate_work_count": source_candidate_counts[source_id],
                "target_work_count": source_target_counts[source_id],
                "target_work_share": round(source_target_counts[source_id] / 5000, 6),
                "only_source_target_artist_count": sum(
                    1
                    for artist in target_artists
                    if len(artist["source_identities"]) == 1
                    and artist["source_identities"][0]["source_id"] == source_id
                ),
                "regions": sorted(
                    {
                        artist["primary_coverage_bucket"]
                        for artist in target_artists
                        if any(
                            item["source_id"] == source_id for item in artist["source_identities"]
                        )
                    }
                ),
                "periods": dict(
                    sorted(
                        Counter(
                            artist["historical_period"]
                            for artist in target_artists
                            if any(
                                item["source_id"] == source_id
                                for item in artist["source_identities"]
                            )
                        ).items()
                    )
                ),
                "media": dict(
                    sorted(
                        Counter(
                            tag
                            for work in target_works
                            if work["source_id"] == source_id
                            for tag in work["medium_tags"]
                        ).items()
                    )
                ),
            }
        )
    coverage_matrix = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "primary_bucket_counts": dict(
            sorted(Counter(artist["primary_coverage_bucket"] for artist in target_artists).items())
        ),
        "guardrails": REGION_GUARDRAILS,
        "historical_period_counts": dict(
            sorted(Counter(artist["historical_period"] for artist in target_artists).items())
        ),
        "media_practice_counts": dict(
            sorted(
                Counter(
                    tag
                    for artist in target_artists
                    for tag in artist["documented_media_practice_tags"]
                ).items()
            )
        ),
        "content_depth_counts": dict(
            sorted(Counter(artist["content_depth_tier"] for artist in target_artists).items())
        ),
        "legacy_primary_bucket_counts": dict(
            sorted(Counter(EXISTING_COVERAGE.values()).items())
        ),
        "sensitive_identity_inference_used": False,
        "coverage_note": (
            "Primary buckets are evidence-backed research-routing labels, not nationality, "
            "ethnicity, bloodline, value, or historical-influence claims."
        ),
    }
    source_audit = _source_audit(input_records)
    first_batch = batches[0]
    first_batch_ids = set(first_batch["artist_ids"])
    first_batch_works = [
        work for work in target_works if work["artist_id"] in first_batch_ids
    ]
    first_batch_risks = {
        "P0": [],
        "P1": [],
        "P2": [],
        "P3": [
            {
                "code": "source-record-drift",
                "owner": "MUSEUM-09B batch writer",
                "mitigation": "refresh only changed source records by stable ID and content hash",
                "review_by": "before MUSEUM-09B promotion",
            }
        ],
    }
    documents: dict[str, Any] = {
        "discovery-manifest.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "built_at": BUILT_AT,
            "raw_discovered_artist_count": sum(universe.raw_source_counts.values()),
            "raw_discovery_by_source": dict(sorted(universe.raw_source_counts.items())),
            "deduplicated_real_person_candidate_count": len(eligible_ids),
            "deceased_verified_candidate_count": len(eligible_ids),
            "input_closure_hash": input_hash,
            "inputs": input_records,
            "raw_cache_tracked": False,
            "raw_cache_policy": "ignored source vault; normalized reviewed package is tracked",
            "new_media_download_count": 0,
        },
        "normalized-candidates.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "candidate_count": len(artist_documents),
            "candidates": artist_documents,
        },
        "deceased-evidence.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "evidence_count": len(deceased_evidence),
            "records": deceased_evidence,
        },
        "duplicate-clusters.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "cluster_count": len(duplicate_clusters),
            "clusters": duplicate_clusters,
        },
        "coverage-matrix.json": coverage_matrix,
        "artist-decisions.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "program_target_ids": sorted(assignments),
            "reserve_ids": reserve_ids,
            "rejected_ids": rejected_ids,
            "blocked_ids": sorted(
                artist_id
                for artist_id, artist in universe.artists.items()
                if artist_id not in eligible_ids
            ),
            "selection_contract": [
                "identity and confirmed-deceased hard gates",
                "official source and work-mapping closure",
                "coverage contribution",
                "source/institution diversity",
                "batch executability",
                "stable ID tie-breaker",
            ],
            "forbidden_scores_absent": True,
        },
        "candidate-artworks.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "artwork_count": len(candidate_works),
            "artworks": candidate_works,
        },
        "target-artworks.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "artwork_count": len(target_works),
            "artworks": target_works,
        },
        "source-audit.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "source_count": len(source_audit),
            "official_source_count": len(source_audit),
            "sources": source_audit,
        },
        "source-contribution-matrix.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "sources": source_contribution,
            "maximum_single_source_target_work_share": max(
                item["target_work_share"] for item in source_contribution
            ),
            "multi_source_target_artist_count": sum(
                len(artist["source_identities"]) > 1 for artist in target_artists
            ),
            "one_source_target_artist_count": sum(
                len(artist["source_identities"]) == 1 for artist in target_artists
            ),
        },
        "batch-registry-snapshot.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "legacy_baseline": {
                "artist_count": 12,
                "work_count": 44,
                "artist_ids": existing_artist_ids,
                "work_ids": existing_work_ids,
                "status": "reference_only_not_rebuilt",
            },
            "legacy_target_supplement": {
                "artist_ids": existing_artist_ids,
                "work_ids": sorted(
                    work["id"]
                    for work in target_works
                    if work["artist_id"] in existing_artist_id_set
                    and not work["legacy_existing"]
                ),
                "status": "registered_not_started",
                "note": (
                    "New candidate works needed to bring every retained legacy artist to the "
                    "same minimum-work contract; existing 12/44 records remain unchanged."
                ),
            },
            "batch_count": 10,
            "batches": batches,
            "reserve_replacement_order": reserve_ids,
            "assignment_contract": "deterministic, disjoint, stable-ID based; replacement only on hard-gate failure",
        },
        "museum-09b-first-batch.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "status": "recommended_not_started",
            "batch_id": first_batch["id"],
            "artist_count": first_batch["artist_count"],
            "work_count": len(first_batch_works),
            "artist_ids": first_batch["artist_ids"],
            "work_ids": sorted(work["id"] for work in first_batch_works),
            "coverage_delta": first_batch["coverage_delta"],
            "source_metadata_readiness": dict(
                sorted(Counter(work["source_id"] for work in first_batch_works).items())
            ),
            "media_feasibility": {
                "metadata_only_ready": len(first_batch_works),
                "media_permission_ready": 0,
                "media_downloaded": 0,
                "note": "availability is not permission; M09B must review object by object",
            },
            "selection_reasons": [
                "hard gates passed",
                "coverage balance",
                "source metadata cache ready",
                "stable-ID deterministic assignment",
            ],
            "risks": first_batch_risks,
            "museum_09b_entered": False,
        },
        "public-leakage-label-set.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "candidate_roots": [
                "data/reviewed/art/museum-09a/",
                "governance/museum-09-batch-registry.json",
            ],
            "forbidden_public_markers": [
                "artist:m09a-",
                "candidate-work:",
                "museum-09-batch-",
                "global-expansion-universe-v1",
            ],
            "public_runtime_allowlist": [],
            "candidate_public_leakage_count": 0,
        },
        "status-history.json": {
            "schema_version": "1.0.0",
            "phase_id": PHASE_ID,
            "artist_status_counts": dict(
                sorted(Counter(artist["status"] for artist in artist_documents).items())
            ),
            "artwork_status_counts": dict(
                sorted(Counter(work["status"] for work in candidate_works).items())
            ),
            "forbidden_waiting_states_present": False,
            "generated_at": BUILT_AT,
        },
    }
    written_relatives: list[str] = []
    for relative, document in documents.items():
        if relative in SHARDED_DOCUMENTS:
            written_relatives.extend(
                _write_sharded_document(
                    output,
                    relative,
                    document,
                    **SHARDED_DOCUMENTS[relative],
                )
            )
        else:
            write_canonical_json(output / relative, document)
            written_relatives.append(relative)

    manifest_entries = [
        {
            "path": relative,
            "bytes": (output / relative).stat().st_size,
            "sha256": sha256_file(output / relative),
        }
        for relative in sorted(written_relatives)
    ]
    build_manifest = {
        "schema_version": "1.0.0",
        "phase_id": PHASE_ID,
        "build_version": "museum-09a-global-expansion-v1",
        "built_at": BUILT_AT,
        "baseline_commit": BASELINE_COMMIT,
        "input_release_id": INPUT_RELEASE_ID,
        "input_release_content_hash": INPUT_RELEASE_CONTENT_HASH,
        "input_release_manifest_sha256": INPUT_RELEASE_MANIFEST_SHA256,
        "input_release_tree_sha256": INPUT_RELEASE_TREE_SHA256,
        "input_closure_hash": input_hash,
        "canonical_writer": "museum_pipeline/art/global_expansion.py",
        "writer_sha256": sha256_file(Path(__file__)),
        "artifact_entries": manifest_entries,
        "artifact_content_hash": _canonical_hash(manifest_entries),
        "public_release_changed": False,
        "new_media_download_count": 0,
        "museum_09b_entered": False,
        "arms_museum_entered": False,
        "remaining_open_decisions": ["OD-011"],
        "deterministic_rebuild_status": deterministic_rebuild_status,
    }
    write_canonical_json(output / "build-manifest.json", build_manifest)
    summary = validate_global_expansion(output, include_validation_summary=False)
    summary["deterministic_rebuild_status"] = deterministic_rebuild_status
    write_canonical_json(output / "validation-summary.json", summary)
    return summary


def _group_by(items: Iterable[Any], key: Any) -> dict[Any, list[Any]]:
    result: dict[Any, list[Any]] = defaultdict(list)
    for item in items:
        result[key(item)].append(item)
    return result


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_global_expansion(
    output: Path = DEFAULT_OUTPUT,
    *,
    verify_deterministic: bool = False,
) -> dict[str, Any]:
    universe, existing_artist_ids, existing_work_ids = discover_universe()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".museum-09a-", dir=output.parent) as temporary:
        staged = Path(temporary) / output.name
        staged.mkdir()
        _write_documents(
            staged,
            universe,
            existing_artist_ids,
            existing_work_ids,
            deterministic_rebuild_status="pass",
        )
        if verify_deterministic:
            second = Path(temporary) / f"{output.name}-determinism"
            second.mkdir()
            _write_documents(
                second,
                universe,
                existing_artist_ids,
                existing_work_ids,
                deterministic_rebuild_status="pass",
            )
            if _file_hashes(staged) != _file_hashes(second):
                raise ValueError("deterministic rebuild produced different bytes")
        if output.exists():
            if _file_hashes(output) == _file_hashes(staged):
                if output == DEFAULT_OUTPUT.resolve():
                    write_canonical_json(
                        DEFAULT_BATCH_REGISTRY,
                        _json(output / "batch-registry-snapshot.json"),
                    )
                return validate_global_expansion(output)
            shutil.rmtree(output)
        shutil.copytree(staged, output)
    if output == DEFAULT_OUTPUT.resolve():
        write_canonical_json(
            DEFAULT_BATCH_REGISTRY,
            _json(output / "batch-registry-snapshot.json"),
        )
    return validate_global_expansion(output)


def _public_release_profile() -> dict[str, Any]:
    manifest = _json(PUBLIC_RELEASE / "manifest.json")
    return {
        "release_id": manifest.get("id"),
        "content_hash": manifest.get("content_hash"),
        "manifest_sha256": sha256_file(PUBLIC_RELEASE / "manifest.json"),
        "tree_hash": physical_tree(PUBLIC_RELEASE)["hash"],
    }


def validate_global_expansion(
    package_root: Path = DEFAULT_OUTPUT,
    *,
    include_validation_summary: bool = True,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []

    def fail(code: str, message: str, path: str = "$") -> None:
        failures.append({"code": code, "message": message, "path": path})

    required = {
        "discovery": "discovery-manifest.json",
        "artists": "normalized-candidates.json",
        "deceased": "deceased-evidence.json",
        "duplicates": "duplicate-clusters.json",
        "coverage": "coverage-matrix.json",
        "decisions": "artist-decisions.json",
        "candidate_works": "candidate-artworks.json",
        "target_works": "target-artworks.json",
        "source_audit": "source-audit.json",
        "source_matrix": "source-contribution-matrix.json",
        "batches": "batch-registry-snapshot.json",
        "first_batch": "museum-09b-first-batch.json",
        "leakage": "public-leakage-label-set.json",
        "history": "status-history.json",
        "build": "build-manifest.json",
    }
    if include_validation_summary:
        required["validation"] = "validation-summary.json"
    documents: dict[str, Any] = {}
    for key, relative in required.items():
        try:
            documents[key] = _json(package_root / relative)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            fail("artifact_unreadable", str(error), relative)
    if failures:
        return {"ok": False, "phase_id": PHASE_ID, "failures": failures}

    for key, relative in (
        ("artists", required["artists"]),
        ("deceased", required["deceased"]),
        ("candidate_works", required["candidate_works"]),
        ("target_works", required["target_works"]),
    ):
        documents[key] = _read_sharded_document(
            package_root,
            relative,
            documents[key],
            fail=fail,
            **SHARDED_DOCUMENTS[relative],
        )

    schema_bindings = {
        "artists": ROOT / "schemas" / "art" / "expansion" / "candidate-universe.schema.json",
        "candidate_works": ROOT / "schemas" / "art" / "expansion" / "artwork-universe.schema.json",
        "target_works": ROOT / "schemas" / "art" / "expansion" / "artwork-universe.schema.json",
        "batches": ROOT / "schemas" / "art" / "expansion" / "batch-registry.schema.json",
    }
    for key, schema_path in schema_bindings.items():
        schema = _json(schema_path)
        Draft202012Validator.check_schema(schema)
        for error in sorted(
            Draft202012Validator(schema).iter_errors(documents[key]),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        ):
            location = ".".join(str(part) for part in error.absolute_path)
            fail("expansion_schema", error.message, f"{required[key]}:{location}")

    artists = documents["artists"]["candidates"]
    target_artists = [artist for artist in artists if artist["status"] == "program_target"]
    reserve_artists = [artist for artist in artists if artist["status"] == "reserve"]
    candidate_works = documents["candidate_works"]["artworks"]
    target_works = documents["target_works"]["artworks"]
    artist_ids = [artist["id"] for artist in artists]
    target_ids = {artist["id"] for artist in target_artists}
    work_ids = [work["id"] for work in candidate_works]
    target_work_ids = {work["id"] for work in target_works}
    legacy_artist_ids = set(documents["batches"]["legacy_baseline"]["artist_ids"])
    legacy_work_ids = set(documents["batches"]["legacy_baseline"]["work_ids"])

    if documents["discovery"]["raw_discovered_artist_count"] < 900:
        fail("raw_artist_count", "raw discovered artist count is below 900")
    if documents["discovery"]["deduplicated_real_person_candidate_count"] < 700:
        fail("deduplicated_artist_count", "deduplicated candidate count is below 700")
    if len(target_artists) != 500 or len(target_ids) != 500:
        fail("target_artist_count", "program target artists must be exactly 500")
    if len(reserve_artists) < 100:
        fail("reserve_artist_count", "reserve artists must be at least 100")
    if len(legacy_artist_ids) != 12 or len(target_ids - legacy_artist_ids) != 488:
        fail("legacy_new_artist_count", "existing/new target artist split must be 12/488")
    if len(candidate_works) < 7500:
        fail("candidate_work_count", "candidate works must be at least 7,500")
    if len(target_works) != 5000 or len(target_work_ids) != 5000:
        fail("target_work_count", "program target works must be exactly 5,000")
    if len(legacy_work_ids) != 44 or len(target_work_ids - legacy_work_ids) != 4956:
        fail("legacy_new_work_count", "existing/new target work split must be 44/4,956")
    if len(artist_ids) != len(set(artist_ids)):
        fail("artist_id_duplicate", "artist stable IDs must be unique")
    if artist_ids != sorted(artist_ids):
        fail("nondeterministic_order", "normalized candidates must be stable-ID sorted")
    if len(work_ids) != len(set(work_ids)):
        fail("work_id_duplicate", "candidate work stable IDs must be unique")
    if work_ids != sorted(work_ids):
        fail("nondeterministic_order", "candidate works must be stable-ID sorted")
    if [work["id"] for work in target_works] != sorted(target_work_ids):
        fail("nondeterministic_order", "target works must be stable-ID sorted")
    if not legacy_artist_ids <= target_ids or not legacy_work_ids <= target_work_ids:
        fail("legacy_inclusion", "existing 12/44 must be exact subsets of targets")

    evidence_ids = {
        record["id"] for record in documents["deceased"]["records"]
    }
    for artist in target_artists:
        if artist.get("artist_kind") != "individual":
            fail("non_person_target", artist["id"], artist["id"])
        if artist.get("deceased_status") != "confirmed_deceased":
            fail("deceased_gate", artist["id"], artist["id"])
        birth_year = artist.get("birth", {}).get("year")
        death_year = artist.get("death", {}).get("year")
        if (
            not isinstance(death_year, int)
            or death_year > 2026
            or (
                isinstance(birth_year, int)
                and not 10 <= death_year - birth_year <= 150
            )
        ):
            fail("implausible_life_dates", artist["id"], artist["id"])
        if not artist.get("deceased_verification_evidence_ids"):
            fail("missing_deceased_evidence", artist["id"], artist["id"])
        if not set(artist.get("deceased_verification_evidence_ids", [])) <= evidence_ids:
            fail("deceased_evidence_closure", artist["id"], artist["id"])
        if not artist.get("source_identities"):
            fail("wikidata_only_target", artist["id"], artist["id"])
        if any(item["source_id"] == "wikidata_discovery" for item in artist["source_identities"]):
            fail("discovery_source_promoted", artist["id"], artist["id"])
        if artist.get("conflict_notes"):
            fail("target_identity_conflict", artist["id"], artist["id"])

    target_work_counts = Counter(work["artist_id"] for work in target_works)
    for artist_id in target_ids:
        if target_work_counts[artist_id] < 3:
            fail("target_without_three_works", artist_id, artist_id)
    duplicate_target_clusters = [
        cluster
        for cluster, count in Counter(work["duplicate_cluster_id"] for work in target_works).items()
        if count > 1
    ]
    if duplicate_target_clusters:
        fail("duplicate_target_work", f"{len(duplicate_target_clusters)} duplicate clusters")
    for work in target_works:
        if work["artist_id"] not in target_ids:
            fail("target_work_artist_closure", work["id"], work["id"])
        if not work.get("evidence", {}).get("source_id") or not work.get("source_object_id"):
            fail("work_evidence_closure", work["id"], work["id"])
        if work.get("attribution_qualifier") in {
            "anonymous",
            "workshop",
            "tradition",
            "unknown",
            "attribution_conflict",
        }:
            fail("work_attribution_conflict", work["id"], work["id"])

    coverage_counts = Counter(artist["primary_coverage_bucket"] for artist in target_artists)
    for region, rule in REGION_GUARDRAILS.items():
        if "minimum" in rule and coverage_counts[region] < rule["minimum"]:
            fail("coverage_minimum", f"{region}={coverage_counts[region]}")
        if "maximum" in rule and coverage_counts[region] > rule["maximum"]:
            fail("coverage_maximum", f"{region}={coverage_counts[region]}")
    if dict(sorted(coverage_counts.items())) != documents["coverage"]["primary_bucket_counts"]:
        fail("coverage_matrix_closure", "coverage matrix counts do not match target artists")

    source_counts = Counter(work["source_id"] for work in target_works)
    if max(source_counts.values()) / 5000 > 0.30:
        fail("one_source_dominance", f"maximum target source share is {max(source_counts.values()) / 5000:.3f}")
    source_matrix = documents["source_matrix"]
    if source_matrix["maximum_single_source_target_work_share"] > 0.30:
        fail("source_matrix_dominance", "source matrix maximum exceeds 30%")

    batches = documents["batches"]["batches"]
    batch_artist_ids = [artist_id for batch in batches for artist_id in batch["artist_ids"]]
    if len(batches) != 10:
        fail("batch_count", "exactly 10 expansion batches are required")
    if len(batch_artist_ids) != 488 or len(batch_artist_ids) != len(set(batch_artist_ids)):
        fail("batch_overlap_or_count", "batch assignments must be disjoint and close 488 new artists")
    if set(batch_artist_ids) != target_ids - legacy_artist_ids:
        fail("batch_artist_closure", "batch artist IDs do not equal new target artist IDs")
    if [batch["artist_count"] for batch in batches] != [50, 49, 49, 49, 49, 49, 49, 48, 48, 48]:
        fail("batch_sizes", "batch sizes are not the fixed 50/49/48 closure")
    if documents["first_batch"]["artist_count"] != 50:
        fail("first_batch_artist_count", "M09B recommended first batch must contain 50 artists")
    if not 450 <= documents["first_batch"]["work_count"] <= 550:
        fail("first_batch_work_count", "M09B first batch must contain about 500 works")
    if documents["first_batch"]["status"] != "recommended_not_started":
        fail("museum_09b_boundary", "M09B must not be entered")

    reserve_orders = sorted(
        artist["reserve_order"] for artist in reserve_artists
    )
    if reserve_orders != list(range(1, len(reserve_artists) + 1)):
        fail("reserve_order", "reserve order must be complete and deterministic")
    if any(
        "ordered_replacement_candidate" not in artist.get("selection_reason_codes", [])
        for artist in reserve_artists
    ):
        fail("reserve_without_reason", "every reserve must retain its replacement reason")

    forbidden_key = re.compile(
        r"(importance|popularity|market(?:_value)?|western_canon|museum_fame|"
        r"social_media|query_frequency|ai_aesthetic)(?:_score)?$"
    )

    def scan(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if forbidden_key.search(key.casefold()):
                    fail("forbidden_score", key, f"{path}.{key}")
                if key.casefold() in {
                    "inferred_gender",
                    "inferred_ethnicity",
                    "inferred_race",
                    "inferred_sensitive_identity",
                }:
                    fail("sensitive_identity_inference", key, f"{path}.{key}")
                if key == "status" and isinstance(item, str) and item.startswith("waiting_for"):
                    fail("manual_waiting_state", item, f"{path}.{key}")
                scan(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                scan(item, f"{path}[{index}]")

    for document in documents.values():
        scan(document)

    media_files = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".mp4", ".mp3"}
    ]
    if media_files:
        fail("media_bytes", f"candidate package contains media: {media_files[:10]}")
    build_profile = documents["build"]
    if (
        build_profile.get("input_release_id") != INPUT_RELEASE_ID
        or build_profile.get("input_release_content_hash") != INPUT_RELEASE_CONTENT_HASH
        or build_profile.get("input_release_manifest_sha256") != INPUT_RELEASE_MANIFEST_SHA256
        or build_profile.get("input_release_tree_sha256") != INPUT_RELEASE_TREE_SHA256
        or build_profile.get("public_release_changed") is not False
    ):
        fail("current_release_mutation", "build manifest predecessor profile drifted")
    public_profile = _public_release_profile()
    expected_profile = {
        "release_id": INPUT_RELEASE_ID,
        "content_hash": INPUT_RELEASE_CONTENT_HASH,
        "manifest_sha256": INPUT_RELEASE_MANIFEST_SHA256,
        "tree_hash": INPUT_RELEASE_TREE_SHA256,
    }
    if public_profile != expected_profile:
        fail("current_release_mutation", json.dumps(public_profile, sort_keys=True))
    leakage_markers = documents["leakage"]["forbidden_public_markers"]
    leakage_hits: list[str] = []
    for path in sorted((ROOT / "public").rglob("*")):
        if not path.is_file() or path.stat().st_size > 20_000_000:
            continue
        payload = path.read_bytes()
        for marker in leakage_markers:
            if marker.encode("utf-8") in payload:
                leakage_hits.append(f"{path.relative_to(ROOT).as_posix()}:{marker}")
    if leakage_hits:
        fail("candidate_public_leakage", json.dumps(leakage_hits[:20]))
    if documents["leakage"].get("candidate_public_leakage_count") != 0:
        fail("candidate_public_leakage", "leakage label set records a nonzero count")
    if package_root.resolve() == DEFAULT_OUTPUT.resolve():
        if not DEFAULT_BATCH_REGISTRY.is_file():
            fail("governance_batch_registry_missing", str(DEFAULT_BATCH_REGISTRY))
        elif _json(DEFAULT_BATCH_REGISTRY) != documents["batches"]:
            fail(
                "governance_batch_registry_drift",
                "governance registry differs from canonical package snapshot",
            )

    if include_validation_summary:
        summary = documents["validation"]
        if summary.get("ok") is not True or summary.get("failure_count") != 0:
            fail("committed_validation_summary", "committed validation summary is not pass")
    return {
        "ok": not failures,
        "phase_id": PHASE_ID,
        "status": "pass" if not failures else "fail",
        "failure_count": len(failures),
        "failures": failures,
        "counts": {
            "raw_discovered_artists": documents["discovery"]["raw_discovered_artist_count"],
            "deduplicated_artists": documents["discovery"]["deduplicated_real_person_candidate_count"],
            "deceased_verified_candidates": documents["discovery"]["deceased_verified_candidate_count"],
            "program_target_artists": len(target_artists),
            "existing_target_artists": len(legacy_artist_ids),
            "new_target_artists": len(target_ids - legacy_artist_ids),
            "reserve_artists": len(reserve_artists),
            "candidate_artworks": len(candidate_works),
            "program_target_artworks": len(target_works),
            "existing_target_artworks": len(legacy_work_ids),
            "new_target_artworks": len(target_work_ids - legacy_work_ids),
            "batch_count": len(batches),
            "candidate_public_leakage": len(leakage_hits),
            "new_media_downloads": 0,
        },
        "coverage": dict(sorted(coverage_counts.items())),
        "sources": dict(sorted(source_counts.items())),
        "maximum_single_source_target_work_share": round(max(source_counts.values()) / 5000, 6),
        "public_release": public_profile,
        "package_bytes": sum(path.stat().st_size for path in package_root.rglob("*") if path.is_file()),
        "deterministic_rebuild_status": documents.get("build", {}).get(
            "deterministic_rebuild_status", "not_checked"
        ),
        "candidate_public_leakage_count": len(leakage_hits),
        "new_media_download_count": 0,
        "museum_09b_entered": False,
        "arms_museum_entered": False,
        "remaining_open_decisions": ["OD-011"],
    }


def public_release_content_hash() -> str:
    manifest = _json(PUBLIC_RELEASE / "manifest.json")
    return release_content_hash(manifest.get("manifest_files", []))
