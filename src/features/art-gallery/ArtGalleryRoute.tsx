import { lazy, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { galleryCopy } from "./copy";
import { loadArtGalleryData } from "./gallery-data";
import type { ArtGalleryData } from "./gallery-types";
import "./art-gallery-shell.css";

const ArtistIndexPage = lazy(() => import("./artists/ArtistIndexPage").then((module) => ({ default: module.ArtistIndexPage })));
const ArtistGalleryPage = lazy(() => import("./artists/ArtistGalleryPage").then((module) => ({ default: module.ArtistGalleryPage })));
const ArtworkDetailPage = lazy(() => import("./artwork/ArtworkDetailPage").then((module) => ({ default: module.ArtworkDetailPage })));
const ComparePage = lazy(() => import("./compare/ComparePage").then((module) => ({ default: module.ComparePage })));
const ToursPage = lazy(() => import("./tours/ToursPage").then((module) => ({ default: module.ToursPage })));

type GalleryLoadState =
  | { attempt: number; status: "loading" }
  | { attempt: number; status: "loaded"; data: ArtGalleryData }
  | { attempt: number; status: "failed" };

function routeId(pathname: string, kind: "artists" | "artworks" | "tours") {
  const match = new RegExp(`^/art/${kind}/([^/]+)$`).exec(pathname);
  if (!match?.[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function ArtGalleryRoute() {
  const { locale } = useI18n();
  const copy = galleryCopy[locale];
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<GalleryLoadState>({ attempt: 0, status: "loading" });
  const visibleState: GalleryLoadState = state.attempt === attempt
    ? state
    : { attempt, status: "loading" };

  useEffect(() => {
    let active = true;
    void loadArtGalleryData().then(
      (data) => { if (active) setState({ attempt, status: "loaded", data }); },
      () => { if (active) setState({ attempt, status: "failed" }); },
    );
    return () => { active = false; };
  }, [attempt]);

  useEffect(() => {
    (mainRef.current ?? document.getElementById("main-content"))?.focus({ preventScroll: true });
  }, [location.pathname, visibleState.status]);

  if (visibleState.status === "loading") {
    return (
      <main ref={mainRef} id="main-content" className="inner-page gallery-route-state" tabIndex={-1}>
        <div className="gallery-state-mark" aria-hidden="true"><span /></div>
        <p role="status">{copy.loading}</p>
      </main>
    );
  }

  if (visibleState.status === "failed") {
    return (
      <main ref={mainRef} id="main-content" className="inner-page gallery-route-state" tabIndex={-1}>
        <div className="gallery-state-mark" aria-hidden="true"><span /></div>
        <p className="eyebrow">{copy.artistIndexEyebrow}</p>
        <h1>{copy.loadErrorTitle}</h1>
        <p>{copy.loadErrorText}</p>
        <div className="gallery-state-actions">
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>{locale === "zh-CN" ? "重新核对" : "Try again"}</button>
          <Link to="/art/constellation">← {copy.backConstellation}</Link>
        </div>
      </main>
    );
  }

  const artistId = routeId(location.pathname, "artists");
  const artworkId = routeId(location.pathname, "artworks");
  const tourId = routeId(location.pathname, "tours");
  if (artistId) return <div data-museum05a-status="ready" data-gallery-route="artist"><ArtistGalleryPage {...visibleState.data} artistId={artistId} /></div>;
  if (artworkId) return <div data-museum05a-status="ready" data-gallery-route="artwork"><ArtworkDetailPage {...visibleState.data} artworkId={artworkId} /></div>;
  if (location.pathname === "/art/compare") return <div data-museum05a-status="ready" data-gallery-route="compare"><ComparePage {...visibleState.data} /></div>;
  if (location.pathname === "/art/tours") return <div data-museum05a-status="ready" data-gallery-route="tours"><ToursPage {...visibleState.data} tourId={null} /></div>;
  if (location.pathname.startsWith("/art/tours/")) return <div data-museum05a-status="ready" data-gallery-route="tour"><ToursPage {...visibleState.data} tourId={tourId ?? "invalid:tour-route"} /></div>;
  return <div data-museum05a-status="ready" data-gallery-route="artists"><ArtistIndexPage {...visibleState.data} /></div>;
}

export default ArtGalleryRoute;
