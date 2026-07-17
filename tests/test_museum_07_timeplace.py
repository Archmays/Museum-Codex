from __future__ import annotations

import gzip
import json
import unittest
from collections import Counter
from pathlib import Path

from museum_pipeline.art.timeplace import (
    EXPECTED_OVERLAY,
    INPUT_MANIFEST_SHA256,
    INPUT_RELEASE,
    INPUT_RELEASE_HASH,
    RELEASE_ID,
    SCHEMA_BY_FILE,
    validate_museum_07_release,
)
from museum_pipeline.canonical_json import canonical_json_bytes
from museum_pipeline.config import ROOT
from museum_pipeline.hashing import sha256_file
from museum_pipeline.validation.dispatch import canonical_schema_path, validate_record


RELEASE = ROOT / "public" / "releases" / "art-time-place-1.3.0"


def load(name: str):
    return json.loads((RELEASE / name).read_text(encoding="utf-8"))


class Museum07TimePlaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load("manifest.json")
        cls.places_doc = load("place-identities.json")
        cls.episodes_doc = load("artist-place-episodes.json")
        cls.claims_doc = load("geospatial-claims.json")
        cls.artwork_places_doc = load("artwork-place-claims.json")
        cls.holdings_doc = load("holding-locations.json")
        cls.points_doc = load("map-points.geojson")
        cls.map_index = load("map-index.json")
        cls.timeline = load("timeline-index.json")
        cls.filters = load("filter-index.json")
        cls.style = load("map-style.json")
        cls.layers = load("map-layer-config.json")
        cls.view_state = load("map-view-state.json")
        cls.basemap = load("basemap-manifest.json")
        cls.attributions = load("map-source-attributions.json")
        cls.decision = load("od-006-snapshot.json")
        cls.dispositions = load("place-research-dispositions.json")
        cls.places = cls.places_doc["places"]
        cls.episodes = cls.episodes_doc["episodes"]

    def test_01_predecessor_release_is_exact(self) -> None:
        predecessor = json.loads((INPUT_RELEASE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(INPUT_RELEASE_HASH, predecessor["content_hash"])
        self.assertEqual(INPUT_MANIFEST_SHA256, sha256_file(INPUT_RELEASE / "manifest.json"))
        self.assertEqual("release:art-pathways-1.2.0", self.manifest["predecessor"])

    def test_02_release_identity_and_physical_validator_pass(self) -> None:
        result = validate_museum_07_release(RELEASE)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual("sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f", result["content_hash"])

    def test_03_overlay_file_set_is_exact(self) -> None:
        predecessor = json.loads((INPUT_RELEASE / "manifest.json").read_text(encoding="utf-8"))
        old = {item["path"] for item in predecessor["manifest_files"]}
        current = {item["path"] for item in self.manifest["manifest_files"]}
        self.assertEqual(EXPECTED_OVERLAY, current - old)

    def test_04_manifest_files_close_bytes_and_hashes(self) -> None:
        for entry in self.manifest["manifest_files"]:
            path = RELEASE / entry["path"]
            with self.subTest(path=entry["path"]):
                self.assertTrue(path.is_file())
                self.assertEqual(entry["bytes"], path.stat().st_size)
                self.assertEqual(entry["sha256"], sha256_file(path, prefixed=False))

    def test_05_od_006_is_closed_with_only_three_open_decisions(self) -> None:
        self.assertEqual("closed", self.decision["status"])
        self.assertEqual(3, self.decision["open_decisions_count"])
        self.assertEqual(["OD-008", "OD-009", "OD-011"], self.decision["remaining_open_decisions"])
        self.assertFalse(self.decision["token_required"])
        self.assertEqual("none", self.decision["external_tile_provider"])

    def test_06_natural_earth_source_and_raw_hashes_are_exact(self) -> None:
        expected = {
            "land": "sha256:1926c621afd6ac67c3f36639bb1236134a48d82226dc675d3e3df53d02d2a3de",
            "coastline": "sha256:664449b39070027e882abb295974d182afec18ca21107273d17e9e8bf6f64817",
            "lakes": "sha256:f2eed3c738a93010770acb0ba44273ea6a83b053641588bc902d9d6fd1cdafcb",
        }
        self.assertEqual("public_domain", self.basemap["license_decision"])
        self.assertEqual("Made with Natural Earth", self.basemap["attribution"])
        self.assertEqual("1:110m", self.basemap["scale"])
        self.assertEqual(expected, {item["layer"]: item["source_sha256"] for item in self.basemap["layers"]})

    def test_07_basemap_outputs_close_parent_hashes_and_geometry(self) -> None:
        for item in self.basemap["layers"]:
            path = RELEASE / item["output_path"]
            document = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(layer=item["layer"]):
                self.assertEqual(item["output_sha256"], sha256_file(path))
                self.assertEqual("FeatureCollection", document["type"])
                self.assertTrue(document["features"])
                self.assertTrue(all(feature["properties"] == {} for feature in document["features"]))

    def test_08_basemap_contains_no_modern_boundary_properties(self) -> None:
        text = " ".join((RELEASE / f"basemap/{name}.geojson").read_text(encoding="utf-8").lower() for name in ("land", "coastline", "lakes"))
        for forbidden in ("admin", "sovereignt", "country", "border", "boundary", "iso_a2", "iso_a3"):
            self.assertNotIn(forbidden, text)

    def test_09_place_identity_count_and_tgn_identity_are_exact(self) -> None:
        self.assertEqual(23, len(self.places))
        self.assertEqual(23, len({item["id"] for item in self.places}))
        self.assertTrue(all(item["id"] == f"place:tgn-{item['tgn_id']}" for item in self.places))
        self.assertTrue(all(item["tgn_uri"] == f"http://vocab.getty.edu/tgn/{item['tgn_id']}" for item in self.places))

    def test_10_place_names_hierarchy_and_multilingual_labels_are_present(self) -> None:
        for place in self.places:
            with self.subTest(place=place["id"]):
                self.assertTrue(place["preferred_historical_label"])
                self.assertTrue(place["current_common_label"])
                self.assertTrue({"zh-Hans", "en", "source"} <= set(place["labels"]))
                self.assertGreaterEqual(len(place["names"]), 3)
                self.assertIsInstance(place["broader_hierarchy"], list)

    def test_11_coordinate_precision_does_not_overstate_source(self) -> None:
        for place in self.places:
            with self.subTest(place=place["id"]):
                coordinates = place["coordinates"]
                if place["coordinate_precision"] == "unknown":
                    self.assertIsNone(coordinates)
                    self.assertEqual("none", place["geometry_type"])
                    self.assertEqual("verified_list_only", place["release_status"])
                else:
                    self.assertEqual(2, len(coordinates))
                    self.assertTrue(-180 <= coordinates[0] <= 180)
                    self.assertTrue(-90 <= coordinates[1] <= 90)
                if place["coordinate_precision"] == "regional_centroid":
                    self.assertGreaterEqual(place["uncertainty_radius_km"], 100)

    def test_12_known_bad_tgn_coordinates_remain_list_only(self) -> None:
        by_tgn = {item["tgn_id"]: item for item in self.places}
        self.assertEqual("unknown", by_tgn["7007227"]["coordinate_precision"])
        self.assertEqual("upstream_invalid_coordinate_string", by_tgn["7007227"]["coordinate_issue"])
        self.assertEqual("unknown", by_tgn["7029465"]["coordinate_precision"])
        self.assertEqual("source_has_no_coordinate", by_tgn["7029465"]["coordinate_issue"])

    def test_13_modern_jurisdiction_is_secondary_only(self) -> None:
        self.assertTrue(all(item["modern_jurisdiction_role"] == "secondary_context_only" for item in self.places))

    def test_14_episode_count_and_artist_distribution_are_exact(self) -> None:
        counts = Counter(item["artist_id"] for item in self.episodes)
        self.assertEqual(12, len(counts))
        self.assertEqual({3}, set(counts.values()))
        self.assertEqual(36, len(self.episodes))

    def test_15_each_artist_has_birth_death_and_nonholding_activity(self) -> None:
        for artist_id in {item["artist_id"] for item in self.episodes}:
            types = {item["episode_type"] for item in self.episodes if item["artist_id"] == artist_id}
            with self.subTest(artist=artist_id):
                self.assertTrue({"birth", "death"} <= types)
                self.assertTrue(types - {"birth", "death", "current_holding_institution"})

    def test_16_time_and_place_precision_are_explicit(self) -> None:
        allowed_date = {"year", "year_range", "decade", "circa", "unknown"}
        allowed_place = {"exact_site", "locality", "city_centroid", "regional_centroid", "bounded_area", "unknown"}
        self.assertTrue(all(item["date_precision"] in allowed_date for item in self.episodes))
        self.assertTrue(all(item["place_precision"] in allowed_place for item in self.episodes))
        self.assertEqual({"city_centroid": 31, "regional_centroid": 2, "unknown": 3}, dict(Counter(item["place_precision"] for item in self.episodes)))

    def test_17_claim_evidence_source_closure_is_exact(self) -> None:
        claims = {item["id"]: item for item in self.claims_doc["claims"]}
        source_ids = {item["id"] for item in self.attributions["sources"]}
        for episode in self.episodes:
            with self.subTest(episode=episode["id"]):
                claim = claims[episode["claim_id"]]
                evidence_ids = {item["id"] for item in episode["evidence"]}
                self.assertEqual(set(claim["evidence_ids"]), evidence_ids)
                self.assertEqual(set(claim["source_ids"]), set(episode["source_ids"]))
                self.assertFalse(set(episode["source_ids"]) - source_ids)
                self.assertTrue(all(item["record_sha256"].startswith("sha256:") for item in episode["evidence"]))

    def test_18_no_inferred_travel_or_movement_geometry_exists(self) -> None:
        self.assertTrue(all(item["geometry"]["type"] == "Point" for item in self.points_doc["features"]))
        self.assertFalse(self.style["runtime_guards"]["route_lines"])
        self.assertIn("travel_routes", self.layers["forbidden_layers"])

    def test_19_list_only_episodes_never_enter_map_points(self) -> None:
        point_ids = {item["id"] for item in self.points_doc["features"]}
        for episode in self.episodes:
            self.assertEqual(episode["release_status"] == "verified_public", episode["id"] in point_ids)
        self.assertEqual(12, sum(item["release_status"] == "verified_list_only" for item in self.episodes))

    def test_20_creation_places_fail_closed_without_proxy_inference(self) -> None:
        records = self.artwork_places_doc["claims"]
        self.assertEqual(44, len(records))
        self.assertTrue(all(item["status"] == "not_asserted" for item in records))
        self.assertTrue(all(item["place_id"] is None and item["claim_id"] is None for item in records))
        self.assertTrue(all("residence" in item["reason"] and "holding" in item["reason"] for item in records))

    def test_21_current_holdings_are_separate_and_cover_44_artworks(self) -> None:
        holdings = self.holdings_doc["locations"]
        artwork_ids = [artwork for item in holdings for artwork in item["artwork_ids"]]
        self.assertEqual(2, len(holdings))
        self.assertEqual(44, len(artwork_ids))
        self.assertEqual(44, len(set(artwork_ids)))
        self.assertTrue(all("not an artwork creation place" in item["does_not_prove"] for item in holdings))

    def test_22_map_timeline_and_filter_indexes_share_episode_ids(self) -> None:
        episode_ids = {item["id"] for item in self.episodes}
        self.assertEqual(episode_ids, {item["episode_id"] for item in self.timeline["entries"]})
        self.assertEqual(12, len(self.filters["facets"]["artists"]))
        self.assertEqual({"artist_activity", "artwork_creation_place", "current_holding_institution"}, {item["id"] for item in self.filters["facets"]["layers"]})

    def test_23_url_state_and_privacy_contract_are_allowlisted(self) -> None:
        self.assertEqual(["artist", "place", "episodeType", "fromYear", "toYear", "region", "precision", "layer", "view", "episode"], self.view_state["url_state_allowlist"])
        self.assertEqual("none", self.view_state["storage"])
        self.assertFalse(self.view_state["external_runtime_api"])
        self.assertFalse(self.view_state["user_geolocation"])
        self.assertFalse(self.view_state["analytics"])
        self.assertFalse(self.view_state["history_collection"])

    def test_24_style_is_local_only_stable_and_two_dimensional(self) -> None:
        self.assertEqual("maplibre-gl-js", self.style["renderer"])
        self.assertEqual("5.24.0", self.style["renderer_version"])
        self.assertTrue(all(source["data"].endswith((".geojson")) for source in self.style["style"]["sources"].values()))
        serialized = json.dumps(self.style["style"], sort_keys=True).lower()
        for forbidden in ("http://", "https://", "tiles", "glyphs", "sprite", "token", "mapbox"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(0, self.style["runtime_guards"]["pitch"])
        self.assertEqual(0, self.style["runtime_guards"]["bearing"])

    def test_25_getty_and_renderer_attribution_are_exact(self) -> None:
        sources = {item["id"]: item for item in self.attributions["sources"]}
        self.assertEqual("ODC-BY-1.0", sources["source:getty_tgn"]["license"])
        self.assertIn("changes", sources["source:getty_tgn"]["attribution"])
        self.assertEqual("ODC-BY-1.0", sources["source:getty_ulan"]["license"])
        self.assertEqual("BSD-3-Clause", self.attributions["renderer_notice"]["license"])
        self.assertTrue(self.attributions["renderer_notice"]["exact_pin"])
        self.assertFalse(self.attributions["renderer_notice"]["prerelease"])

    def test_26_all_new_typed_documents_validate_and_dispatch_canonically(self) -> None:
        for filename, schema_path in SCHEMA_BY_FILE.items():
            document = load(filename)
            with self.subTest(filename=filename):
                self.assertEqual([], validate_record(document, requested_schema=schema_path))
                self.assertEqual(schema_path, canonical_schema_path(document))

    def test_27_new_json_artifacts_are_canonical(self) -> None:
        for filename in SCHEMA_BY_FILE:
            path = RELEASE / filename
            with self.subTest(filename=filename):
                self.assertEqual(canonical_json_bytes(json.loads(path.read_text(encoding="utf-8"))), path.read_bytes())

    def test_28_research_dispositions_are_terminal_and_autonomous(self) -> None:
        allowed = {"verified_public", "verified_list_only", "retained_for_more_evidence", "rejected", "out_of_scope", "superseded"}
        records = self.dispositions["dispositions"]
        self.assertTrue(all(item["disposition"] in allowed for item in records))
        self.assertTrue(all(item["human_review_dependency"] is False for item in records))
        serialized = json.dumps(records).lower()
        self.assertNotIn("waiting for human", serialized)
        self.assertNotIn("pending user", serialized)

    def test_29_map_data_and_basemap_gzip_are_within_budget(self) -> None:
        basemap_gzip = sum(len(gzip.compress((RELEASE / f"basemap/{name}.geojson").read_bytes(), compresslevel=9, mtime=0)) for name in ("land", "coastline", "lakes"))
        data_gzip = sum(len(gzip.compress((RELEASE / name).read_bytes(), compresslevel=9, mtime=0)) for name in ("place-identities.json", "artist-place-episodes.json", "timeline-index.json", "filter-index.json", "map-points.geojson"))
        self.assertLessEqual(basemap_gzip, 250_000)
        self.assertLessEqual(data_gzip, 100_000)
        self.assertEqual(177_467, basemap_gzip)
        self.assertEqual(14_408, data_gzip)

    def test_30_museum_08_is_absent_from_release(self) -> None:
        self.assertNotIn("museum-08", json.dumps(self.manifest).lower())
        self.assertEqual(RELEASE_ID, self.manifest["id"])


if __name__ == "__main__":
    unittest.main()
