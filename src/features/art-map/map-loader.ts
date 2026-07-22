import { loadAssetResolutionManifest, loadStaticRelease } from "../../data/release-loader";
import {
  currentArtReleaseBaseUrl,
} from "../../data/art-release-profile";
import type {
  ArtistEpisode,
  ArtistSummary,
  ArtworkSummary,
  FeatureCollection,
  HoldingLocation,
  MapBundle,
  MapGeometry,
  MapSource,
  MapStyleDocument,
  PlaceIdentity,
  LocalizedText,
} from "./types";

const DATA_FILES = [
  "place-identities.json",
  "artist-place-episodes.json",
  "holding-locations.json",
  "map-source-attributions.json",
  "map-style.json",
  "map-index.json",
  "filter-index.json",
  "map-artworks.json",
] as const;
const GEOMETRY_FILES = ["basemap/land.geojson", "basemap/coastline.geojson", "basemap/lakes.geojson", "map-points.geojson"] as const;

export class MapLoadError extends Error {
  constructor(public readonly status: "incompatible_release" | "tampered_map_data" | "request_failed") {
    super(status);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

async function digestHex(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) throw new MapLoadError("request_failed");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function fetchArtifact(
  base: URL,
  file: { path: string; bytes: number; sha256: string; resolved_path?: string },
  fetcher: typeof fetch,
) {
  const siteBase = new URL(import.meta.env.BASE_URL, base.origin);
  const url = file.resolved_path ? new URL(file.resolved_path, siteBase) : new URL(file.path, base);
  if (url.origin !== base.origin || !url.pathname.startsWith(siteBase.pathname)) throw new MapLoadError("request_failed");
  const response = await fetcher(url.href, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new MapLoadError("request_failed");
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== file.bytes || await digestHex(bytes) !== file.sha256.replace(/^sha256:/, "")) {
    throw new MapLoadError("tampered_map_data");
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes)) as unknown;
  } catch {
    throw new MapLoadError("tampered_map_data");
  }
}

function list(root: unknown, key: string): unknown[] {
  if (!isRecord(root) || !Array.isArray(root[key])) throw new MapLoadError("tampered_map_data");
  return root[key] as unknown[];
}

function assertBundle(bundle: Omit<MapBundle, "manifest" | "fileByPath">) {
  const guards = bundle.style.runtime_guards;
  const counts = bundle.mapIndex.counts;
  const listOnlyCount = bundle.episodes.filter((episode) => episode.release_status === "verified_list_only").length;
  const mappedCount = bundle.episodes.filter((episode) => episode.release_status === "verified_public").length;
  if (
    counts.places !== bundle.places.length || counts.episodes !== bundle.episodes.length ||
    counts.holding_institutions !== bundle.holdings.length || counts.artists !== bundle.artists.length ||
    counts.artworks !== bundle.artworkCount || counts.list_only_episodes !== listOnlyCount ||
    counts.verified_public_episodes !== mappedCount || bundle.style.renderer_version !== "5.24.0" ||
    guards.remote_style !== false || guards.tile_urls !== false || guards.glyphs !== false || guards.sprite !== false ||
    guards.geolocation !== false || guards.route_lines !== false
  ) throw new MapLoadError("tampered_map_data");
  const placeIds = new Set(bundle.places.map((place) => place.id));
  const artistIds = new Set(bundle.artists.map((artist) => artist.id));
  const artworkIds = new Set(bundle.artworks.map((artwork) => artwork.id));
  if (
    placeIds.size !== bundle.places.length || artistIds.size !== bundle.artists.length ||
    artworkIds.size !== bundle.artworks.length ||
    bundle.episodes.some((episode) => !placeIds.has(episode.place_id) || !artistIds.has(episode.artist_id)) ||
    bundle.holdings.some((holding) =>
      !placeIds.has(holding.place_id) || holding.artwork_ids.some((artworkId) => !artworkIds.has(artworkId))
    )
  ) {
    throw new MapLoadError("tampered_map_data");
  }
}

export async function loadMapBundle(fetcher: typeof fetch = fetch): Promise<MapBundle> {
  const base = new URL(currentArtReleaseBaseUrl(), typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new MapLoadError("request_failed");
  const manifestResult = await loadStaticRelease(new URL("manifest.json", base).href, fetcher);
  if (manifestResult.status !== "loaded") throw new MapLoadError("incompatible_release");
  let assetResolution;
  try {
    assetResolution = await loadAssetResolutionManifest(base, manifestResult.manifest, fetcher);
  } catch {
    throw new MapLoadError("tampered_map_data");
  }
  const fileByPath = new Map([
    ...manifestResult.manifest.manifest_files,
    ...(manifestResult.manifest.referenced_files ?? []),
    ...assetResolution.referenced_files,
    ...assetResolution.materialized_asset_files,
  ].map((file) => [file.path, file]));
  const references = DATA_FILES.map((path) => {
    const file = fileByPath.get(path);
    if (!file) throw new MapLoadError("tampered_map_data");
    return file;
  });
  const [placesRoot, episodesRoot, holdingsRoot, attributionRoot, styleRoot, mapIndexRoot, filterIndexRoot, artworksRoot] = await Promise.all(
    references.map((file) => fetchArtifact(base, file, fetcher)),
  );
  if (!isRecord(attributionRoot) || !isRecord(styleRoot) || !isRecord(mapIndexRoot) || !isRecord(filterIndexRoot)) {
    throw new MapLoadError("tampered_map_data");
  }
  const artistFacets = isRecord(filterIndexRoot.facets) ? list(filterIndexRoot.facets, "artists") : [];
  const artworkCount = isRecord(mapIndexRoot.counts) && typeof mapIndexRoot.counts.artworks === "number"
    ? mapIndexRoot.counts.artworks
    : -1;
  const bundle = {
    places: list(placesRoot, "places") as PlaceIdentity[],
    episodes: list(episodesRoot, "episodes") as ArtistEpisode[],
    holdings: list(holdingsRoot, "locations") as HoldingLocation[],
    artists: artistFacets.map((item) => {
      if (!isRecord(item) || typeof item.id !== "string" || !isRecord(item.labels)) throw new MapLoadError("tampered_map_data");
      return { id: item.id, labels: item.labels as LocalizedText };
    }) as ArtistSummary[],
    artworks: list(artworksRoot, "artworks") as ArtworkSummary[],
    artworkCount,
    sources: list(attributionRoot, "sources") as MapSource[],
    style: styleRoot as unknown as MapStyleDocument,
    mapIndex: mapIndexRoot as unknown as MapBundle["mapIndex"],
    filterIndex: filterIndexRoot as unknown as MapBundle["filterIndex"],
  };
  assertBundle(bundle);
  return { ...bundle, manifest: manifestResult.manifest, fileByPath };
}

export async function loadMapGeometry(bundle: MapBundle, fetcher: typeof fetch = fetch): Promise<MapGeometry> {
  const base = new URL(currentArtReleaseBaseUrl(), window.location.href);
  const documents = await Promise.all(GEOMETRY_FILES.map((path) => {
    const file = bundle.fileByPath.get(path);
    if (!file) throw new MapLoadError("tampered_map_data");
    return fetchArtifact(base, file, fetcher);
  }));
  for (const document of documents) {
    if (!isRecord(document) || document.type !== "FeatureCollection" || !Array.isArray(document.features)) {
      throw new MapLoadError("tampered_map_data");
    }
  }
  return { land: documents[0] as FeatureCollection, coastline: documents[1] as FeatureCollection, lakes: documents[2] as FeatureCollection, points: documents[3] as FeatureCollection };
}
