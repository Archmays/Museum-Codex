import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { loadArtConstellationRelease } from "../data/release-loader";
import { loadArtInteractionIndex } from "../features/art-gallery/interaction-loader";
import { ToursPage } from "../features/art-gallery/tours/ToursPage";
import type { GallerySharedProps } from "../features/art-gallery/gallery-types";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";

if (!globalThis.crypto?.subtle) Object.defineProperty(globalThis, "crypto", { configurable: true, value: webcrypto });

const BASE = "/Museum-Codex/releases/art-gallery-interactions-1.1.0/";
let data: GallerySharedProps;

function releaseFetcher() {
  return vi.fn<typeof fetch>(async (input) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const relative = url.pathname.replace(/^\/(?:Museum-Codex\/)?/, "");
    try {
      const bytes = await readFile(resolve(process.cwd(), "public", relative));
      return new Response(bytes, { status: 200, headers: { "Content-Type": "application/json" } });
    } catch {
      return new Response(null, { status: 404 });
    }
  });
}

function renderEnglish(tourId: string | null) {
  localStorage.setItem("museum-locale", "en");
  return render(<I18nProvider><PreferencesProvider><MemoryRouter initialEntries={[tourId ? `/art/tours/${encodeURIComponent(tourId)}` : "/art/tours"]}><ToursPage {...data} tourId={tourId} /></MemoryRouter></PreferencesProvider></I18nProvider>);
}

beforeAll(async () => {
  const fetcher = releaseFetcher();
  const base = new URL(BASE, window.location.href).href;
  const [releaseResult, interactions] = await Promise.all([
    loadArtConstellationRelease(base, fetcher),
    loadArtInteractionIndex(base, fetcher),
  ]);
  if (releaseResult.status !== "loaded") throw new Error(releaseResult.reason);
  const catalog = await releaseResult.dataSource.loadArtworkCatalog();
  if (catalog.status !== "loaded") throw new Error(catalog.reason);
  data = { release: releaseResult.release, dataSource: releaseResult.dataSource, catalog: catalog.data, interactions };
});

describe("MUSEUM-05B curated tours", () => {
  it("loads the immutable overlay and closes all interaction counts", () => {
    expect(data.release.manifestId).toBe("release:art-gallery-interactions-1.1.0");
    expect(data.interactions.observation_cards).toHaveLength(44);
    expect(data.interactions.artist_tours).toHaveLength(12);
    expect(data.interactions.thematic_tours).toHaveLength(6);
    expect(data.interactions.hero_selections).toHaveLength(12);
    expect(data.interactions.detail_regions).toHaveLength(24);
  });

  it("renders all 12 artist tours and six thematic tours without loading an index image", () => {
    const { container } = renderEnglish(null);
    expect(screen.getByRole("heading", { level: 1, name: /18 fixed routes/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Enter tour" })).toHaveLength(12);
    expect(screen.getAllByRole("link", { name: "Enter fixed tour" })).toHaveLength(6);
    expect(container.querySelector("img")).toBeNull();
  });

  it("renders a thematic tour with a fixed non-causal boundary and metadata-only path", () => {
    const tour = data.interactions.thematic_tours[0];
    renderEnglish(tour.id);
    expect(screen.getByRole("heading", { level: 1, name: "Paper, Ink, and Reproduction" })).toBeInTheDocument();
    expect(screen.getAllByText(/does not imply contact, influence, transmission/).length).toBeGreaterThan(0);
    const sequence = screen.getByRole("heading", { name: "Observe one formal record at a time" }).closest("section");
    expect(sequence).not.toBeNull();
    expect(within(sequence!).getAllByRole("listitem").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText(/Works without images use the same observation questions/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open print view" })).toBeInTheDocument();
  });

  it("renders an artist tour with image and no-image equivalent instructions", () => {
    const tour = data.interactions.artist_tours.find((entry) => entry.artist_id === "artist:mary-cassatt")!;
    renderEnglish(tour.id);
    expect(screen.getByRole("heading", { level: 1, name: "Observing Mary Cassatt" })).toBeInTheDocument();
    expect(screen.getByText(/Without an approved image, use complete metadata/)).toBeInTheDocument();
    expect(screen.queryByText(/automatic recommendation/i)).toBeInTheDocument();
  });

  it("fails clearly for an invalid tour ID", () => {
    renderEnglish("tour:theme-not-in-release");
    expect(screen.getByRole("heading", { level: 1, name: "This formal tour was not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to all tours" })).toHaveAttribute("href", "/art/tours");
  });
});
