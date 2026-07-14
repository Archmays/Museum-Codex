import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const HOME_BASELINE_GZIP_BYTES = 89_515;
const HOME_LIMIT_GZIP_BYTES = 102_942;
const ROUTE_LIMIT_GZIP_BYTES = 450 * 1024;
const GRAPH_SUMMARY_LIMIT_GZIP_BYTES = 100 * 1024;
const INITIAL_DATA_FILES = [
  "manifest.json",
  "graph-summary.json",
  "artists.json",
  "layout.json",
  "facets.json",
  "search-index.json",
];
const DEFERRED_DETAIL_FILES = [
  "contexts.json",
  "relationships.json",
  "artworks.json",
  "evidence.json",
  "sources.json",
  "rights.json",
];
const MEDIA_EXTENSIONS = new Set([
  ".avif",
  ".bmp",
  ".flac",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".m4a",
  ".m4v",
  ".mov",
  ".mp3",
  ".mp4",
  ".ogg",
  ".opus",
  ".png",
  ".svg",
  ".tif",
  ".tiff",
  ".wav",
  ".webm",
  ".webp",
  ".woff",
  ".woff2",
]);

function parseArgs(argv) {
  const options = {
    dist: join(ROOT, "dist"),
    release: null,
    json: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--json") {
      options.json = true;
    } else if (argument === "--dist" || argument === "--release") {
      const value = argv[index + 1];
      if (!value) throw new Error(`${argument} requires a path`);
      options[argument.slice(2)] = isAbsolute(value) ? value : resolve(ROOT, value);
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }
  options.dist = resolve(options.dist);
  options.release = resolve(
    options.release ?? join(options.dist, "releases", "art-constellation-0.1.0"),
  );
  return options;
}

function walk(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

function within(directory, relativePath, failures) {
  const path = resolve(directory, relativePath);
  const rel = relative(directory, path);
  if (rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel))) return path;
  failures.push(`path escapes build directory: ${relativePath}`);
  return null;
}

function gzipComponent(base, relativePath, failures) {
  const path = within(base, relativePath, failures);
  if (!path || !existsSync(path) || !statSync(path).isFile()) {
    failures.push(`required file is missing: ${relativePath}`);
    return { path: relativePath, rawBytes: 0, gzipBytes: 0 };
  }
  const bytes = readFileSync(path);
  return {
    path: relativePath.replaceAll("\\", "/"),
    rawBytes: bytes.length,
    gzipBytes: gzipSync(bytes, { level: 9 }).length,
  };
}

function sum(components, field = "gzipBytes") {
  return components.reduce((total, component) => total + component[field], 0);
}

function loadManifest(dist, failures) {
  const candidates = [join(dist, ".vite", "manifest.json"), join(dist, "manifest.json")];
  const path = candidates.find((candidate) => existsSync(candidate));
  if (!path) {
    failures.push("Vite manifest is missing (expected dist/.vite/manifest.json)");
    return { path: candidates[0], records: {} };
  }
  try {
    const records = JSON.parse(readFileSync(path, "utf8"));
    if (!records || typeof records !== "object" || Array.isArray(records)) {
      failures.push("Vite manifest root must be an object");
      return { path, records: {} };
    }
    return { path, records };
  } catch (error) {
    failures.push(`Vite manifest is not valid JSON: ${error.message}`);
    return { path, records: {} };
  }
}

function recordText(key, record) {
  return [key, record?.src, record?.name, record?.file].filter(Boolean).join(" ").toLowerCase();
}

function findOneRecord(records, label, pattern, failures) {
  const matches = Object.entries(records)
    .filter(([key, record]) => pattern.test(recordText(key, record)))
    .map(([key]) => key);
  if (matches.length !== 1) {
    failures.push(`${label} manifest record count must be 1, found ${matches.length}: ${matches.join(", ") || "none"}`);
    return matches[0] ?? null;
  }
  return matches[0];
}

function collectRecords(records, seeds, includeDynamic, failures) {
  const collected = new Set();
  const pending = [...seeds].filter(Boolean);
  while (pending.length) {
    const key = pending.pop();
    if (collected.has(key)) continue;
    const record = records[key];
    if (!record) {
      failures.push(`manifest references unknown record: ${key}`);
      continue;
    }
    collected.add(key);
    pending.push(...(Array.isArray(record.imports) ? record.imports : []));
    if (includeDynamic) {
      pending.push(...(Array.isArray(record.dynamicImports) ? record.dynamicImports : []));
    }
  }
  return collected;
}

function recordFiles(records, keys) {
  const js = new Set();
  const css = new Set();
  for (const key of keys) {
    const record = records[key];
    if (typeof record?.file === "string" && record.file.endsWith(".js")) js.add(record.file);
    for (const path of Array.isArray(record?.css) ? record.css : []) css.add(path);
  }
  return { js, css };
}

function difference(values, excluded) {
  return new Set([...values].filter((value) => !excluded.has(value)));
}

function inspectRuntimeResources(dist, failures) {
  const htmlResourcePattern = /<(?:audio|iframe|img|link|script|source|video)\b[^>]*(?:href|src)\s*=\s*["'](?:https?:)?\/\//i;
  const cssRuntimePattern = /(?:@import\s+["']|url\(\s*["']?)(?:https?:)?\/\//i;
  const jsRuntimePatterns = [
    /\bfetch\(\s*["']https?:\/\//i,
    /\b(?:EventSource|WebSocket|Worker)\(\s*["']https?:\/\//i,
    /\bimport\(\s*["']https?:\/\//i,
  ];
  for (const path of walk(dist)) {
    const extension = extname(path).toLowerCase();
    if (![".css", ".html", ".js"].includes(extension)) continue;
    const text = readFileSync(path, "utf8");
    const relativePath = relative(dist, path).replaceAll("\\", "/");
    if (extension === ".html" && htmlResourcePattern.test(text)) {
      failures.push(`external runtime HTML resource in ${relativePath}`);
    }
    if (extension === ".css" && cssRuntimePattern.test(text)) {
      failures.push(`external runtime CSS resource in ${relativePath}`);
    }
    if (extension === ".js" && jsRuntimePatterns.some((pattern) => pattern.test(text))) {
      failures.push(`external runtime JavaScript request in ${relativePath}`);
    }
  }
}

function hasNonEmptyMediaValue(key, value) {
  const normalized = key.toLowerCase();
  const mediaField = /^(?:audio|image|media|thumbnail|video)(?:_(?:bytes|count|file|file_ids|files|id|ids|path|paths|url|urls))?$/.test(normalized);
  if (!mediaField) return false;
  if (value === null || value === false || value === 0 || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") {
    if (normalized !== "media") return Object.keys(value).length > 0;
    const allowedZeroMediaFields = new Set(["bytes", "count", "downloaded", "statement"]);
    return Object.entries(value).some(([field, item]) => {
      if (!allowedZeroMediaFields.has(field)) return true;
      if (field === "statement") return false;
      return item !== 0 && item !== false && item !== null && item !== "";
    });
  }
  return true;
}

function inspectJsonMedia(value, location, failures) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectJsonMedia(item, `${location}[${index}]`, failures));
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    if (hasNonEmptyMediaValue(key, item)) failures.push(`non-empty media field at ${location}.${key}`);
    inspectJsonMedia(item, `${location}.${key}`, failures);
  }
}

function inspectRelease(release, failures) {
  if (!existsSync(release)) {
    failures.push(`release directory is missing: ${release}`);
    return;
  }
  for (const path of walk(release)) {
    const relativePath = relative(release, path).replaceAll("\\", "/");
    const segments = relativePath.toLowerCase().split("/");
    const extension = extname(path).toLowerCase();
    if (MEDIA_EXTENSIONS.has(extension) || segments.some((segment) => /^(?:audio|images?|media|thumbnails?|videos?)$/.test(segment))) {
      failures.push(`release contains a media file or directory: ${relativePath}`);
    }
    if (extension !== ".json") continue;
    try {
      inspectJsonMedia(JSON.parse(readFileSync(path, "utf8")), relativePath, failures);
    } catch (error) {
      failures.push(`release JSON is invalid (${relativePath}): ${error.message}`);
    }
  }
}

function inspectBenchmarkLeakage(dist, failures) {
  const textExtensions = new Set([".css", ".html", ".js", ".json", ".md", ".txt"]);
  for (const path of walk(dist)) {
    const relativePath = relative(dist, path).replaceAll("\\", "/");
    const segments = relativePath.toLowerCase().split("/");
    const filename = segments.at(-1) ?? "";
    if (segments.includes("benchmarks") || filename.includes("benchmark")) {
      failures.push(`repo-only benchmark artifact was shipped: ${relativePath}`);
    }
    if (
      segments.includes("fixture") || segments.includes("fixtures") ||
      segments.some((segment) => segment.includes("synthetic")) ||
      /(?:scale[-_]?fixture|museum[-_]?04[-_]?scale)/i.test(filename)
    ) {
      failures.push(`synthetic scale fixture file was shipped: ${relativePath}`);
    }
    if (textExtensions.has(extname(path).toLowerCase()) && readFileSync(path, "utf8").includes("__MUSEUM04_SCALE_BENCHMARK__")) {
      failures.push(`repo-only benchmark marker was shipped: ${relativePath}`);
    }
  }
}

function formatKiB(bytes) {
  return Number((bytes / 1024).toFixed(2));
}

function run(options) {
  const failures = [];
  const { path: manifestPath, records } = loadManifest(options.dist, failures);
  const entryKeys = Object.entries(records)
    .filter(([, record]) => record?.isEntry === true)
    .map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`Vite manifest must have exactly one entry, found ${entryKeys.length}`);
  const entryKey = entryKeys[0] ?? null;
  const routeKey = findOneRecord(records, "ArtConstellationPage", /art[-_ ]?constellationpage/, failures);
  const graphKey = findOneRecord(records, "SigmaGraphRenderer", /sigmagraphrenderer/, failures);

  const homeRecords = collectRecords(records, [entryKey], false, failures);
  const entryReachable = collectRecords(records, [entryKey], true, failures);
  const routeRecords = collectRecords(records, [routeKey], true, failures);
  if (routeKey && !entryReachable.has(routeKey)) failures.push("ArtConstellationPage is not a lazy descendant of the app entry");
  if (routeKey && homeRecords.has(routeKey)) failures.push("ArtConstellationPage is present in the home initial closure");
  if (graphKey && !routeRecords.has(graphKey)) failures.push("SigmaGraphRenderer is not a dynamic descendant of ArtConstellationPage");
  if (graphKey && homeRecords.has(graphKey)) failures.push("SigmaGraphRenderer is present in the home initial closure");

  const homeFiles = recordFiles(records, homeRecords);
  const allRouteFiles = recordFiles(records, routeRecords);
  const addedRouteFiles = {
    js: difference(allRouteFiles.js, homeFiles.js),
    css: difference(allRouteFiles.css, homeFiles.css),
  };
  const homeJs = [...homeFiles.js].sort().map((path) => gzipComponent(options.dist, path, failures));
  const homeCss = [...homeFiles.css].sort().map((path) => gzipComponent(options.dist, path, failures));
  const routeJs = [...addedRouteFiles.js].sort().map((path) => gzipComponent(options.dist, path, failures));
  const routeCss = [...addedRouteFiles.css].sort().map((path) => gzipComponent(options.dist, path, failures));

  const graphFingerprints = [/graphology/i, /Graph\.addNode:/, /SigmaGraphRenderer/, /Sigma: container/i];
  for (const component of homeJs) {
    const path = within(options.dist, component.path, failures);
    if (path && graphFingerprints.some((pattern) => pattern.test(readFileSync(path, "utf8")))) {
      failures.push(`graph library fingerprint found in home initial JavaScript: ${component.path}`);
    }
  }

  const initialData = INITIAL_DATA_FILES.map((path) => gzipComponent(options.release, path, failures));
  const deferredDetails = DEFERRED_DETAIL_FILES.map((path) => gzipComponent(options.release, path, failures));
  const graphSummary = initialData.find((component) => component.path === "graph-summary.json") ?? {
    path: "graph-summary.json",
    rawBytes: 0,
    gzipBytes: 0,
  };
  const homeGzipBytes = sum(homeJs) + sum(homeCss);
  const routeJsGzipBytes = sum(routeJs);
  const routeCssGzipBytes = sum(routeCss);
  const initialDataGzipBytes = sum(initialData);
  const routeTotalGzipBytes = routeJsGzipBytes + routeCssGzipBytes + initialDataGzipBytes;

  if (homeGzipBytes > HOME_LIMIT_GZIP_BYTES) {
    failures.push(`home initial gzip ${homeGzipBytes} B exceeds ${HOME_LIMIT_GZIP_BYTES} B`);
  }
  if (routeTotalGzipBytes > ROUTE_LIMIT_GZIP_BYTES) {
    failures.push(`constellation route gzip ${routeTotalGzipBytes} B exceeds ${ROUTE_LIMIT_GZIP_BYTES} B`);
  }
  if (graphSummary.gzipBytes > GRAPH_SUMMARY_LIMIT_GZIP_BYTES) {
    failures.push(`graph-summary.json gzip ${graphSummary.gzipBytes} B exceeds ${GRAPH_SUMMARY_LIMIT_GZIP_BYTES} B`);
  }

  inspectRuntimeResources(options.dist, failures);
  inspectRelease(options.release, failures);
  inspectBenchmarkLeakage(options.dist, failures);

  const report = {
    algorithm: "node:zlib gzip level 9; each file compressed independently",
    manifest: relative(options.dist, manifestPath).replaceAll("\\", "/"),
    homeInitial: {
      baselineGzipBytes: HOME_BASELINE_GZIP_BYTES,
      baselineKiB: formatKiB(HOME_BASELINE_GZIP_BYTES),
      limitGzipBytes: HOME_LIMIT_GZIP_BYTES,
      limitKiB: formatKiB(HOME_LIMIT_GZIP_BYTES),
      js: homeJs,
      css: homeCss,
      gzipBytes: homeGzipBytes,
      kib: formatKiB(homeGzipBytes),
      deltaGzipBytes: homeGzipBytes - HOME_BASELINE_GZIP_BYTES,
      growthPercent: Number((((homeGzipBytes / HOME_BASELINE_GZIP_BYTES) - 1) * 100).toFixed(3)),
      pass: homeGzipBytes <= HOME_LIMIT_GZIP_BYTES,
    },
    constellationRoute: {
      limitGzipBytes: ROUTE_LIMIT_GZIP_BYTES,
      limitKiB: formatKiB(ROUTE_LIMIT_GZIP_BYTES),
      js: routeJs,
      css: routeCss,
      initialData,
      jsGzipBytes: routeJsGzipBytes,
      cssGzipBytes: routeCssGzipBytes,
      initialDataGzipBytes,
      gzipBytes: routeTotalGzipBytes,
      kib: formatKiB(routeTotalGzipBytes),
      pass: routeTotalGzipBytes <= ROUTE_LIMIT_GZIP_BYTES,
    },
    graphSummary: {
      ...graphSummary,
      limitGzipBytes: GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
      limitKiB: formatKiB(GRAPH_SUMMARY_LIMIT_GZIP_BYTES),
      pass: graphSummary.gzipBytes <= GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
    },
    deferredDetails: {
      files: deferredDetails,
      gzipBytes: sum(deferredDetails),
      kib: formatKiB(sum(deferredDetails)),
      informationalOnly: true,
    },
    graphLibrariesAbsentFromHomeInitial: !failures.some((failure) => /graph library|SigmaGraphRenderer.*home/.test(failure)),
    zeroReleaseMediaAndExternalRuntime: !failures.some((failure) => /media|external runtime/i.test(failure)),
    benchmarkHarnessAbsentFromDist: !failures.some((failure) => /benchmark|synthetic scale fixture/i.test(failure)),
    failures,
    status: failures.length ? "fail" : "pass",
  };
  return report;
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(`[museum-04-budget] ${error.message}`);
  process.exit(2);
}

const report = run(options);
if (options.json) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(`[museum-04-budget] gzip=${report.algorithm}`);
  console.log(
    `[museum-04-budget] home js=${report.homeInitial.js.reduce((n, file) => n + file.gzipBytes, 0)} B css=${report.homeInitial.css.reduce((n, file) => n + file.gzipBytes, 0)} B total=${report.homeInitial.gzipBytes} B (${report.homeInitial.kib} KiB) limit=${report.homeInitial.limitGzipBytes} B`,
  );
  for (const component of [...report.homeInitial.js, ...report.homeInitial.css]) {
    console.log(`[museum-04-budget] home ${component.path}=${component.gzipBytes} B gzip`);
  }
  console.log(
    `[museum-04-budget] route js=${report.constellationRoute.jsGzipBytes} B css=${report.constellationRoute.cssGzipBytes} B initial-json=${report.constellationRoute.initialDataGzipBytes} B total=${report.constellationRoute.gzipBytes} B (${report.constellationRoute.kib} KiB) limit=${report.constellationRoute.limitGzipBytes} B`,
  );
  for (const component of [
    ...report.constellationRoute.js,
    ...report.constellationRoute.css,
    ...report.constellationRoute.initialData,
  ]) {
    console.log(`[museum-04-budget] route ${component.path}=${component.gzipBytes} B gzip`);
  }
  console.log(
    `[museum-04-budget] graph-summary=${report.graphSummary.gzipBytes} B (${formatKiB(report.graphSummary.gzipBytes)} KiB) limit=${report.graphSummary.limitGzipBytes} B`,
  );
  console.log(
    `[museum-04-budget] deferred-details=${report.deferredDetails.gzipBytes} B (${report.deferredDetails.kib} KiB) informational-only`,
  );
}

if (report.failures.length) {
  console.error(report.failures.map((failure) => `[museum-04-budget] FAIL ${failure}`).join("\n"));
  process.exit(1);
}
console.log("[museum-04-budget] PASS home, route, graph summary, lazy graph, zero media, external-runtime, and benchmark-non-shipping gates");
