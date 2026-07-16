import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";
import { ArtworkDetailPage } from "../features/art-gallery/artwork/ArtworkDetailPage";
import { ArtworkZoom } from "../features/art-gallery/artwork/ArtworkZoom";
import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtistRecord,
  ArtworkCatalog,
  ArtworkDetails,
  ArtworkRecord,
  MediaAsset,
} from "../features/art-constellation/types";
import { interactionFixtureFor } from "./interaction-fixture";

const artist: ArtistRecord = {
  id: "artist:test",
  labels: { "zh-Hans": "\u6d4b\u8bd5\u827a\u672f\u5bb6", en: "Test Artist" },
  summary: { "zh-Hans": "\u7ecf\u5ba1\u6838\u7b80\u4ecb", en: "Reviewed introduction" },
  aliases: [],
  period: "nineteenth-century",
  region: "Europe",
  tradition: "printmaking",
  lifeDisplay: { "zh-Hans": "1800\u20131880", en: "1800\u20131880" },
  mediaPractice: { "zh-Hans": "\u7248\u753b", en: "Printmaking" },
  claimIds: [],
  sourceIds: ["source:test"],
  relationCount: 1,
  artworkIds: ["artwork:test"],
  representativeMediaId: "media:test:1600:jpeg",
  approvedMediaArtworkCount: 1,
  reviewer: "automated_cross_validation_pipeline",
  reviewDate: "2026-07-15",
};

const artwork: ArtworkRecord = {
  id: "artwork:test",
  artistId: artist.id,
  title: { "zh-Hans": "\u6d4b\u8bd5\u4f5c\u54c1", en: "Test Work" },
  dateDisplay: { "zh-Hans": "1869\u5e74", en: "1869" },
  mediumDisplay: { "zh-Hans": "\u7eb8\u672c\u6728\u523b", en: "Woodcut on paper" },
  institution: { "zh-Hans": "\u6d4b\u8bd5\u535a\u7269\u9986", en: "Test Museum" },
  objectUrl: "https://www.metmuseum.org/art/collection/search/1",
  sourceIds: ["source:test"],
  attribution: "Test Museum, public-domain object",
  accessionNumber: "TEST.1",
  materials: [{ "zh-Hans": "\u7eb8", en: "Paper" }],
  techniques: [{ "zh-Hans": "\u6728\u523b", en: "Woodcut" }],
  subjects: [{ "zh-Hans": "\u98ce\u666f", en: "Landscape" }],
  metadataLicense: "CC0-1.0",
  limitations: { "zh-Hans": "\u672a\u4e3b\u5f20\u5f71\u54cd\u5173\u7cfb", en: "No influence relationship is claimed." },
  media: {
    decision: "approved_self_hosted",
    reasonCodes: ["identity_rights_bytes_quality_pass"],
    representativeMediaId: "media:test:1600:jpeg",
    mediaIds: ["media:test:1600:jpeg"],
  },
};

const media: MediaAsset = {
  id: "media:test:1600:jpeg",
  artworkId: artwork.id,
  parentMediaId: "media:test:original",
  src: "/Museum-Codex/releases/art-constellation-1.0.0/assets/artwork-test/1600w.jpeg",
  publicPath: "assets/artwork-test/1600w.jpeg",
  format: "jpeg",
  mimeType: "image/jpeg",
  width: 1600,
  height: 1200,
  bytes: 240000,
  sha256: "a".repeat(64),
  role: "zoom",
  attribution: "Test Museum",
  changesStatement: "Resized without content alteration.",
  licenseIdentifier: "CC0-1.0",
  licenseUrl: "https://creativecommons.org/publicdomain/zero/1.0/",
  sourceUrl: artwork.objectUrl!,
  withdrawalStatus: "active",
  withdrawalNotice: "Mapped to the formal withdrawal register.",
};

const details: ArtworkDetails = {
  artwork,
  artist,
  media: [media],
  claims: [{
    id: "claim:test",
    subjectId: artwork.id,
    predicate: "has_reviewed_object_identity",
    objectId: "source:test",
    evidenceIds: ["evidence:test"],
    text: { "zh-Hans": "\u5bf9\u8c61\u8eab\u4efd\u5df2\u6838\u5bf9", en: "The object identity is reviewed." },
  }],
  evidence: [{
    id: "evidence:test",
    claimIds: ["claim:test"],
    sourceIds: ["source:test"],
    summary: { "zh-Hans": "\u5b98\u65b9\u85cf\u54c1\u8bb0\u5f55", en: "Official collection record." },
    locator: "object/1",
    reliabilityNote: { "zh-Hans": "\u673a\u6784\u4e00\u7ea7\u6765\u6e90", en: "Institutional primary source." },
  }],
  sources: [{
    id: "source:test",
    title: "Official object record",
    publisher: "Test Museum",
    officialUrl: artwork.objectUrl!,
    date: "2026-07-15",
    locator: { "zh-Hans": "\u5bf9\u8c61 1", en: "Object 1" },
    license: "CC0-1.0",
    attribution: "Test Museum",
  }],
};

const release = {
  manifestId: "release:art-constellation-1.0.0",
  version: "1.0.0",
  isPublicRelease: true,
  artists: [artist],
  searchEntries: [],
  layout: [],
  facets: { periods: [], regions: [], traditions: [], relationshipTypes: [] },
  summary: {
    releaseId: "release:art-constellation-1.0.0",
    title: { "zh-Hans": "\u827a\u672f\u661f\u6d77", en: "Art Constellation" },
    artistCount: 12,
    contextCount: 31,
    relationshipCount: 36,
    artworkCount: 44,
    mediaCount: 242,
    mediaBytes: 1,
    approvedMediaArtworkCount: 31,
    noImageArtworkCount: 13,
    levelCounts: { A: 0, B: 0, C: 36 },
    relationshipTypeCounts: { shared_material: 1, shared_subject: 1, shared_technique: 1 },
    semantics: { "zh-Hans": "C \u7ea7", en: "C-level comparison" },
    initialState: "artists_only",
  },
} as ArtConstellationRelease;

const catalog: ArtworkCatalog = { artworks: [artwork], media: [media] };

function dataSourceFor(result: ArtworkDetails = details): ArtConstellationDataSource {
  return {
    loadArtworkDetails: vi.fn(() => Promise.resolve({ status: "loaded" as const, data: result })),
    loadArtworkCatalog: vi.fn(() => Promise.resolve({ status: "loaded" as const, data: catalog })),
    loadRelationshipIndex: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "not-used" })),
    loadArtistSources: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "not-used" })),
    loadRelationshipDetails: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "not-used" })),
    loadRights: vi.fn(() => Promise.resolve({ status: "failed" as const, reason: "not-used" })),
  };
}

function renderArtworkPage(options: { lowBandwidth?: boolean; result?: ArtworkDetails } = {}) {
  localStorage.setItem("museum-locale", "en");
  localStorage.setItem("museum-low-bandwidth", String(Boolean(options.lowBandwidth)));
  const dataSource = dataSourceFor(options.result);
  render(
    <I18nProvider>
      <PreferencesProvider>
        <MemoryRouter>
          <ArtworkDetailPage release={release} catalog={catalog} dataSource={dataSource} interactions={interactionFixtureFor([artwork])} artworkId={artwork.id} />
        </MemoryRouter>
      </PreferencesProvider>
    </I18nProvider>,
  );
  return dataSource;
}

describe("MUSEUM-05A artwork detail", () => {
  it("renders the formal object record and Claim to Evidence to Source closure", async () => {
    const dataSource = renderArtworkPage();

    expect(await screen.findByRole("heading", { level: 1, name: "Test Work" })).toBeInTheDocument();
    expect(dataSource.loadArtworkDetails).toHaveBeenCalledWith(artwork.id, expect.any(AbortSignal));
    expect(screen.getByText("The formal release does not model a separate original-language title; none is inferred.")).toBeInTheDocument();
    expect(screen.getAllByText("Test Museum").length).toBeGreaterThan(0);
    expect(screen.getByText("TEST.1")).toBeInTheDocument();
    expect(screen.getByText("Paper")).toBeInTheDocument();
    expect(screen.getByText("Woodcut")).toBeInTheDocument();
    expect(screen.getByText("Landscape")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Visit official artwork source" })).toHaveAttribute("href", artwork.objectUrl);
    expect(screen.getByText("The object identity is reviewed.")).toBeInTheDocument();
    expect(screen.getByText("Official collection record.")).toBeInTheDocument();
    expect(screen.getByText("Institutional primary source.")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Evidence records" })).getByRole("link", { name: "Official object record" })).toHaveAttribute("href", artwork.objectUrl);
    expect(screen.getAllByRole("link", { name: "Official object record" })).toHaveLength(2);
    expect(screen.getByText("CC0-1.0", { selector: "p" })).toBeInTheDocument();

    const image = screen.getByRole("img", { name: "Test Artist, Test Work, 1869" });
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("src", media.src);
    expect(image).toHaveAttribute("srcset", `${media.src} 1600w`);
    expect(image).toHaveAttribute("sizes", "(max-width: 760px) 92vw, 100vw");
  });

  it("caps zoom at natural pixels and supports keyboard pan and reset", async () => {
    const user = userEvent.setup();
    renderArtworkPage();
    const image = await screen.findByRole("img", { name: "Test Artist, Test Work, 1869" });
    const viewport = screen.getByRole("group", { name: "Zoomable artwork image: Test Work" });
    Object.defineProperties(image, {
      clientWidth: { configurable: true, value: 800 },
      clientHeight: { configurable: true, value: 600 },
      currentSrc: { configurable: true, value: new URL(media.src, window.location.href).href },
      naturalWidth: { configurable: true, value: 800 },
    });
    Object.defineProperties(viewport, {
      clientWidth: { configurable: true, value: 800 },
      clientHeight: { configurable: true, value: 600 },
    });
    fireEvent.load(image);

    const zoomIn = screen.getByRole("button", { name: "Zoom in" });
    await waitFor(() => expect(zoomIn).toBeEnabled());
    for (let index = 0; index < 6; index += 1) await user.click(zoomIn);
    expect(screen.getByText("Zoom 200%")).toBeInTheDocument();
    expect(zoomIn).toBeDisabled();

    viewport.focus();
    await user.keyboard("{ArrowRight}");
    expect(image).toHaveStyle({ transform: "translate(32px, 0px) scale(2)" });
    await user.keyboard("0");
    expect(screen.getByText("Zoom 100%")).toBeInTheDocument();
    expect(image).toHaveStyle({ transform: "translate(0px, 0px) scale(1)" });
  });

  it("makes low-bandwidth loading explicit and falls back without losing metadata on decode failure", async () => {
    const user = userEvent.setup();
    renderArtworkPage({ lowBandwidth: true });

    await screen.findByRole("heading", { level: 1, name: "Test Work" });
    expect(screen.queryByRole("img", { name: "Test Artist, Test Work, 1869" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load this artwork image" }));
    const image = screen.getByRole("img", { name: "Test Artist, Test Work, 1869" });
    fireEvent.error(image);

    await waitFor(() => expect(screen.queryByRole("img", { name: "Test Artist, Test Work, 1869" })).not.toBeInTheDocument());
    expect(screen.getByRole("img", { name: "The image could not be decoded; artwork metadata and the official source remain available." })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("The image could not be decoded");
    expect(screen.getByText("TEST.1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Visit official artwork source" })).toBeInTheDocument();
  });

  it("rejects remote media, falls back to approved detail media, and keeps sibling ARIA references unique", () => {
    localStorage.setItem("museum-locale", "en");
    const remote = { ...media, id: "media:remote", src: "https://example.invalid/work.jpeg" };
    const nonZoom = {
      ...media,
      id: "media:detail",
      src: "/Museum-Codex/releases/art-constellation-1.0.0/assets/artwork-test/960w.jpeg",
      publicPath: "assets/artwork-test/960w.jpeg",
      width: 960,
      role: "detail" as const,
    };
    render(
      <I18nProvider>
        <PreferencesProvider>
          <MemoryRouter>
            <div>
              <ArtworkZoom artwork={artwork} media={[remote, nonZoom]} artistName="Test Artist" lowBandwidth={false} />
              <ArtworkZoom artwork={artwork} media={[media]} artistName="Test Artist" lowBandwidth={false} />
            </div>
          </MemoryRouter>
        </PreferencesProvider>
      </I18nProvider>,
    );

    const groups = screen.getAllByRole("group", { name: "Zoomable artwork image: Test Work" });
    expect(groups).toHaveLength(2);
    expect(within(groups[0]).getByRole("img")).toHaveAttribute("src", nonZoom.src);
    expect(within(groups[0]).getByRole("img")).toHaveAttribute("srcset", `${nonZoom.src} 960w`);
    expect(within(groups[1]).getByRole("img")).toHaveAttribute("src", media.src);
    const describedIds = groups.flatMap((group) => group.getAttribute("aria-describedby")?.split(" ") ?? []);
    expect(describedIds).toHaveLength(4);
    describedIds.forEach((id) => expect(document.getElementById(id)).not.toBeNull());
    expect(new Set(describedIds).size).toBe(4);
  });

  it("jumps to deterministic detail regions by button and keyboard, then resets", async () => {
    const user = userEvent.setup();
    localStorage.setItem("museum-locale", "en");
    const region = {
      id: "detail-region:test-1",
      hero_id: "hero:test",
      artwork_id: artwork.id,
      label: { "zh-Hans": "细节区域 1", en: "Detail region 1" },
      source_asset: { media_id: media.id, path: media.publicPath, sha256: media.sha256, width: 1600, height: 1200 },
      rect: { x: 640, y: 480, width: 512, height: 384 },
      normalized_rect: { x: 0.4, y: 0.4, width: 0.32, height: 0.32 },
      metrics: { edge_density: 0.2, local_contrast: 0.3, entropy: 0.5, saliency: 0.4, score: 0.35 },
      algorithm: { name: "structural-detail-navigation" as const, version: "1.0.0", input_release_hash: "sha256:" + "a".repeat(64) },
      semantic_label: null,
    };
    render(<I18nProvider><PreferencesProvider><MemoryRouter><ArtworkZoom artwork={artwork} media={[media]} artistName="Test Artist" lowBandwidth={false} regions={[region]} /></MemoryRouter></PreferencesProvider></I18nProvider>);
    const image = screen.getByRole("img", { name: "Test Artist, Test Work, 1869" });
    const viewport = screen.getByRole("group", { name: "Zoomable artwork image: Test Work" });
    Object.defineProperties(image, { clientWidth: { configurable: true, value: 800 }, clientHeight: { configurable: true, value: 600 }, naturalWidth: { configurable: true, value: 1600 }, currentSrc: { configurable: true, value: new URL(media.src, window.location.href).href } });
    Object.defineProperties(viewport, { clientWidth: { configurable: true, value: 800 }, clientHeight: { configurable: true, value: 600 } });
    fireEvent.load(image);
    await user.click(screen.getByRole("button", { name: "Detail region 1" }));
    expect(screen.getByRole("button", { name: "Detail region 1" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("status").some((status) => status.textContent === "Detail region 1")).toBe(true);
    viewport.focus();
    await user.keyboard("{Escape}");
    expect(screen.getByText("Current: overview")).toBeInTheDocument();
  });
});
