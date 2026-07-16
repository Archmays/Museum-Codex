import { loadArtConstellationRelease } from "../../data/release-loader";
import { currentArtReleaseBaseUrl } from "../../data/art-release-profile";
import { loadArtInteractionIndex } from "./interaction-loader";
import type { ArtGalleryData } from "./gallery-types";

let galleryDataPromise: Promise<ArtGalleryData> | null = null;

export function loadArtGalleryData(): Promise<ArtGalleryData> {
  if (!galleryDataPromise) {
    const baseUrl = currentArtReleaseBaseUrl();
    galleryDataPromise = Promise.all([loadArtConstellationRelease(baseUrl), loadArtInteractionIndex(baseUrl)]).then(async ([result, interactions]) => {
      if (result.status !== "loaded") throw new Error(result.reason);
      const catalogResult = await result.dataSource.loadArtworkCatalog();
      if (catalogResult.status !== "loaded") throw new Error(catalogResult.reason);
      if (
        result.release.artists.length !== 12 ||
        catalogResult.data.artworks.length !== 44 ||
        catalogResult.data.media.length !== 242
      ) throw new Error("gallery_release_counts_invalid");
      if (
        interactions.observation_cards.some((card) => !catalogResult.data.artworks.some((artwork) => artwork.id === card.artwork_id)) ||
        interactions.hero_selections.some((hero) => !result.release.artists.some((artist) => artist.id === hero.artist_id))
      ) throw new Error("gallery_interaction_reference_invalid");
      return { release: result.release, dataSource: result.dataSource, catalog: catalogResult.data, interactions };
    }).catch((error) => {
      galleryDataPromise = null;
      throw error;
    });
  }
  return galleryDataPromise;
}
