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
import type { DetailRegion } from "../interaction-types";

export type ArtworkZoomProps = {
  artwork: ArtworkRecord;
  media: MediaAsset[];
  artistName: string;
  lowBandwidth: boolean;
  regions?: DetailRegion[];
  activeRegionId?: string | null;
  onRegionChange?: (regionId: string | null) => void;
  printMode?: boolean;
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

export function ArtworkZoom({
  artwork,
  media,
  artistName,
  lowBandwidth,
  regions = [],
  activeRegionId,
  onRegionChange,
  printMode = false,
}: ArtworkZoomProps) {
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
  const [internalRegionId, setInternalRegionId] = useState<string | null>(null);

  const candidates = useMemo(
    () => mediaForArtwork(media, artwork.id)
      .sort((left, right) => left.width - right.width || left.format.localeCompare(right.format)),
    [artwork.id, media],
  );
  const jpegCandidates = useMemo(
    () => candidates.filter((item) => item.format === "jpeg"),
    [candidates],
  );
  const asset = printMode
    ? (jpegCandidates.find((item) => item.width === 320) ?? jpegCandidates[0] ?? candidates[0] ?? null)
    : (jpegCandidates.at(-1) ?? candidates.at(-1) ?? null);
  const responsiveSrcSet = printMode ? "" : jpegCandidates.map((item) => `${item.src} ${item.width}w`).join(", ");
  const minimapAsset = jpegCandidates[0] ?? null;

  const activeAssetId = asset?.id ?? null;
  const activeView = view.assetId === activeAssetId ? view : initialView(activeAssetId);
  const { zoom, maximumZoom, pan } = activeView;
  const explicitlyRequested = explicitAssetId === activeAssetId;
  const failed = Boolean(activeAssetId && failedAssetId === activeAssetId);
  const loaded = Boolean(activeAssetId && loadedAssetId === activeAssetId);
  const shouldCreateImage = Boolean(asset && !failed && (printMode || !lowBandwidth || explicitlyRequested));
  const selectedRegionId = activeRegionId === undefined ? internalRegionId : activeRegionId;

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
    setInternalRegionId(null);
    onRegionChange?.(null);
  }, [onRegionChange, updateView]);

  const positionRegion = useCallback((region: DetailRegion) => {
    if (!loaded || !imageRef.current) return;
    const targetZoom = clamp(Math.max(2, zoom), 1, maximumZoom);
    const centerX = region.normalized_rect.x + region.normalized_rect.width / 2;
    const centerY = region.normalized_rect.y + region.normalized_rect.height / 2;
    const target = boundedPan({
      x: (0.5 - centerX) * imageRef.current.clientWidth * targetZoom,
      y: (0.5 - centerY) * imageRef.current.clientHeight * targetZoom,
    }, targetZoom);
    updateView((current) => ({ ...current, zoom: targetZoom, pan: target }));
    setInternalRegionId(region.id);
  }, [boundedPan, loaded, maximumZoom, updateView, zoom]);

  const jumpToRegion = useCallback((region: DetailRegion) => {
    positionRegion(region);
    onRegionChange?.(region.id);
  }, [onRegionChange, positionRegion]);

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

  useEffect(() => {
    if (activeRegionId === undefined || !loaded) return;
    const applyExternalRegion = () => {
      if (activeRegionId === null) {
        if (internalRegionId !== null) {
          updateView((current) => ({ ...current, zoom: 1, pan: { x: 0, y: 0 } }));
          setInternalRegionId(null);
        }
        return;
      }
      const region = regions.find((item) => item.id === activeRegionId);
      if (region) positionRegion(region);
    };
    const frame = typeof window.requestAnimationFrame === "function"
      ? window.requestAnimationFrame(applyExternalRegion)
      : window.setTimeout(applyExternalRegion, 0);
    return () => {
      if (typeof window.cancelAnimationFrame === "function") window.cancelAnimationFrame(frame);
      else window.clearTimeout(frame);
    };
  }, [activeRegionId, internalRegionId, loaded, positionRegion, regions, updateView]);

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
    if (["+", "=", "-", "0", "Escape", "1", "2", "3", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
    }
    if (event.key === "+" || event.key === "=") setSafeZoom(zoom + ZOOM_STEP);
    if (event.key === "-") setSafeZoom(zoom - ZOOM_STEP);
    if (event.key === "0" || event.key === "Escape") resetView();
    if (/^[1-3]$/.test(event.key)) {
      const region = regions[Number(event.key) - 1];
      if (region) jumpToRegion(region);
    }
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
              sizes={printMode ? "320px" : "(max-width: 760px) 92vw, 100vw"}
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

          {regions.length > 0 && !printMode ? (
            <section className="detail-navigator" aria-labelledby={`${instanceId}-detail-title`}>
              <div>
                <p className="eyebrow">{locale === "zh-CN" ? "细节导航" : "Detail navigation"}</p>
                <h3 id={`${instanceId}-detail-title`}>{locale === "zh-CN" ? "结构区域，不是策展结论" : "Structural regions, not curatorial conclusions"}</h3>
                <p>{locale === "zh-CN" ? "这些区域由图像结构自动选取，不代表策展结论。按 1、2、3 跳转，按 0 或 Esc 重置。" : "These regions are selected from image structure and do not represent curatorial conclusions. Press 1, 2, or 3 to jump; press 0 or Escape to reset."}</p>
                <p>{locale === "zh-CN" ? "来源图像尺寸" : "Source image dimensions"}: {asset.width} × {asset.height}</p>
              </div>
              {minimapAsset && !lowBandwidth ? (
                <div className="detail-minimap" role="img" aria-label={locale === "zh-CN" ? "细节区域小地图" : "Detail-region minimap"}>
                  <img src={minimapAsset.src} width={minimapAsset.width} height={minimapAsset.height} alt="" loading="lazy" decoding="async" />
                  {regions.map((region, index) => (
                    <span
                      key={region.id}
                      aria-hidden="true"
                      data-current={selectedRegionId === region.id ? "true" : "false"}
                      style={{ left: `${region.normalized_rect.x * 100}%`, top: `${region.normalized_rect.y * 100}%`, width: `${region.normalized_rect.width * 100}%`, height: `${region.normalized_rect.height * 100}%` }}
                    >{index + 1}</span>
                  ))}
                </div>
              ) : null}
              <div className="detail-region-buttons" aria-label={locale === "zh-CN" ? "选择细节区域" : "Choose a detail region"}>
                {regions.map((region) => (
                  <button key={region.id} type="button" aria-pressed={selectedRegionId === region.id} disabled={!loaded} onClick={() => jumpToRegion(region)}>
                    {localize(region.label, locale)}
                  </button>
                ))}
                <button type="button" disabled={!loaded} onClick={resetView}>{copy.zoomReset}</button>
              </div>
              <p className="detail-region-status" role="status" aria-live="polite">
                {selectedRegionId
                  ? localize(regions.find((region) => region.id === selectedRegionId)?.label ?? { "zh-Hans": "概览", en: "Overview" }, locale)
                  : (locale === "zh-CN" ? "当前：概览" : "Current: overview")}
              </p>
            </section>
          ) : null}

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
