export const CORE_ART_RELEASE_ID = "release:art-constellation-1.0.0";
export const INTERACTION_ART_RELEASE_ID = "release:art-gallery-interactions-1.1.0";
export const INTERACTION_ART_RELEASE_VERSION = "1.1.0";
export const CURRENT_ART_RELEASE_ID = "release:art-pathways-1.2.0";
export const CURRENT_ART_RELEASE_VERSION = "1.2.0";
export const CURRENT_ART_RELEASE_DIRECTORY = "art-pathways-1.2.0";
export const TIME_PLACE_ART_RELEASE_ID = "release:art-time-place-1.3.0";
export const TIME_PLACE_ART_RELEASE_VERSION = "1.3.0";
export const TIME_PLACE_ART_RELEASE_DIRECTORY = "art-time-place-1.3.0";
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
  return `${import.meta.env.BASE_URL}releases/${TIME_PLACE_ART_RELEASE_DIRECTORY}/`;
}

export function isKnownArtReleaseAssetPath(pathname: string) {
  return /\/releases\/(?:art-constellation-1\.0\.0|art-gallery-interactions-1\.1\.0|art-pathways-1\.2\.0|art-time-place-1\.3\.0)\/assets\/[a-z0-9._-]+\/[0-9]+w\.(?:jpe?g|webp)$/i.test(pathname);
}
