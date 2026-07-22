import { createHash, webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { loadArtConstellationRelease } from "../data/release-loader";
import {
  createConstellationState,
  deriveConstellationView,
  stateToSearchParams,
} from "../features/art-constellation/model";

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: webcrypto });
}

const RELEASE_PREFIX = "/Museum-Codex/releases/art-constellation-1.0.0/";

afterEach(() => vi.unstubAllGlobals());

function releaseBaseUrl() {
  return new URL(RELEASE_PREFIX, window.location.href).href;
}

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

async function publicReleaseFetcherWithMutation(
  artifactName: string,
  mutate: (artifact: unknown) => void,
) {
  const releaseDirectory = resolve(process.cwd(), "public", "releases", "art-constellation-1.0.0");
  const artifact = JSON.parse(await readFile(resolve(releaseDirectory, artifactName), "utf8")) as unknown;
  mutate(artifact);
  const artifactText = JSON.stringify(artifact);
  const artifactHash = createHash("sha256").update(artifactText).digest("hex");
  const manifest = JSON.parse(await readFile(resolve(releaseDirectory, "manifest.json"), "utf8")) as {
    manifest_files: Array<{ path: string; sha256: string }>;
  };
  const manifestFile = manifest.manifest_files.find((file) => file.path === artifactName);
  if (!manifestFile) throw new Error(`Missing ${artifactName} from test release manifest`);
  manifestFile.sha256 = artifactHash;
  const manifestText = JSON.stringify(manifest);
  const fallback = publicReleaseFetcher();
  return vi.fn<typeof fetch>(async (input, init) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const name = url.pathname.slice(url.pathname.lastIndexOf("/") + 1);
    if (name === "manifest.json") {
      return new Response(manifestText, { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (name === artifactName) {
      return new Response(artifactText, { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return fallback(input, init);
  });
}

function requestedNames(fetcher: ReturnType<typeof publicReleaseFetcher>) {
  return fetcher.mock.calls.map(([input]) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    return url.pathname.slice(url.pathname.lastIndexOf("/") + 1);
  });
}

async function loadActualRelease(fetcher = publicReleaseFetcher()) {
  const result = await loadArtConstellationRelease(releaseBaseUrl(), fetcher);
  expect(result.status).toBe("loaded");
  if (result.status !== "loaded") throw new Error(`Actual MUSEUM-04 release did not load: ${result.reason}`);
  return { ...result, fetcher };
}

describe("MUSEUM-04 formal public release", () => {
  it("loads only the formal lifecycle and creates no initial image request", async () => {
    const result = await loadArtConstellationRelease(releaseBaseUrl(), publicReleaseFetcher());
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    expect(result.release.isPublicRelease).toBe(true);

    const user = userEvent.setup();
    localStorage.setItem("museum-locale", "zh-CN");
    localStorage.setItem("museum-low-bandwidth", "true");
    const fetcher = publicReleaseFetcher();
    vi.stubGlobal("fetch", fetcher);
    window.location.hash = "#/art/constellation";
    render(<App />);

    await screen.findByRole("heading", { level: 1, name: "艺术星海：观察与比较" });
    expect(screen.getByText("正式发布")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(requestedNames(fetcher)).not.toContain("media-index.json");
    const activeListTab = await screen.findByRole("tab", { name: /艺术家列表/ });
    expect(activeListTab).toHaveAttribute("aria-controls", "constellation-view-panel");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", activeListTab.id);

    await user.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByText("Formal release")).toBeInTheDocument();
  });

  it("rejects a manifest mounted under the wrong release directory", async () => {
    const fallback = publicReleaseFetcher();
    const manifest = JSON.parse(
      await readFile(resolve(process.cwd(), "public", "releases", "art-constellation-1.0.0", "manifest.json"), "utf8"),
    ) as { id: string };
    manifest.id = "release:wrong-release-1.0.0";
    const fetcher = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
      if (url.pathname.endsWith("/manifest.json")) {
        return new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return fallback(input, init);
    });
    expect(await loadArtConstellationRelease(releaseBaseUrl(), fetcher)).toEqual({
      status: "failed",
      reason: "manifest_release_identity_mismatch",
    });
  });

  it("loads only the six permitted initial files, then verifies detail groups on demand", async () => {
    const { release, dataSource, fetcher } = await loadActualRelease();
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "manifest.json",
      "graph-summary.json",
      "artists.json",
      "layout.json",
      "facets.json",
      "search-index.json",
    ]));
    expect(requestedNames(fetcher)).toHaveLength(6);
    expect(requestedNames(fetcher)).not.toEqual(expect.arrayContaining([
      "relationships.json",
      "contexts.json",
      "artworks.json",
      "evidence.json",
      "sources.json",
      "rights.json",
      "media-index.json",
      "attributions.json",
      "withdrawal-mapping.json",
      "third-party-notices.json",
    ]));

    const indexResult = await dataSource.loadRelationshipIndex();
    expect(indexResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["contexts.json", "relationships.json"]));
    if (indexResult.status !== "loaded") return;

    const mediaArtist = release.artists.find((artist) => artist.representativeMediaId !== null);
    expect(mediaArtist).toBeDefined();
    if (!mediaArtist) return;
    const artistResult = await dataSource.loadArtistSources(mediaArtist.id);
    expect(artistResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "sources.json", "artworks.json", "media-index.json", "attributions.json", "withdrawal-mapping.json",
    ]));
    if (artistResult.status === "loaded") expect(artistResult.data.media.length).toBeGreaterThan(0);

    const relationResult = await dataSource.loadRelationshipDetails(indexResult.data.relationships[0].id);
    expect(relationResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["artworks.json", "evidence.json"]));
    if (relationResult.status === "loaded") {
      expect(relationResult.data.artworks.length).toBeGreaterThan(0);
      expect(relationResult.data.evidence.length).toBeGreaterThan(0);
      expect(relationResult.data.sources.length).toBeGreaterThan(0);
    }

    const rightsResult = await dataSource.loadRights();
    expect(rightsResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["rights.json", "third-party-notices.json"]));
  });

  it("provides a 44-work M05A catalog and claim-evidence-source detail closure", async () => {
    const { dataSource, fetcher } = await loadActualRelease();
    const catalogResult = await dataSource.loadArtworkCatalog();
    expect(catalogResult.status).toBe("loaded");
    if (catalogResult.status !== "loaded") return;
    expect(catalogResult.data.artworks).toHaveLength(44);
    expect(catalogResult.data.media).toHaveLength(242);
    const approvedWork = catalogResult.data.artworks.find(
      (artwork) => artwork.media.decision === "approved_self_hosted",
    );
    expect(approvedWork).toBeDefined();
    if (!approvedWork) return;

    const details = await dataSource.loadArtworkDetails(approvedWork.id);
    expect(details.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "claims.json", "evidence.json", "sources.json", "artworks.json", "media-index.json",
    ]));
    if (details.status !== "loaded") return;
    expect(details.data.artist.artworkIds).toContain(approvedWork.id);
    expect(details.data.claims.length).toBeGreaterThan(0);
    expect(details.data.evidence.length).toBeGreaterThan(0);
    expect(details.data.sources.length).toBeGreaterThan(0);
    expect(details.data.media.length).toBeGreaterThan(0);
    expect(details.data.claims.every((claim) =>
      claim.evidenceIds.every((evidenceId) => details.data.evidence.some((item) => item.id === evidenceId)),
    )).toBe(true);
  });

  it.each([
    ["non-HTTPS scheme", "http://api.artic.edu/api/v1/artworks/111442", "artwork_official_object_url_not_https"],
    ["script scheme", "javascript:alert(1)", "artwork_official_object_url_not_https"],
    ["unregistered official host", "https://example.invalid/artworks/111442", "artwork_official_object_source_mismatch"],
  ])("rejects an artwork object URL with a %s", async (_label, objectUrl, expectedReason) => {
    const fetcher = await publicReleaseFetcherWithMutation("artworks.json", (raw) => {
      const root = raw as { artworks: Array<{ official_object_url: string }> };
      root.artworks[0].official_object_url = objectUrl;
    });
    const result = await loadArtConstellationRelease(releaseBaseUrl(), fetcher);
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    const detail = await result.dataSource.loadArtistSources(result.release.artists[0].id);
    expect(detail).toEqual({ status: "failed", reason: expectedReason });
  });

  it("rejects an official object URL paired with another institution source ID", async () => {
    const fetcher = await publicReleaseFetcherWithMutation("artworks.json", (raw) => {
      const root = raw as { artworks: Array<{ source_ids: string[] }> };
      root.artworks[0].source_ids = ["source:met_open_access"];
    });
    const result = await loadArtConstellationRelease(releaseBaseUrl(), fetcher);
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    const detail = await result.dataSource.loadArtistSources(result.release.artists[0].id);
    expect(detail).toEqual({ status: "failed", reason: "artwork_official_object_source_mismatch" });
  });

  it.each([
    ["script scheme", "javascript:alert(1)", "rights_request_url_not_approved"],
    ["unapproved HTTPS host", "https://example.invalid/rights", "rights_request_url_not_approved"],
    ["protocol-relative host", "//github.com/Archmays/Museum-Codex/issues/new", "rights_request_url_invalid"],
  ])("rejects a rights-request URL with a %s", async (_label, requestUrl, expectedReason) => {
    const fetcher = await publicReleaseFetcherWithMutation("rights.json", (raw) => {
      const root = raw as { rights_request: { url: string } };
      root.rights_request.url = requestUrl;
    });
    const result = await loadArtConstellationRelease(releaseBaseUrl(), fetcher);
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    const detail = await result.dataSource.loadRights();
    expect(detail).toEqual({ status: "failed", reason: expectedReason });
  });

  it("accepts a same-origin relative rights-request URL", async () => {
    const fetcher = await publicReleaseFetcherWithMutation("rights.json", (raw) => {
      const root = raw as { rights_request: { url: string } };
      root.rights_request.url = "rights-request";
    });
    const result = await loadArtConstellationRelease(releaseBaseUrl(), fetcher);
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    const detail = await result.dataSource.loadRights();
    expect(detail.status).toBe("loaded");
    if (detail.status === "loaded") {
      expect(detail.data.rights.rightsRequestUrl).toBe(new URL("rights-request", releaseBaseUrl()).href);
    }
  });

  it("keeps search, tradition, level, focus, and canonical URL state in one model", async () => {
    const { release, dataSource } = await loadActualRelease();
    const indexResult = await dataSource.loadRelationshipIndex();
    if (indexResult.status !== "loaded") throw new Error("Relationship index did not load");
    const artist = release.artists.find((candidate) => candidate.aliases.length > 0) ?? release.artists[0];
    const state = createConstellationState(new URLSearchParams({
      q: artist.aliases[0],
      tradition: artist.tradition ?? "",
      focus: artist.id,
      level: "C",
      view: "list",
    }), release);
    const view = deriveConstellationView(release, indexResult.data, state);
    expect(view.artists.some((candidate) => candidate.id === artist.id)).toBe(true);
    expect(view.matchReasons.get(artist.id)).toBe("alias");
    expect(view.graphRelationships.every((relationship) =>
      relationship.sourceArtistId === artist.id || relationship.targetArtistId === artist.id,
    )).toBe(true);

    const params = stateToSearchParams(state, release.version);
    expect(params.get("focus")).toBe(artist.id);
    expect(params.get("tradition")).toBe(artist.tradition);
    expect(params.get("level")).toBe("C");
    expect(params.get("release")).toBe(release.version);

    const emptyLevels = deriveConstellationView(release, indexResult.data, { ...state, level: "A" });
    expect(emptyLevels.relationships).toHaveLength(0);
  });

  it.each([
    { name: "search", label: "搜索艺术家", value: "a", input: true },
    { name: "level", label: "关系等级", value: "C" },
    { name: "period", label: "时期" },
    { name: "region", label: "地区" },
    { name: "tradition", label: "艺术传统" },
  ])("loads exact relationship counts when the $name filter changes", async ({ label, value, input }) => {
    const user = userEvent.setup();
    const fetcher = publicReleaseFetcher();
    vi.stubGlobal("fetch", fetcher);
    localStorage.setItem("museum-low-bandwidth", "true");
    window.location.hash = "#/art/constellation";
    render(<App />);

    await screen.findByRole("heading", { level: 1, name: "艺术星海：观察与比较" });
    expect(await screen.findByText(/正在按需核对与当前筛选一致的关系数量/)).toBeInTheDocument();
    expect(requestedNames(fetcher)).not.toContain("relationships.json");

    const control = screen.getByLabelText(label);
    if (input) {
      await user.type(control, value ?? "a");
    } else {
      const select = control as HTMLSelectElement;
      const selectedValue = value ?? select.options[1]?.value;
      expect(selectedValue).toBeTruthy();
      await user.selectOptions(select, selectedValue);
    }

    await waitFor(() => expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "relationships.json", "contexts.json",
    ])));
    await waitFor(() => expect(screen.queryByText(/正在按需核对与当前筛选一致的关系数量/)).not.toBeInTheDocument());
  });

  it("defers relationship, media, evidence, source, and rights requests until visitor actions", async () => {
    const loaded = await loadActualRelease();
    const mediaArtist = loaded.release.artists.find((artist) => artist.representativeMediaId !== null);
    if (!mediaArtist) throw new Error("Expected at least one artist with approved representative media");
    const user = userEvent.setup();
    const fetcher = publicReleaseFetcher();
    vi.stubGlobal("fetch", fetcher);
    localStorage.setItem("museum-low-bandwidth", "true");
    window.location.hash = "#/art/constellation";
    render(<App />);

    await screen.findByRole("heading", { level: 1, name: "艺术星海：观察与比较" });
    expect(requestedNames(fetcher)).not.toEqual(expect.arrayContaining([
      "relationships.json", "contexts.json", "sources.json", "artworks.json", "evidence.json", "rights.json",
    ]));
    expect(screen.getByRole("main")).toHaveAttribute("data-view", "list");

    const artistName = await screen.findByRole("heading", { name: mediaArtist.labels["zh-Hans"] });
    const artistItem = artistName.closest("li");
    if (!artistItem) throw new Error("Artist list item missing");
    const firstArtistButton = within(artistItem).getByRole("button", { name: "查看艺术家说明" });
    await user.click(firstArtistButton);
    const artistPanel = await screen.findByRole("complementary", { name: "艺术家说明" });
    await waitFor(() => expect(within(artistPanel).getByRole("button", { name: "关闭说明" })).toHaveFocus());
    expect(await within(artistPanel).findByText("艺术传统")).toBeInTheDocument();
    await waitFor(() => expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "relationships.json", "contexts.json", "sources.json", "artworks.json", "media-index.json",
      "attributions.json", "withdrawal-mapping.json",
    ])));
    expect(requestedNames(fetcher)).not.toContain("evidence.json");
    expect(within(artistPanel).queryByRole("img")).not.toBeInTheDocument();
    await user.click(await within(artistPanel).findByRole("button", { name: "加载这件作品图像" }));
    expect(await within(artistPanel).findByRole("img", { name: new RegExp(mediaArtist.labels["zh-Hans"]) })).toBeInTheDocument();

    const relationshipButton = await waitFor(() => {
      const currentArtistPanel = screen.getByRole("complementary", { name: "艺术家说明" });
      const candidates = within(currentArtistPanel).getAllByRole("button").filter((button) => button.closest("li"));
      expect(candidates.length).toBeGreaterThan(0);
      return candidates[0];
    });
    const panelScroll = artistPanel.querySelector<HTMLElement>(".panel-scroll");
    expect(panelScroll).not.toBeNull();
    if (panelScroll) panelScroll.scrollTop = 480;
    await user.click(relationshipButton);
    const relationshipPanel = await screen.findByRole("complementary", { name: "关系解释" });
    await waitFor(() => {
      const title = relationshipPanel.querySelector("#constellation-panel-content-title");
      expect(title?.textContent?.trim()).toBeTruthy();
      expect(title).toBeVisible();
      return title;
    });
    await waitFor(() => expect(within(relationshipPanel).getByRole("button", { name: "关闭说明" })).toHaveFocus());
    await waitFor(() => expect(relationshipPanel.querySelector<HTMLElement>(".panel-scroll")?.scrollTop).toBe(0));
    await waitFor(() => expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["artworks.json", "evidence.json"])));
    expect((await screen.findAllByText("元数据许可规则")).length).toBeGreaterThan(0);
    expect(screen.getByText("支持性 Claim")).toBeInTheDocument();
    expect(within(relationshipPanel).getByText("未主张历史关系")).toBeInTheDocument();
    expect(within(relationshipPanel).getByText("本版本未纳入计算相似度")).toBeInTheDocument();
    expect(within(relationshipPanel).queryByText(/\(null\)/)).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "关系解释" })).not.toBeInTheDocument());
    await waitFor(() => expect(firstArtistButton).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "查看权利与第三方通知" }));
    await screen.findByRole("complementary", { name: "权利与公开范围" });
    await waitFor(() => expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["rights.json", "third-party-notices.json"])));
    expect((await screen.findAllByText(/保留所有权利/)).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "EN" }));
    const currentRightsPanel = screen.getByRole("complementary", { name: "Rights and public scope" });
    expect(within(currentRightsPanel).getAllByText(/All rights reserved/).length).toBeGreaterThan(0);
    expect(within(currentRightsPanel).getByRole("link", { name: "Read third-party notices" })).toHaveAttribute(
      "href",
      `${import.meta.env.BASE_URL}THIRD_PARTY_NOTICES.md`,
    );
  });
});
