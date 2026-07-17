import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { preloadArtConstellationData } from "./data/art-constellation-bootstrap";
import { preloadArtConstellationRoute } from "./features/art-constellation/route-loader";
import { preloadArtGalleryRoute } from "./features/art-gallery/route-loader";
import { currentArtReleaseBaseUrl } from "./data/art-release-profile";
import { preloadArtMapRoute } from "./features/art-map/route-loader";
import "./styles/global.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Application root is missing");
}

if (window.location.hash.startsWith("#/art/constellation")) {
  void preloadArtConstellationRoute();
  preloadArtConstellationData(currentArtReleaseBaseUrl());
}

if (/^#\/art\/(?:artists|artworks|compare|tours)(?:\/|$|\?)/.test(window.location.hash)) {
  void preloadArtGalleryRoute();
  preloadArtConstellationData(currentArtReleaseBaseUrl());
}

if (window.location.hash.startsWith("#/art/map")) {
  void preloadArtMapRoute();
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
