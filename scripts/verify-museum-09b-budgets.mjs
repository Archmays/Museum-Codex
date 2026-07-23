import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const DIST = join(ROOT, "dist");
const RELEASE = join(DIST, "releases", "art-expansion-batch-02-1.6.0");
const QA = join(ROOT, "docs", "qa", "museum-09c");
const OUTPUT = join(QA, "bundle-budget.json");
const FIXED_LIMITS = {
  home: Math.floor(100_059 * 1.02),
  constellation: 180_000,
  searchRoute: 220_000,
  searchIndex: 300_000,
  nonMap: 350_000,
};
const SCALE_BASELINES = {
  searchRecords: 979,
  firstQueryShardsGzip: 73_513,
  mapEpisodes: 110,
  mapRouteGzip: 549_956,
  mapMarginalGzipPerEpisode: 320,
  lowBandwidthArtists: 62,
  lowBandwidthTransfer: 226_171,
  lowBandwidthMarginalPerArtist: 750,
};
const ROUTES = {
  constellation: ["src/features/art-constellation/ArtConstellationPage.tsx"],
  artist_index: ["src/features/art-gallery/ArtGalleryRoute.tsx", "src/features/art-gallery/artists/ArtistIndexPage.tsx"],
  artist_gallery: ["src/features/art-gallery/ArtGalleryRoute.tsx", "src/features/art-gallery/artists/ArtistGalleryPage.tsx"],
  artwork_detail: ["src/features/art-gallery/ArtGalleryRoute.tsx", "src/features/art-gallery/artwork/ArtworkDetailPage.tsx"],
  compare: ["src/features/art-gallery/ArtGalleryRoute.tsx", "src/features/art-gallery/compare/ComparePage.tsx"],
  tours: ["src/features/art-gallery/ArtGalleryRoute.tsx", "src/features/art-gallery/tours/ToursPage.tsx"],
  paths: ["src/features/art-paths/ArtPathsPage.tsx"],
  search: ["src/features/art-search/ArtSearchPage.tsx"],
};

function readJson(path, failures) {
  if (!existsSync(path)) { failures.push(`missing ${relative(ROOT, path).replaceAll("\\", "/")}`); return {}; }
  try { return JSON.parse(readFileSync(path, "utf8")); } catch (error) { failures.push(`invalid JSON ${path}: ${error.message}`); return {}; }
}

function metric(path, failures) {
  if (!existsSync(path)) { failures.push(`missing ${relative(ROOT, path).replaceAll("\\", "/")}`); return { path, raw_bytes: 0, gzip_bytes: 0, sha256: "missing" }; }
  const bytes = readFileSync(path);
  return {
    path: relative(ROOT, path).replaceAll("\\", "/"),
    raw_bytes: bytes.length,
    gzip_bytes: gzipSync(bytes, { level: 9 }).length,
    sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
  };
}

function findRecord(records, source, failures) {
  const matches = Object.entries(records).filter(([key, record]) => key === source || record?.src === source).map(([key]) => key);
  if (matches.length !== 1) failures.push(`${source} Vite record count ${matches.length}`);
  return matches[0];
}

function collect(records, seeds, failures) {
  const result = new Set();
  const pending = seeds.filter(Boolean);
  while (pending.length) {
    const key = pending.pop();
    if (result.has(key)) continue;
    const record = records[key];
    if (!record) { failures.push(`unknown Vite record ${key}`); continue; }
    result.add(key);
    pending.push(...(record.imports ?? []));
  }
  return result;
}

function viteFiles(records, keys, failures) {
  const names = new Set();
  for (const key of keys) {
    const record = records[key];
    if (record?.file) names.add(record.file);
    for (const css of record?.css ?? []) names.add(css);
  }
  return [...names].sort().map((name) => metric(join(DIST, name), failures));
}

function sum(files, field = "gzip_bytes") { return files.reduce((total, item) => total + item[field], 0); }

function main() {
  const failures = [];
  const records = readJson(join(DIST, ".vite", "manifest.json"), failures);
  const entryKeys = Object.entries(records).filter(([, record]) => record.isEntry).map(([key]) => key);
  const homeKeys = collect(records, entryKeys, failures);
  const homeFiles = viteFiles(records, homeKeys, failures);
  const routeMeasurements = {};
  for (const [name, sources] of Object.entries(ROUTES)) {
    const closure = collect(records, sources.map((source) => findRecord(records, source, failures)), failures);
    const files = viteFiles(records, new Set([...closure].filter((key) => !homeKeys.has(key))), failures);
    routeMeasurements[name] = { files, gzip_bytes: sum(files) };
  }

  const searchManifest = readJson(join(RELEASE, "search", "manifest.json"), failures);
  const shardFiles = (searchManifest.shards ?? []).map((item) => metric(join(RELEASE, item.path), failures));
  const searchManifestFile = metric(join(RELEASE, "search", "manifest.json"), failures);
  const searchIndexGzip = searchManifestFile.gzip_bytes + sum(shardFiles);
  const releaseManifestFile = metric(join(RELEASE, "manifest.json"), failures);
  const searchRouteGzip = routeMeasurements.search.gzip_bytes + searchIndexGzip + releaseManifestFile.gzip_bytes;
  routeMeasurements.search.total_gzip_bytes = searchRouteGzip;
  for (const measurement of Object.values(routeMeasurements)) measurement.total_gzip_bytes ??= measurement.gzip_bytes;
  const [largestName, largest] = Object.entries(routeMeasurements).sort((a, b) => b[1].total_gzip_bytes - a[1].total_gzip_bytes)[0];

  const mapSeeds = [
    findRecord(records, "src/features/art-map/ArtMapPage.tsx", failures),
    findRecord(records, "src/features/art-map/MapCanvas.tsx", failures),
  ];
  const mapCanvas = records[mapSeeds[1]];
  const mapClosure = collect(records, [...mapSeeds, ...(mapCanvas?.dynamicImports ?? [])], failures);
  const mapAssetFiles = viteFiles(records, new Set([...mapClosure].filter((key) => !homeKeys.has(key))), failures);
  const mapJsonNames = ["manifest.json", "place-identities.json", "artist-place-episodes.json", "holding-locations.json", "map-source-attributions.json", "map-style.json", "map-index.json", "filter-index.json", "map-artworks.json"];
  const mapJsonFiles = mapJsonNames.map((name) => metric(join(RELEASE, name), failures));
  const predecessor = join(DIST, "releases", "art-v1-candidate-1.4.0");
  const basemapFiles = ["land.geojson", "coastline.geojson", "lakes.geojson"].map((name) => metric(join(predecessor, "basemap", name), failures));
  const mapRouteGzip = sum(mapAssetFiles) + sum(mapJsonFiles) + sum(basemapFiles);
  const episodeDocument = readJson(join(RELEASE, "artist-place-episodes.json"), failures);
  const artistDocument = readJson(join(RELEASE, "artists.json"), failures);
  const searchRecordCount = searchManifest.counts?.records ?? 0;
  const episodeCount = episodeDocument.episodes?.length ?? 0;
  const artistCount = artistDocument.artists?.length ?? 0;
  const limits = {
    ...FIXED_LIMITS,
    firstQueryShards: Math.ceil(
      SCALE_BASELINES.firstQueryShardsGzip * searchRecordCount / SCALE_BASELINES.searchRecords,
    ),
    map: SCALE_BASELINES.mapRouteGzip
      + Math.max(0, episodeCount - SCALE_BASELINES.mapEpisodes)
      * SCALE_BASELINES.mapMarginalGzipPerEpisode,
    lowBandwidth: SCALE_BASELINES.lowBandwidthTransfer
      + Math.max(0, artistCount - SCALE_BASELINES.lowBandwidthArtists)
      * SCALE_BASELINES.lowBandwidthMarginalPerArtist,
  };

  const browser = readJson(join(QA, "browser-metrics.json"), failures);
  const search = readJson(join(QA, "search-performance.json"), failures);
  const materialization = readJson(join(DIST, "museum-current-media-materialization.json"), failures);
  const checks = [
    [sum(homeFiles) <= limits.home, `home gzip ${sum(homeFiles)} > ${limits.home}`],
    [routeMeasurements.constellation.total_gzip_bytes <= limits.constellation, `relationship explorer gzip ${routeMeasurements.constellation.total_gzip_bytes} > ${limits.constellation}`],
    [searchRouteGzip <= limits.searchRoute, `search route gzip ${searchRouteGzip} > ${limits.searchRoute}`],
    [searchIndexGzip <= limits.searchIndex, `search index gzip ${searchIndexGzip} > ${limits.searchIndex}`],
    [sum(shardFiles) <= limits.firstQueryShards, `first query shards gzip ${sum(shardFiles)} > ${limits.firstQueryShards}`],
    [largest.total_gzip_bytes <= limits.nonMap, `${largestName} gzip ${largest.total_gzip_bytes} > ${limits.nonMap}`],
    [mapRouteGzip <= limits.map, `map route gzip ${mapRouteGzip} > ${limits.map}`],
    [browser.low_bandwidth_initial_transfer_p95_bytes <= limits.lowBandwidth, "low-bandwidth transfer budget failed"],
    [browser.desktop_first_interactive_p95_ms <= 1_800, "desktop FTI budget failed"],
    [browser.mobile_first_interactive_p95_ms <= 2_500, "mobile FTI budget failed"],
    [browser.interaction_p95_ms <= 100, "interaction budget failed"],
    [browser.cls_p95 <= 0.1, "CLS budget failed"],
    [browser.external_request_count === 0, "external runtime request detected"],
    [browser.unexpected_media_preload_count === 0, "unexpected media preload detected"],
    [search.current_release?.p95_ms <= 80, "current search budget failed"],
    [search.synthetic_5000?.p95_ms <= 120, "synthetic 5000 search budget failed"],
    [materialization.reencoded === 0 && materialization.file_count === 318, "materialization closure failed"],
  ];
  failures.push(...checks.filter(([ok]) => !ok).map(([, message]) => message));
  const report = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-09C",
    measurement: "node:zlib gzip level 9; independent asset compression and deterministic route closure",
    budgets: limits,
    scaling_contract: {
      first_query_shards: {
        formula: "ceil(73513 * current_search_records / 979)",
        baseline_records: SCALE_BASELINES.searchRecords,
        baseline_gzip_bytes: SCALE_BASELINES.firstQueryShardsGzip,
        current_records: searchRecordCount,
      },
      map_route: {
        formula: "549956 + max(0, current_episodes - 110) * 320",
        baseline_episodes: SCALE_BASELINES.mapEpisodes,
        baseline_gzip_bytes: SCALE_BASELINES.mapRouteGzip,
        current_episodes: episodeCount,
      },
      low_bandwidth: {
        formula: "226171 + max(0, current_artists - 62) * 750",
        baseline_artists: SCALE_BASELINES.lowBandwidthArtists,
        baseline_transfer_bytes: SCALE_BASELINES.lowBandwidthTransfer,
        current_artists: artistCount,
        marginal_limit_bytes_per_artist: SCALE_BASELINES.lowBandwidthMarginalPerArtist,
      },
    },
    measurements: {
      home: { files: homeFiles, gzip_bytes: sum(homeFiles), growth_percent: Number(((sum(homeFiles) / 100_059 - 1) * 100).toFixed(3)) },
      routes: routeMeasurements,
      largest_non_map_route: { route: largestName, gzip_bytes: largest.total_gzip_bytes },
      search_index_gzip_bytes: searchIndexGzip,
      first_query_shards_gzip_bytes: sum(shardFiles),
      search_route_gzip_bytes: searchRouteGzip,
      map_route_gzip_bytes: mapRouteGzip,
      map_route: { asset_files: mapAssetFiles, json_files: mapJsonFiles, basemap_files: basemapFiles, gzip_bytes: mapRouteGzip },
      browser,
      search,
      materialization: { file_count: materialization.file_count, bytes: materialization.bytes, reencoded: materialization.reencoded },
    },
    failures,
    status: failures.length ? "fail" : "pass",
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
