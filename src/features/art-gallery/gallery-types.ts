import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtworkCatalog,
} from "../art-constellation/types";
import type { ArtInteractionIndex } from "./interaction-types";

export type GallerySharedProps = {
  release: ArtConstellationRelease;
  catalog: ArtworkCatalog;
  dataSource: ArtConstellationDataSource;
  interactions: ArtInteractionIndex;
};

export type ArtGalleryData = GallerySharedProps;
