import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..");
const HOME_BASELINE_GZIP_BYTES = 89_515;
const HOME_LIMIT_GZIP_BYTES = 102_942;
const ROUTE_LIMIT_GZIP_BYTES = 450 * 1024;
const GRAPH_SUMMARY_LIMIT_GZIP_BYTES = 100 * 1024;
const RELEASE_ID = "release:art-constellation-1.0.0";
const EXPECTED_ARTWORK_ROWS = 44;
const EXPECTED_APPROVED_ARTWORKS = 31;
const EXPECTED_NO_IMAGE_ARTWORKS = 13;
const EXPECTED_MEDIA_RECORDS = 273;
const EXPECTED_PHYSICAL_MEDIA = 242;
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
  "media-index.json",
  "attributions.json",
  "third-party-notices.json",
  "withdrawal-mapping.json",
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
    options.release ?? join(options.dist, "releases", "art-constellation-1.0.0"),
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
  const htmlImageTagPattern = /<(?:img|source)\b[^>]*>/gi;
  const htmlImagePreloadPattern = /<link\b(?=[^>]*\brel\s*=\s*["']preload["'])(?=[^>]*\bas\s*=\s*["']image["'])[^>]*>/gi;
  const imageAttributePattern = /\b(?:src|srcset)\s*=\s*["']([^"']+)["']/gi;
  const hrefAttributePattern = /\bhref\s*=\s*["']([^"']+)["']/i;
  const cssRuntimePattern = /(?:@import\s+["']|url\(\s*["']?)(?:https?:)?\/\//i;
  const cssImagePattern = /url\(\s*(["']?)([^"')]+)\1\s*\)/gi;
  const jsRuntimePatterns = [
    /\bfetch\(\s*["']https?:\/\//i,
    /\b(?:EventSource|WebSocket|Worker)\(\s*["']https?:\/\//i,
    /\bimport\(\s*["']https?:\/\//i,
  ];
  const initialImageLocators = new Set();
  let initialImageBytes = 0;
  const recordInitialImage = (locator, path) => {
    if (!locator || locator.startsWith("data:")) return;
    initialImageLocators.add(locator);
    if (/^(?:https?:)?\/\//i.test(locator)) return;
    const pathname = locator.split(/[?#]/, 1)[0];
    const marker = pathname.match(/\/(assets|releases)\/(.+)$/);
    const localPath = marker
      ? join(dist, marker[1], marker[2])
      : resolve(dirname(path), pathname.replace(/^\/+/, ""));
    if (existsSync(localPath) && !lstatSync(localPath).isSymbolicLink()) {
      initialImageBytes += statSync(localPath).size;
    }
  };
  for (const path of walk(dist)) {
    const extension = extname(path).toLowerCase();
    if (![".css", ".html", ".js"].includes(extension)) continue;
    const text = readFileSync(path, "utf8");
    const relativePath = relative(dist, path).replaceAll("\\", "/");
    if (extension === ".html" && htmlResourcePattern.test(text)) {
      failures.push(`external runtime HTML resource in ${relativePath}`);
    }
    if (extension === ".html") {
      for (const tag of text.matchAll(htmlImagePreloadPattern)) {
        const locator = tag[0].match(hrefAttributePattern)?.[1]?.trim() ?? "";
        failures.push(`initial image preload is forbidden in ${relativePath}${locator ? `: ${locator}` : ""}`);
        recordInitialImage(locator, path);
      }
      for (const tag of text.matchAll(htmlImageTagPattern)) {
        const isImageElement = /^<img\b/i.test(tag[0]);
        for (const attribute of tag[0].matchAll(imageAttributePattern)) {
          for (const candidate of attribute[1].split(",")) {
            const locator = candidate.trim().split(/\s+/, 1)[0];
            if (!locator || locator.startsWith("data:")) continue;
            if (!isImageElement && !/\.(?:avif|gif|jpe?g|png|svg|webp)(?:[?#]|$)/i.test(locator)) continue;
            failures.push(`initial HTML image address is forbidden in ${relativePath}: ${locator}`);
            recordInitialImage(locator, path);
          }
        }
      }
    }
    if (extension === ".css" && cssRuntimePattern.test(text)) {
      failures.push(`external runtime CSS resource in ${relativePath}`);
    }
    if (extension === ".css") {
      for (const match of text.matchAll(cssImagePattern)) {
        const locator = match[2].trim();
        if (locator.startsWith("data:image/")) {
          initialImageBytes += Buffer.byteLength(locator, "utf8");
          failures.push(`initial CSS embedded image is forbidden in ${relativePath}`);
        } else if (/\.(?:avif|gif|jpe?g|png|svg|webp)(?:[?#]|$)/i.test(locator)) {
          failures.push(`initial CSS image address is forbidden in ${relativePath}: ${locator}`);
          recordInitialImage(locator, path);
        }
      }
    }
    if (extension === ".js" && jsRuntimePatterns.some((pattern) => pattern.test(text))) {
      failures.push(`external runtime JavaScript request in ${relativePath}`);
    }
  }
  return { requests: initialImageLocators.size, bytes: initialImageBytes };
}

function hasValue(value) {
  if (value === null || value === false || value === 0 || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function inspectInitialJsonMedia(value, location, failures) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectInitialJsonMedia(item, `${location}[${index}]`, failures));
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    const normalized = key.toLowerCase();
    if (
      /^(?:src|srcset|image_url|media_url|thumbnail_url|image_path|media_path|thumbnail_path)$/.test(normalized) &&
      hasValue(item)
    ) {
      failures.push(`initial data addresses media at ${location}.${key}`);
    }
    if (typeof item === "string" && /(?:^|\/)assets\/[^?#"']+\.(?:jpe?g|webp)(?:[?#]|$)/i.test(item)) {
      failures.push(`initial data contains a physical media locator at ${location}.${key}`);
    }
    inspectInitialJsonMedia(item, `${location}.${key}`, failures);
  }
}

function loadJson(path, label, failures) {
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

function normalizedSha256(value) {
  const hash = typeof value === "string" ? value.replace(/^sha256:/, "") : "";
  return /^[0-9a-f]{64}$/.test(hash) ? hash : null;
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function verifyMediaMagic(path, extension, relativePath, failures) {
  const bytes = readFileSync(path);
  const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  const webp = bytes.length >= 12 && bytes.subarray(0, 4).toString("ascii") === "RIFF" && bytes.subarray(8, 12).toString("ascii") === "WEBP";
  if ((extension === ".jpg" || extension === ".jpeg") && !jpeg) failures.push(`media magic bytes do not match JPEG: ${relativePath}`);
  if (extension === ".webp" && !webp) failures.push(`media magic bytes do not match WebP: ${relativePath}`);
}

function inspectInitialReleaseData(release, failures) {
  for (const relativePath of INITIAL_DATA_FILES) {
    // The manifest is the physical closure and therefore lists every deferred
    // asset. Runtime image addressability is governed by media-index.json and
    // is measured separately; the other initial DTOs must remain media-free.
    if (relativePath === "manifest.json") continue;
    const path = within(release, relativePath, failures);
    if (!path || !existsSync(path)) continue;
    const value = loadJson(path, `initial release JSON ${relativePath}`, failures);
    if (value !== null) inspectInitialJsonMedia(value, relativePath, failures);
  }
}

function inspectRelease(release, failures) {
  if (!existsSync(release)) {
    failures.push(`release directory is missing: ${release}`);
    return { artworkRows: 0, mediaRecords: 0, physicalFiles: 0, physicalBytes: 0, initialMediaRequests: 0, initialMediaBytes: 0 };
  }
  inspectInitialReleaseData(release, failures);
  const actualMedia = new Map();
  for (const path of walk(release)) {
    const relativePath = relative(release, path).replaceAll("\\", "/");
    const extension = extname(path).toLowerCase();
    if (!MEDIA_EXTENSIONS.has(extension)) continue;
    if (![".jpg", ".jpeg", ".webp"].includes(extension)) {
      failures.push(`release media must be JPEG or WebP: ${relativePath}`);
      continue;
    }
    if (lstatSync(path).isSymbolicLink()) {
      failures.push(`release media must not be a symbolic link: ${relativePath}`);
      continue;
    }
    actualMedia.set(relativePath, path);
    verifyMediaMagic(path, extension, relativePath, failures);
  }

  const manifestPath = join(release, "manifest.json");
  const mediaIndexPath = join(release, "media-index.json");
  const manifest = existsSync(manifestPath) ? loadJson(manifestPath, "release manifest", failures) : null;
  const mediaIndex = existsSync(mediaIndexPath) ? loadJson(mediaIndexPath, "media-index.json", failures) : null;
  if (!existsSync(manifestPath)) failures.push("required file is missing: manifest.json");
  if (!existsSync(mediaIndexPath)) failures.push("required deferred file is missing: media-index.json");

  const manifestFiles = Array.isArray(manifest?.manifest_files) ? manifest.manifest_files : [];
  if (manifest && manifest.id !== RELEASE_ID) failures.push(`release manifest id must be ${RELEASE_ID}`);
  if (manifest && !Array.isArray(manifest.manifest_files)) failures.push("release manifest manifest_files must be an array");
  const manifestMedia = new Map();
  for (const [index, record] of manifestFiles.entries()) {
    const path = record?.path;
    if (typeof path !== "string" || !/\.(?:jpe?g|webp)$/i.test(path)) continue;
    if (manifestMedia.has(path)) failures.push(`duplicate manifest media path: ${path}`);
    manifestMedia.set(path, record);
    if (record.record_type !== "media") failures.push(`manifest media record_type must be media: ${path}`);
    const resolved = within(release, path, failures);
    if (!resolved || !actualMedia.has(path)) continue;
    const bytes = statSync(resolved).size;
    if (record.bytes !== bytes) failures.push(`manifest media byte count mismatch: ${path}`);
    const expectedHash = normalizedSha256(record.sha256);
    if (!expectedHash) failures.push(`manifest media sha256 is invalid: ${path}`);
    else if (sha256(resolved) !== expectedHash) failures.push(`manifest media sha256 mismatch: ${path}`);
    if (!Array.isArray(record.record_ids) || record.record_ids.length !== 1 || typeof record.record_ids[0] !== "string") {
      failures.push(`manifest media record_ids must contain exactly one child id: manifest_files[${index}]`);
    }
  }
  for (const path of actualMedia.keys()) {
    if (!manifestMedia.has(path)) failures.push(`physical media is absent from manifest closure: ${path}`);
  }
  for (const path of manifestMedia.keys()) {
    if (!actualMedia.has(path)) failures.push(`manifest media file is absent from physical closure: ${path}`);
  }

  const artworks = Array.isArray(mediaIndex?.artworks) ? mediaIndex.artworks : [];
  const assets = Array.isArray(mediaIndex?.assets) ? mediaIndex.assets : [];
  const counts = mediaIndex?.counts;
  if (mediaIndex && mediaIndex.release_id !== RELEASE_ID) failures.push(`media-index release_id must be ${RELEASE_ID}`);
  if (mediaIndex && (!Array.isArray(mediaIndex.artworks) || !Array.isArray(mediaIndex.assets))) {
    failures.push("media-index artworks and assets must be arrays");
  }
  if (
    !counts || counts.approved_artworks !== EXPECTED_APPROVED_ARTWORKS ||
    counts.no_image_artworks !== EXPECTED_NO_IMAGE_ARTWORKS || counts.assets !== EXPECTED_PHYSICAL_MEDIA
  ) {
    failures.push(`media-index counts must declare ${EXPECTED_APPROVED_ARTWORKS} approved, ${EXPECTED_NO_IMAGE_ARTWORKS} no-image, and ${EXPECTED_PHYSICAL_MEDIA} assets`);
  }
  const expectedDeliveryPolicy = {
    external_runtime_api: false,
    external_delivery_count: 0,
    blocked_asset_count: 0,
    preferred: "self_hosted",
    low_bandwidth_default: "metadata_only",
  };
  for (const [field, expectedValue] of Object.entries(expectedDeliveryPolicy)) {
    if (mediaIndex?.delivery_policy?.[field] !== expectedValue) {
      failures.push(`media-index delivery_policy.${field} must equal ${JSON.stringify(expectedValue)}`);
    }
  }
  if (artworks.length !== EXPECTED_ARTWORK_ROWS) failures.push(`media-index must contain ${EXPECTED_ARTWORK_ROWS} artwork rows, found ${artworks.length}`);
  if (assets.length !== EXPECTED_PHYSICAL_MEDIA) failures.push(`media-index must contain ${EXPECTED_PHYSICAL_MEDIA} physical child assets, found ${assets.length}`);
  if (actualMedia.size !== EXPECTED_PHYSICAL_MEDIA) failures.push(`release must contain ${EXPECTED_PHYSICAL_MEDIA} physical media files, found ${actualMedia.size}`);

  const includedMediaIds = manifest?.included_media_asset_ids;
  if (!Array.isArray(includedMediaIds) || includedMediaIds.length !== EXPECTED_MEDIA_RECORDS || new Set(includedMediaIds).size !== EXPECTED_MEDIA_RECORDS) {
    failures.push(`release manifest must bind ${EXPECTED_MEDIA_RECORDS} unique common media records`);
  }
  const artworkIds = new Set();
  const artworkMedia = new Map();
  for (const [index, artwork] of artworks.entries()) {
    if (typeof artwork?.artwork_id !== "string" || artworkIds.has(artwork.artwork_id)) {
      failures.push(`media-index artwork_id must be unique at artworks[${index}]`);
      continue;
    }
    artworkIds.add(artwork.artwork_id);
    artworkMedia.set(artwork.artwork_id, artwork);
    if (!Array.isArray(artwork.media_ids)) failures.push(`media-index artwork media_ids must be an array: ${artwork.artwork_id}`);
  }
  const assetIds = new Set();
  const parentMediaIds = new Set();
  const assetById = new Map();
  const assetsByArtwork = new Map();
  for (const [index, asset] of assets.entries()) {
    if (typeof asset?.id !== "string" || assetIds.has(asset.id)) {
      failures.push(`media-index asset id must be unique at assets[${index}]`);
      continue;
    }
    assetIds.add(asset.id);
    if (typeof asset.parent_media_id !== "string") failures.push(`media-index asset parent_media_id is required: ${asset.id}`);
    else parentMediaIds.add(asset.parent_media_id);
    assetById.set(asset.id, asset);
    if (!artworkIds.has(asset.artwork_id)) failures.push(`media-index asset references unknown artwork: ${asset.id}`);
    const grouped = assetsByArtwork.get(asset.artwork_id) ?? [];
    grouped.push(asset.id);
    assetsByArtwork.set(asset.artwork_id, grouped);
    if (typeof asset.src !== "string" || /^(?:https?:)?\/\//i.test(asset.src) || asset.src.includes("\\") || !/^assets\/[a-z0-9][a-z0-9._-]*\/(?:320|640|960|1600)w\.(?:jpg|webp)$/.test(asset.src)) {
      failures.push(`media-index asset src must be a bounded local JPEG/WebP path: ${asset.id}`);
      continue;
    }
    const manifestRecord = manifestMedia.get(asset.src);
    const physicalPath = actualMedia.get(asset.src);
    if (!manifestRecord || !physicalPath) failures.push(`media-index asset is outside manifest/physical closure: ${asset.id}`);
    const expectedFormat = asset.src.endsWith(".webp") ? "webp" : "jpeg";
    const expectedMime = expectedFormat === "webp" ? "image/webp" : "image/jpeg";
    const width = Number(asset.src.match(/\/(\d+)w\./)?.[1]);
    if (asset.format !== expectedFormat || asset.mime_type !== expectedMime || asset.width !== width) {
      failures.push(`media-index format, MIME, or width does not match src: ${asset.id}`);
    }
    if (physicalPath && asset.bytes !== statSync(physicalPath).size) failures.push(`media-index byte count mismatch: ${asset.id}`);
    const assetHash = normalizedSha256(asset.sha256);
    if (!assetHash || (physicalPath && sha256(physicalPath) !== assetHash)) failures.push(`media-index sha256 mismatch: ${asset.id}`);
    if (manifestRecord && !manifestRecord.record_ids?.includes(asset.id)) failures.push(`manifest record_ids do not bind media-index child: ${asset.id}`);
  }
  for (const [artworkId, artwork] of artworkMedia.entries()) {
    const declared = Array.isArray(artwork.media_ids) ? artwork.media_ids : [];
    const expected = assetsByArtwork.get(artworkId) ?? [];
    if (declared.length !== new Set(declared).size || [...declared].sort().join("\0") !== [...expected].sort().join("\0")) {
      failures.push(`media-index artwork media_ids do not equal child closure: ${artworkId}`);
    }
    if (artwork.representative_media_id !== null) {
      const representative = assetById.get(artwork.representative_media_id);
      if (!representative || !declared.includes(artwork.representative_media_id)) {
        failures.push(`media-index representative_media_id is outside artwork closure: ${artworkId}`);
      } else if (![320, 640].includes(representative.width)) {
        failures.push(`media-index representative thumbnail must prefer 320w/640w: ${artworkId}`);
      }
    } else if (declared.length) {
      failures.push(`media-index approved artwork requires a representative_media_id: ${artworkId}`);
    }
    if ((artwork.decision === "approved_self_hosted") !== (declared.length > 0)) {
      failures.push(`media-index artwork decision does not match its child media closure: ${artworkId}`);
    }
  }
  const approvedArtworkRows = artworks.filter((artwork) => artwork?.decision === "approved_self_hosted").length;
  if (approvedArtworkRows !== EXPECTED_APPROVED_ARTWORKS || artworks.length - approvedArtworkRows !== EXPECTED_NO_IMAGE_ARTWORKS) {
    failures.push(`media-index artwork rows must resolve to ${EXPECTED_APPROVED_ARTWORKS} approved and ${EXPECTED_NO_IMAGE_ARTWORKS} no-image decisions`);
  }
  for (const childId of assetIds) {
    if (!includedMediaIds?.includes(childId)) failures.push(`release manifest included_media_asset_ids omits child: ${childId}`);
  }
  if (parentMediaIds.size !== EXPECTED_APPROVED_ARTWORKS) {
    failures.push(`media-index assets must bind ${EXPECTED_APPROVED_ARTWORKS} common parent media records, found ${parentMediaIds.size}`);
  }
  const expectedIncludedMediaIds = new Set([...parentMediaIds, ...assetIds]);
  if (
    !Array.isArray(includedMediaIds) || includedMediaIds.length !== expectedIncludedMediaIds.size ||
    includedMediaIds.some((id) => !expectedIncludedMediaIds.has(id))
  ) {
    failures.push("release manifest included_media_asset_ids must equal the 31 parent + 242 child closure");
  }
  const physicalBytes = [...actualMedia.values()].reduce((total, path) => total + statSync(path).size, 0);
  if (counts?.bytes !== physicalBytes) failures.push(`media-index counts.bytes must equal physical media bytes ${physicalBytes}`);
  return {
    artworkRows: artworks.length,
    mediaRecords: Array.isArray(includedMediaIds) ? includedMediaIds.length : 0,
    physicalFiles: actualMedia.size,
    physicalBytes,
    initialMediaRequests: 0,
    initialMediaBytes: 0,
  };
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

  const initialHtmlMedia = inspectRuntimeResources(options.dist, failures);
  const mediaDelivery = inspectRelease(options.release, failures);
  mediaDelivery.initialMediaRequests = initialHtmlMedia.requests;
  mediaDelivery.initialMediaBytes = initialHtmlMedia.bytes;
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
    mediaDelivery,
    mediaAwareReleaseAndExternalRuntimeSafe: !failures.some((failure) => /media|external runtime|image preload/i.test(failure)),
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
  console.log(
    `[museum-04-budget] physical-media=${report.mediaDelivery.physicalFiles} files ${report.mediaDelivery.physicalBytes} B records=${report.mediaDelivery.mediaRecords} artwork-rows=${report.mediaDelivery.artworkRows} initial-media=${report.mediaDelivery.initialMediaBytes} B/${report.mediaDelivery.initialMediaRequests} requests`,
  );
}

if (report.failures.length) {
  console.error(report.failures.map((failure) => `[museum-04-budget] FAIL ${failure}`).join("\n"));
  process.exit(1);
}
console.log("[museum-04-budget] PASS home, route, graph summary, lazy graph, deferred manifest-closed media, zero initial media, external-runtime, and benchmark-non-shipping gates");
