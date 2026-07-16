import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ComparePage } from "../features/art-gallery/compare/ComparePage";
import type { GallerySharedProps } from "../features/art-gallery/gallery-types";
import type {
  ArtistRecord,
  ArtworkRecord,
  MediaAsset,
} from "../features/art-constellation/types";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";
import { interactionFixtureFor } from "./interaction-fixture";

const localized = (value: string) => ({ "zh-Hans": value, en: value });

function buildArtwork(index: number): ArtworkRecord {
  const id = `artwork:test-${String(index + 1).padStart(2, "0")}`;
  const approved = index < 2;
  const blocked = index === 2;
  return {
    id,
    artistId: `artist:test-${(index % 12) + 1}`,
    title: localized(`Work ${String(index + 1).padStart(2, "0")}`),
    dateDisplay: localized(`${1800 + index}`),
    mediumDisplay: localized(`Medium ${index + 1}`),
    institution: localized(`Museum ${index + 1}`),
    objectUrl: `https://museum.example.test/objects/${index + 1}`,
    sourceIds: [`source:test-${index + 1}`],
    attribution: null,
    accessionNumber: `ACC-${index + 1}`,
    materials: [localized(index % 2 === 0 ? "Paper" : "Canvas")],
    techniques: [localized(index % 2 === 0 ? "Ink" : "Oil paint")],
    subjects: [localized(index % 2 === 0 ? "Portrait" : "Landscape")],
    metadataLicense: "metadata-rule:test",
    limitations: localized("Recorded metadata supports observation, not influence."),
    media: {
      decision: approved
        ? "approved_self_hosted"
        : blocked
          ? "blocked_rights_conflict"
          : "metadata_only_after_automated_review",
      reasonCodes: blocked ? ["rights_conflict"] : [],
      representativeMediaId: approved ? `media:test-${index + 1}-1600w-jpeg` : null,
      mediaIds: approved ? [`media:test-${index + 1}-1600w-jpeg`] : [],
    },
  };
}

function buildArtist(index: number, artworks: ArtworkRecord[]): ArtistRecord {
  const id = `artist:test-${index + 1}`;
  const artistArtworks = artworks.filter((artwork) => artwork.artistId === id);
  const approved = artistArtworks.filter((artwork) => artwork.media.decision === "approved_self_hosted");
  return {
    id,
    labels: localized(`Artist ${String(index + 1).padStart(2, "0")}`),
    summary: localized(`Reviewed artist ${index + 1}`),
    aliases: [],
    period: "1800–1900",
    region: "Test region",
    tradition: "Test tradition",
    lifeDisplay: localized("1800–1900"),
    mediaPractice: localized("Painting and printmaking"),
    claimIds: [],
    sourceIds: [],
    relationCount: 0,
    artworkIds: artistArtworks.map((artwork) => artwork.id),
    representativeMediaId: approved[0]?.media.representativeMediaId ?? null,
    approvedMediaArtworkCount: approved.length,
    reviewer: "automated-release-validation-pipeline",
    reviewDate: "2026-07-15",
  };
}

function buildMedia(artwork: ArtworkRecord, index: number): MediaAsset {
  return {
    id: `media:test-${index + 1}-1600w-jpeg`,
    artworkId: artwork.id,
    parentMediaId: `media:test-${index + 1}-original`,
    src: `http://localhost:3000/Museum-Codex/releases/art-constellation-1.0.0/assets/test-${index + 1}/1600w.jpg`,
    publicPath: `assets/test-${index + 1}/1600w.jpg`,
    format: "jpeg",
    mimeType: "image/jpeg",
    width: 1600,
    height: 1200,
    bytes: 320_000,
    sha256: `sha256:${String(index + 1).padStart(64, "0")}`,
    role: "zoom",
    attribution: `Museum ${index + 1}, reviewed public-domain image`,
    changesStatement: "Resized and compressed; artwork content unchanged.",
    licenseIdentifier: "CC0-1.0",
    licenseUrl: "https://creativecommons.org/publicdomain/zero/1.0/",
    sourceUrl: artwork.objectUrl ?? "https://museum.example.test/",
    withdrawalStatus: "active",
    withdrawalNotice: "Remove from a future release if rights status changes.",
  };
}

const artworks = Array.from({ length: 44 }, (_, index) => buildArtwork(index));
const artists = Array.from({ length: 12 }, (_, index) => buildArtist(index, artworks));
const approvedMedia = artworks.slice(0, 2).map(buildMedia);
const blockedRemoteMedia: MediaAsset = {
  ...buildMedia(artworks[2], 2),
  id: "media:blocked-remote",
  src: "https://images.example.test/blocked.jpg",
};

const props: GallerySharedProps = {
  release: {
    manifestId: "release:art-constellation-1.0.0",
    version: "1.0.0",
    isPublicRelease: true,
    summary: {
      releaseId: "release:art-constellation-1.0.0",
      title: localized("Art comparison"),
      artistCount: 12,
      contextCount: 31,
      relationshipCount: 36,
      artworkCount: 44,
      mediaCount: 242,
      mediaBytes: 35_907_176,
      approvedMediaArtworkCount: 31,
      noImageArtworkCount: 13,
      levelCounts: { A: 0, B: 0, C: 36 },
      relationshipTypeCounts: { shared_material: 12, shared_subject: 12, shared_technique: 12 },
      semantics: localized("C-level curatorial comparison only"),
      initialState: "artists_only",
    },
    artists,
    searchEntries: [],
    layout: [],
    facets: { periods: [], regions: [], traditions: [], relationshipTypes: [] },
  },
  catalog: { artworks, media: [...approvedMedia, blockedRemoteMedia] },
  dataSource: {} as GallerySharedProps["dataSource"],
  interactions: interactionFixtureFor(artworks),
};

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location-search">{location.search}</span>;
}

function renderCompare(initialEntry = "/art/compare") {
  return render(
    <I18nProvider>
      <PreferencesProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route
              path="/art/compare"
              element={<><ComparePage {...props} /><LocationProbe /></>}
            />
          </Routes>
        </MemoryRouter>
      </PreferencesProvider>
    </I18nProvider>,
  );
}

function currentParams() {
  return new URLSearchParams(screen.getByTestId("location-search").textContent ?? "");
}

describe("MUSEUM-05A artwork comparison", () => {
  beforeEach(() => window.localStorage.setItem("museum-locale", "en"));

  it("offers all 44 formal works, stores two different choices in the URL, and swaps them", async () => {
    const user = userEvent.setup();
    renderCompare();
    const left = screen.getByLabelText("Choose the left work");
    const right = screen.getByLabelText("Choose the right work");
    expect(within(left).getAllByRole("option")).toHaveLength(45);
    expect(within(right).getAllByRole("option")).toHaveLength(45);

    await user.selectOptions(left, artworks[0].id);
    expect(within(right).getByRole("option", { name: /Work 01/ })).toBeDisabled();
    await user.selectOptions(right, artworks[1].id);
    expect(currentParams().get("left")).toBe(artworks[0].id);
    expect(currentParams().get("right")).toBe(artworks[1].id);
    expect(document.querySelector(".compare-status")).toHaveTextContent(/Two different works selected.*Work 01.*Work 02/);

    await user.click(screen.getByRole("button", { name: /Swap works/ }));
    expect(currentParams().get("left")).toBe(artworks[1].id);
    expect(currentParams().get("right")).toBe(artworks[0].id);
    const workPanels = document.querySelectorAll(".compare-work");
    expect(workPanels[0].querySelector(".compare-work-heading h2")).toHaveTextContent("Work 02");
    expect(workPanels[1].querySelector(".compare-work-heading h2")).toHaveTextContent("Work 01");
  });

  it("sanitizes an invalid same-work URL pair instead of comparing a work with itself", async () => {
    renderCompare(`/art/compare?left=${encodeURIComponent(artworks[0].id)}&right=${encodeURIComponent(artworks[0].id)}`);
    await waitFor(() => expect(currentParams().has("right")).toBe(false));
    expect(screen.getByLabelText("Choose the left work")).toHaveValue(artworks[0].id);
    expect(screen.getByLabelText("Choose the right work")).toHaveValue("");
    expect(document.querySelector(".compare-status")).toHaveTextContent("Choose two different works");
    expect(document.querySelector(".compare-stage")).toBeNull();
  });

  it("shows comparable metadata, official rights, prompts, and a stable no-image state for blocked media", () => {
    renderCompare(`/art/compare?left=${encodeURIComponent(artworks[0].id)}&right=${encodeURIComponent(artworks[2].id)}`);
    const panels = [...document.querySelectorAll<HTMLElement>(".compare-work")];
    expect(panels).toHaveLength(2);
    expect(within(panels[0]).getByText("Paper")).toBeInTheDocument();
    expect(within(panels[0]).getByText("Ink")).toBeInTheDocument();
    expect(within(panels[0]).getByText("Portrait")).toBeInTheDocument();
    const leftMetadata = panels[0].querySelector<HTMLElement>(".compare-metadata");
    expect(leftMetadata).not.toBeNull();
    if (leftMetadata) expect(within(leftMetadata).getByText("1800")).toBeInTheDocument();
    expect(within(panels[0]).getAllByRole("link", { name: "CC0-1.0" })).not.toHaveLength(0);
    expect(within(panels[0]).getAllByRole("link", { name: "CC0-1.0" })[0]).toHaveAttribute(
      "href",
      "https://creativecommons.org/publicdomain/zero/1.0/",
    );
    expect(within(panels[0]).getByRole("link", { name: "Visit official artwork source" })).toHaveAttribute(
      "href",
      artworks[0].objectUrl,
    );
    expect(panels[1].querySelector("img")).toBeNull();
    expect(within(panels[1]).getByRole("img", { name: /No image passed/ })).toBeInTheDocument();
    expect(within(panels[1]).getByText("blocked_rights_conflict")).toBeInTheDocument();
    expect(screen.getAllByText(/No AI visual-similarity score/).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Observation prompts" })).toBeInTheDocument();
    expect(document.querySelectorAll(".compare-prompts li")).toHaveLength(3);
  });

  it("keeps the two zoom controls independent", async () => {
    const user = userEvent.setup();
    renderCompare(`/art/compare?left=${encodeURIComponent(artworks[0].id)}&right=${encodeURIComponent(artworks[1].id)}`);
    const panels = [...document.querySelectorAll<HTMLElement>(".compare-work")];
    const images = panels.map((panel) => within(panel).getByRole("img"));
    for (const image of images) {
      Object.defineProperty(image, "clientWidth", { configurable: true, value: 400 });
      fireEvent.load(image);
    }
    const leftZoomIn = within(panels[0]).getByRole("button", { name: "Zoom in" });
    await waitFor(() => expect(leftZoomIn).toBeEnabled());
    expect(panels[0].querySelector("output")).toHaveTextContent("Zoom 100%");
    expect(panels[1].querySelector("output")).toHaveTextContent("Zoom 100%");
    await user.click(leftZoomIn);
    expect(panels[0].querySelector("output")).toHaveTextContent("Zoom 125%");
    expect(panels[1].querySelector("output")).toHaveTextContent("Zoom 100%");
  });

  it("creates no image elements in low-bandwidth mode until an individual work is requested", async () => {
    window.localStorage.setItem("museum-low-bandwidth", "true");
    const user = userEvent.setup();
    renderCompare(`/art/compare?left=${encodeURIComponent(artworks[0].id)}&right=${encodeURIComponent(artworks[1].id)}`);
    expect(document.querySelectorAll(".compare-stage img")).toHaveLength(0);
    const loadButtons = screen.getAllByRole("button", { name: "Load this artwork image" });
    expect(loadButtons).toHaveLength(2);
    await user.click(loadButtons[0]);
    expect(document.querySelectorAll(".compare-stage img")).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Load this artwork image" })).toHaveLength(1);
  });

  it("exposes compact, forced-color, and reduced-motion state without changing the comparison semantics", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({
        matches: query.includes("forced-colors") || query.includes("reduced-motion") || query.includes("max-width"),
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => true,
      } satisfies MediaQueryList),
    });
    renderCompare();
    const main = document.querySelector(".compare-page");
    expect(main).toHaveAttribute("data-compact", "true");
    expect(main).toHaveAttribute("data-forced-colors", "active");
    expect(main).toHaveAttribute("data-reduced-motion", "true");
    expect(screen.getByText(/never rewritten as historical influence/)).toBeInTheDocument();
  });
});
