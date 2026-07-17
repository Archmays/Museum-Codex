import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const DIST = resolve(ROOT, "dist");
const RELEASE = join(DIST, "releases", "art-time-place-1.3.0");
const OUTPUT = resolve(ROOT, "docs/qa/museum-07/bundle-budget.json");
const BROWSER_METRICS = resolve(ROOT, "docs/qa/museum-07/browser-metrics.json");
const HOME_BASELINE_GZIP = 99_390;
const HOME_LIMIT_GZIP = Math.floor(HOME_BASELINE_GZIP * 1.02);
const MAP_ROUTE_LIMIT = 550 * 1024;
const RENDERER_LIMIT = 400 * 1024;
const BASEMAP_LIMIT = 250 * 1024;
const PLACE_DATA_LIMIT = 100 * 1024;

const INITIAL_JSON = [
  "manifest.json", "place-identities.json", "artist-place-episodes.json", "holding-locations.json",
  "map-source-attributions.json", "map-style.json", "map-index.json", "filter-index.json", "artists.json", "artworks.json",
];
const PLACE_DATA = [
  "place-identities.json", "place-names.json", "artist-place-episodes.json", "artwork-place-claims.json",
  "holding-locations.json", "geospatial-claims.json", "map-index.json", "timeline-index.json", "filter-index.json", "map-points.geojson",
];
const BASEMAP = ["basemap/land.geojson", "basemap/coastline.geojson", "basemap/lakes.geojson"];
const RUNTIME_SOURCES = [
  "src/features/art-map/ArtMapPage.tsx", "src/features/art-map/MapCanvas.tsx",
  "src/features/art-map/map-loader.ts", "src/features/art-map/types.ts", "src/data/art-release-profile.ts",
];
const FORBIDDEN = [
  /navigator\.geolocation/i,
  /navigator\.sendBeacon/i,
  /\bgtag\s*\(/i,
  /\bmixpanel\b/i,
  /\bsegment\.(?:track|identify)\b/i,
  /(?:visit|view|map|location)[_-]history/i,
  /localStorage\.(?:setItem|getItem)\s*\(\s*["'][^"']*(?:visit|history|location|map)/i,
  /fetch\s*\(\s*["']https?:\/\//i,
  /(?:tiles|glyphs|sprite)\s*:\s*["']https?:\/\//i,
];

function readJson(path, failures) {
  if (!existsSync(path)) { failures.push(`missing ${path}`); return null; }
  try { return JSON.parse(readFileSync(path, "utf8")); }
  catch (error) { failures.push(`invalid JSON ${path}: ${error.message}`); return null; }
}

function metric(path, failures) {
  if (!existsSync(path)) {
    failures.push(`missing file ${path}`);
    return { path: path.replaceAll("\\", "/"), rawBytes: 0, gzipBytes: 0, sha256: "missing" };
  }
  const bytes = readFileSync(path);
  return {
    path: path.replace(`${ROOT}\\`, "").replaceAll("\\", "/"),
    rawBytes: bytes.length,
    gzipBytes: gzipSync(bytes, { level: 9 }).length,
    sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
  };
}

function findRecord(records, source, failures) {
  const matches = Object.entries(records).filter(([key, record]) => key === source || record?.src === source).map(([key]) => key);
  if (matches.length !== 1) failures.push(`${source} Vite record count must be 1, found ${matches.length}`);
  return matches[0] ?? null;
}

function collect(records, seeds, failures, includeDynamic = false) {
  const result = new Set();
  const pending = seeds.filter(Boolean);
  while (pending.length) {
    const key = pending.pop();
    if (result.has(key)) continue;
    const record = records[key];
    if (!record) { failures.push(`unknown Vite record ${key}`); continue; }
    result.add(key);
    pending.push(...(record.imports ?? []));
    if (includeDynamic) pending.push(...(record.dynamicImports ?? []));
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
    rawBytes: files.reduce((sum, file) => sum + file.rawBytes, 0),
    gzipBytes: files.reduce((sum, file) => sum + file.gzipBytes, 0),
  };
}

function fileGroup(names, failures) {
  const files = names.map((name) => metric(join(RELEASE, name), failures));
  return { files, rawBytes: files.reduce((sum, file) => sum + file.rawBytes, 0), gzipBytes: files.reduce((sum, file) => sum + file.gzipBytes, 0) };
}

function main() {
  const failures = [];
  const records = readJson(join(DIST, ".vite", "manifest.json"), failures) ?? {};
  const entryKeys = Object.entries(records).filter(([, record]) => record.isEntry).map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`expected one Vite entry, got ${entryKeys.length}`);
  const homeKeys = collect(records, entryKeys, failures);
  const home = recordFiles(records, homeKeys, failures);
  const pageKey = findRecord(records, "src/features/art-map/ArtMapPage.tsx", failures);
  const canvasKey = findRecord(records, "src/features/art-map/MapCanvas.tsx", failures);
  const maplibreKeys = canvasKey ? (records[canvasKey]?.dynamicImports ?? []) : [];
  const routeKeys = collect(records, [pageKey, canvasKey, ...maplibreKeys], failures);
  const routeOnlyKeys = new Set([...routeKeys].filter((key) => !homeKeys.has(key)));
  const routeAssets = recordFiles(records, routeOnlyKeys, failures);
  const rendererKeys = collect(records, [canvasKey, ...maplibreKeys], failures);
  const rendererAssets = recordFiles(records, new Set([...rendererKeys].filter((key) => !homeKeys.has(key))), failures);
  const initialJson = fileGroup(INITIAL_JSON, failures);
  const placeData = fileGroup(PLACE_DATA, failures);
  const basemap = fileGroup(BASEMAP, failures);
  const mapRouteTotal = routeAssets.gzipBytes + initialJson.gzipBytes + basemap.gzipBytes;
  const browser = readJson(BROWSER_METRICS, failures) ?? {};
  const packageJson = readJson(join(ROOT, "package.json"), failures) ?? {};
  const packageLock = readJson(join(ROOT, "package-lock.json"), failures) ?? {};

  if (packageJson.dependencies?.["maplibre-gl"] !== "5.24.0") failures.push("maplibre-gl must be exact-pinned to 5.24.0");
  if (packageLock.packages?.["node_modules/maplibre-gl"]?.version !== "5.24.0") failures.push("lockfile must resolve maplibre-gl 5.24.0");
  if (home.gzipBytes > HOME_LIMIT_GZIP) failures.push(`home gzip ${home.gzipBytes} B > ${HOME_LIMIT_GZIP} B`);
  if (mapRouteTotal > MAP_ROUTE_LIMIT) failures.push(`map route gzip ${mapRouteTotal} B > ${MAP_ROUTE_LIMIT} B`);
  if (rendererAssets.gzipBytes > RENDERER_LIMIT) failures.push(`renderer closure gzip ${rendererAssets.gzipBytes} B > ${RENDERER_LIMIT} B`);
  if (basemap.gzipBytes > BASEMAP_LIMIT) failures.push(`basemap gzip ${basemap.gzipBytes} B > ${BASEMAP_LIMIT} B`);
  if (placeData.gzipBytes > PLACE_DATA_LIMIT) failures.push(`place/timeline/filter gzip ${placeData.gzipBytes} B > ${PLACE_DATA_LIMIT} B`);
  if (browser.desktop_first_interactive_ms > 1800) failures.push(`desktop first interactive ${browser.desktop_first_interactive_ms} ms > 1800 ms`);
  if (browser.mobile_first_interactive_ms > 2500) failures.push(`mobile first interactive ${browser.mobile_first_interactive_ms} ms > 2500 ms`);
  if (browser.low_bandwidth_list_first_interactive_ms > 2000) failures.push(`low bandwidth list first interactive ${browser.low_bandwidth_list_first_interactive_ms} ms > 2000 ms`);
  if (browser.filter_p95_ms > 150) failures.push(`filter p95 ${browser.filter_p95_ms} ms > 150 ms`);
  if (browser.marker_selection_p95_ms > 100) failures.push(`marker selection p95 ${browser.marker_selection_p95_ms} ms > 100 ms`);
  if (browser.mobile_heap_increment_bytes > 40 * 1024 * 1024) failures.push(`mobile heap increment ${browser.mobile_heap_increment_bytes} B > 40 MB`);
  if (browser.cls > 0.1) failures.push(`CLS ${browser.cls} > 0.1`);
  if (browser.external_request_count !== 0) failures.push(`external request count ${browser.external_request_count} > 0`);
  if (browser.analytics_request_count !== 0) failures.push(`analytics request count ${browser.analytics_request_count} > 0`);
  if (browser.geolocation_call_count !== 0) failures.push(`geolocation call count ${browser.geolocation_call_count} > 0`);
  if (browser.status !== "pass") failures.push("browser metrics status is not pass");

  const runtimeMatches = [];
  for (const source of RUNTIME_SOURCES) {
    const sourceText = readFileSync(join(ROOT, source), "utf8");
    for (const pattern of FORBIDDEN) if (pattern.test(sourceText)) runtimeMatches.push({ path: source, pattern: pattern.source });
  }
  if (runtimeMatches.length) failures.push(`map runtime contains ${runtimeMatches.length} forbidden pattern matches`);

  const output = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-07",
    measurement: "node:zlib gzip level 9; each asset compressed independently",
    status: failures.length ? "fail" : "pass",
    failures,
    budgets: {
      home_baseline_gzip_bytes: HOME_BASELINE_GZIP, home_limit_gzip_bytes: HOME_LIMIT_GZIP,
      map_route_limit_gzip_bytes: MAP_ROUTE_LIMIT, renderer_limit_gzip_bytes: RENDERER_LIMIT,
      basemap_limit_gzip_bytes: BASEMAP_LIMIT, place_data_limit_gzip_bytes: PLACE_DATA_LIMIT,
    },
    measurements: { home, route_assets: routeAssets, renderer_assets: rendererAssets, initial_json: initialJson, place_data: placeData, basemap, map_route_total_gzip_bytes: mapRouteTotal, browser },
    runtime_policy: { files_scanned: RUNTIME_SOURCES, forbidden_matches: runtimeMatches, external_runtime_requests: false, user_geolocation: false, analytics: false, visit_history: false },
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(output, null, 2)}\n`);
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
