import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";
import ArtMapPage from "../features/art-map/ArtMapPage";
import { loadMapBundle } from "../features/art-map/map-loader";
import { CURRENT_ART_RELEASE_ID } from "../data/art-release-profile";

vi.mock("../features/art-map/MapCanvas", () => ({
  MapCanvas: ({ visibleFeatures }: { visibleFeatures: unknown[] }) => <div role="region" aria-label="Two-dimensional art place map">{visibleFeatures.length} local points</div>,
}));

if (!globalThis.crypto?.subtle) Object.defineProperty(globalThis, "crypto", { configurable: true, value: webcrypto });

const originalFetch = globalThis.fetch;

function releaseFetcher(tamperPath?: string) {
  return vi.fn<typeof fetch>(async (input) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const relative = url.pathname.replace(/^\/(?:Museum-Codex\/)?/, "");
    try {
      const bytes = await readFile(resolve(process.cwd(), "public", relative));
      if (tamperPath && relative.endsWith(tamperPath)) return new Response(new TextEncoder().encode("{}"), { status: 200 });
      return new Response(bytes, { status: 200, headers: { "Content-Type": "application/json" } });
    } catch {
      return new Response(null, { status: 404 });
    }
  });
}

function renderPage(entry = "/art/map?view=list") {
  localStorage.setItem("museum-locale", "en");
  return render(
    <I18nProvider><PreferencesProvider><MemoryRouter initialEntries={[entry]}><ArtMapPage /></MemoryRouter></PreferencesProvider></I18nProvider>,
  );
}

beforeEach(() => {
  globalThis.fetch = releaseFetcher();
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe("Art Across Time and Place current-release projection", () => {
  it("loads the exact immutable release and its formal counts", async () => {
    const bundle = await loadMapBundle();
    expect(bundle.manifest.id).toBe(CURRENT_ART_RELEASE_ID);
    expect(bundle.places).toHaveLength(24);
    expect(bundle.episodes).toHaveLength(110);
    expect(bundle.holdings).toHaveLength(2);
    expect(bundle.style.renderer_version).toBe("5.24.0");
  });

  it("fails closed when a manifest-bound artifact has different bytes", async () => {
    await expect(loadMapBundle(releaseFetcher("artist-place-episodes.json"))).rejects.toMatchObject({ status: "tampered_map_data" });
  });

  it("renders the equivalent place table with historical/current labels and all dated episodes", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Art Across Time and Place" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: /same filters as map and timeline/i });
    expect(within(table).getAllByRole("row")).toHaveLength(99);
    expect(within(table).getAllByText(/list only/i)).not.toHaveLength(0);
    expect(screen.getByText(/Modern outlines are not historical political borders/)).toBeInTheDocument();
  });

  it("uses the same artist and episode-type filters for map, timeline, and list", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    await user.selectOptions(screen.getByLabelText("Artist"), "artist:albrecht-durer");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(4);
    await user.selectOptions(screen.getByLabelText("Episode type"), "birth");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Timeline" }));
    expect(screen.getByRole("list", { name: "Place episode timeline" })).toHaveTextContent("Albrecht Dürer");
  });

  it("filters discrete episodes by keyboard-operable year controls", async () => {
    const user = userEvent.setup();
    renderPage("/art/map?view=list&fromYear=1900&toYear=1950");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByLabelText("From")).toHaveValue(1900);
    expect(screen.getByLabelText("To")).toHaveValue(1950);
    const before = within(screen.getByRole("table")).getAllByRole("row").length;
    await user.clear(screen.getByLabelText("From"));
    await user.type(screen.getByLabelText("From"), "1940");
    await waitFor(() => expect(within(screen.getByRole("table")).getAllByRole("row").length).toBeLessThan(before));
  });

  it("keeps artwork creation places fail-closed instead of using residence or holding proxies", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    await user.selectOptions(screen.getByLabelText("Layer"), "artwork_creation_place");
    expect(screen.getByText(/all remain not_asserted/i)).toBeInTheDocument();
    expect(screen.getByText(/^0$/)).toBeInTheDocument();
  });

  it("separates the two current holding institutions from creation places", async () => {
    const user = userEvent.setup();
    renderPage("/art/map?view=list&layer=current_holding_institution");
    await screen.findByRole("heading", { level: 1 });
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    await user.click(within(table).getAllByRole("button", { name: "Evidence" })[0]);
    expect(screen.getByText(/not an artwork creation place/i)).toBeInTheDocument();
    expect(screen.getByText(/6 related artworks/i)).toBeInTheDocument();
  });

  it("opens Claim/Evidence/Source-equivalent details with place and precision wording", async () => {
    renderPage("/art/map?view=list&artist=artist%3Aalbrecht-durer&episode=episode%3Aalbrecht-durer%3Abirth");
    expect(await screen.findByRole("heading", { level: 2, name: "Albrecht Dürer" })).toBeInTheDocument();
    expect(screen.getAllByText("Nuremberg").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/City centroid/).length).toBeGreaterThan(0);
    expect(screen.getByText(/does not prove a travel route/i)).toBeInTheDocument();
    expect(screen.getByText("Evidence / Source")).toBeInTheDocument();
  });

  it("sanitizes invalid IDs and never exposes an internal error", async () => {
    renderPage("/art/map?view=list&artist=artist%3Aunreviewed&place=place%3Aguessed&episode=episode%3Apending-user");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByLabelText("Artist")).toHaveValue("");
    expect(screen.getByLabelText("Place")).toHaveValue("");
    expect(screen.getByRole("heading", { level: 2, name: "Open a place record" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/stack|exception|pending user/i);
  });

  it("defaults to the equivalent list in low-bandwidth mode without loading the WebGL view", async () => {
    localStorage.setItem("museum-low-bandwidth", "true");
    renderPage("/art/map?view=map");
    expect(await screen.findByText(/preferences use the equivalent place table/i)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Two-dimensional art place map" })).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders only local formal map points and a synchronized DOM marker list", async () => {
    renderPage("/art/map?view=map");
    expect(await screen.findByRole("region", { name: "Two-dimensional art place map" })).toHaveTextContent("24 local points");
    const navigator = screen.getByRole("complementary", { name: /synchronized with the map/i });
    expect(within(navigator).getAllByRole("button")).toHaveLength(24);
  });
});
