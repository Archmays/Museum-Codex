import { useEffect, useMemo, useRef, useState } from "react";
import type { MediaAsset } from "./types";
import { isKnownArtReleaseAssetPath } from "../../data/art-release-profile";

type ArtworkImageProps = {
  artworkId: string;
  representativeMediaId: string | null;
  media: MediaAsset[];
  alt: string;
  lowBandwidth: boolean;
  variant?: "representative" | "thumbnail";
  noImageText: string;
  lowBandwidthText: string;
  loadImageText: string;
  imageLoadingText: string;
  imageLoadedText: string;
  unavailableText: string;
  rightsLabel: string;
  withdrawalLabel: string;
  officialSourceLabel: string;
  officialSourceUrl: string | null;
};

function allowedReleaseAsset(asset: MediaAsset) {
  try {
    const url = new URL(asset.src, window.location.href);
    return (
      url.origin === window.location.origin &&
      isKnownArtReleaseAssetPath(url.pathname)
    );
  } catch {
    return false;
  }
}

function srcSet(assets: MediaAsset[]) {
  return assets
    .sort((left, right) => left.width - right.width)
    .map((asset) => `${asset.src} ${asset.width}w`)
    .join(", ");
}

export function ArtworkImage({
  artworkId,
  representativeMediaId,
  media,
  alt,
  lowBandwidth,
  variant = "representative",
  noImageText,
  lowBandwidthText,
  loadImageText,
  imageLoadingText,
  imageLoadedText,
  unavailableText,
  rightsLabel,
  withdrawalLabel,
  officialSourceLabel,
  officialSourceUrl,
}: ArtworkImageProps) {
  const [explicitlyLoadedArtworkId, setExplicitlyLoadedArtworkId] = useState<string | null>(null);
  const [failedArtworkId, setFailedArtworkId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState<{ artworkId: string; text: string; focus: boolean } | null>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const explicitlyLoaded = explicitlyLoadedArtworkId === artworkId;
  const failed = failedArtworkId === artworkId;
  const currentAnnouncement = announcement?.artworkId === artworkId ? announcement.text : "";

  useEffect(() => {
    if (announcement?.artworkId === artworkId && announcement.focus) statusRef.current?.focus();
  }, [announcement, artworkId]);

  const assets = useMemo(() => {
    const permitted = media.filter((asset) => asset.artworkId === artworkId && allowedReleaseAsset(asset));
    const maxWidth = variant === "thumbnail" ? 640 : 960;
    const preferred = permitted.filter((asset) => asset.width <= maxWidth);
    return preferred.length > 0 ? preferred : permitted;
  }, [artworkId, media, variant]);
  const jpegAssets = assets.filter((asset) => asset.format === "jpeg");
  const webpAssets = assets.filter((asset) => asset.format === "webp");
  const representative = assets.find((asset) => asset.id === representativeMediaId)
    ?? jpegAssets.at(-1)
    ?? webpAssets.at(-1)
    ?? null;
  const fallback = jpegAssets.find((asset) => asset.width >= 640) ?? jpegAssets.at(-1) ?? representative;
  const shouldCreateImage = Boolean(representative && fallback && !failed && (!lowBandwidth || explicitlyLoaded));
  const sizes = variant === "thumbnail" ? "(max-width: 760px) 44vw, 240px" : "(max-width: 760px) 86vw, 420px";

  if (!representative || !fallback) {
    return <div className="artwork-no-image" role="img" aria-label={noImageText}><span>{noImageText}</span></div>;
  }

  return (
    <figure className={`artwork-image artwork-image-${variant}`} data-media-id={representative.id}>
      {!shouldCreateImage ? (
        <div className="artwork-image-gate">
          <p>{failed ? unavailableText : lowBandwidthText}</p>
          {!failed && lowBandwidth ? (
            <button
              type="button"
              onClick={() => {
                setAnnouncement({ artworkId, text: imageLoadingText, focus: true });
                setExplicitlyLoadedArtworkId(artworkId);
              }}
            >
              {loadImageText}
            </button>
          ) : null}
        </div>
      ) : (
        <picture>
          {webpAssets.length > 0 ? <source type="image/webp" srcSet={srcSet([...webpAssets])} sizes={sizes} /> : null}
          <img
            src={fallback.src}
            srcSet={jpegAssets.length > 0 ? srcSet([...jpegAssets]) : undefined}
            sizes={sizes}
            width={fallback.width}
            height={fallback.height}
            alt={alt}
            loading="lazy"
            decoding="async"
            onLoad={() => {
              if (explicitlyLoaded) setAnnouncement({ artworkId, text: imageLoadedText, focus: false });
            }}
            onError={() => {
              setFailedArtworkId(artworkId);
              setAnnouncement({ artworkId, text: unavailableText, focus: false });
            }}
          />
        </picture>
      )}
      <div
        ref={statusRef}
        className="artwork-image-status"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        tabIndex={-1}
      >
        {currentAnnouncement}
      </div>
      <figcaption>
        <p><strong>{rightsLabel}</strong> {representative.attribution}</p>
        <p>
          <a href={representative.licenseUrl}>{representative.licenseIdentifier}</a>
          <span aria-hidden="true"> · </span>
          <span>{representative.changesStatement}</span>
        </p>
        <p><strong>{withdrawalLabel}</strong> {representative.withdrawalNotice}</p>
        {officialSourceUrl ? <a href={officialSourceUrl}>{officialSourceLabel}</a> : null}
      </figcaption>
    </figure>
  );
}
