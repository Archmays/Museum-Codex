export const CORE_ART_RELEASE_ID = "release:art-constellation-1.0.0";
export const CURRENT_ART_RELEASE_ID = "release:art-gallery-interactions-1.1.0";
export const CURRENT_ART_RELEASE_VERSION = "1.1.0";
export const CURRENT_ART_RELEASE_DIRECTORY = "art-gallery-interactions-1.1.0";
export const INTERACTION_INDEX_PATH = "interaction-index.json";

export function currentArtReleaseBaseUrl() {
  return `${import.meta.env.BASE_URL}releases/${CURRENT_ART_RELEASE_DIRECTORY}/`;
}

export function isKnownArtReleaseAssetPath(pathname: string) {
  return /\/releases\/(?:art-constellation-1\.0\.0|art-gallery-interactions-1\.1\.0)\/assets\/[a-z0-9._-]+\/[0-9]+w\.(?:jpe?g|webp)$/i.test(pathname);
}
