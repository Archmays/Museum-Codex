import { webcrypto } from "node:crypto";
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

const RELEASE_PREFIX = "/Museum-Codex/releases/art-constellation-0.1.0/";

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

function reviewedCandidateFetcher() {
  const baseFetcher = publicReleaseFetcher();
  return vi.fn<typeof fetch>(async (input, init) => {
    const original = await baseFetcher(input, init);
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    if (!url.pathname.endsWith("/manifest.json") || !original.ok) return original;
    const manifest = await original.json() as Record<string, unknown>;
    return new Response(JSON.stringify({ ...manifest, status: "reviewed", public_release: false }), {
      status: original.status,
      headers: { "Content-Type": "application/json" },
    });
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

describe("MUSEUM-04 staged public release", () => {
  it("loads the reviewed candidate only through the constellation path and labels it in both languages", async () => {
    const result = await loadArtConstellationRelease(releaseBaseUrl(), reviewedCandidateFetcher());
    expect(result.status).toBe("loaded");
    if (result.status !== "loaded") return;
    expect(result.release.isPublicRelease).toBe(false);

    const user = userEvent.setup();
    localStorage.setItem("museum-locale", "zh-CN");
    localStorage.setItem("museum-low-bandwidth", "true");
    vi.stubGlobal("fetch", reviewedCandidateFetcher());
    window.location.hash = "#/art/constellation";
    render(<App />);

    await screen.findByRole("heading", { level: 1, name: "艺术星海：观察与比较" });
    expect(screen.getByText("发布候选 · 待人工审核")).toBeInTheDocument();
    expect(screen.queryByText("正式发布")).not.toBeInTheDocument();
    const activeListTab = await screen.findByRole("tab", { name: /艺术家列表/ });
    expect(activeListTab).toHaveAttribute("aria-controls", "constellation-view-panel");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", activeListTab.id);

    await user.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByText("Release candidate · human review pending")).toBeInTheDocument();
    expect(screen.queryByText("Formal release")).not.toBeInTheDocument();
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
      "third-party-notices.json",
    ]));

    const indexResult = await dataSource.loadRelationshipIndex();
    expect(indexResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toEqual(expect.arrayContaining(["contexts.json", "relationships.json"]));
    if (indexResult.status !== "loaded") return;

    const artistResult = await dataSource.loadArtistSources(release.artists[0].id);
    expect(artistResult.status).toBe("loaded");
    expect(requestedNames(fetcher)).toContain("sources.json");

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

  it("defers relationship, evidence, source, and rights requests until visitor actions", async () => {
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

    const firstArtistButton = (await screen.findAllByRole("button", { name: "查看艺术家说明" }))[0];
    await user.click(firstArtistButton);
    const artistPanel = await screen.findByRole("complementary", { name: "艺术家说明" });
    await waitFor(() => expect(within(artistPanel).getByRole("button", { name: "关闭说明" })).toHaveFocus());
    expect(await within(artistPanel).findByText("艺术传统")).toBeInTheDocument();
    await waitFor(() => expect(requestedNames(fetcher)).toEqual(expect.arrayContaining([
      "relationships.json", "contexts.json", "sources.json",
    ])));
    expect(requestedNames(fetcher)).not.toContain("artworks.json");
    expect(requestedNames(fetcher)).not.toContain("evidence.json");

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
