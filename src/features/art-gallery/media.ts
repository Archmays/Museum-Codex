import { localize, type ArtworkRecord, type MediaAsset } from "../art-constellation/types";
import type { Locale } from "../../i18n/translations";

export function isLocalApprovedAsset(asset: MediaAsset) {
  try {
    const url = new URL(asset.src, window.location.href);
    return (
      url.origin === window.location.origin &&
      /\/releases\/art-constellation-1\.0\.0\/assets\/[a-z0-9._-]+\/[0-9]+w\.(?:jpe?g|webp)$/i.test(url.pathname)
    );
  } catch {
    return false;
  }
}

export function mediaForArtwork(media: MediaAsset[], artworkId: string) {
  return media
    .filter((asset) => asset.artworkId === artworkId && isLocalApprovedAsset(asset))
    .sort((left, right) => left.width - right.width || left.format.localeCompare(right.format));
}

export function largestArtworkAsset(media: MediaAsset[], artworkId: string) {
  const assets = mediaForArtwork(media, artworkId);
  return assets.filter((asset) => asset.format === "jpeg").at(-1) ?? assets.at(-1) ?? null;
}

export function artworkPath(artworkId: string) {
  return `/art/artworks/${encodeURIComponent(artworkId)}`;
}

export function artistPath(artistId: string) {
  return `/art/artists/${encodeURIComponent(artistId)}`;
}

export function factualArtworkAlt(artistName: string, artwork: ArtworkRecord, date: string | null, locale: Locale) {
  return [artistName, localize(artwork.title, locale), date].filter(Boolean).join(", ");
}
