export type EntityShardReference = {
  id: string;
  path: string;
  bytes: number;
  sha256: string;
  entity_types: string[];
  languages: string[];
  stable_hash_prefix: string | null;
};

export type EntityShardManifest = {
  base_url: string;
  shards: EntityShardReference[];
};

export type EntityShardSelector = {
  entityType?: string;
  language?: string;
  stableHashPrefix?: string;
};

const SAFE_PATH = /^[a-z0-9][a-z0-9._/-]*\.json$/;
const SHA256 = /^(?:sha256:)?[a-f0-9]{64}$/;

async function digest(bytes: ArrayBuffer) {
  const value = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function selectEntityShards(
  references: EntityShardReference[],
  selector: EntityShardSelector,
) {
  return references.filter((reference) =>
    (!selector.entityType || reference.entity_types.includes(selector.entityType)) &&
    (!selector.language || reference.languages.includes(selector.language)) &&
    (!selector.stableHashPrefix || reference.stable_hash_prefix?.startsWith(selector.stableHashPrefix))
  ).sort((left, right) => left.path.localeCompare(right.path));
}

export async function loadSelectedEntityShards<T>(
  manifest: EntityShardManifest,
  selector: EntityShardSelector,
  fetcher: typeof fetch = fetch,
): Promise<{ records: T[]; loadedShardIds: string[] }> {
  const documentUrl = typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href;
  const base = new URL(manifest.base_url, documentUrl);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new Error("entity_shard_cross_origin");
  const references = selectEntityShards(manifest.shards, selector);
  const groups = await Promise.all(references.map(async (reference) => {
    if (!SAFE_PATH.test(reference.path) || !SHA256.test(reference.sha256) || reference.bytes <= 0) {
      throw new Error("entity_shard_reference_invalid");
    }
    const url = new URL(reference.path, base);
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) throw new Error("entity_shard_path_escape");
    const response = await fetcher(url.href, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`entity_shard_http_${response.status}`);
    const bytes = await response.arrayBuffer();
    if (
      bytes.byteLength !== reference.bytes ||
      await digest(bytes) !== reference.sha256.replace(/^sha256:/, "")
    ) throw new Error("entity_shard_hash_mismatch");
    const value = JSON.parse(new TextDecoder().decode(bytes)) as { records?: T[] };
    if (!Array.isArray(value.records)) throw new Error("entity_shard_shape");
    return value.records;
  }));
  return {
    records: groups.flat(),
    loadedShardIds: references.map((reference) => reference.id),
  };
}
