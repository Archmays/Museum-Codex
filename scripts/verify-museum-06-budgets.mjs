import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const DIST = resolve(ROOT, "dist");
const RELEASE = join(DIST, "releases", "art-pathways-1.2.0");
const OUTPUT = resolve(ROOT, "docs/qa/museum-06/bundle-budget.json");
const BROWSER_METRICS = resolve(ROOT, "docs/qa/museum-06/browser-metrics.json");
const PATH_BENCHMARK = resolve(ROOT, "docs/qa/museum-06/path-benchmark.json");
const HOME_BASELINE_GZIP = 98_891;
const HOME_LIMIT_GZIP = Math.floor(HOME_BASELINE_GZIP * 1.02);
const PATH_ROUTE_LIMIT = 250 * 1024;
const PATH_INDEX_LIMIT = 64 * 1024;
const PATH_ALGORITHM_LIMIT = 80 * 1024;

const INITIAL_JSON = [
  "manifest.json", "graph-summary.json", "artists.json", "search-index.json", "layout.json", "facets.json",
  "path-algorithm-contract.json", "path-graph-input.json", "path-index.json", "path-explanations.json", "path-route-config.json",
];

const RUNTIME_SOURCES = [
  "src/features/art-paths/ArtPathsPage.tsx",
  "src/features/art-paths/path-algorithm.ts",
  "src/features/art-paths/path-loader.ts",
  "src/features/art-paths/PathGraphView.tsx",
  "src/features/art-paths/types.ts",
];

const FORBIDDEN = [
  /navigator\.sendBeacon/i,
  /\bgtag\s*\(/i,
  /\bmixpanel\b/i,
  /\bsegment\.(?:track|identify)\b/i,
  /(?:path|query|visit|view|profile)[_-]history/i,
  /localStorage\.(?:setItem|getItem)\s*\(\s*["'][^"']*(?:path|query|visit|history|profile)/i,
  /fetch\s*\(\s*["']https?:\/\//i,
];

function readJson(path, failures) {
  if (!existsSync(path)) { failures.push(`missing ${path}`); return null; }
  try { return JSON.parse(readFileSync(path, "utf8")); }
  catch (error) { failures.push(`invalid JSON ${path}: ${error.message}`); return null; }
}

function metric(path, failures) {
  if (!existsSync(path)) { failures.push(`missing file ${path}`); return { path, rawBytes: 0, gzipBytes: 0 }; }
  const bytes = readFileSync(path);
  return {
    path: path.replace(`${ROOT}\\`, "").replaceAll("\\", "/"),
    rawBytes: bytes.length,
    gzipBytes: gzipSync(bytes, { level: 9 }).length,
    sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
  };
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
    rawBytes: files.reduce((total, file) => total + file.rawBytes, 0),
    gzipBytes: files.reduce((total, file) => total + file.gzipBytes, 0),
  };
}

function main() {
  const failures = [];
  const records = readJson(join(DIST, ".vite", "manifest.json"), failures) ?? {};
  const entryKeys = Object.entries(records).filter(([, record]) => record.isEntry).map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`expected one Vite entry, got ${entryKeys.length}`);
  const homeKeys = collect(records, entryKeys, failures);
  const home = recordFiles(records, homeKeys, failures);
  const pathKey = Object.entries(records).find(([key, record]) =>
    key === "src/features/art-paths/ArtPathsPage.tsx" || record.src === "src/features/art-paths/ArtPathsPage.tsx"
  )?.[0];
  if (!pathKey) failures.push("ArtPathsPage dynamic record missing");
  const pathKeys = collect(records, [pathKey], failures);
  const pathOnlyKeys = new Set([...pathKeys].filter((key) => !homeKeys.has(key)));
  const pathAssets = recordFiles(records, pathOnlyKeys, failures);
  const algorithmFiles = pathAssets.files.filter((file) => /\.(?:m?js)$/.test(file.path));
  const algorithmGzip = algorithmFiles.reduce((total, file) => total + file.gzipBytes, 0);
  const jsonFiles = INITIAL_JSON.map((name) => metric(join(RELEASE, name), failures));
  const jsonGzip = jsonFiles.reduce((total, file) => total + file.gzipBytes, 0);
  const pathRouteTotal = pathAssets.gzipBytes + jsonGzip;
  const pathIndex = jsonFiles.find((file) => file.path.endsWith("/path-index.json"));
  const browser = readJson(BROWSER_METRICS, failures) ?? {};
  const benchmark = readJson(PATH_BENCHMARK, failures) ?? {};

  if (home.gzipBytes > HOME_LIMIT_GZIP) failures.push(`home gzip ${home.gzipBytes} B > ${HOME_LIMIT_GZIP} B`);
  if (pathRouteTotal > PATH_ROUTE_LIMIT) failures.push(`path route gzip ${pathRouteTotal} B > ${PATH_ROUTE_LIMIT} B`);
  if ((pathIndex?.gzipBytes ?? 0) > PATH_INDEX_LIMIT) failures.push(`path index gzip ${pathIndex?.gzipBytes} B > ${PATH_INDEX_LIMIT} B`);
  if (algorithmGzip > PATH_ALGORITHM_LIMIT) failures.push(`path JS/algorithm closure gzip ${algorithmGzip} B > ${PATH_ALGORITHM_LIMIT} B`);
  if (browser.route_interaction_p95_ms > 150) failures.push(`route interaction p95 ${browser.route_interaction_p95_ms} ms > 150 ms`);
  if (browser.mobile_heap_increment_bytes > 25 * 1024 * 1024) failures.push(`mobile heap increment ${browser.mobile_heap_increment_bytes} B > 25 MB`);
  if (browser.cls > 0.1) failures.push(`CLS ${browser.cls} > 0.1`);
  if (browser.external_request_count !== 0) failures.push(`external request count ${browser.external_request_count} > 0`);
  if (benchmark.ok !== true) failures.push("bounded path benchmark evidence is not passing");

  for (const source of RUNTIME_SOURCES) {
    const text = readFileSync(resolve(ROOT, source), "utf8");
    for (const pattern of FORBIDDEN) if (pattern.test(text)) failures.push(`${source} matches forbidden runtime pattern ${pattern}`);
  }
  const output = {
    ok: failures.length === 0,
    failures,
    budgets: {
      homeBaselineGzipBytes: HOME_BASELINE_GZIP,
      homeLimitGzipBytes: HOME_LIMIT_GZIP,
      pathRouteLimitGzipBytes: PATH_ROUTE_LIMIT,
      pathIndexLimitGzipBytes: PATH_INDEX_LIMIT,
      pathAlgorithmLimitGzipBytes: PATH_ALGORITHM_LIMIT,
    },
    measurements: {
      home,
      pathAssets,
      initialJson: { files: jsonFiles, gzipBytes: jsonGzip },
      pathRouteTotalGzipBytes: pathRouteTotal,
      pathIndexGzipBytes: pathIndex?.gzipBytes ?? 0,
      pathAlgorithmGzipBytes: algorithmGzip,
      browser,
      benchmark,
    },
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(output, null, 2)}\n`);
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
