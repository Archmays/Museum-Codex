import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const RELEASE_ID = "release:art-constellation-1.0.0";

// OD-005/MUSEUM-04 inherited ceilings. M05A adds two conservative sub-budgets
// inside the already-approved 450 KiB route ceiling.
const HOME_BASELINE_GZIP_BYTES = 89_515;
const HOME_LIMIT_GZIP_BYTES = 102_942;
const ROUTE_LIMIT_GZIP_BYTES = 450 * 1024;
const GRAPH_SUMMARY_LIMIT_GZIP_BYTES = 100 * 1024;
const GALLERY_ASSET_LIMIT_GZIP_BYTES = 128 * 1024;
const GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES = 128 * 1024;

const M04_INITIAL_DATA_FILES = [
  "manifest.json",
  "graph-summary.json",
  "artists.json",
  "layout.json",
  "facets.json",
  "search-index.json",
];

// These are the exact artifacts fetched before the gallery route declares its
// 44-record catalog ready. Claims/evidence/sources remain artwork-detail data.
const GALLERY_INITIAL_DATA_FILES = [
  ...M04_INITIAL_DATA_FILES,
  "artworks.json",
  "media-index.json",
  "attributions.json",
  "withdrawal-mapping.json",
];

const ROUTE_SOURCES = {
  constellation: "src/features/art-constellation/ArtConstellationPage.tsx",
  graph: "src/features/art-constellation/SigmaGraphRenderer.tsx",
  galleryShell: "src/features/art-gallery/ArtGalleryRoute.tsx",
  artistIndex: "src/features/art-gallery/artists/ArtistIndexPage.tsx",
  artistGallery: "src/features/art-gallery/artists/ArtistGalleryPage.tsx",
  artworkDetail: "src/features/art-gallery/artwork/ArtworkDetailPage.tsx",
  compare: "src/features/art-gallery/compare/ComparePage.tsx",
  tours: "src/features/art-gallery/tours/ToursPage.tsx",
};

function parseArgs(argv) {
  const options = {
    dist: join(ROOT, "dist"),
    release: null,
    output: join(ROOT, "docs", "qa", "museum-05a", "bundle-budget.json"),
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
    options.release ?? join(options.dist, "releases", "art-constellation-1.0.0"),
  );
  options.output = resolve(options.output);
  return options;
}

function within(directory, relativePath, failures) {
  const path = resolve(directory, relativePath);
  const rel = relative(directory, path);
  if (rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel))) return path;
  failures.push(`path escapes build directory: ${relativePath}`);
  return null;
}

function loadJson(path, label, failures) {
  if (!existsSync(path)) {
    failures.push(`${label} is missing`);
    return null;
  }
  try {
    const value = JSON.parse(readFileSync(path, "utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      failures.push(`${label} root must be an object`);
      return null;
    }
    return value;
  } catch (error) {
    failures.push(`${label} is invalid JSON: ${error.message}`);
    return null;
  }
}

function loadViteManifest(dist, failures) {
  const path = [join(dist, ".vite", "manifest.json"), join(dist, "manifest.json")]
    .find((candidate) => existsSync(candidate));
  if (!path) {
    failures.push("Vite manifest is missing (expected dist/.vite/manifest.json)");
    return { path: join(dist, ".vite", "manifest.json"), records: {} };
  }
  return { path, records: loadJson(path, "Vite manifest", failures) ?? {} };
}

function findSourceRecord(records, label, source, failures, optional = false) {
  const matches = Object.entries(records)
    .filter(([key, record]) => key === source || record?.src === source)
    .map(([key]) => key);
  if (matches.length !== 1 && !(optional && matches.length === 0)) {
    failures.push(`${label} manifest record count must be 1, found ${matches.length}`);
  }
  return matches[0] ?? null;
}

function collectRecords(records, seeds, includeDynamic, failures, dynamicBoundaries = new Set()) {
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
    if (includeDynamic && !dynamicBoundaries.has(key)) {
      pending.push(...(Array.isArray(record.dynamicImports) ? record.dynamicImports : []));
    }
  }
  return collected;
}

function difference(values, excluded) {
  return new Set([...values].filter((value) => !excluded.has(value)));
}

function union(...sets) {
  return new Set(sets.flatMap((set) => [...set]));
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

function gzipComponent(base, relativePath, failures) {
  const path = within(base, relativePath, failures);
  if (!path || !existsSync(path)) {
    failures.push(`required file is missing: ${relativePath}`);
    return { path: relativePath.replaceAll("\\", "/"), rawBytes: 0, gzipBytes: 0 };
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

function componentsForRecords(records, recordKeys, dist, failures) {
  const files = recordFiles(records, recordKeys);
  return {
    js: [...files.js].sort().map((path) => gzipComponent(dist, path, failures)),
    css: [...files.css].sort().map((path) => gzipComponent(dist, path, failures)),
  };
}

function routeMetrics(components, initialJsonGzipBytes, limits) {
  const jsGzipBytes = sum(components.js);
  const cssGzipBytes = sum(components.css);
  const assetGzipBytes = jsGzipBytes + cssGzipBytes;
  const totalGzipBytes = assetGzipBytes + initialJsonGzipBytes;
  return {
    js: components.js,
    css: components.css,
    jsGzipBytes,
    cssGzipBytes,
    assetGzipBytes,
    assetLimitGzipBytes: limits.assets,
    initialJsonGzipBytes,
    totalGzipBytes,
    totalLimitGzipBytes: limits.total,
    pass: assetGzipBytes <= limits.assets && totalGzipBytes <= limits.total,
  };
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function inputRecord(label, path) {
  const bytes = readFileSync(path);
  return { path: label, bytes: bytes.length, sha256: `sha256:${sha256(bytes)}` };
}

function inspectRelease(release, failures) {
  const manifestPath = join(release, "manifest.json");
  const mediaIndexPath = join(release, "media-index.json");
  const manifest = loadJson(manifestPath, "release manifest", failures);
  const mediaIndex = loadJson(mediaIndexPath, "media-index.json", failures);
  if (manifest && manifest.id !== RELEASE_ID) failures.push(`release id must be ${RELEASE_ID}`);
  if (manifest?.attribution_manifest?.path !== "attributions.json") {
    failures.push("release attribution manifest must resolve to attributions.json");
  }

  const artworks = Array.isArray(mediaIndex?.artworks) ? mediaIndex.artworks : [];
  const assets = Array.isArray(mediaIndex?.assets) ? mediaIndex.assets : [];
  if (artworks.length !== 44) failures.push(`media-index must contain 44 artwork rows, found ${artworks.length}`);
  if (assets.length !== 242) failures.push(`media-index must contain 242 derivative assets, found ${assets.length}`);
  const mediaPaths = [];
  for (const [index, asset] of assets.entries()) {
    const path = asset?.src;
    if (
      typeof path !== "string" ||
      !/^assets\/[a-z0-9][a-z0-9-]*\/(?:320|640|960|1600)w\.(?:jpe?g|webp)$/.test(path) ||
      /^(?:https?:)?\/\//i.test(path)
    ) {
      failures.push(`media-index asset src is not a bounded release derivative at assets[${index}]`);
      continue;
    }
    mediaPaths.push(path);
  }
  if (new Set(mediaPaths).size !== mediaPaths.length) failures.push("media-index derivative paths must be unique");
  return { artworkRows: artworks.length, mediaPaths: [...new Set(mediaPaths)].sort() };
}

function inspectHomeMediaEmbedding(dist, homeComponents, mediaPaths, failures) {
  const files = [
    { label: "index.html", path: join(dist, "index.html") },
    ...[...homeComponents.js, ...homeComponents.css].map((component) => ({
      label: component.path,
      path: join(dist, component.path),
    })),
  ];
  const matches = [];
  for (const file of files) {
    if (!existsSync(file.path)) {
      failures.push(`required home file is missing: ${file.label}`);
      continue;
    }
    const text = readFileSync(file.path, "utf8");
    for (const mediaPath of mediaPaths) {
      if (text.includes(mediaPath)) matches.push({ file: file.label, mediaPath });
    }
    if (/releases\/art-constellation-1\.0\.0\/assets\/[a-z0-9-]+\/(?:320|640|960|1600)w\.(?:jpe?g|webp)/i.test(text)) {
      matches.push({ file: file.label, mediaPath: "generic_release_media_locator" });
    }
  }
  const uniqueMatches = [...new Map(matches.map((match) => [`${match.file}\0${match.mediaPath}`, match])).values()]
    .sort((left, right) => `${left.file}\0${left.mediaPath}`.localeCompare(`${right.file}\0${right.mediaPath}`));
  if (uniqueMatches.length) {
    failures.push(`home initial closure embeds ${uniqueMatches.length} release media locator(s)`);
  }
  return {
    artworkRowsChecked: 44,
    derivativeUrlsChecked: mediaPaths.length,
    embeddedMatches: uniqueMatches,
    pass: uniqueMatches.length === 0,
  };
}

function run(options) {
  const failures = [];
  const { path: viteManifestPath, records } = loadViteManifest(options.dist, failures);
  const entryKeys = Object.entries(records)
    .filter(([, record]) => record?.isEntry === true)
    .map(([key]) => key);
  if (entryKeys.length !== 1) failures.push(`Vite manifest must have exactly one entry, found ${entryKeys.length}`);
  const entryKey = entryKeys[0] ?? null;
  const routeKeys = Object.fromEntries(Object.entries(ROUTE_SOURCES).map(([label, source]) => [
    label,
    findSourceRecord(records, label, source, failures, label === "tours"),
  ]));

  const homeRecords = collectRecords(records, [entryKey], false, failures);
  const allEntryRecords = collectRecords(records, [entryKey], true, failures);
  const homeComponents = componentsForRecords(records, homeRecords, options.dist, failures);
  const homeGzipBytes = sum(homeComponents.js) + sum(homeComponents.css);
  if (homeGzipBytes > HOME_LIMIT_GZIP_BYTES) {
    failures.push(`home initial gzip ${homeGzipBytes} B exceeds inherited limit ${HOME_LIMIT_GZIP_BYTES} B`);
  }

  // Shared home records are static ancestors of the route. Their sibling
  // dynamic imports are not part of the constellation route closure.
  const constellationRecords = collectRecords(records, [routeKeys.constellation], true, failures, homeRecords);
  const constellationAdded = difference(constellationRecords, homeRecords);
  const constellationComponents = componentsForRecords(records, constellationAdded, options.dist, failures);
  const m04InitialData = M04_INITIAL_DATA_FILES.map((path) => gzipComponent(options.release, path, failures));
  const m04InitialDataGzipBytes = sum(m04InitialData);
  const constellationRoute = routeMetrics(constellationComponents, m04InitialDataGzipBytes, {
    assets: ROUTE_LIMIT_GZIP_BYTES,
    total: ROUTE_LIMIT_GZIP_BYTES,
  });
  if (constellationRoute.totalGzipBytes > ROUTE_LIMIT_GZIP_BYTES) {
    failures.push(`M04 constellation route gzip ${constellationRoute.totalGzipBytes} B exceeds inherited limit ${ROUTE_LIMIT_GZIP_BYTES} B`);
  }
  const graphSummary = m04InitialData.find((item) => item.path === "graph-summary.json");
  if ((graphSummary?.gzipBytes ?? 0) > GRAPH_SUMMARY_LIMIT_GZIP_BYTES) {
    failures.push(`graph-summary.json gzip ${graphSummary.gzipBytes} B exceeds inherited limit ${GRAPH_SUMMARY_LIMIT_GZIP_BYTES} B`);
  }

  if (routeKeys.constellation && !allEntryRecords.has(routeKeys.constellation)) {
    failures.push("ArtConstellationPage is not a lazy descendant of the app entry");
  }
  if (routeKeys.constellation && homeRecords.has(routeKeys.constellation)) {
    failures.push("ArtConstellationPage is present in the home initial closure");
  }
  if (routeKeys.graph && !constellationRecords.has(routeKeys.graph)) {
    failures.push("SigmaGraphRenderer is not a dynamic descendant of ArtConstellationPage");
  }
  if (routeKeys.graph && homeRecords.has(routeKeys.graph)) {
    failures.push("SigmaGraphRenderer is present in the home initial closure");
  }

  const galleryInitialData = GALLERY_INITIAL_DATA_FILES.map((path) => gzipComponent(options.release, path, failures));
  const galleryInitialJsonGzipBytes = sum(galleryInitialData);
  if (galleryInitialJsonGzipBytes > GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES) {
    failures.push(`gallery initial JSON gzip ${galleryInitialJsonGzipBytes} B exceeds ${GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES} B`);
  }

  const pageLabels = ["artistIndex", "artistGallery", "artworkDetail", "compare"];
  const galleryKey = routeKeys.galleryShell;
  const galleryShellRecords = collectRecords(records, [galleryKey], false, failures);
  if (galleryKey && !allEntryRecords.has(galleryKey)) failures.push("ArtGalleryRoute is not a lazy descendant of the app entry");
  if (galleryKey && homeRecords.has(galleryKey)) failures.push("ArtGalleryRoute is present in the home initial closure");
  const directGalleryImports = new Set(Array.isArray(records[galleryKey]?.dynamicImports) ? records[galleryKey].dynamicImports : []);
  const expectedPageKeys = new Set(pageLabels.map((label) => routeKeys[label]).filter(Boolean));
  const allowedPageKeys = new Set([...expectedPageKeys, routeKeys.tours].filter(Boolean));
  for (const label of pageLabels) {
    const pageKey = routeKeys[label];
    if (pageKey && !directGalleryImports.has(pageKey)) failures.push(`${label} is not a direct lazy page of ArtGalleryRoute`);
    if (pageKey && !allEntryRecords.has(pageKey)) failures.push(`${label} is not reachable from the app entry`);
    if (pageKey && homeRecords.has(pageKey)) failures.push(`${label} is present in the home initial closure`);
    if (pageKey && galleryShellRecords.has(pageKey)) failures.push(`${label} is statically bundled into ArtGalleryRoute`);
  }
  const unexpectedDynamicImports = [...directGalleryImports].filter((key) => !allowedPageKeys.has(key));
  if (unexpectedDynamicImports.length || directGalleryImports.size < expectedPageKeys.size) {
    failures.push(`ArtGalleryRoute must retain the four formal M05A lazy pages and may add the M05B tours page; unexpected=${unexpectedDynamicImports.join(",") || "none"}`);
  }

  const galleryShellAdded = difference(galleryShellRecords, homeRecords);
  const galleryShellComponents = componentsForRecords(records, galleryShellAdded, options.dist, failures);
  const galleryRoutes = {};
  const pageClosures = [];
  for (const label of pageLabels) {
    const pageRecords = collectRecords(records, [galleryKey, routeKeys[label]], false, failures);
    pageClosures.push(pageRecords);
    const added = difference(pageRecords, homeRecords);
    const metrics = routeMetrics(
      componentsForRecords(records, added, options.dist, failures),
      galleryInitialJsonGzipBytes,
      { assets: GALLERY_ASSET_LIMIT_GZIP_BYTES, total: ROUTE_LIMIT_GZIP_BYTES },
    );
    galleryRoutes[label] = metrics;
    if (metrics.assetGzipBytes > GALLERY_ASSET_LIMIT_GZIP_BYTES) {
      failures.push(`${label} JS/CSS gzip ${metrics.assetGzipBytes} B exceeds ${GALLERY_ASSET_LIMIT_GZIP_BYTES} B`);
    }
    if (metrics.totalGzipBytes > ROUTE_LIMIT_GZIP_BYTES) {
      failures.push(`${label} route total gzip ${metrics.totalGzipBytes} B exceeds ${ROUTE_LIMIT_GZIP_BYTES} B`);
    }
  }
  const allGalleryRecords = difference(union(galleryShellRecords, ...pageClosures), homeRecords);
  const allGalleryComponents = componentsForRecords(records, allGalleryRecords, options.dist, failures);

  const releaseInspection = inspectRelease(options.release, failures);
  const mediaEmbedding = inspectHomeMediaEmbedding(
    options.dist,
    homeComponents,
    releaseInspection.mediaPaths,
    failures,
  );

  const measuredAssetPaths = [...new Set([
    ...homeComponents.js,
    ...homeComponents.css,
    ...constellationComponents.js,
    ...constellationComponents.css,
    ...allGalleryComponents.js,
    ...allGalleryComponents.css,
  ].map((component) => component.path))].sort();
  const inputPaths = [
    { label: ".vite/manifest.json", path: viteManifestPath },
    { label: "index.html", path: join(options.dist, "index.html") },
    ...measuredAssetPaths.map((path) => ({ label: path, path: join(options.dist, path) })),
    ...GALLERY_INITIAL_DATA_FILES.map((name) => ({ label: `releases/art-constellation-1.0.0/${name}`, path: join(options.release, name) })),
    { label: "scripts/verify-museum-05a-budgets.mjs", path: SCRIPT_PATH },
  ].filter(({ path }) => existsSync(path));
  const inputs = inputPaths.map(({ label, path }) => inputRecord(label, path));
  const inputSha256 = `sha256:${sha256(Buffer.from(inputs.map((item) => `${item.path}\0${item.sha256}\n`).join("")))}`;

  return {
    schemaVersion: "1.0.0",
    phase: "MUSEUM-05A",
    measurement: "node:zlib gzip level 9; each file compressed independently",
    thresholds: {
      homeBaselineGzipBytes: HOME_BASELINE_GZIP_BYTES,
      homeLimitGzipBytes: HOME_LIMIT_GZIP_BYTES,
      inheritedRouteTotalLimitGzipBytes: ROUTE_LIMIT_GZIP_BYTES,
      inheritedGraphSummaryLimitGzipBytes: GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
      galleryAssetLimitGzipBytes: GALLERY_ASSET_LIMIT_GZIP_BYTES,
      galleryInitialJsonLimitGzipBytes: GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES,
      basis: "OD-005 inherited M04 ceilings; 128 KiB gallery asset and initial-JSON sub-budgets measured against the 44-artwork/242-derivative formal release",
    },
    inputs,
    inputSha256,
    homeInitial: {
      ...homeComponents,
      baselineGzipBytes: HOME_BASELINE_GZIP_BYTES,
      limitGzipBytes: HOME_LIMIT_GZIP_BYTES,
      gzipBytes: homeGzipBytes,
      growthPercent: Number((((homeGzipBytes / HOME_BASELINE_GZIP_BYTES) - 1) * 100).toFixed(3)),
      pass: homeGzipBytes <= HOME_LIMIT_GZIP_BYTES,
    },
    m04Regression: {
      constellationRoute: {
        ...constellationRoute,
        initialData: m04InitialData,
      },
      graphSummary: {
        ...graphSummary,
        limitGzipBytes: GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
        pass: (graphSummary?.gzipBytes ?? 0) <= GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
      },
      pass: homeGzipBytes <= HOME_LIMIT_GZIP_BYTES && constellationRoute.pass &&
        (graphSummary?.gzipBytes ?? 0) <= GRAPH_SUMMARY_LIMIT_GZIP_BYTES,
    },
    lazyBoundaries: {
      entry: entryKey,
      galleryShell: galleryKey,
      directPages: Object.fromEntries(pageLabels.map((label) => [label, routeKeys[label]])),
      galleryShellAbsentFromHome: galleryKey ? !homeRecords.has(galleryKey) : false,
      pagesAbsentFromHome: Object.fromEntries(pageLabels.map((label) => [label, routeKeys[label] ? !homeRecords.has(routeKeys[label]) : false])),
      pagesAbsentFromShellStaticClosure: Object.fromEntries(pageLabels.map((label) => [label, routeKeys[label] ? !galleryShellRecords.has(routeKeys[label]) : false])),
      pass: galleryKey ? !homeRecords.has(galleryKey) && pageLabels.every((label) =>
        routeKeys[label] && directGalleryImports.has(routeKeys[label]) &&
        !homeRecords.has(routeKeys[label]) && !galleryShellRecords.has(routeKeys[label])) : false,
    },
    galleryInitialJson: {
      files: galleryInitialData,
      rawBytes: sum(galleryInitialData, "rawBytes"),
      gzipBytes: galleryInitialJsonGzipBytes,
      limitGzipBytes: GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES,
      pass: galleryInitialJsonGzipBytes <= GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES,
    },
    galleryShell: routeMetrics(galleryShellComponents, 0, {
      assets: GALLERY_ASSET_LIMIT_GZIP_BYTES,
      total: GALLERY_ASSET_LIMIT_GZIP_BYTES,
    }),
    galleryRoutes,
    allGalleryLazyAssets: {
      ...allGalleryComponents,
      gzipBytes: sum(allGalleryComponents.js) + sum(allGalleryComponents.css),
      informationalOnly: true,
    },
    mediaLocatorEmbedding: mediaEmbedding,
    failures,
    status: failures.length ? "fail" : "pass",
  };
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(`[museum-05a-budget] ${error.message}`);
  process.exit(2);
}

const report = run(options);
mkdirSync(dirname(options.output), { recursive: true });
writeFileSync(options.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");

if (options.json) {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} else {
  console.log(`[museum-05a-budget] evidence=${relative(ROOT, options.output).replaceAll("\\", "/")}`);
  console.log(`[museum-05a-budget] home=${report.homeInitial.gzipBytes}/${report.homeInitial.limitGzipBytes} B gzip growth=${report.homeInitial.growthPercent}%`);
  console.log(`[museum-05a-budget] M04-route=${report.m04Regression.constellationRoute.totalGzipBytes}/${ROUTE_LIMIT_GZIP_BYTES} B gzip`);
  console.log(`[museum-05a-budget] gallery-initial-json=${report.galleryInitialJson.gzipBytes}/${GALLERY_INITIAL_JSON_LIMIT_GZIP_BYTES} B gzip`);
  for (const [label, route] of Object.entries(report.galleryRoutes)) {
    console.log(`[museum-05a-budget] ${label} assets=${route.assetGzipBytes}/${GALLERY_ASSET_LIMIT_GZIP_BYTES} B total=${route.totalGzipBytes}/${ROUTE_LIMIT_GZIP_BYTES} B gzip`);
  }
  console.log(`[museum-05a-budget] home-media=${report.mediaLocatorEmbedding.embeddedMatches.length} matches across ${report.mediaLocatorEmbedding.derivativeUrlsChecked} derivative URLs`);
}

if (report.failures.length) {
  console.error(report.failures.map((failure) => `[museum-05a-budget] FAIL ${failure}`).join("\n"));
  process.exit(1);
}
console.log("[museum-05a-budget] PASS lazy shell/pages, inherited M04 budgets, M05A route/data budgets, and zero home media embedding");
