import type { ReleaseManifest } from "../../data/release-loader";

export type LocalizedText = { "zh-Hans": string; en: string; [key: string]: string };
export type CoordinatePrecision = "exact_site" | "locality" | "city_centroid" | "regional_centroid" | "bounded_area" | "unknown";
export type MapLayer = "artist_activity" | "artwork_creation_place" | "current_holding_institution";
export type MapView = "map" | "timeline" | "list";

export type PlaceIdentity = {
  id: string;
  tgn_id: string;
  tgn_uri: string;
  preferred_historical_label: string;
  current_common_label: string;
  labels: LocalizedText & { source: string };
  alternate_historical_names: string[];
  place_types: string[];
  broader_hierarchy: Array<{ authority_id: string; label: string }>;
  coordinates: [number, number] | null;
  coordinate_precision: CoordinatePrecision;
  geometry_type: "Point" | "Polygon" | "None";
  uncertainty_radius_km: number | null;
  valid_time: { start_year: number | null; end_year: number | null } | null;
  modern_jurisdiction: string | null;
  modern_jurisdiction_role: "secondary_context_only";
  region: string;
  source_ids: string[];
  release_status: "verified_public" | "verified_list_only";
  coordinate_issue: string | null;
};

export type EpisodeEvidence = { id: string; source_id: string; locator: string; record_sha256: string; stance: "supports" | "contradicts" };
export type ArtistEpisode = {
  id: string;
  artist_id: string;
  place_id: string;
  episode_type: string;
  start_year: number | null;
  end_year: number | null;
  date_precision: string;
  place_precision: CoordinatePrecision;
  role: string;
  claim_id: string;
  evidence: EpisodeEvidence[];
  source_ids: string[];
  confidence: string;
  uncertain: boolean;
  public_wording: LocalizedText;
  what_it_proves: string;
  does_not_prove: string;
  release_status: "verified_public" | "verified_list_only";
  release_id: string;
};

export type HoldingLocation = {
  id: string;
  institution_id: string;
  place_id: string;
  artwork_ids: string[];
  source_ids: string[];
  what_it_proves: string;
  does_not_prove: string;
};

export type MapSource = { id: string; name: string; tier: number; url: string; license: string; attribution: string };
export type ArtistSummary = { id: string; labels: LocalizedText };
export type ArtworkSummary = { id: string; artist_id: string; labels: LocalizedText };
export type MapFeature = {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: { episodeId?: string; holdingId?: string; artistId?: string; placeId: string; episodeType?: string; precision: CoordinatePrecision; layer: MapLayer; uncertaintyKm: number };
};
export type FeatureCollection = { type: "FeatureCollection"; features: MapFeature[] };

export type MapStyleDocument = {
  renderer: "maplibre-gl-js";
  renderer_version: string;
  style: Record<string, unknown> & { sources: Record<string, { type: "geojson"; data: string }>; layers: Array<Record<string, unknown>> };
  runtime_guards: Record<string, boolean | number>;
};

export type MapBundle = {
  manifest: ReleaseManifest;
  places: PlaceIdentity[];
  episodes: ArtistEpisode[];
  holdings: HoldingLocation[];
  artists: ArtistSummary[];
  artworks: ArtworkSummary[];
  sources: MapSource[];
  style: MapStyleDocument;
  mapIndex: { counts: Record<string, number>; year_range: { min: number; max: number }; limitations: string[] };
  filterIndex: { facets: Record<string, Array<Record<string, unknown>>> };
  fileByPath: Map<string, { path: string; bytes: number; sha256: string }>;
};

export type MapGeometry = { land: FeatureCollection; coastline: FeatureCollection; lakes: FeatureCollection; points: FeatureCollection };

export type MapFilters = {
  artist: string;
  place: string;
  episodeType: string;
  fromYear: number;
  toYear: number;
  region: string;
  precision: string;
  layer: MapLayer;
};
