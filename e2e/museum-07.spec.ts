import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const screenshotDirectory = path.resolve(process.env.MUSEUM07_QA_DIR ?? "docs/qa/museum-07/screenshots");
const metricsPath = path.resolve("docs/qa/museum-07/browser-metrics.json");
const expectedWebGlDiagnostic = /^\[\.WebGL-[^\]]+\]GL Driver Message/;
const expectedContextLossCleanup = /^There is no style added to the map\.$/;
mkdirSync(screenshotDirectory, { recursive: true });

type MapStyleProbe = {
  style: { layers: Array<{ id: string }> };
  runtime_guards: Record<string, boolean | number>;
};

function expectedOrigin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observeRuntime(page: Page, origin: string) {
  const consoleIssues: string[] = [];
  const externalRequests: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  const imageRequests: string[] = [];
  page.on("console", (message) => {
    if ((message.type() === "warning" || message.type() === "error") && !expectedWebGlDiagnostic.test(message.text()) && !expectedContextLossCleanup.test(message.text())) {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== origin) externalRequests.push(`${request.resourceType()} ${request.url()}`);
    if (request.resourceType() === "image") imageRequests.push(request.url());
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  page.on("response", (response) => { if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`); });
  return { consoleIssues, externalRequests, failedRequests, httpErrors, imageRequests };
}

function expectCleanRuntime(observed: ReturnType<typeof observeRuntime>) {
  expect(observed.consoleIssues).toEqual([]);
  expect(observed.externalRequests).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
  expect(observed.httpErrors).toEqual([]);
}

async function installEnglish(page: Page, lowBandwidth = false) {
  await page.addInitScript(({ low }) => {
    localStorage.setItem("museum-locale", "en");
    if (localStorage.getItem("museum-low-bandwidth") === null) localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

async function installVitals(page: Page) {
  await page.addInitScript(() => {
    const target = window as Window & { __museum07Vitals?: { cls: number } };
    target.__museum07Vitals = { cls: 0 };
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput && target.__museum07Vitals) target.__museum07Vitals.cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
}

async function gotoMap(page: Page, query = "view=map", waitUntil: "domcontentloaded" | "networkidle" = "networkidle") {
  const response = await page.goto(`./#/art/map?${query}`, { waitUntil });
  if (response) expect(response.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1, name: "Art Across Time and Place" })).toBeVisible();
}

async function expectNoOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

async function capture(page: Page, name: string) {
  const style = await page.addStyleTag({ content: ".skip-link:not(:focus) { visibility: hidden !important; }" });
  await page.screenshot({ path: path.join(screenshotDirectory, `${name}.png`), fullPage: true });
  await style.evaluate((element: HTMLStyleElement) => element.remove());
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.ceil(sorted.length * ratio) - 1];
}

test("local-only map exposes synchronized markers, evidence, uncertainty, and no political or route layers", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await gotoMap(page);
  await expect(page.getByText("258 / 24 / 400")).toBeVisible();
  await expect(page.getByRole("region", { name: "Two-dimensional art place map" })).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  const markerNavigator = page.getByRole("complementary", { name: /synchronized with the map/i });
  await expect(markerNavigator.getByRole("button")).toHaveCount(24);
  await expect.poll(() => page.locator(".map-place-marker").count()).toBeGreaterThan(0);
  await markerNavigator.getByRole("button").first().click();
  await expect(page.locator(".map-selection")).toContainText("What it proves");
  await expect(page.locator(".map-selection")).toContainText("What it does not prove");
  await page.locator(".map-selection details").first().getByText("Evidence / Source").click();
  await expect(page.locator(".map-selection details").first().locator("a[href^='https://']")).toBeVisible();
  await expect(page.getByText(/Modern outlines are not historical political borders/)).toBeVisible();
  await expect(page.getByText(/current holding institution is not a creation place/i)).toBeVisible();
  const style = await page.evaluate(async (): Promise<MapStyleProbe> => {
    const response = await fetch("./releases/art-expansion-batch-05-1.9.0/map-style.json");
    return await response.json() as MapStyleProbe;
  });
  expect(style.style.layers.map((layer) => layer.id)).toEqual(["background", "land", "lakes", "coastline", "uncertainty-halos", "place-markers"]);
  expect(style.runtime_guards).toMatchObject({ tile_urls: false, remote_style: false, glyphs: false, sprite: false, geolocation: false, route_lines: false });
  expect(observed.imageRequests).toEqual([]);
  await capture(page, "art-map-desktop-evidence");
  await page.locator(".maplibregl-canvas").dispatchEvent("webglcontextlost");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText(/rendering is unavailable; switched to the equivalent place table/i)).toBeAttached();
  await expectNoOverflow(page);
  expectCleanRuntime(observed);
});

test("map, timeline, and place table share allowlisted URL state and keep holding separate from creation", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await gotoMap(page, "view=list&artist=artist%3Aunreviewed&episode=episode%3Apending&tracking=discarded&lat=51");
  await expect(page.locator(".map-place-table tbody tr")).toHaveCount(386);
  await expect.poll(() => new URL(page.url()).hash).not.toContain("tracking");
  expect(page.url()).not.toMatch(/unreviewed|pending|lat=/);
  const artistSelect = page.locator(".map-filter-grid label").filter({ hasText: /^Artist/ }).locator("select");
  const layerSelect = page.locator(".map-filter-grid label").filter({ hasText: /^Layer/ }).locator("select");
  await artistSelect.selectOption({ index: 1 });
  await expect(page.locator(".map-place-table tbody tr")).toHaveCount(3);
  const selectedArtist = await artistSelect.inputValue();
  await page.getByRole("button", { name: "Timeline", exact: true }).click();
  await expect(page.getByRole("list", { name: "Place episode timeline" }).locator(":scope > li")).toHaveCount(3);
  await page.reload({ waitUntil: "networkidle" });
  await expect(artistSelect).toHaveValue(selectedArtist);
  await expect(page.getByRole("list", { name: "Place episode timeline" })).toBeVisible();
  await artistSelect.selectOption("");
  await expect(page.locator(".map-timeline em").filter({ hasText: "list only" }).first()).toBeVisible();
  await layerSelect.selectOption("current_holding_institution");
  await expect(page.locator(".map-place-table tbody tr")).toHaveCount(2);
  await page.locator(".map-place-table tbody tr").first().getByRole("button", { name: "Evidence" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Current holding institution" })).toBeVisible();
  await expect(page.locator(".selection-limit")).toContainText(/not.*creation/i);
  await layerSelect.selectOption("artwork_creation_place");
  await expect(page.locator(".map-empty-state")).toContainText("0");
  await expect(page.locator(".map-empty-state")).toContainText("not_asserted");
  await capture(page, "art-map-timeline-holding-separation");
  expectCleanRuntime(observed);
});

test("WebGL failure, forced colors, reduced motion, mobile, keyboard, and print retain the equivalent task", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await page.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.emulateMedia({ forcedColors: "none", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoMap(page);
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText(/rendering is unavailable; switched to the equivalent place table/i)).toBeAttached();
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  const resetBox = await page.getByRole("button", { name: "Reset" }).boundingBox();
  expect(resetBox?.height ?? 0).toBeGreaterThanOrEqual(44);
  await expectNoOverflow(page);
  await capture(page, "art-map-mobile-forced-colors-fallback");
  await page.getByRole("button", { name: "Print timeline/place table" }).click();
  await page.emulateMedia({ media: "print", forcedColors: "none", reducedMotion: "reduce" });
  await expect(page.getByRole("table")).toBeVisible();
  await capture(page, "art-map-print-place-table");
  expectCleanRuntime(observed);
});

test("@museum-07-isolated-performance controlled first-interactive, filter, marker, heap, CLS, privacy, and request metrics pass", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  let geolocationCalls = 0;
  await page.exposeFunction("__museum07RecordGeolocation", () => { geolocationCalls += 1; });
  await page.addInitScript(() => {
    const record = () => void (window as Window & { __museum07RecordGeolocation?: () => Promise<void> }).__museum07RecordGeolocation?.();
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: {
      getCurrentPosition: record, watchPosition: () => { record(); return 0; }, clearWatch: () => undefined,
    } });
  });
  await installEnglish(page);
  await installVitals(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  let started = performance.now();
  await gotoMap(page, "view=map", "domcontentloaded");
  await expect(page.getByRole("complementary", { name: /synchronized with the map/i })).toBeVisible();
  const desktopFirstInteractive = performance.now() - started;

  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const heapUsed = async () => {
    const result = await session.send("Performance.getMetrics");
    return result.metrics.find((metric) => metric.name === "JSHeapUsedSize")?.value ?? 0;
  };
  await page.goto("./#/art", { waitUntil: "networkidle" });
  await session.send("HeapProfiler.collectGarbage");
  const heapBefore = await heapUsed();
  await page.setViewportSize({ width: 390, height: 844 });
  started = performance.now();
  await gotoMap(page, "view=map", "domcontentloaded");
  await expect(page.getByRole("complementary", { name: /synchronized with the map/i })).toBeVisible();
  const mobileFirstInteractive = performance.now() - started;
  await session.send("HeapProfiler.collectGarbage");
  const heapAfter = await heapUsed();

  const interactionRuns = await page.evaluate(async () => {
    const artist = document.querySelector<HTMLSelectElement>(".map-filter-grid select");
    if (!artist) return { filters: [], markers: [] };
    const firstArtist = artist.options[1]?.value ?? "";
    const filters: number[] = [];
    for (let index = 0; index < 30; index += 1) {
      const runStarted = performance.now();
      artist.value = index % 2 ? firstArtist : "";
      artist.dispatchEvent(new Event("change", { bubbles: true }));
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      filters.push(performance.now() - runStarted);
    }
    artist.value = "";
    artist.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    const buttons = [...document.querySelectorAll<HTMLButtonElement>(".map-place-marker")];
    const markers: number[] = [];
    for (let index = 0; index < 30; index += 1) {
      const runStarted = performance.now();
      buttons[index % buttons.length].click();
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      markers.push(performance.now() - runStarted);
    }
    return { filters, markers };
  });
  expect(interactionRuns.filters).toHaveLength(30);
  expect(interactionRuns.markers).toHaveLength(30);

  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    document.documentElement.style.scrollBehavior = "auto";
    history.scrollRestoration = "manual";
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    localStorage.setItem("museum-low-bandwidth", "true");
  });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  started = performance.now();
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 1, name: "Art Across Time and Place" })).toBeVisible();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByRole("table")).toBeVisible();
  const lowBandwidthFirstInteractive = performance.now() - started;
  const cls = await page.evaluate(() => (window as Window & { __museum07Vitals?: { cls: number } }).__museum07Vitals?.cls ?? 0);
  const storageKeys = await page.evaluate(() => Object.keys(localStorage).sort());
  const filterP95 = percentile(interactionRuns.filters, 0.95);
  const markerP95 = percentile(interactionRuns.markers, 0.95);
  const heapIncrement = Math.max(0, heapAfter - heapBefore);
  expect(desktopFirstInteractive).toBeLessThanOrEqual(1800);
  expect(mobileFirstInteractive).toBeLessThanOrEqual(2500);
  expect(lowBandwidthFirstInteractive).toBeLessThanOrEqual(2000);
  expect(filterP95).toBeLessThanOrEqual(150);
  expect(markerP95).toBeLessThanOrEqual(100);
  expect(heapIncrement).toBeLessThanOrEqual(40 * 1024 * 1024);
  expect(cls).toBeLessThanOrEqual(0.1);
  expect(storageKeys).toEqual(["museum-locale", "museum-low-bandwidth"]);
  expect(geolocationCalls).toBe(0);
  expectCleanRuntime(observed);
  const metrics = {
    schema_version: "1.0.0", phase_id: "MUSEUM-07", evidence_class: "controlled_browser_probe", real_user_metric: false,
    route: "#/art/map", desktop_first_interactive_ms: Number(desktopFirstInteractive.toFixed(3)),
    mobile_first_interactive_ms: Number(mobileFirstInteractive.toFixed(3)),
    low_bandwidth_list_first_interactive_ms: Number(lowBandwidthFirstInteractive.toFixed(3)),
    filter_runs: interactionRuns.filters.length, filter_p95_ms: Number(filterP95.toFixed(3)),
    marker_selection_runs: interactionRuns.markers.length, marker_selection_p95_ms: Number(markerP95.toFixed(3)),
    mobile_heap_increment_bytes: heapIncrement, cls, external_request_count: observed.externalRequests.length,
    analytics_request_count: 0, geolocation_call_count: geolocationCalls, storage_keys: storageKeys, status: "pass",
  };
  writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
});
