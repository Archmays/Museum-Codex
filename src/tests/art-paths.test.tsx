import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ArtPathsPage from "../features/art-paths/ArtPathsPage";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../preferences/PreferencesProvider";

if (!globalThis.crypto?.subtle) Object.defineProperty(globalThis, "crypto", { configurable: true, value: webcrypto });

const originalFetch = globalThis.fetch;

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

function renderPage(entry = "/art/paths?from=artist%3Aalbrecht-durer&to=artist%3Afrancisco-de-goya&mode=comparison&maxHops=6&path=1&view=text") {
  localStorage.setItem("museum-locale", "en");
  return render(
    <I18nProvider><PreferencesProvider><MemoryRouter initialEntries={[entry]}><ArtPathsPage /></MemoryRouter></PreferencesProvider></I18nProvider>,
  );
}

beforeAll(() => {
  globalThis.fetch = releaseFetcher();
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe("MUSEUM-06 explainable artist pathways UI", () => {
  it("loads the path release and renders three modes, alternatives, and ordered text steps", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1, name: "What explainable relations connect A to B?" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Historical path/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Context path/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Comparison path/ })).toBeChecked();
    const alternatives = screen.getByRole("tablist", { name: "Alternative paths" });
    expect(within(alternatives).getAllByRole("tab")).toHaveLength(3);
    expect(screen.getAllByText(/C｜Curatorial comparison/).length).toBeGreaterThan(0);
    expect(screen.getByText(/The shortest path is not the truest or most important/)).toBeInTheDocument();
    expect(screen.getByText(/not prove acquaintance, influence, instruction, or transmission/)).toBeInTheDocument();
  });

  it("switches to an accurate historical empty state without relabeling comparison", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    await user.click(screen.getByRole("radio", { name: /Historical path/ }));
    await user.click(screen.getByRole("button", { name: "Find paths" }));
    expect(await screen.findAllByText(/No displayable path exists in the current release under these filters/)).not.toHaveLength(0);
    expect(screen.queryByRole("tablist", { name: "Alternative paths" })).not.toBeInTheDocument();
  });

  it("prevents identical endpoints and exposes the exact state through the live region", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    const selects = screen.getAllByRole("combobox").slice(0, 2);
    await user.selectOptions(selects[1], "artist:albrecht-durer");
    await user.click(screen.getByRole("button", { name: "Find paths" }));
    expect(await screen.findByRole("status", { name: "" })).toHaveTextContent("Start and end must differ.");
  });

  it("swaps endpoints, supports alternative selection, and keeps a shareable allowlisted URL", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    await user.click(screen.getByRole("button", { name: "Swap endpoints" }));
    await user.click(screen.getByRole("button", { name: "Find paths" }));
    expect(await screen.findByRole("heading", { level: 2, name: /Francisco de Goya.*Albrecht Dürer/ })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Path 2/ }));
    const print = screen.getByRole("link", { name: "Open print view" });
    expect(print.getAttribute("href")).toMatch(/from=artist%3Afrancisco-de-goya/);
    expect(print.getAttribute("href")).not.toMatch(/utm_|tracking|claim=/i);
  });

  it("expands Claim, Evidence, Source, supporting works, rights, and withdrawal status", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    const closure = screen.getAllByText("Claim → Evidence → Source")[0];
    await user.click(closure);
    await waitFor(() => expect(screen.getAllByRole("link", { name: /Art Institute|Metropolitan Museum/ }).length).toBeGreaterThan(0));
    expect(screen.getAllByText("active").length).toBeGreaterThan(0);
    await user.click(screen.getAllByText("Context · Supporting works · Rights and attribution")[0]);
    expect(screen.getAllByRole("link", { name: /.+/ }).some((link) => link.getAttribute("href")?.startsWith("/art/artworks/"))).toBe(true);
  });

  it("fails accurately for an invalid URL endpoint and stores no path history", async () => {
    renderPage("/art/paths?from=artist%3Aunreviewed&to=artist%3Afrancisco-de-goya&mode=comparison&maxHops=6&path=1&view=text");
    expect(await screen.findByRole("status", { name: "" })).toHaveTextContent("The start ID is not in the current formal artist set.");
    expect(Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index))).not.toContain("museum-path-history");
  });
});
