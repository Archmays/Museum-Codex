import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { preloadArtConstellationData } from "./data/art-constellation-bootstrap";
import { preloadArtConstellationRoute } from "./features/art-constellation/route-loader";
import "./styles/global.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Application root is missing");
}

if (window.location.hash.startsWith("#/art/constellation")) {
  void preloadArtConstellationRoute();
  preloadArtConstellationData(`${import.meta.env.BASE_URL}releases/art-constellation-1.0.0/`);
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
