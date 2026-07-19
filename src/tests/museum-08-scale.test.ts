import { describe, expect, it } from "vitest";
import {
  loadSelectedEntityShards,
  selectEntityShards,
  type EntityShardManifest,
} from "../data/sharded-entity-loader";
import {
  CONSTELLATION_GRAPH_EDGE_LIMIT,
  CONSTELLATION_GRAPH_NODE_LIMIT,
  CONSTELLATION_LIST_PAGE_SIZE,
  planConstellationGraph,
  stablePage,
} from "../features/art-constellation/scale-strategy";

const artists = Array.from({ length: 500 }, (_, index) => ({
  id: `synthetic:artist:${String(index).padStart(4, "0")}`,
}));
const relationships = Array.from({ length: 10_000 }, (_, index) => ({
  id: `synthetic:relationship:${String(index).padStart(5, "0")}`,
  sourceArtistId: artists[index % artists.length].id,
  targetArtistId: artists[(index * 17 + 1) % artists.length].id,
}));

describe("MUSEUM-08 constellation scale strategy", () => {
  it("bounds graph work while preserving a deterministic focus neighborhood", () => {
    const focus = artists[321].id;
    const first = planConstellationGraph(artists, relationships, focus);
    const second = planConstellationGraph(artists, relationships, focus);
    expect(first.limited).toBe(true);
    expect(first.strategy).toBe("focus_neighborhood_then_stable_id");
    expect(first.artists).toHaveLength(CONSTELLATION_GRAPH_NODE_LIMIT);
    expect(first.relationships.length).toBeLessThanOrEqual(CONSTELLATION_GRAPH_EDGE_LIMIT);
    expect(first.artists[0].id).toBe(focus);
    expect(second).toEqual(first);
  });

  it("exposes every synthetic artist through stable 50-record keyboard pages", () => {
    const seen: string[] = [];
    const pageCount = Math.ceil(artists.length / CONSTELLATION_LIST_PAGE_SIZE);
    for (let page = 1; page <= pageCount; page += 1) {
      const window = stablePage(artists, page, CONSTELLATION_LIST_PAGE_SIZE);
      expect(window.page).toBe(page);
      seen.push(...window.items.map((artist) => artist.id));
    }
    expect(seen).toEqual(artists.map((artist) => artist.id));
    expect(new Set(seen).size).toBe(500);
  });
});

describe("MUSEUM-08 sharded stable-ID loader", () => {
  it("selects only the requested entity, language, and stable hash prefix", () => {
    const references = [
      { id: "a", path: "shards/a.json", bytes: 1, sha256: "0".repeat(64), entity_types: ["artist"], languages: ["en"], stable_hash_prefix: "ab" },
      { id: "b", path: "shards/b.json", bytes: 1, sha256: "1".repeat(64), entity_types: ["artwork"], languages: ["en"], stable_hash_prefix: "ab" },
      { id: "c", path: "shards/c.json", bytes: 1, sha256: "2".repeat(64), entity_types: ["artist"], languages: ["zh-Hans"], stable_hash_prefix: "cd" },
    ];
    expect(selectEntityShards(references, { entityType: "artist", language: "en", stableHashPrefix: "a" }).map((item) => item.id)).toEqual(["a"]);
  });

  it("hash-verifies a selected shard and leaves unrelated shards unloaded", async () => {
    const body = JSON.stringify({ records: [{ id: "synthetic:artist:0001" }] });
    const bytes = new TextEncoder().encode(body);
    const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    const manifest: EntityShardManifest = {
      base_url: "/Museum-Codex/releases/synthetic/",
      shards: [
        { id: "artist-en-a", path: "shards/artist-en-a.json", bytes: bytes.byteLength, sha256: hash, entity_types: ["artist"], languages: ["en"], stable_hash_prefix: "a" },
        { id: "artwork-en-b", path: "shards/artwork-en-b.json", bytes: 10, sha256: "f".repeat(64), entity_types: ["artwork"], languages: ["en"], stable_hash_prefix: "b" },
      ],
    };
    const requests: string[] = [];
    const fetcher = ((input: string | URL | Request) => {
      requests.push(input instanceof Request ? input.url : input instanceof URL ? input.href : input);
      return Promise.resolve(new Response(bytes));
    }) as typeof fetch;
    const result = await loadSelectedEntityShards<{ id: string }>(
      manifest,
      { entityType: "artist", language: "en", stableHashPrefix: "a" },
      fetcher,
    );
    expect(result.loadedShardIds).toEqual(["artist-en-a"]);
    expect(result.records).toEqual([{ id: "synthetic:artist:0001" }]);
    expect(requests).toHaveLength(1);
  });
});
