import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const HOME_BASELINE_GZIP_BYTES = 98_684;
const HOME_LIMIT_GZIP_BYTES = 103_618;
const TOURS_ROUTE_LIMIT_GZIP_BYTES = 300 * 1024;
const ARTWORK_INTERACTION_LIMIT_GZIP_BYTES = 180 * 1024;
const INTERACTION_JSON_LIMIT_GZIP_BYTES = 120 * 1024;
const DETAIL_REGIONS_LIMIT_GZIP_BYTES = 30 * 1024;

const RELEASE_FILES_LOADED_BY_GALLERY = [
  "manifest.json",
  "graph-summary.json",
  "artists.json",
  "layout.json",
  "facets.json",
  "search-index.json",
  "artworks.json",
  "media-index.json",
  "attributions.json",
  "withdrawal-mapping.json",
  "interaction-index.json",
];

const SOURCES = {
  gallery: "src/features/art-gallery/ArtGalleryRoute.tsx",
  tours: "src/features/art-gallery/tours/ToursPage.tsx",
  artwork: "src/features/art-gallery/artwork/ArtworkDetailPage.tsx",
};

const RUNTIME_POLICY_SOURCES = [
  "src/features/art-gallery/ArtGalleryRoute.tsx",
  "src/features/art-gallery/interaction-loader.ts",
  "src/features/art-gallery/artwork/ArtworkDetailPage.tsx",
  "src/features/art-gallery/artwork/ArtworkZoom.tsx",
  "src/features/art-gallery/compare/ComparePage.tsx",
  "src/features/art-gallery/observation/PrintShareControls.tsx",
  "src/features/art-gallery/tours/ToursPage.tsx",
];

const FORBIDDEN_RUNTIME_PATTERNS = [
  /navigator\.sendBeacon/i,
  /\bgtag\s*\(/i,
  /\bmixpanel\b/i,
  /\bsegment\.(?:track|identify)\b/i,
  /(?:visit|view|profile)[_-]history/i,
  /localStorage\.(?:setItem|getItem)\s*\(\s*["'][^"']*(?:visit|history|profile)/i,
];

function parseArgs(argv) {
  const options = {
    dist: join(ROOT, "dist"),
    release: null,
    output: join(ROOT, "docs", "qa", "museum-05b", "bundle-budget.json"),
    json: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--json") {
      options.json = true;
      continue;
    }
    if (!["--dist", "--release", "--output"].includes(argument)) {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = argv[index + 1];
    if (!value) throw new Error(`${argument} requires a path`);
    options[argument.slice(2)] = isAbsolute(value) ? value : resolve(ROOT, value);
    index += 1;
  }
  options.dist = resolve(options.dist);
  options.release = resolve(
    options.release ?? join(options.dist, "releases", "art-gallery-interactions-1.1.0"),
  );
  options.output = resolve(options.output);
  return options;
}

function safePath(base, name, failures) {
  const path = resolve(base, name);
  const rel = relative(base, path);
  if (rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel))) return path;
  failures.push(`path escapes root: ${name}`);
  return null;
}

function readJson(path, label, failures) {
  if (!existsSync(path)) {
    failures.push(`${label} is missing`);
    return null;
  }
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    failures.push(`${label} is invalid JSON: ${error.message}`);
    return null;
  }
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function gzipBytes(bytes) {
  return gzipSync(bytes, { level: 9 }).length;
}

function fileMetric(base, name, failures) {
  const path = safePath(base, name, failures);
  if (!path || !existsSync(path)) {
    failures.push(`required file is missing: ${name}`);
    return { path: name.replaceAll("\\", "/"), rawBytes: 0, gzipBytes: 0 };
  }
  const bytes = readFileSync(path);
  return {
    path: name.replaceAll("\\", "/"),
    rawBytes: bytes.length,
    gzipBytes: gzipBytes(bytes),
    sha256: `sha256:${sha256(bytes)}`,
  };
}

function findRecord(records, source, failures) {
  const matches = Object.entries(records)
    .filter(([key, record]) => key === source || record?.src === source)
    .map(([key]) => key);
  if (matches.length !== 1) failures.push(`${source} manifest record count must be 1, found ${matches.length}`);
  return matches[0] ?? null;
}

function collectStatic(records, seeds, failures) {
  const collected = new Set();
  const pending = seeds.filter(Boolean);
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
  }
  return collected;
}

function recordMetrics(records, keys, dist, failures) {
  const names = new Set();
  for (const key of keys) {
    const record = records[key];
    if (typeof record?.file === "string") names.add(record.file);
    for (const name of Array.isArray(record?.css) ? record.css : []) names.add(name);
  }
  const files = [...names].sort().map((name) => fileMetric(dist, name, failures));
  return {
    files,
    rawBytes: files.reduce((sum, file) => sum + file.rawBytes, 0),
    gzipBytes: files.reduce((sum, file) => sum + file.gzipBytes, 0),
  };
}

function routeMetrics(records, entryRecords, galleryKey, pageKey, dist, failures) {
  const closure = collectStatic(records, [galleryKey, pageKey], failures);
  const added = new Set([...closure].filter((key) => !entryRecords.has(key)));
  return recordMetrics(records, added, dist, failures);
}

function run(options) {
  const failures = [];
  const manifestPath = join(options.dist, ".vite", "manifest.json");
  const records = readJson(manifestPath, "Vite manifest", failures) ?? {};
  const entryKeys = Object.entries(records)
    .filter(([, record]) => record?.isEntry === true)
    .map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`Vite manifest must have one entry, found ${entryKeys.length}`);
  const entryRecords = collectStatic(records, [entryKeys[0]], failures);
  const home = recordMetrics(records, entryRecords, options.dist, failures);
  if (home.gzipBytes > HOME_LIMIT_GZIP_BYTES) {
    failures.push(`home gzip ${home.gzipBytes} B exceeds 5% growth limit ${HOME_LIMIT_GZIP_BYTES} B`);
  }

  const galleryKey = findRecord(records, SOURCES.gallery, failures);
  const toursKey = findRecord(records, SOURCES.tours, failures);
  const artworkKey = findRecord(records, SOURCES.artwork, failures);
  const directPages = new Set(Array.isArray(records[galleryKey]?.dynamicImports) ? records[galleryKey].dynamicImports : []);
  for (const [label, key] of [["tours", toursKey], ["artwork", artworkKey]]) {
    if (key && !directPages.has(key)) failures.push(`${label} is not a direct lazy gallery page`);
    if (key && entryRecords.has(key)) failures.push(`${label} is present in the home closure`);
  }

  const toursAssets = routeMetrics(records, entryRecords, galleryKey, toursKey, options.dist, failures);
  const artworkAssets = routeMetrics(records, entryRecords, galleryKey, artworkKey, options.dist, failures);
  const initialJsonFiles = RELEASE_FILES_LOADED_BY_GALLERY.map((name) => fileMetric(options.release, name, failures));
  const initialJsonGzipBytes = initialJsonFiles.reduce((sum, file) => sum + file.gzipBytes, 0);
  const interactionFile = initialJsonFiles.find((file) => file.path === "interaction-index.json");
  const interaction = readJson(join(options.release, "interaction-index.json"), "interaction-index.json", failures);
  const detailRegionBytes = Buffer.from(JSON.stringify({ detail_regions: interaction?.detail_regions ?? [] }));
  const detailRegionsGzipBytes = gzipBytes(detailRegionBytes);
  const toursTotalGzipBytes = toursAssets.gzipBytes + initialJsonGzipBytes;

  if ((interactionFile?.gzipBytes ?? 0) > INTERACTION_JSON_LIMIT_GZIP_BYTES) {
    failures.push(`interaction JSON gzip ${interactionFile?.gzipBytes ?? 0} B exceeds ${INTERACTION_JSON_LIMIT_GZIP_BYTES} B`);
  }
  if (detailRegionsGzipBytes > DETAIL_REGIONS_LIMIT_GZIP_BYTES) {
    failures.push(`detail regions gzip ${detailRegionsGzipBytes} B exceeds ${DETAIL_REGIONS_LIMIT_GZIP_BYTES} B`);
  }
  if (toursTotalGzipBytes > TOURS_ROUTE_LIMIT_GZIP_BYTES) {
    failures.push(`tours route gzip ${toursTotalGzipBytes} B exceeds ${TOURS_ROUTE_LIMIT_GZIP_BYTES} B`);
  }
  if (artworkAssets.gzipBytes > ARTWORK_INTERACTION_LIMIT_GZIP_BYTES) {
    failures.push(`artwork interaction assets gzip ${artworkAssets.gzipBytes} B exceeds ${ARTWORK_INTERACTION_LIMIT_GZIP_BYTES} B`);
  }
  if (interaction?.performance_contract?.initial_loads_all_tour_images !== false) {
    failures.push("performance contract must prohibit loading every tour image initially");
  }
  if (interaction?.performance_contract?.low_bandwidth_default !== "no_images") {
    failures.push("performance contract must make low bandwidth image-free by default");
  }
  if (interaction?.performance_contract?.print_loads_large_images !== false) {
    failures.push("performance contract must prohibit large print images");
  }
  if (interaction?.print_share_configuration?.tracking_parameters !== false || interaction?.print_share_configuration?.upload_data !== false) {
    failures.push("print/share contract must prohibit tracking parameters and data upload");
  }
  const runtimePolicyMatches = [];
  for (const name of RUNTIME_POLICY_SOURCES) {
    const text = readFileSync(join(ROOT, name), "utf8");
    FORBIDDEN_RUNTIME_PATTERNS.forEach((pattern) => {
      if (pattern.test(text)) runtimePolicyMatches.push({ path: name, pattern: pattern.source });
    });
  }
  if (runtimePolicyMatches.length) failures.push(`runtime sources contain analytics or history storage patterns: ${runtimePolicyMatches.length}`);

  const inputs = [
    fileMetric(options.dist, ".vite/manifest.json", failures),
    ...home.files,
    ...toursAssets.files,
    ...artworkAssets.files,
    ...initialJsonFiles,
    fileMetric(ROOT, "scripts/verify-museum-05b-budgets.mjs", failures),
  ];
  const inputSha256 = `sha256:${sha256(Buffer.from(inputs.map((item) => `${item.path}\0${item.sha256 ?? "missing"}\n`).join("")))}`;

  return {
    schemaVersion: "1.0.0",
    phase: "MUSEUM-05B",
    measurement: "node:zlib gzip level 9; each asset compressed independently",
    inputSha256,
    thresholds: {
      homeBaselineGzipBytes: HOME_BASELINE_GZIP_BYTES,
      homeGrowthPercentMax: 5,
      homeLimitGzipBytes: HOME_LIMIT_GZIP_BYTES,
      toursRouteGzipMax: TOURS_ROUTE_LIMIT_GZIP_BYTES,
      artworkInteractionChunkGzipMax: ARTWORK_INTERACTION_LIMIT_GZIP_BYTES,
      interactionJsonGzipMax: INTERACTION_JSON_LIMIT_GZIP_BYTES,
      detailRegionsGzipMax: DETAIL_REGIONS_LIMIT_GZIP_BYTES,
    },
    home: {
      ...home,
      growthPercent: Number((((home.gzipBytes / HOME_BASELINE_GZIP_BYTES) - 1) * 100).toFixed(3)),
      pass: home.gzipBytes <= HOME_LIMIT_GZIP_BYTES,
    },
    lazyBoundaries: {
      gallery: galleryKey,
      tours: toursKey,
      artwork: artworkKey,
      toursDirect: Boolean(toursKey && directPages.has(toursKey)),
      artworkDirect: Boolean(artworkKey && directPages.has(artworkKey)),
      absentFromHome: Boolean(toursKey && artworkKey && !entryRecords.has(toursKey) && !entryRecords.has(artworkKey)),
    },
    toursRoute: {
      assets: toursAssets,
      initialJsonFiles,
      initialJsonGzipBytes,
      totalGzipBytes: toursTotalGzipBytes,
      limitGzipBytes: TOURS_ROUTE_LIMIT_GZIP_BYTES,
      pass: toursTotalGzipBytes <= TOURS_ROUTE_LIMIT_GZIP_BYTES,
    },
    artworkInteractionAssets: {
      ...artworkAssets,
      limitGzipBytes: ARTWORK_INTERACTION_LIMIT_GZIP_BYTES,
      pass: artworkAssets.gzipBytes <= ARTWORK_INTERACTION_LIMIT_GZIP_BYTES,
    },
    interactionJson: {
      ...interactionFile,
      limitGzipBytes: INTERACTION_JSON_LIMIT_GZIP_BYTES,
      pass: (interactionFile?.gzipBytes ?? 0) <= INTERACTION_JSON_LIMIT_GZIP_BYTES,
    },
    detailRegions: {
      count: interaction?.detail_regions?.length ?? 0,
      rawBytes: detailRegionBytes.length,
      gzipBytes: detailRegionsGzipBytes,
      limitGzipBytes: DETAIL_REGIONS_LIMIT_GZIP_BYTES,
      pass: detailRegionsGzipBytes <= DETAIL_REGIONS_LIMIT_GZIP_BYTES,
    },
    runtimePolicies: {
      initialTourImages: "verified by M05B Playwright request assertions",
      lowBandwidth: interaction?.performance_contract?.low_bandwidth_default,
      printLoadsLargeImages: interaction?.performance_contract?.print_loads_large_images,
      analyticsOrHistoryStorage: {
        filesScanned: RUNTIME_POLICY_SOURCES,
        matches: runtimePolicyMatches,
        pass: runtimePolicyMatches.length === 0,
      },
    },
    failures,
    status: failures.length ? "fail" : "pass",
  };
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(`[museum-05b-budget] ${error.message}`);
  process.exit(2);
}

const report = run(options);
mkdirSync(dirname(options.output), { recursive: true });
writeFileSync(options.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
if (options.json) process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
else {
  console.log(`[museum-05b-budget] evidence=${relative(ROOT, options.output).replaceAll("\\", "/")}`);
  console.log(`[museum-05b-budget] home=${report.home.gzipBytes}/${HOME_LIMIT_GZIP_BYTES} B (${report.home.growthPercent}%)`);
  console.log(`[museum-05b-budget] tours=${report.toursRoute.totalGzipBytes}/${TOURS_ROUTE_LIMIT_GZIP_BYTES} B`);
  console.log(`[museum-05b-budget] artwork-assets=${report.artworkInteractionAssets.gzipBytes}/${ARTWORK_INTERACTION_LIMIT_GZIP_BYTES} B`);
  console.log(`[museum-05b-budget] interaction-json=${report.interactionJson.gzipBytes}/${INTERACTION_JSON_LIMIT_GZIP_BYTES} B`);
  console.log(`[museum-05b-budget] regions=${report.detailRegions.gzipBytes}/${DETAIL_REGIONS_LIMIT_GZIP_BYTES} B`);
}
if (report.failures.length) {
  console.error(report.failures.map((failure) => `[museum-05b-budget] FAIL ${failure}`).join("\n"));
  process.exit(1);
}
console.log("[museum-05b-budget] PASS route, JSON, lazy-load, low-bandwidth, and print budgets");
