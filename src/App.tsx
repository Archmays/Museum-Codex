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

const ArtConstellationPage = lazy(preloadArtConstellationRoute);

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
