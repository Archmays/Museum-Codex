import interactionIndex from "../../public/releases/art-gallery-interactions-1.1.0/interaction-index.json";
import type { ArtInteractionIndex } from "../features/art-gallery/interaction-types";
import type { ArtworkRecord } from "../features/art-constellation/types";

export const interactionFixture = interactionIndex as unknown as ArtInteractionIndex;

export function interactionFixtureFor(artworks: ArtworkRecord[]): ArtInteractionIndex {
  const template = interactionFixture.observation_cards[0];
  return {
    ...interactionFixture,
    observation_cards: artworks.map((artwork) => ({
      ...template,
      id: `observation:${artwork.id.split(":", 2)[1]}`,
      artwork_id: artwork.id,
      title: { "zh-Hans": `观察${artwork.title["zh-Hans"]}`, en: `Observe ${artwork.title.en}` },
      rights_status: artwork.media.decision,
      image_availability: artwork.media.decision === "approved_self_hosted" ? "approved_image" : "metadata_only",
      accessibility_version: {
        mode: artwork.media.decision === "approved_self_hosted" ? "image_plus_text" : "evidence_only",
        summary: template.accessibility_version.summary,
      },
    })),
    detail_regions: [],
  };
}
