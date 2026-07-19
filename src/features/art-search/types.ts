export type SearchValueReason =
  | "preferred"
  | "approved_alias"
  | "transliteration"
  | "source_language"
  | "description";

export type SearchValue = {
  text: string;
  normalized: string;
  language: string;
  reason: SearchValueReason;
};

export type SearchRecord = {
  id: string;
  stable_id: string;
  entity_type: "artist" | "artwork" | "context" | "tour" | "place" | "relationship" | "path" | "page";
  route: string;
  labels: Record<string, string>;
  description: Record<string, string>;
  values: SearchValue[];
  visitor_task_order: number;
  withdrawal_status: "active" | "withdrawn";
};

export type SearchShardReference = {
  id: string;
  path: string;
  entity_types: string[];
  languages: string[];
  stable_hash_prefix: string | null;
  record_count: number;
  bytes: number;
  sha256: string;
  records_hash: string;
};

export type SearchManifest = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "search_index_manifest";
  phase_id: string;
  release_id: string;
  config_path: "search/config.json";
  normalization: "unicode_nfkc_lower_diacritic_fold_whitespace_v1";
  matching_modes: ["exact_preferred", "exact_alias", "prefix", "segmenter_token", "substring"];
  ranking_tuple: ["match_class", "visitor_task_entity_type", "stable_id"];
  segmenter_optional: true;
  fallback_complete: true;
  query_logging: false;
  media_paths_included: false;
  shard_contract: {
    strategies: string[];
    incremental_rebuild: true;
    unchanged_shards_hash_only: true;
    lazy_load: true;
  };
  shards: SearchShardReference[];
  counts: {
    records: number;
    shards: number;
    by_entity_type: Record<string, number>;
  };
  budgets: {
    search_route_gzip_bytes_max: number;
    search_index_gzip_bytes_max: number;
    current_query_p95_ms_max: number;
    synthetic_1000_query_p95_ms_max: number;
    external_requests_max: 0;
  };
};

export type SearchShard = {
  schema_version: "1.0.0";
  id: string;
  entity_type: "search_index_shard";
  release_id: string;
  strategy: "entity_type" | "language" | "stable_hash_prefix";
  shard_key: string;
  input_closure_hash: string;
  records_hash: string;
  record_count: number;
  records: SearchRecord[];
};

export type MatchReason = "exact_preferred" | "exact_alias" | "prefix" | "segmenter_token" | "substring";

export type SearchResult = {
  record: SearchRecord;
  matchReason: MatchReason;
  matchedValue: SearchValue;
  rankTuple: readonly [number, number, string];
};
