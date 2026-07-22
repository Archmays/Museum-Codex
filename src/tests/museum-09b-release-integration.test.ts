import { readFileSync } from "node:fs";
import path from "node:path";
import { loadArtConstellationRelease, loadStaticRelease } from "../data/release-loader";
import { loadArtInteractionIndex } from "../features/art-gallery/interaction-loader";
import { loadSearchIndex } from "../features/art-search/search-loader";

const releaseRoot = path.resolve("public/releases/art-expansion-batch-01-1.5.1");
const baseUrl = new URL("/Museum-Codex/releases/art-expansion-batch-01-1.5.1/", window.location.href).href;

const releaseFetcher = vi.fn<typeof fetch>((input: RequestInfo | URL) => {
  const url = new URL(typeof input === "string" || input instanceof URL ? input.toString() : input.url);
  const marker = "/releases/art-expansion-batch-01-1.5.1/";
  const relativePath = decodeURIComponent(url.pathname.slice(url.pathname.indexOf(marker) + marker.length));
  try {
    const bytes = readFileSync(path.join(releaseRoot, ...relativePath.split("/")));
    return Promise.resolve(new Response(bytes, { status: 200, headers: { "Content-Type": "application/json" } }));
  } catch {
    return Promise.resolve(new Response(null, { status: 404 }));
  }
});

describe("MUSEUM-09B-UX-01 formal browser release", () => {
  it("passes the canonical manifest loader", async () => {
    const result = await loadStaticRelease(`${baseUrl}manifest.json`, releaseFetcher);
    expect(result.status).toBe("loaded");
  });

  it("loads initial, catalog, and interaction closures from the physical bundle", async () => {
    const release = await loadArtConstellationRelease(baseUrl, releaseFetcher);
    expect(release.status).toBe("loaded");
    if (release.status !== "loaded") throw new Error(release.reason);
    expect(release.release.artists).toHaveLength(62);
    expect(release.release.explorerConfig.algorithm).toBe("focused_relation_lanes_v1");
    expect(release.release.explorerConfig.defaultGlobalGraphNodeCount).toBe(0);
    const catalog = await release.dataSource.loadArtworkCatalog();
    expect(catalog.status).toBe("loaded");
    if (catalog.status !== "loaded") throw new Error(catalog.reason);
    expect(catalog.data.artworks).toHaveLength(532);
    expect(catalog.data.media).toHaveLength(560);
    const interactions = await loadArtInteractionIndex(baseUrl, releaseFetcher);
    expect(interactions.artist_tours).toHaveLength(12);
  });

  it("loads every expanded local-search shard", async () => {
    const search = await loadSearchIndex(releaseFetcher);
    const records = await search.loadRecords();
    expect(records).toHaveLength(979);
    expect(records.some((record) => record.stable_id === "artist:m09a-aic_api-12128")).toBe(true);
  });
});
