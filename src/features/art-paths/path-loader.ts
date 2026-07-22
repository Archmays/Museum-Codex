import {
  CURRENT_ART_RELEASE_ID,
  CURRENT_ART_RELEASE_VERSION,
  PATH_ART_RELEASE_ID,
  PATH_ALGORITHM_PATH,
  PATH_EXPLANATIONS_PATH,
  PATH_GRAPH_PATH,
  PATH_INDEX_PATH,
  PATH_ROUTE_CONFIG_PATH,
  currentArtReleaseBaseUrl,
} from "../../data/art-release-profile";
import { loadArtConstellationRelease, loadStaticRelease, publicNarrativeText } from "../../data/release-loader";
import type { ArtConstellationRelease } from "../art-constellation/types";
import type {
  PathAlgorithmContract,
  PathExplanationCollection,
  PathGraphInput,
  PathIndex,
  PathRouteConfig,
  PathwayBundle,
} from "./types";

const REQUIRED_FILES = [
  PATH_ALGORITHM_PATH,
  PATH_GRAPH_PATH,
  PATH_INDEX_PATH,
  PATH_EXPLANATIONS_PATH,
  PATH_ROUTE_CONFIG_PATH,
] as const;

export class PathLoadError extends Error {
  constructor(public readonly status: "incompatible_release" | "tampered_path_index" | "runtime_calculation_failed") {
    super(status);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

async function digestHex(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) throw new PathLoadError("runtime_calculation_failed");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function fetchArtifact(
  base: URL,
  filename: string,
  file: { bytes: number; sha256: string },
  fetcher: typeof fetch,
) {
  const response = await fetcher(new URL(filename, base).href, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new PathLoadError("runtime_calculation_failed");
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== file.bytes || await digestHex(bytes) !== file.sha256.replace(/^sha256:/, "")) {
    throw new PathLoadError("tampered_path_index");
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes)) as unknown;
  } catch {
    throw new PathLoadError("tampered_path_index");
  }
}

function assertBundleShape(
  graph: unknown,
  index: unknown,
  algorithm: unknown,
  explanations: unknown,
  routeConfig: unknown,
): asserts graph is PathGraphInput {
  const artistCount = isRecord(graph) && Array.isArray(graph.artists) ? graph.artists.length : -1;
  const relationshipCount = isRecord(graph) && Array.isArray(graph.relationships) ? graph.relationships.length : -1;
  const expectedPairCount = artistCount >= 0 ? artistCount * (artistCount - 1) / 2 : -1;
  if (
    !isRecord(graph) || graph.entity_type !== "art_path_graph_input" || graph.release_id !== PATH_ART_RELEASE_ID ||
    !Array.isArray(graph.artists) || graph.artists.length === 0 || !Array.isArray(graph.relationships) ||
    !isRecord(graph.counts) || graph.counts.artists !== artistCount || graph.counts.relationships !== relationshipCount ||
    !isRecord(index) || index.entity_type !== "art_path_index" || index.release_id !== PATH_ART_RELEASE_ID ||
    index.input_graph_hash !== graph.graph_hash || index.default_pair_count !== expectedPairCount ||
    !Array.isArray(index.pairs) || !(
      index.pairs.length === expectedPairCount ||
      (index.pairs.length === 0 && index.computed_at_runtime === true)
    ) ||
    !isRecord(algorithm) || algorithm.entity_type !== "art_path_algorithm_contract" ||
    algorithm.algorithm_version !== "museum-paths-bibfs-yen-1.0.0" ||
    !isRecord(explanations) || explanations.entity_type !== "art_path_explanation_collection" ||
    explanations.input_graph_hash !== graph.graph_hash || !Array.isArray(explanations.explanations) ||
    explanations.explanations.length !== relationshipCount ||
    !isRecord(routeConfig) || routeConfig.route !== "#/art/paths" || routeConfig.storage !== "none" ||
    routeConfig.analytics !== false || routeConfig.external_runtime_api !== false
  ) throw new PathLoadError("tampered_path_index");
  const graphIds = new Set((graph.relationships as Array<Record<string, unknown>>).map((item) => item.id));
  if (
    graphIds.size !== relationshipCount ||
    new Set((graph.artists as Array<Record<string, unknown>>).map((item) => item.id)).size !== artistCount ||
    (graph.relationships as Array<Record<string, unknown>>).some((edge) =>
      edge.level !== "C" || edge.directed !== false || edge.is_algorithmic !== false || edge.computational_similarity !== null
    ) ||
    (index.pairs as Array<Record<string, unknown>>).some((pair) =>
      !isRecord(pair.modes) ||
      !["comparison", "context", "historical"].every((mode) => isRecord(pair.modes) && isRecord(pair.modes[mode]))
    )
  ) throw new PathLoadError("tampered_path_index");
}

function normalizePathGraph(graph: PathGraphInput, release: ArtConstellationRelease): PathGraphInput {
  const releaseArtists = new Map(release.artists.map((artist) => [artist.id, artist]));
  const artists = graph.artists.map((artist) => {
    const source = artist as unknown as Record<string, unknown>;
    const releaseArtist = releaseArtists.get(artist.id);
    if (!releaseArtist) throw new PathLoadError("tampered_path_index");
    const aliases = Array.isArray(source.aliases)
      ? source.aliases
      : releaseArtist.aliases.map((text) => ({ language: "und", text }));
    return {
      ...artist,
      aliases: aliases as PathGraphInput["artists"][number]["aliases"],
      life_span: isRecord(source.life_span)
        ? source.life_span as PathGraphInput["artists"][number]["life_span"]
        : { birth_year: null, death_year: null },
      public_display: source.public_display === undefined ? true : source.public_display === true,
      review_status: typeof source.review_status === "string" ? source.review_status : "publishable",
      lifecycle_status: typeof source.lifecycle_status === "string" ? source.lifecycle_status : "published",
      withdrawn: source.withdrawn === true,
    };
  });
  const artistById = new Map(artists.map((artist) => [artist.id, artist]));
  const relationships = graph.relationships.map((relationship) => {
    const source = relationship as unknown as Record<string, unknown>;
    const relationshipType = typeof source.type === "string"
      ? source.type
      : typeof source.relationship_type === "string"
        ? source.relationship_type
        : null;
    const sourceArtist = artistById.get(relationship.source_artist_id);
    const targetArtist = artistById.get(relationship.target_artist_id);
    if (
      !relationshipType || !["shared_material", "shared_subject", "shared_technique"].includes(relationshipType) ||
      !sourceArtist || !targetArtist ||
      (source.rights_visibility !== undefined && source.rights_visibility !== "public")
    ) throw new PathLoadError("tampered_path_index");
    return {
      ...relationship,
      release_id: typeof source.release_id === "string" ? source.release_id : graph.release_id,
      type: relationshipType,
      public_display: source.public_display === undefined ? true : source.public_display === true,
      review_status: typeof source.review_status === "string" ? source.review_status : "publishable",
      lifecycle_status: typeof source.lifecycle_status === "string" ? source.lifecycle_status : "published",
      withdrawn: source.withdrawn === true,
      deprecated: source.deprecated === true,
      rights_visibility: "public" as const,
      periods: Array.isArray(source.periods)
        ? source.periods as string[]
        : [...new Set([...sourceArtist.periods, ...targetArtist.periods])],
      regions: Array.isArray(source.regions)
        ? source.regions as string[]
        : [...new Set([...sourceArtist.regions, ...targetArtist.regions])],
      why_connected: {
        "zh-Hans": publicNarrativeText(relationship.why_connected["zh-Hans"]),
        en: publicNarrativeText(relationship.why_connected.en),
      },
      does_not_prove: {
        "zh-Hans": publicNarrativeText(relationship.does_not_prove["zh-Hans"]),
        en: publicNarrativeText(relationship.does_not_prove.en),
      },
    };
  });
  return { ...graph, artists, relationships };
}

let bundlePromise: Promise<PathwayBundle> | null = null;

export function loadPathwayBundle(fetcher: typeof fetch = fetch): Promise<PathwayBundle> {
  if (fetcher !== fetch) return loadPathwayBundleUncached(fetcher);
  bundlePromise ??= loadPathwayBundleUncached(fetcher).catch((error) => {
    bundlePromise = null;
    throw error;
  });
  return bundlePromise;
}

async function loadPathwayBundleUncached(fetcher: typeof fetch): Promise<PathwayBundle> {
  const base = new URL(currentArtReleaseBaseUrl(), typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new PathLoadError("runtime_calculation_failed");
  const [manifestResult, releaseResult] = await Promise.all([
    loadStaticRelease(new URL("manifest.json", base).href, fetcher),
    loadArtConstellationRelease(base.href, fetcher),
  ]);
  if (
    manifestResult.status !== "loaded" || releaseResult.status !== "loaded" ||
    manifestResult.manifest.id !== CURRENT_ART_RELEASE_ID || manifestResult.manifest.version !== CURRENT_ART_RELEASE_VERSION
  ) throw new PathLoadError("incompatible_release");
  const fileByPath = new Map(manifestResult.manifest.manifest_files.map((file) => [file.path, file]));
  const files = REQUIRED_FILES.map((filename) => {
    const file = fileByPath.get(filename);
    if (!file || file.schema_path !== "schemas/art/release/art-pathways-artifact.schema.json") {
      throw new PathLoadError("tampered_path_index");
    }
    return file;
  });
  const [algorithm, graph, index, explanations, routeConfig] = await Promise.all(
    REQUIRED_FILES.map((filename, position) => fetchArtifact(base, filename, files[position], fetcher)),
  );
  assertBundleShape(graph, index, algorithm, explanations, routeConfig);
  const normalizedGraph = normalizePathGraph(graph, releaseResult.release);
  return {
    release: releaseResult.release,
    dataSource: releaseResult.dataSource,
    graph: normalizedGraph,
    index: index as PathIndex,
    algorithm: algorithm as PathAlgorithmContract,
    explanations: explanations as PathExplanationCollection,
    routeConfig: routeConfig as PathRouteConfig,
  };
}
