import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const DIST = join(ROOT, "dist");
const RELEASE = join(DIST, "releases", "art-v1-candidate-1.4.0");
const OUTPUT = join(ROOT, "docs", "qa", "museum-08", "bundle-budget.json");
const BROWSER_METRICS = join(ROOT, "docs", "qa", "museum-08", "browser-metrics.json");
const SEARCH_METRICS = join(ROOT, "docs", "qa", "museum-08", "search-performance.json");

const HOME_BASELINE_GZIP = 100_059;
const HOME_LIMIT_GZIP = Math.floor(HOME_BASELINE_GZIP * 1.02);
const SEARCH_ROUTE_LIMIT_GZIP = 220_000;
const SEARCH_INDEX_LIMIT_GZIP = 150_000;
const NON_MAP_ROUTE_LIMIT_GZIP = 300 * 1024;
const MAP_ROUTE_LIMIT_GZIP = 550 * 1024;
const LOW_BANDWIDTH_TRANSFER_LIMIT = 250_000;

const MAP_INITIAL_JSON = [
  "manifest.json",
  "place-identities.json",
  "artist-place-episodes.json",
  "holding-locations.json",
  "map-source-attributions.json",
  "map-style.json",
  "map-index.json",
  "filter-index.json",
  "artists.json",
  "artworks.json",
];
const MAP_BASEMAP = ["basemap/land.geojson", "basemap/coastline.geojson", "basemap/lakes.geojson"];
const NON_MAP_ROUTES = {
  constellation: ["src/features/art-constellation/ArtConstellationPage.tsx"],
  artist_index: [
    "src/features/art-gallery/ArtGalleryRoute.tsx",
    "src/features/art-gallery/artists/ArtistIndexPage.tsx",
  ],
  artist_gallery: [
    "src/features/art-gallery/ArtGalleryRoute.tsx",
    "src/features/art-gallery/artists/ArtistGalleryPage.tsx",
  ],
  artwork_detail: [
    "src/features/art-gallery/ArtGalleryRoute.tsx",
    "src/features/art-gallery/artwork/ArtworkDetailPage.tsx",
  ],
  compare: [
    "src/features/art-gallery/ArtGalleryRoute.tsx",
    "src/features/art-gallery/compare/ComparePage.tsx",
  ],
  tours: [
    "src/features/art-gallery/ArtGalleryRoute.tsx",
    "src/features/art-gallery/tours/ToursPage.tsx",
  ],
  paths: ["src/features/art-paths/ArtPathsPage.tsx"],
  search: ["src/features/art-search/ArtSearchPage.tsx"],
};

function readJson(path, failures) {
  if (!existsSync(path)) {
    failures.push(`missing ${relative(ROOT, path).replaceAll("\\", "/")}`);
    return null;
  }
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    failures.push(`invalid JSON ${relative(ROOT, path)}: ${error.message}`);
    return null;
  }
}

function metric(path, failures) {
  if (!existsSync(path)) {
    failures.push(`missing ${relative(ROOT, path).replaceAll("\\", "/")}`);
    return { path: relative(ROOT, path).replaceAll("\\", "/"), raw_bytes: 0, gzip_bytes: 0, sha256: "missing" };
  }
  const bytes = readFileSync(path);
  return {
    path: relative(ROOT, path).replaceAll("\\", "/"),
    raw_bytes: bytes.length,
    gzip_bytes: gzipSync(bytes, { level: 9 }).length,
    sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
  };
}

function findRecord(records, source, failures) {
  const matches = Object.entries(records)
    .filter(([key, record]) => key === source || record?.src === source)
    .map(([key]) => key);
  if (matches.length !== 1) failures.push(`${source} Vite record count must be 1, found ${matches.length}`);
  return matches[0] ?? null;
}

function collect(records, seeds, failures) {
  const result = new Set();
  const pending = seeds.filter(Boolean);
  while (pending.length) {
    const key = pending.pop();
    if (result.has(key)) continue;
    const record = records[key];
    if (!record) {
      failures.push(`unknown Vite record ${key}`);
      continue;
    }
    result.add(key);
    pending.push(...(record.imports ?? []));
  }
  return result;
}

function recordFiles(records, keys, failures) {
  const names = new Set();
  for (const key of keys) {
    const record = records[key];
    if (record?.file) names.add(record.file);
    for (const css of record?.css ?? []) names.add(css);
  }
  const files = [...names].sort().map((name) => metric(join(DIST, name), failures));
  return {
    files,
    raw_bytes: files.reduce((sum, file) => sum + file.raw_bytes, 0),
    gzip_bytes: files.reduce((sum, file) => sum + file.gzip_bytes, 0),
  };
}

function fileGroup(base, names, failures) {
  const files = names.map((name) => metric(join(base, name), failures));
  return {
    files,
    raw_bytes: files.reduce((sum, file) => sum + file.raw_bytes, 0),
    gzip_bytes: files.reduce((sum, file) => sum + file.gzip_bytes, 0),
  };
}

function main() {
  const failures = [];
  const records = readJson(join(DIST, ".vite", "manifest.json"), failures) ?? {};
  const entryKeys = Object.entries(records).filter(([, record]) => record.isEntry).map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`expected one Vite entry, got ${entryKeys.length}`);
  const homeKeys = collect(records, entryKeys, failures);
  const home = recordFiles(records, homeKeys, failures);

  const routeMeasurements = {};
  for (const [label, sources] of Object.entries(NON_MAP_ROUTES)) {
    const seeds = sources.map((source) => findRecord(records, source, failures));
    const closure = collect(records, seeds, failures);
    const routeOnly = new Set([...closure].filter((key) => !homeKeys.has(key)));
    routeMeasurements[label] = recordFiles(records, routeOnly, failures);
  }

  const searchManifest = readJson(join(RELEASE, "search", "manifest.json"), failures) ?? { shards: [] };
  const searchIndexNames = [
    "search/manifest.json",
    ...(Array.isArray(searchManifest.shards) ? searchManifest.shards.map((item) => item.path) : []),
  ];
  const searchIndex = fileGroup(RELEASE, searchIndexNames, failures);
  const candidateManifest = metric(join(RELEASE, "manifest.json"), failures);
  const searchRouteTotal =
    (routeMeasurements.search?.gzip_bytes ?? 0) +
    searchIndex.gzip_bytes +
    candidateManifest.gzip_bytes;

  const mapPageKey = findRecord(records, "src/features/art-map/ArtMapPage.tsx", failures);
  const mapCanvasKey = findRecord(records, "src/features/art-map/MapCanvas.tsx", failures);
  const rendererSeeds = mapCanvasKey ? (records[mapCanvasKey]?.dynamicImports ?? []) : [];
  const mapClosure = collect(records, [mapPageKey, mapCanvasKey, ...rendererSeeds], failures);
  const mapRouteAssets = recordFiles(
    records,
    new Set([...mapClosure].filter((key) => !homeKeys.has(key))),
    failures,
  );
  const mapInitialJson = fileGroup(RELEASE, MAP_INITIAL_JSON, failures);
  const mapBasemap = fileGroup(RELEASE, MAP_BASEMAP, failures);
  const mapRouteTotal = mapRouteAssets.gzip_bytes + mapInitialJson.gzip_bytes + mapBasemap.gzip_bytes;

  const comparableNonMapRoutes = Object.fromEntries(
    Object.entries(routeMeasurements).map(([label, measurement]) => [
      label,
      {
        ...measurement,
        total_gzip_bytes: label === "search" ? searchRouteTotal : measurement.gzip_bytes,
      },
    ]),
  );
  const [largestNonMapRoute, largestNonMap] = Object.entries(comparableNonMapRoutes)
    .sort((left, right) => right[1].total_gzip_bytes - left[1].total_gzip_bytes)[0] ?? ["none", { total_gzip_bytes: 0 }];

  const browser = readJson(BROWSER_METRICS, failures) ?? {};
  const searchPerformance = readJson(SEARCH_METRICS, failures) ?? {};
  if (home.gzip_bytes > HOME_LIMIT_GZIP) failures.push(`home gzip ${home.gzip_bytes} B > ${HOME_LIMIT_GZIP} B`);
  if (searchRouteTotal > SEARCH_ROUTE_LIMIT_GZIP) failures.push(`search route gzip ${searchRouteTotal} B > ${SEARCH_ROUTE_LIMIT_GZIP} B`);
  if (searchIndex.gzip_bytes > SEARCH_INDEX_LIMIT_GZIP) failures.push(`search index gzip ${searchIndex.gzip_bytes} B > ${SEARCH_INDEX_LIMIT_GZIP} B`);
  if (largestNonMap.total_gzip_bytes > NON_MAP_ROUTE_LIMIT_GZIP) {
    failures.push(`largest non-map route ${largestNonMapRoute} ${largestNonMap.total_gzip_bytes} B > ${NON_MAP_ROUTE_LIMIT_GZIP} B`);
  }
  if (mapRouteTotal > MAP_ROUTE_LIMIT_GZIP) failures.push(`map route gzip ${mapRouteTotal} B > ${MAP_ROUTE_LIMIT_GZIP} B`);
  if (browser.desktop_first_interactive_p95_ms > 1_800) failures.push(`desktop FTI p95 ${browser.desktop_first_interactive_p95_ms} ms > 1800 ms`);
  if (browser.mobile_first_interactive_p95_ms > 2_500) failures.push(`mobile FTI p95 ${browser.mobile_first_interactive_p95_ms} ms > 2500 ms`);
  if (browser.cls_p95 > 0.1) failures.push(`CLS p95 ${browser.cls_p95} > 0.1`);
  if (browser.interaction_p95_ms > 150) failures.push(`interaction p95 ${browser.interaction_p95_ms} ms > 150 ms`);
  if (browser.low_bandwidth_initial_transfer_p95_bytes > LOW_BANDWIDTH_TRANSFER_LIMIT) {
    failures.push(`low-bandwidth transfer p95 ${browser.low_bandwidth_initial_transfer_p95_bytes} B > ${LOW_BANDWIDTH_TRANSFER_LIMIT} B`);
  }
  if (browser.external_request_count !== 0) failures.push(`external requests ${browser.external_request_count} > 0`);
  if (browser.unexpected_media_preload_count !== 0) failures.push(`unexpected media preload ${browser.unexpected_media_preload_count} > 0`);
  if (browser.geolocation_call_count !== 0) failures.push(`geolocation calls ${browser.geolocation_call_count} > 0`);
  if (browser.status !== "pass") failures.push("browser metrics status is not pass");
  if (searchPerformance.status !== "pass") failures.push("search performance status is not pass");
  if (searchPerformance.current_release?.p95_ms > 80) failures.push("current search p95 exceeds 80 ms");
  if (searchPerformance.synthetic_1000?.p95_ms > 120) failures.push("1000-record search p95 exceeds 120 ms");

  const report = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-08",
    measurement: "node:zlib gzip level 9; each asset compressed independently; route assets exclude the separately reported initial shell",
    status: failures.length ? "fail" : "pass",
    failures,
    budgets: {
      home_baseline_gzip_bytes: HOME_BASELINE_GZIP,
      home_limit_gzip_bytes: HOME_LIMIT_GZIP,
      search_route_limit_gzip_bytes: SEARCH_ROUTE_LIMIT_GZIP,
      search_index_limit_gzip_bytes: SEARCH_INDEX_LIMIT_GZIP,
      largest_non_map_route_limit_gzip_bytes: NON_MAP_ROUTE_LIMIT_GZIP,
      map_route_limit_gzip_bytes: MAP_ROUTE_LIMIT_GZIP,
      low_bandwidth_initial_transfer_limit_bytes: LOW_BANDWIDTH_TRANSFER_LIMIT,
    },
    measurements: {
      home,
      home_growth_percent: Number((((home.gzip_bytes / HOME_BASELINE_GZIP) - 1) * 100).toFixed(3)),
      routes: comparableNonMapRoutes,
      largest_non_map_route: {
        route: largestNonMapRoute,
        gzip_bytes: largestNonMap.total_gzip_bytes,
      },
      search_index: searchIndex,
      candidate_manifest: candidateManifest,
      search_route_total_gzip_bytes: searchRouteTotal,
      map_route_assets: mapRouteAssets,
      map_initial_json: mapInitialJson,
      map_basemap: mapBasemap,
      map_route_total_gzip_bytes: mapRouteTotal,
      browser,
      search_performance: searchPerformance,
    },
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
