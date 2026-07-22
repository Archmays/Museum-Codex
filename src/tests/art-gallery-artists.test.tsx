import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { loadArtConstellationRelease } from "../data/release-loader";
import { ArtistGalleryPage, ArtistIndexPage } from "../features/art-gallery/artists";
import type { GallerySharedProps } from "../features/art-gallery/gallery-types";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";
import { interactionFixture } from "./interaction-fixture";

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: webcrypto });
}

const RELEASE_PREFIX = "/Museum-Codex/releases/art-constellation-1.0.0/";
let galleryData: GallerySharedProps;

function publicReleaseFetcher() {
  return vi.fn<typeof fetch>(async (input, init) => {
    if (init?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const relativePath = url.pathname.replace(/^\/(?:Museum-Codex\/)?/, "");
    try {
      const bytes = await readFile(resolve(process.cwd(), "public", relativePath));
      const body = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      return new Response(body, { status: 200, headers: { "Content-Type": "application/json" } });
    } catch {
      return new Response(null, { status: 404 });
    }
  });
}

function renderEnglish(element: React.ReactNode) {
  localStorage.setItem("museum-locale", "en");
  return render(
    <I18nProvider>
      <PreferencesProvider>
        <MemoryRouter>{element}</MemoryRouter>
      </PreferencesProvider>
    </I18nProvider>,
  );
}

beforeAll(async () => {
  const baseUrl = new URL(RELEASE_PREFIX, window.location.href).href;
  const releaseResult = await loadArtConstellationRelease(baseUrl, publicReleaseFetcher());
  if (releaseResult.status !== "loaded") throw new Error(releaseResult.reason);
  const catalogResult = await releaseResult.dataSource.loadArtworkCatalog();
  if (catalogResult.status !== "loaded") throw new Error(catalogResult.reason);
  galleryData = {
    release: releaseResult.release,
    dataSource: releaseResult.dataSource,
    catalog: catalogResult.data,
    interactions: interactionFixture,
  };
});

describe("MUSEUM-05A artist galleries", () => {
  it("keeps all 12 artists in release order and exposes accessible filters without image ranking", async () => {
    const user = userEvent.setup();
    const { container } = renderEnglish(<ArtistIndexPage {...galleryData} />);

    expect(screen.getByRole("heading", { level: 1, name: "Each artist offers a way to begin looking" })).toBeInTheDocument();
    const index = screen.getByRole("list", { name: "Artist index" });
    expect(within(index).getAllByRole("listitem")).toHaveLength(12);
    expect(within(index).getAllByRole("heading", { level: 2 })[0]).toHaveTextContent("Albrecht Dürer");
    expect(screen.getByText("Showing 12 artists")).toHaveAttribute("role", "status");

    await user.type(screen.getByRole("searchbox", { name: "Search artists" }), "Tanner");
    expect(within(screen.getByRole("list", { name: "Artist index" })).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2, name: "Henry Ossawa Tanner" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Artwork images" }), "without-image");
    const noImageIndex = screen.getByRole("list", { name: "Artist index" });
    expect(within(noImageIndex).getAllByRole("listitem")).toHaveLength(4);
    expect(within(noImageIndex).getAllByRole("img", { name: "No image passed the public-media gate for this record." })).toHaveLength(4);
    expect(within(noImageIndex).getByRole("heading", { name: "Mary Cassatt" })).toBeInTheDocument();
    expect(within(noImageIndex).getByRole("heading", { name: "Käthe Kollwitz" })).toBeInTheDocument();

    for (const image of container.querySelectorAll("img")) {
      expect(new URL(image.src).origin).toBe(window.location.origin);
      expect(new URL(image.src).pathname).toMatch(/\/releases\/art-constellation-1\.0\.0\/assets\//);
    }
  });

  it("shows every formal work, exact rights states, official sources, and C-level related artists", async () => {
    renderEnglish(<ArtistGalleryPage {...galleryData} artistId="artist:albrecht-durer" />);

    expect(screen.getByRole("heading", { level: 1, name: "Albrecht Dürer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Meet the artist" })).toBeInTheDocument();
    const worksSection = screen.getByRole("heading", { level: 2, name: "Formal works in this release" }).closest("section");
    expect(worksSection).not.toBeNull();
    expect(within(worksSection!).getAllByRole("listitem")).toHaveLength(4);
    expect(within(worksSection!).getAllByRole("link", { name: "View artwork detail" })).toHaveLength(4);
    expect(within(worksSection!).getAllByText("Image available here")).toHaveLength(4);
    expect(within(worksSection!).getAllByRole("link", { name: "Visit official artwork source" })).toHaveLength(8);

    const relatedArtist = await screen.findByRole("link", { name: "Francisco de Goya" });
    expect(relatedArtist).toHaveAttribute("href", "/art/artists/francisco-de-goya");
    expect(screen.getAllByText(/· C$/).length).toBeGreaterThan(0);
    expect(await screen.findByRole("link", { name: "The Metropolitan Museum of Art Open Access" })).toHaveAttribute(
      "href",
      "https://metmuseum.github.io/",
    );
    const supportSection = screen.getByRole("heading", { level: 2, name: "What supports the introduction" }).closest("section");
    expect(supportSection).not.toBeNull();
    expect(within(supportSection!).getByText(/never artistic status|do not imply influence/i)).toBeInTheDocument();
  });

  it("keeps a complete four-work gallery when no public artwork image is approved", async () => {
    const { container } = renderEnglish(<ArtistGalleryPage {...galleryData} artistId="artist:henry-ossawa-tanner" />);

    const worksSection = screen.getByRole("heading", { level: 2, name: "Formal works in this release" }).closest("section");
    expect(worksSection).not.toBeNull();
    expect(within(worksSection!).getAllByRole("listitem")).toHaveLength(4);
    expect(within(worksSection!).getAllByRole("img", { name: "No image passed the public-media gate for this record." })).toHaveLength(4);
    expect(container.querySelector("img")).toBeNull();
    expect(within(worksSection!).getAllByRole("link", { name: "Visit official artwork source" })).toHaveLength(4);
    expect(within(worksSection!).getAllByText("Metadata record")).toHaveLength(4);
    await waitFor(() => expect(screen.getByRole("link", { name: "Albrecht Dürer" })).toBeInTheDocument());
  });

  it("reports relationship and source integrity failures instead of presenting empty reviewed data", async () => {
    const failedData = {
      ...galleryData,
      dataSource: {
        ...galleryData.dataSource,
        loadRelationshipIndex: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "integrity-failed" })),
        loadArtistSources: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "integrity-failed" })),
      },
    };
    renderEnglish(<ArtistGalleryPage {...failedData} artistId="artist:albrecht-durer" />);

    expect(await screen.findByText("Relationship data failed its integrity check; the failure is not presented as an empty result.")).toHaveAttribute("role", "alert");
    expect(await screen.findByText("Complete source material is temporarily unavailable; retry from this page later.")).toHaveAttribute("role", "alert");
    expect(screen.queryByText("This release has no related artists to display.")).not.toBeInTheDocument();
  });
});
