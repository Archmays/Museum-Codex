import { lazy, Suspense } from "react";
import { HashRouter, Route, Routes, useLocation } from "react-router-dom";
import { RouteErrorBoundary } from "./components/RouteErrorBoundary";
import { SiteChrome } from "./components/SiteChrome";
import { I18nProvider, useI18n } from "./i18n/I18nProvider";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PreferencesProvider } from "./preferences/PreferencesProvider";
import { preloadArtConstellationRoute } from "./features/art-constellation/route-loader";
import { preloadArtGalleryRoute } from "./features/art-gallery/route-loader";
import { preloadArtPathsRoute } from "./features/art-paths/route-loader";
import { preloadArtMapRoute } from "./features/art-map/route-loader";
import { preloadArtSearchRoute } from "./features/art-search/route-loader";

const ArtConstellationPage = lazy(preloadArtConstellationRoute);
const ArtGalleryRoute = lazy(preloadArtGalleryRoute);
const ArtPathsPage = lazy(preloadArtPathsRoute);
const ArtMapPage = lazy(preloadArtMapRoute);
const ArtSearchPage = lazy(preloadArtSearchRoute);
const AboutPage = lazy(() => import("./pages/AboutPage").then((module) => ({ default: module.AboutPage })));
const AccessibilityPage = lazy(() => import("./pages/AccessibilityPage").then((module) => ({ default: module.AccessibilityPage })));
const ArtFoyerPage = lazy(() => import("./pages/ArtFoyerPage").then((module) => ({ default: module.ArtFoyerPage })));

const galleryFallback = (
  <main id="main-content" className="inner-page route-loading" tabIndex={-1}>
    <p role="status">正在加载数字展厅…… / Loading digital galleries…</p>
  </main>
);
const pageFallback = (
  <main id="main-content" className="inner-page route-loading" tabIndex={-1}>
    <p role="status">正在载入页面…… / Loading page…</p>
  </main>
);

function MuseumRoutes() {
  const { locale } = useI18n();
  const { pathname } = useLocation();
  return (
    <RouteErrorBoundary key={pathname} locale={locale}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/art" element={<Suspense fallback={pageFallback}><ArtFoyerPage /></Suspense>} />
        <Route
          path="/art/constellation"
          element={
            <Suspense fallback={<main id="main-content" className="inner-page route-loading" tabIndex={-1}><p role="status">正在加载艺术星海…… / Loading Art Constellation…</p></main>}>
              <ArtConstellationPage />
            </Suspense>
          }
        />
        <Route path="/art/artists" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/art/artists/:artistId" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/art/artworks/:artworkId" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/art/compare" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/art/paths" element={<Suspense fallback={galleryFallback}><ArtPathsPage /></Suspense>} />
        <Route path="/art/map" element={<Suspense fallback={<main id="main-content" className="inner-page route-loading" tabIndex={-1}><p role="status">正在加载艺术时空地图…… / Loading Art Across Time and Place…</p></main>}><ArtMapPage /></Suspense>} />
        <Route path="/art/search" element={<Suspense fallback={<main id="main-content" className="inner-page route-loading" tabIndex={-1}><p role="status">正在加载本地搜索…… / Loading local search…</p></main>}><ArtSearchPage /></Suspense>} />
        <Route path="/art/tours" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/art/tours/:tourId" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
        <Route path="/about" element={<Suspense fallback={pageFallback}><AboutPage /></Suspense>} />
        <Route path="/rights" element={<Suspense fallback={pageFallback}><AboutPage /></Suspense>} />
        <Route path="/accessibility" element={<Suspense fallback={pageFallback}><AccessibilityPage /></Suspense>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </RouteErrorBoundary>
  );
}

export function App() {
  return (
    <I18nProvider>
      <PreferencesProvider>
        <HashRouter>
          <SiteChrome>
            <MuseumRoutes />
          </SiteChrome>
        </HashRouter>
      </PreferencesProvider>
    </I18nProvider>
  );
}
