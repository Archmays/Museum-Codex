import {
  INTERACTION_ART_RELEASE_ID,
  INTERACTION_ART_RELEASE_VERSION,
  INTERACTION_INDEX_PATH,
} from "../../data/art-release-profile";
import { loadStaticRelease } from "../../data/release-loader";
import type { ArtInteractionIndex } from "./interaction-types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasLocalizedText(value: unknown) {
  return isRecord(value) && typeof value["zh-Hans"] === "string" && Boolean(value["zh-Hans"]) && typeof value.en === "string" && Boolean(value.en);
}

function publicNarrativeText(value: string) {
  return value
    .replace(/\breviewed\b/gi, "source-supported")
    .replace(/经审核的?/g, "有来源支持的");
}

function naturalizeLocalizedText(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(naturalizeLocalizedText);
  if (!isRecord(value)) return value;
  const result = Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, naturalizeLocalizedText(entry)]));
  if (hasLocalizedText(value)) {
    result["zh-Hans"] = publicNarrativeText(String(value["zh-Hans"]));
    result.en = publicNarrativeText(String(value.en));
  }
  return result;
}

async function digestHex(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) throw new Error("web_crypto_unavailable");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function parseInteractionIndex(value: unknown): ArtInteractionIndex {
  if (!isRecord(value)) throw new Error("interaction_not_object");
  const counts = value.counts;
  const cards = value.observation_cards;
  const heroes = value.hero_selections;
  const regions = value.detail_regions;
  const artistTours = value.artist_tours;
  const thematicTours = value.thematic_tours;
  const lenses = value.lenses;
  const composition = value.release_composition;
  const integerCount = (item: unknown) => typeof item === "number" && Number.isInteger(item) && item >= 0;
  if (
    value.schema_version !== "1.0.0" || value.id !== "interaction-index:museum-05b-v1" ||
    value.release_id !== INTERACTION_ART_RELEASE_ID || value.release_version !== INTERACTION_ART_RELEASE_VERSION ||
    !isRecord(composition) || composition.mode !== "immutable_overlay" ||
    composition.base_release_id !== "release:art-constellation-1.0.0" ||
    composition.base_artifact_identity !== "base_release_scoped" ||
    !isRecord(counts) ||
    ![
      counts.artists, counts.artworks, counts.observation_cards, counts.hero_selections,
      counts.visual_heroes, counts.textual_observation_paths, counts.detail_regions,
      counts.artist_tours, counts.thematic_tours, counts.lenses,
    ].every(integerCount) ||
    !Array.isArray(cards) || cards.length !== counts.observation_cards ||
    !Array.isArray(heroes) || heroes.length !== counts.hero_selections ||
    !Array.isArray(regions) || regions.length !== counts.detail_regions ||
    !Array.isArray(artistTours) || artistTours.length !== counts.artist_tours ||
    !Array.isArray(thematicTours) || thematicTours.length !== counts.thematic_tours ||
    !Array.isArray(lenses) || lenses.length !== counts.lenses ||
    counts.artworks !== counts.observation_cards ||
    counts.artists !== counts.hero_selections ||
    counts.artists !== counts.artist_tours ||
    Number(counts.visual_heroes) + Number(counts.textual_observation_paths) !== counts.artists
  ) throw new Error("interaction_profile_invalid");
  if (
    cards.some((card) => !isRecord(card) || typeof card.artwork_id !== "string" || !hasLocalizedText(card.title) || !Array.isArray(card.prompts) || !Array.isArray(card.source_links) || card.release_version !== "1.1.0") ||
    heroes.some((hero) => !isRecord(hero) || typeof hero.artist_id !== "string" || typeof hero.artwork_id !== "string") ||
    regions.some((region) => !isRecord(region) || region.semantic_label !== null || !hasLocalizedText(region.label)) ||
    artistTours.some((tour) => !isRecord(tour) || tour.kind !== "artist" || tour.algorithmic !== false || !hasLocalizedText(tour.title)) ||
    thematicTours.some((tour) => !isRecord(tour) || tour.kind !== "thematic" || tour.pathfinding !== false || tour.automatic_recommendation !== false || !hasLocalizedText(tour.title)) ||
    lenses.some((lens) => !isRecord(lens) || !Array.isArray(lens.entries) || lens.entries.some((entry) => !isRecord(entry) || !Array.isArray(entry.evidence_ids) || !Array.isArray(entry.source_links)))
  ) throw new Error("interaction_record_invalid");
  const cardIds = new Set(cards.map((card) => (card as Record<string, unknown>).artwork_id));
  const heroArtists = new Set(heroes.map((hero) => (hero as Record<string, unknown>).artist_id));
  if (cardIds.size !== cards.length || heroArtists.size !== heroes.length) throw new Error("interaction_reference_duplicates");
  return naturalizeLocalizedText(value) as ArtInteractionIndex;
}

export async function loadArtInteractionIndex(baseUrl: string, fetcher: typeof fetch = fetch): Promise<ArtInteractionIndex> {
  const base = new URL(baseUrl, typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new Error("interaction_cross_origin");
  const manifestResult = await loadStaticRelease(new URL("manifest.json", base).href, fetcher);
  if (manifestResult.status !== "loaded") throw new Error(`interaction_manifest_${manifestResult.status}`);
  const { manifest } = manifestResult;
  const directInteractionRelease = manifest.id === INTERACTION_ART_RELEASE_ID && manifest.version === INTERACTION_ART_RELEASE_VERSION;
  const file = manifest.manifest_files.find((item) =>
    item.path === INTERACTION_INDEX_PATH &&
    item.schema_path === "schemas/art/release/art-gallery-interaction-index.schema.json" &&
    item.record_type === "other" &&
    (item.record_ids.length === 0 ||
      (item.record_ids.length === 1 && item.record_ids[0] === "interaction-index:museum-05b-v1"))
  );
  if (!file || (!directInteractionRelease && manifest.predecessor === null)) {
    throw new Error("interaction_manifest_file_missing");
  }
  const response = await fetcher(new URL(INTERACTION_INDEX_PATH, base).href, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`interaction_http_${response.status}`);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== file.bytes || await digestHex(bytes) !== file.sha256.replace(/^sha256:/, "")) {
    throw new Error("interaction_bytes_invalid");
  }
  return parseInteractionIndex(JSON.parse(new TextDecoder().decode(bytes)));
}
