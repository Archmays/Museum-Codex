import type { ArtConstellationRelease, LocalizedText } from "../art-constellation/types";
import type { ArtConstellationDataSource } from "../art-constellation/types";

export type PathMode = "historical" | "context" | "comparison";
export type PathLevel = "A" | "B" | "C";
export type PathStatus =
  | "ready"
  | "no_path_for_current_release_and_filters"
  | "search_budget_reached"
  | "invalid_start"
  | "invalid_end"
  | "same_endpoint"
  | "withdrawn_endpoint"
  | "withdrawn_relation"
  | "incompatible_release"
  | "tampered_path_index"
  | "runtime_calculation_failed";

export type PathArtist = {
  id: string;
  labels: LocalizedText;
  aliases: Array<{ language: string; text: string }>;
  periods: string[];
  regions: string[];
  life_span: { birth_year: number | null; death_year: number | null };
  public_display: boolean;
  review_status: string;
  lifecycle_status: string;
  withdrawn: boolean;
};

export type PathRelationship = {
  id: string;
  release_id: "release:art-pathways-1.2.0";
  source_artist_id: string;
  target_artist_id: string;
  type: string;
  level: PathLevel;
  directed: boolean;
  is_algorithmic: false;
  computational_similarity: null;
  public_display: boolean;
  review_status: string;
  lifecycle_status: string;
  withdrawn: boolean;
  deprecated: boolean;
  rights_visibility: "public";
  periods: string[];
  regions: string[];
  context_ids: string[];
  claim_ids: string[];
  evidence_ids: string[];
  source_ids: string[];
  supporting_artwork_ids: string[];
  evidence_confidence: number;
  why_connected: LocalizedText;
  does_not_prove: LocalizedText;
  rights_attribution: string[];
};

export type PathGraphInput = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "art_path_graph_input";
  release_id: "release:art-pathways-1.2.0";
  input_release_id: "release:art-gallery-interactions-1.1.0";
  input_release_hash: string;
  graph_hash: string;
  artists: PathArtist[];
  relationships: PathRelationship[];
  counts: { artists: number; relationships: number; levels: Record<PathLevel, number>; directed: number; algorithmic: number };
};

export type PathQuery = {
  schema_version: "1.0.0";
  fixed_release_id: "release:art-pathways-1.2.0";
  start_artist_id: string;
  end_artist_id: string;
  mode: PathMode;
  allowed_relationship_types: string[];
  allowed_levels: PathLevel[];
  period_filter: string[] | null;
  region_filter: string[] | null;
  direction_policy: "respect_semantic_direction";
  max_hops: number;
  k: number;
  candidate_expansion_limit: number;
};

export type PathStep = {
  sequence: number;
  source_artist_id: string;
  target_artist_id: string;
  relationship_id: string;
  direction: "directed_forward" | "undirected";
  relationship_type: string;
  level: PathLevel;
  context_ids: string[];
  claim_ids: string[];
  evidence_ids: string[];
  source_ids: string[];
  supporting_artwork_ids: string[];
  evidence_confidence: number;
  why_connected: LocalizedText;
  does_not_prove: LocalizedText;
  rights_attribution: string[];
  withdrawal_status: "active";
};

export type ArtistPath = {
  id: string;
  rank: number;
  hop_count: number;
  artist_ids: string[];
  relationship_ids: string[];
  steps: PathStep[];
  evidence_level: PathLevel;
  evidence_confidence: number;
  time_coherence: "coherent" | "mixed" | "discontinuous";
  relation_type_repeat_count: number;
  ranking_tuple: {
    hop_count: number;
    evidence_level_rank: number;
    evidence_confidence_desc: number;
    time_coherence_penalty: number;
    relation_type_repeat_count: number;
    stable_relation_id_sequence: string[];
    stable_artist_id_sequence: string[];
  };
};

export type PathResult = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "art_path_result";
  release_id: "release:art-pathways-1.2.0";
  algorithm_version: "museum-paths-bibfs-yen-1.0.0";
  input_graph_hash: string;
  status: PathStatus;
  query: PathQuery;
  paths: ArtistPath[];
  expansions_used: number;
  disclaimer: LocalizedText;
};

export type PathPair = {
  pair_id: string;
  start_artist_id: string;
  end_artist_id: string;
  modes: Record<PathMode, PathResult>;
};

export type PathIndex = {
  schema_version: "1.0.0";
  id: "path-index:museum-06-default-v1";
  entity_type: "art_path_index";
  release_id: "release:art-pathways-1.2.0";
  algorithm_version: "museum-paths-bibfs-yen-1.0.0";
  input_graph_hash: string;
  default_pair_count: 66;
  precomputed_path_count: number;
  pairs: PathPair[];
};

export type PathAlgorithmContract = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "art_path_algorithm_contract";
  release_id: "release:art-pathways-1.2.0";
  algorithm_version: "museum-paths-bibfs-yen-1.0.0";
  input_release_id: "release:art-gallery-interactions-1.1.0";
  input_release_hash: string;
  filter_order: string[];
  ranking_tuple: string[];
  bounds: { k_max: number; max_hops: number; candidate_expansion_limit: number };
  disclaimers: Record<PathMode, LocalizedText>;
};

export type PathExplanationCollection = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "art_path_explanation_collection";
  release_id: "release:art-pathways-1.2.0";
  input_graph_hash: string;
  explanations: Array<PathRelationship>;
};

export type PathRouteConfig = {
  route: "#/art/paths";
  url_state_allowlist: string[];
  default_mode: "comparison";
  storage: "none";
  external_runtime_api: false;
  analytics: false;
};

export type PathwayBundle = {
  release: ArtConstellationRelease;
  dataSource: ArtConstellationDataSource;
  graph: PathGraphInput;
  index: PathIndex;
  algorithm: PathAlgorithmContract;
  explanations: PathExplanationCollection;
  routeConfig: PathRouteConfig;
};
