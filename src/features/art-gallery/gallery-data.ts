import { loadArtConstellationRelease } from "../../data/release-loader";
import type { ArtGalleryData } from "./gallery-types";

let galleryDataPromise: Promise<ArtGalleryData> | null = null;

export function loadArtGalleryData(): Promise<ArtGalleryData> {
  if (!galleryDataPromise) {
    const baseUrl = `${import.meta.env.BASE_URL}releases/art-constellation-1.0.0/`;
    galleryDataPromise = loadArtConstellationRelease(baseUrl).then(async (result) => {
      if (result.status !== "loaded") throw new Error(result.reason);
      const catalogResult = await result.dataSource.loadArtworkCatalog();
      if (catalogResult.status !== "loaded") throw new Error(catalogResult.reason);
      if (
        result.release.artists.length !== 12 ||
        catalogResult.data.artworks.length !== 44 ||
        catalogResult.data.media.length !== 242
      ) throw new Error("gallery_release_counts_invalid");
      return { release: result.release, dataSource: result.dataSource, catalog: catalogResult.data };
    }).catch((error) => {
      galleryDataPromise = null;
      throw error;
    });
  }
  return galleryDataPromise;
}
