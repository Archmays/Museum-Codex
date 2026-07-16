import type { LocalizedText } from "../art-constellation/types";

export type ObservationContextLink = { id: string; label: LocalizedText };

export type ObservationCard = {
  id: string;
  artwork_id: string;
  title: LocalizedText;
  prompts: LocalizedText[];
  contexts: {
    materials: ObservationContextLink[];
    techniques: ObservationContextLink[];
    subjects: ObservationContextLink[];
  };
  date: LocalizedText | null;
  institution: LocalizedText | null;
  directly_observable: LocalizedText[];
  interpretation_requires_sources: LocalizedText[];
  current_evidence_cannot_prove: LocalizedText[];
  evidence_ids: string[];
  source_ids: string[];
  source_links: { source_id: string; label: LocalizedText; url: string }[];
  rights_status: string;
  image_availability: "approved_image" | "metadata_only";
  accessibility_version: { mode: "image_plus_text" | "evidence_only"; summary: LocalizedText };
  review: { status: "automated_pass"; reviewer_kind: string; reviewed_at: string; human_review_dependency: false };
  release_id: string;
  release_version: "1.1.0";
};

export type InteractionSourceAsset = {
  media_id: string;
  path: string;
  sha256: string;
  width: number;
  height: number;
};

export type DetailRegion = {
  id: string;
  hero_id: string;
  artwork_id: string;
  label: LocalizedText;
  source_asset: InteractionSourceAsset;
  rect: { x: number; y: number; width: number; height: number };
  normalized_rect: { x: number; y: number; width: number; height: number };
  metrics: { edge_density: number; local_contrast: number; entropy: number; saliency: number; score: number };
  algorithm: { name: "structural-detail-navigation"; version: string; input_release_hash: string };
  semantic_label: null;
};

export type HeroSelection = {
  id: string;
  artist_id: string;
  artwork_id: string;
  status: "visual_detail_path" | "textual_observation_path";
  selection_input_hash: string;
  rationale: LocalizedText;
  source_asset: InteractionSourceAsset | null;
  detail_region_ids: string[];
};

export type ArtistTour = {
  id: string;
  kind: "artist";
  title: LocalizedText;
  artist_id: string;
  entry_question: LocalizedText;
  artwork_steps: { sequence: number; artwork_id: string; reason: LocalizedText }[];
  focus: { type: "material" | "technique" | "subject"; context_id: string; label: LocalizedText };
  time_place_context: LocalizedText;
  evidence_check: LocalizedText;
  do_not_overinterpret: LocalizedText;
  reflection_question: LocalizedText;
  equivalent_paths: { image: LocalizedText; no_image: LocalizedText };
  source_ids: string[];
  disclaimer: LocalizedText;
  fixed_curatorial: true;
  algorithmic: false;
  share_path: string;
};

export type ThematicTour = {
  id: string;
  kind: "thematic";
  title: LocalizedText;
  summary: LocalizedText;
  artist_ids: string[];
  artwork_ids: string[];
  context_ids: string[];
  period_labels: LocalizedText[];
  region_labels: LocalizedText[];
  source_ids: string[];
  metadata_only_artwork_ids: string[];
  noncausal_statement: LocalizedText;
  fixed_curatorial: true;
  pathfinding: false;
  automatic_recommendation: false;
  share_path: string;
};

export type ObservationLens = {
  id: "lens:material" | "lens:technique" | "lens:subject";
  type: "material" | "technique" | "subject";
  title: LocalizedText;
  boundary: LocalizedText;
  entries: {
    context_id: string;
    label: LocalizedText;
    definition: LocalizedText;
    artwork_ids: string[];
    evidence_ids: string[];
    source_ids: string[];
    source_links: { source_id: string; label: LocalizedText; url: string }[];
  }[];
};

export type ArtInteractionIndex = {
  schema_version: "1.0.0";
  id: "interaction-index:museum-05b-v1";
  release_id: "release:art-gallery-interactions-1.1.0";
  release_version: "1.1.0";
  input_release_id: "release:art-constellation-1.0.0";
  release_composition: {
    mode: "immutable_overlay";
    base_release_id: "release:art-constellation-1.0.0";
    base_release_hash: string;
    base_artifact_identity: "base_release_scoped";
    inherited_manifest_file_count: 263;
    overlay_files: ["interaction-index.json", "media-retry.json"];
  };
  counts: {
    artists: 12;
    artworks: 44;
    observation_cards: 44;
    hero_selections: 12;
    visual_heroes: number;
    textual_observation_paths: number;
    detail_regions: number;
    artist_tours: 12;
    thematic_tours: 6;
    lenses: 3;
  };
  observation_cards: ObservationCard[];
  hero_selections: HeroSelection[];
  detail_regions: DetailRegion[];
  artist_tours: ArtistTour[];
  thematic_tours: ThematicTour[];
  lenses: ObservationLens[];
  compare_prompts: { id: string; lens: ObservationLens["type"]; prompt: LocalizedText; boundary: LocalizedText }[];
  print_share_configuration: {
    allowed_routes: string[];
    allowed_query_keys: string[];
    tracking_parameters: false;
    upload_data: false;
    print_image_policy: "approved_small_image_or_metadata_only";
  };
  performance_contract: {
    low_bandwidth_default: "no_images";
    print_loads_large_images: false;
    initial_loads_all_tour_images: false;
  };
  media_retry_summary: {
    status: "pass" | "partial";
    approved_media_count_before: 31;
    approved_media_count_after: 31;
    no_image_count_after: 13;
    human_review_dependency: false;
  };
};
