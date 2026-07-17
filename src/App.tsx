import { lazy, Suspense } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import { SiteChrome } from "./components/SiteChrome";
import { I18nProvider } from "./i18n/I18nProvider";
import { AboutPage } from "./pages/AboutPage";
import { AccessibilityPage } from "./pages/AccessibilityPage";
import { ArtFoyerPage } from "./pages/ArtFoyerPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PreferencesProvider } from "./preferences/PreferencesProvider";
import { preloadArtConstellationRoute } from "./features/art-constellation/route-loader";
import { preloadArtGalleryRoute } from "./features/art-gallery/route-loader";
import { preloadArtPathsRoute } from "./features/art-paths/route-loader";
import { preloadArtMapRoute } from "./features/art-map/route-loader";

const ArtConstellationPage = lazy(preloadArtConstellationRoute);
const ArtGalleryRoute = lazy(preloadArtGalleryRoute);
const ArtPathsPage = lazy(preloadArtPathsRoute);
const ArtMapPage = lazy(preloadArtMapRoute);

const galleryFallback = (
  <main id="main-content" className="inner-page route-loading" tabIndex={-1}>
    <p role="status">正在加载数字展厅…… / Loading digital galleries…</p>
  </main>
);

export function App() {
  return (
    <I18nProvider>
      <PreferencesProvider>
        <HashRouter>
          <SiteChrome>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/art" element={<ArtFoyerPage />} />
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
              <Route path="/art/tours" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
              <Route path="/art/tours/:tourId" element={<Suspense fallback={galleryFallback}><ArtGalleryRoute /></Suspense>} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/accessibility" element={<AccessibilityPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </SiteChrome>
        </HashRouter>
      </PreferencesProvider>
    </I18nProvider>
  );
}
