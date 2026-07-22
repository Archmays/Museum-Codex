export const CORE_ART_RELEASE_ID = "release:art-constellation-1.0.0";
export const INTERACTION_ART_RELEASE_ID = "release:art-expansion-batch-01-1.5.0";
export const INTERACTION_ART_RELEASE_VERSION = "1.5.0";
export const PATH_ART_RELEASE_ID = "release:art-expansion-batch-01-1.5.0";
export const PATH_ART_RELEASE_VERSION = "1.5.0";
export const TIME_PLACE_ART_RELEASE_ID = "release:art-expansion-batch-01-1.5.0";
export const TIME_PLACE_ART_RELEASE_VERSION = "1.5.0";
export const CURRENT_ART_RELEASE_ID = "release:art-expansion-batch-01-1.5.0";
export const CURRENT_ART_RELEASE_VERSION = "1.5.0";
export const CURRENT_ART_RELEASE_DIRECTORY = "art-expansion-batch-01-1.5.0";
export const INTERACTION_INDEX_PATH = "interaction-index.json";
export const PATH_ALGORITHM_PATH = "path-algorithm-contract.json";
export const PATH_GRAPH_PATH = "path-graph-input.json";
export const PATH_INDEX_PATH = "path-index.json";
export const PATH_EXPLANATIONS_PATH = "path-explanations.json";
export const PATH_ROUTE_CONFIG_PATH = "path-route-config.json";

export function currentArtReleaseBaseUrl() {
  return `${import.meta.env.BASE_URL}releases/${CURRENT_ART_RELEASE_DIRECTORY}/`;
}

export function timePlaceArtReleaseBaseUrl() {
  return currentArtReleaseBaseUrl();
}

export function isKnownArtReleaseAssetPath(pathname: string) {
  return /\/releases\/[a-z0-9._-]+\/assets\/(?:[a-z0-9._-]+\/[0-9]+w|sha256\/[a-f0-9]{2}\/[a-f0-9]{64})\.(?:jpe?g|webp)$/i.test(pathname);
}
