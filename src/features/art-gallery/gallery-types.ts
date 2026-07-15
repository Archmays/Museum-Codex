import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtworkCatalog,
} from "../art-constellation/types";

export type GallerySharedProps = {
  release: ArtConstellationRelease;
  catalog: ArtworkCatalog;
  dataSource: ArtConstellationDataSource;
};

export type ArtGalleryData = GallerySharedProps;
