import { currentArtReleaseBaseUrl } from "../../data/art-release-profile";
import { loadStaticRelease, type ReleaseManifest } from "../../data/release-loader";
import type { SearchManifest, SearchRecord, SearchShard } from "./types";

const SEARCH_SCHEMA = "schemas/art/candidate/search-index.schema.json";
const SHA256 = /^(?:sha256:)?[a-f0-9]{64}$/;
const SAFE_PATH = /^search\/(?:manifest|shards\/[a-z0-9._-]+)\.json$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

async function digestHex(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) throw new Error("search_web_crypto_unavailable");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function fetchVerifiedJson(
  base: URL,
  path: string,
  file: { bytes: number; sha256: string },
  fetcher: typeof fetch,
) {
  if (!SAFE_PATH.test(path) || !SHA256.test(file.sha256)) throw new Error("search_path_or_hash_invalid");
  const url = new URL(path, base);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) throw new Error("search_cross_origin");
  const response = await fetcher(url.href, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`search_http_${response.status}`);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== file.bytes || await digestHex(bytes) !== file.sha256.replace(/^sha256:/, "")) {
    throw new Error("search_artifact_hash_mismatch");
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes)) as unknown;
  } catch {
    throw new Error("search_artifact_json_invalid");
  }
}

function assertManifest(value: unknown, release: ReleaseManifest): asserts value is SearchManifest {
  if (!isRecord(value) || !isRecord(value.counts) || !isRecord(value.shard_contract) || !isRecord(value.budgets)) {
    throw new Error("search_manifest_shape");
  }
  const shards = value.shards;
  if (
    value.schema_version !== "1.0.0" ||
    value.entity_type !== "search_index_manifest" ||
    value.release_id !== release.id ||
    value.normalization !== "unicode_nfkc_lower_diacritic_fold_whitespace_v1" ||
    value.segmenter_optional !== true ||
    value.fallback_complete !== true ||
    value.query_logging !== false ||
    value.media_paths_included !== false ||
    value.shard_contract.incremental_rebuild !== true ||
    value.shard_contract.unchanged_shards_hash_only !== true ||
    value.shard_contract.lazy_load !== true ||
    value.budgets.external_requests_max !== 0 ||
    !Array.isArray(shards) ||
    shards.length !== value.counts.shards ||
    new Set(shards.map((item) => isRecord(item) ? item.path : null)).size !== shards.length ||
    shards.some((item) =>
      !isRecord(item) ||
      typeof item.path !== "string" ||
      !SAFE_PATH.test(item.path) ||
      typeof item.bytes !== "number" ||
      !Number.isInteger(item.bytes) ||
      item.bytes <= 0 ||
      typeof item.sha256 !== "string" ||
      !SHA256.test(item.sha256) ||
      item.stable_hash_prefix !== null && typeof item.stable_hash_prefix !== "string"
    )
  ) throw new Error("search_manifest_contract");
}

function assertShard(value: unknown, manifest: SearchManifest, shardId: string): asserts value is SearchShard {
  if (!isRecord(value) || !Array.isArray(value.records)) throw new Error("search_shard_shape");
  const records = value.records;
  if (
    value.schema_version !== "1.0.0" ||
    value.entity_type !== "search_index_shard" ||
    value.release_id !== manifest.release_id ||
    value.id !== shardId ||
    value.record_count !== records.length ||
    records.some((record) =>
      !isRecord(record) ||
      typeof record.id !== "string" ||
      typeof record.stable_id !== "string" ||
      typeof record.entity_type !== "string" ||
      typeof record.route !== "string" ||
      !isRecord(record.labels) ||
      !(isRecord(record.description) || (typeof record.description === "string" && record.description.trim())) ||
      !Array.isArray(record.values) ||
      record.values.length === 0 ||
      typeof record.visitor_task_order !== "number" ||
      !["active", "withdrawn"].includes(String(record.withdrawal_status)) ||
      record.values.some((searchValue) =>
        !isRecord(searchValue) ||
        typeof searchValue.text !== "string" ||
        typeof searchValue.normalized !== "string" ||
        typeof searchValue.language !== "string" ||
        !["preferred", "approved_alias", "transliteration", "source_language", "description"].includes(String(searchValue.reason))
      ) ||
      JSON.stringify(record).includes("/assets/")
    )
  ) throw new Error("search_shard_contract");
}

function normalizeSearchRecord(record: SearchRecord): SearchRecord {
  const rawDescription = (record as unknown as Record<string, unknown>).description;
  return typeof rawDescription === "string"
    ? { ...record, description: { "zh-Hans": rawDescription, en: rawDescription } }
    : record;
}

export type SearchIndexHandle = {
  manifest: SearchManifest;
  release: ReleaseManifest;
  loadRecords: () => Promise<SearchRecord[]>;
};

let searchHandlePromise: Promise<SearchIndexHandle> | null = null;

export function loadSearchIndex(fetcher: typeof fetch = fetch): Promise<SearchIndexHandle> {
  if (fetcher !== fetch) return loadSearchIndexUncached(fetcher);
  searchHandlePromise ??= loadSearchIndexUncached(fetcher).catch((error) => {
    searchHandlePromise = null;
    throw error;
  });
  return searchHandlePromise;
}

async function loadSearchIndexUncached(fetcher: typeof fetch): Promise<SearchIndexHandle> {
  const documentUrl = typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href;
  const base = new URL(currentArtReleaseBaseUrl(), documentUrl);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new Error("search_cross_origin");
  const releaseResult = await loadStaticRelease(new URL("manifest.json", base).href, fetcher);
  if (releaseResult.status !== "loaded") throw new Error(`search_release_${releaseResult.status}`);
  const release = releaseResult.manifest;
  const fileByPath = new Map(release.manifest_files.map((file) => [file.path, file]));
  const manifestFile = fileByPath.get("search/manifest.json");
  if (
    !manifestFile ||
    manifestFile.record_type !== "other" ||
    manifestFile.schema_path !== SEARCH_SCHEMA ||
    !(manifestFile.record_ids.length === 0 ||
      (manifestFile.record_ids.length === 1 && [
        "search-manifest:art-expansion-1.5.0",
        "search-manifest:art-expansion-1.5.1",
        "search-manifest:art-expansion-1.6.0",
      ].includes(manifestFile.record_ids[0])))
  ) throw new Error("search_manifest_file_missing");
  const manifestValue = await fetchVerifiedJson(base, manifestFile.path, manifestFile, fetcher);
  assertManifest(manifestValue, release);
  const manifest = manifestValue;
  let recordsPromise: Promise<SearchRecord[]> | null = null;
  const loadRecords = () => {
    recordsPromise ??= Promise.all(manifest.shards.map(async (reference) => {
      const file = fileByPath.get(reference.path);
      if (
        !file ||
        file.schema_path !== SEARCH_SCHEMA ||
        file.record_type !== "other" ||
        file.bytes !== reference.bytes ||
        file.sha256.replace(/^sha256:/, "") !== reference.sha256.replace(/^sha256:/, "")
      ) throw new Error("search_shard_manifest_closure");
      const value = await fetchVerifiedJson(base, reference.path, file, fetcher);
      assertShard(value, manifest, reference.id);
      if (value.records.length !== reference.record_count || value.records_hash !== reference.records_hash) {
        throw new Error("search_shard_record_closure");
      }
      return value.records.map(normalizeSearchRecord);
    })).then((groups) => {
      const records = groups.flat();
      if (
        records.length !== manifest.counts.records ||
        new Set(records.map((record) => record.id)).size !== records.length
      ) throw new Error("search_index_record_closure");
      return records;
    }).catch((error) => {
      recordsPromise = null;
      throw error;
    });
    return recordsPromise;
  };
  return { manifest, release, loadRecords };
}
