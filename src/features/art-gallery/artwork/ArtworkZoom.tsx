import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import { localize, type ArtworkRecord, type MediaAsset } from "../../art-constellation/types";
import { galleryCopy, fillCopy } from "../copy";
import { factualArtworkAlt, mediaForArtwork } from "../media";

export type ArtworkZoomProps = {
  artwork: ArtworkRecord;
  media: MediaAsset[];
  artistName: string;
  lowBandwidth: boolean;
};

type Point = { x: number; y: number };
type ZoomView = { assetId: string | null; zoom: number; maximumZoom: number; pan: Point };

const ZOOM_STEP = 0.25;
const PAN_STEP = 32;
const MAX_INTERFACE_ZOOM = 4;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function initialView(assetId: string | null): ZoomView {
  return { assetId, zoom: 1, maximumZoom: 1, pan: { x: 0, y: 0 } };
}

export function ArtworkZoom({ artwork, media, artistName, lowBandwidth }: ArtworkZoomProps) {
  const { locale } = useI18n();
  const { reducedMotion } = usePreferences();
  const instanceId = useId();
  const observationTitleId = `${instanceId}-observation-title`;
  const helpId = `${instanceId}-zoom-help`;
  const statusId = `${instanceId}-zoom-status`;
  const copy = galleryCopy[locale];
  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragRef = useRef<{ pointerId: number; origin: Point; pan: Point } | null>(null);
  const [explicitAssetId, setExplicitAssetId] = useState<string | null>(null);
  const [failedAssetId, setFailedAssetId] = useState<string | null>(null);
  const [loadedAssetId, setLoadedAssetId] = useState<string | null>(null);
  const [view, setView] = useState<ZoomView>(() => initialView(null));

  const candidates = useMemo(
    () => mediaForArtwork(media, artwork.id)
      .sort((left, right) => left.width - right.width || left.format.localeCompare(right.format)),
    [artwork.id, media],
  );
  const jpegCandidates = useMemo(
    () => candidates.filter((item) => item.format === "jpeg"),
    [candidates],
  );
  const asset = jpegCandidates.at(-1) ?? candidates.at(-1) ?? null;
  const responsiveSrcSet = jpegCandidates.map((item) => `${item.src} ${item.width}w`).join(", ");

  const activeAssetId = asset?.id ?? null;
  const activeView = view.assetId === activeAssetId ? view : initialView(activeAssetId);
  const { zoom, maximumZoom, pan } = activeView;
  const explicitlyRequested = explicitAssetId === activeAssetId;
  const failed = Boolean(activeAssetId && failedAssetId === activeAssetId);
  const loaded = Boolean(activeAssetId && loadedAssetId === activeAssetId);
  const shouldCreateImage = Boolean(asset && !failed && (!lowBandwidth || explicitlyRequested));

  const updateView = useCallback((transform: (current: ZoomView) => ZoomView) => {
    setView((current) => transform(current.assetId === activeAssetId ? current : initialView(activeAssetId)));
  }, [activeAssetId]);

  const panBounds = useCallback((atZoom: number) => {
    const viewport = viewportRef.current;
    const image = imageRef.current;
    if (!viewport || !image || atZoom <= 1) return { x: 0, y: 0 };
    return {
      x: Math.max(0, (image.clientWidth * atZoom - viewport.clientWidth) / 2),
      y: Math.max(0, (image.clientHeight * atZoom - viewport.clientHeight) / 2),
    };
  }, []);

  const boundedPan = useCallback((next: Point, atZoom: number) => {
    const bounds = panBounds(atZoom);
    return {
      x: clamp(next.x, -bounds.x, bounds.x),
      y: clamp(next.y, -bounds.y, bounds.y),
    };
  }, [panBounds]);

  const resetView = useCallback(() => {
    updateView((current) => ({ ...current, zoom: 1, pan: { x: 0, y: 0 } }));
  }, [updateView]);

  const recalculateMaximumZoom = useCallback(() => {
    if (!asset || !imageRef.current) {
      resetView();
      return;
    }
    const renderedWidth = imageRef.current.clientWidth;
    const currentSrc = imageRef.current.currentSrc;
    const selectedCandidate = currentSrc
      ? jpegCandidates.find((candidate) => new URL(candidate.src, window.location.href).href === currentSrc)
      : null;
    // Width-descriptor srcset can expose a density-corrected naturalWidth.
    // The reviewed candidate record retains the selected file's real pixels.
    const decodedWidth = selectedCandidate?.width ?? (imageRef.current.naturalWidth || asset.width);
    const pixelSafeMaximum = renderedWidth > 0
      ? clamp(decodedWidth / renderedWidth, 1, MAX_INTERFACE_ZOOM)
      : 1;
    updateView((current) => {
      const nextZoom = clamp(current.zoom, 1, pixelSafeMaximum);
      return {
        ...current,
        maximumZoom: pixelSafeMaximum,
        zoom: nextZoom,
        pan: boundedPan(current.pan, nextZoom),
      };
    });
  }, [asset, boundedPan, jpegCandidates, resetView, updateView]);

  useEffect(() => {
    if (!loaded || !imageRef.current) return;
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(recalculateMaximumZoom);
    observer.observe(imageRef.current);
    return () => observer.disconnect();
  }, [loaded, recalculateMaximumZoom]);

  const setSafeZoom = useCallback((next: number) => {
    const bounded = clamp(next, 1, maximumZoom);
    updateView((current) => ({
      ...current,
      zoom: bounded,
      pan: bounded === 1 ? { x: 0, y: 0 } : boundedPan(current.pan, bounded),
    }));
  }, [boundedPan, maximumZoom, updateView]);

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!loaded) return;
    if (["+", "=", "-", "0", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
    }
    if (event.key === "+" || event.key === "=") setSafeZoom(zoom + ZOOM_STEP);
    if (event.key === "-") setSafeZoom(zoom - ZOOM_STEP);
    if (event.key === "0") resetView();
    if (zoom <= 1) return;
    if (event.key === "ArrowLeft") updateView((current) => ({ ...current, pan: boundedPan({ ...current.pan, x: current.pan.x - PAN_STEP }, zoom) }));
    if (event.key === "ArrowRight") updateView((current) => ({ ...current, pan: boundedPan({ ...current.pan, x: current.pan.x + PAN_STEP }, zoom) }));
    if (event.key === "ArrowUp") updateView((current) => ({ ...current, pan: boundedPan({ ...current.pan, y: current.pan.y - PAN_STEP }, zoom) }));
    if (event.key === "ArrowDown") updateView((current) => ({ ...current, pan: boundedPan({ ...current.pan, y: current.pan.y + PAN_STEP }, zoom) }));
  };

  const beginPan = (event: PointerEvent<HTMLDivElement>) => {
    if (zoom <= 1 || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      origin: { x: event.clientX, y: event.clientY },
      pan,
    };
  };

  const continuePan = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    updateView((current) => ({
      ...current,
      pan: boundedPan({
        x: drag.pan.x + event.clientX - drag.origin.x,
        y: drag.pan.y + event.clientY - drag.origin.y,
      }, zoom),
    }));
  };

  const endPan = (event: PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  };

  if (!asset || failed) {
    return (
      <section className="artwork-zoom artwork-zoom-unavailable" aria-labelledby={observationTitleId}>
        <h2 id={observationTitleId}>{copy.imageObservation}</h2>
        <div className="artwork-detail-no-image" role="img" aria-label={failed ? copy.imageUnavailable : copy.noImage}>
          <span aria-hidden="true">{failed ? "!" : "\u2205"}</span>
          <p>{failed ? copy.imageUnavailable : copy.zoomUnavailable}</p>
        </div>
        {failed ? <p className="sr-only" role="status" aria-live="polite">{copy.imageUnavailable}</p> : null}
      </section>
    );
  }

  const percent = Math.round(zoom * 100);
  const title = localize(artwork.title, locale);
  const date = artwork.dateDisplay ? localize(artwork.dateDisplay, locale) : null;

  return (
    <section className="artwork-zoom" aria-labelledby={observationTitleId}>
      <div className="artwork-zoom-heading">
        <div>
          <p className="eyebrow">{copy.imageObservation}</p>
          <h2 id={observationTitleId}>{title}</h2>
        </div>
        <p id={helpId} className="artwork-zoom-help">{copy.zoomHelp}</p>
      </div>

      {!shouldCreateImage ? (
        <div className="artwork-zoom-gate">
          <p>{copy.lowBandwidthImage}</p>
          <button type="button" onClick={() => setExplicitAssetId(asset.id)}>{copy.loadImage}</button>
        </div>
      ) : (
        <figure className="artwork-zoom-figure">
          <div
            ref={viewportRef}
            className="artwork-zoom-viewport"
            data-zoomed={zoom > 1 ? "true" : "false"}
            data-reduced-motion={reducedMotion ? "true" : "false"}
            role="group"
            aria-label={`${copy.zoomRegion}: ${title}`}
            aria-describedby={`${helpId} ${statusId}`}
            tabIndex={0}
            onKeyDown={handleKeyboard}
            onPointerDown={beginPan}
            onPointerMove={continuePan}
            onPointerUp={endPan}
            onPointerCancel={endPan}
          >
            <img
              ref={imageRef}
              src={asset.src}
              srcSet={responsiveSrcSet || undefined}
              sizes="(max-width: 760px) 92vw, 100vw"
              width={asset.width}
              height={asset.height}
              alt={factualArtworkAlt(artistName, artwork, date, locale)}
              loading="lazy"
              decoding="async"
              draggable={false}
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
              onLoad={() => {
                setLoadedAssetId(asset.id);
                recalculateMaximumZoom();
              }}
              onError={() => {
                setFailedAssetId(asset.id);
                setLoadedAssetId(null);
                resetView();
              }}
            />
          </div>

          <div className="artwork-zoom-controls" aria-label={copy.zoomRegion}>
            <button
              type="button"
              aria-label={copy.zoomOut}
              disabled={!loaded || zoom <= 1}
              onClick={() => setSafeZoom(zoom - ZOOM_STEP)}
            >
              <span aria-hidden="true">&minus;</span>
            </button>
            <output id={statusId} aria-live="polite">
              {fillCopy(copy.zoomPercent, { percent })}
            </output>
            <button
              type="button"
              aria-label={copy.zoomIn}
              disabled={!loaded || zoom >= maximumZoom}
              onClick={() => setSafeZoom(zoom + ZOOM_STEP)}
            >
              <span aria-hidden="true">+</span>
            </button>
            <button type="button" disabled={!loaded || zoom === 1} onClick={resetView}>{copy.zoomReset}</button>
          </div>

          <figcaption>
            <p><strong>{copy.imageRights}</strong> {asset.attribution}</p>
            <p>
              <a href={asset.licenseUrl}>{asset.licenseIdentifier}</a>
              <span aria-hidden="true"> &middot; </span>
              {asset.changesStatement}
            </p>
            <p><strong>{copy.withdrawalStatus}</strong> {asset.withdrawalNotice}</p>
          </figcaption>
        </figure>
      )}
      <div className="sr-only" role="status" aria-live="polite">
        {failed ? copy.imageUnavailable : loaded ? copy.imageLoaded : explicitlyRequested ? copy.imageLoading : ""}
      </div>
    </section>
  );
}
