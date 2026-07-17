import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

type InteractionIndex = {
  release_id: string;
  release_version: string;
  hero_selections: Array<{ artist_id: string; artwork_id: string; status: string; detail_region_ids: string[] }>;
  detail_regions: Array<{ id: string; artwork_id: string }>;
  artist_tours: Array<{ id: string; artist_id: string }>;
  thematic_tours: Array<{ id: string; title: { en: string } }>;
};

type Artwork = { id: string; labels: { en: string }; media: { decision: string } };

const releaseDirectory = path.resolve("public/releases/art-gallery-interactions-1.1.0");
const interactions = JSON.parse(readFileSync(path.join(releaseDirectory, "interaction-index.json"), "utf8")) as InteractionIndex;
const artworks = (JSON.parse(readFileSync(path.join(releaseDirectory, "artworks.json"), "utf8")) as { artworks: Artwork[] }).artworks;
const visualHero = interactions.hero_selections.find((item) => item.status === "visual_detail_path");
const textualHero = interactions.hero_selections.find((item) => item.status === "textual_observation_path");
if (!visualHero || !textualHero) throw new Error("M05B hero fixtures are incomplete");
const visualRegion = interactions.detail_regions.find((item) => item.artwork_id === visualHero.artwork_id);
const textualTour = interactions.artist_tours.find((item) => item.artist_id === textualHero.artist_id);
const noImageArtwork = artworks.find((item) => item.id === textualHero.artwork_id);
if (!visualRegion || !textualTour || !noImageArtwork) throw new Error("M05B route fixtures are incomplete");

const screenshotDirectory = path.resolve(process.env.MUSEUM05B_QA_DIR ?? "docs/qa/museum-05b/screenshots");
const metricsPath = path.resolve("docs/qa/museum-05b/browser-metrics.json");
mkdirSync(screenshotDirectory, { recursive: true });

const expectedWebGlDiagnostic = /^\[\.WebGL-[^\]]+\]GL Driver Message/;

function screenshotPath(name: string) {
  return path.join(screenshotDirectory, `${name}.png`);
}

async function capture(page: Page, name: string) {
  const style = await page.addStyleTag({ content: ".skip-link:not(:focus) { visibility: hidden !important; }" });
  await page.screenshot({ path: screenshotPath(name), fullPage: true });
  await style.evaluate((element: HTMLStyleElement) => {
    element.parentNode?.removeChild(element);
  });
}

function expectedOrigin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observeRuntime(page: Page, origin: string) {
  const consoleIssues: string[] = [];
  const externalRequests: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  const mediaRequests: string[] = [];
  page.on("console", (message) => {
    if ((message.type() === "warning" || message.type() === "error") && !expectedWebGlDiagnostic.test(message.text())) {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== origin) externalRequests.push(`${request.resourceType()} ${request.url()}`);
    if (/\/releases\/art-pathways-1\.2\.0\/assets\//.test(url.pathname)) mediaRequests.push(url.pathname);
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  page.on("response", (response) => { if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`); });
  return { consoleIssues, externalRequests, failedRequests, httpErrors, mediaRequests };
}

function expectCleanRuntime(observed: ReturnType<typeof observeRuntime>) {
  expect(observed.consoleIssues).toEqual([]);
  expect(observed.externalRequests).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
  expect(observed.httpErrors).toEqual([]);
}

async function installPreferences(page: Page, lowBandwidth = false) {
  await page.addInitScript(({ low }) => {
    window.localStorage.setItem("museum-locale", "en");
    window.localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

async function installPerformanceProbe(page: Page) {
  await page.addInitScript(() => {
    const target = window as Window & { __museum05bVitals?: { lcpMs: number | null; cls: number } };
    target.__museum05bVitals = { lcpMs: null, cls: 0 };
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const latest = entries.at(-1);
      if (latest && target.__museum05bVitals) target.__museum05bVitals.lcpMs = latest.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput && target.__museum05bVitals) target.__museum05bVitals.cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
}

async function gotoGallery(page: Page, route: string) {
  const response = await page.goto(`./#${route}`, { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  const expectedRoute = route === "/art/tours"
    ? "tours"
    : route.startsWith("/art/tours/")
      ? "tour"
      : route.startsWith("/art/artworks/")
        ? "artwork"
        : route.startsWith("/art/compare")
          ? "compare"
          : route.startsWith("/art/artists/")
            ? "artist"
            : "artists";
  await expect(page.locator(`[data-museum05a-status=ready][data-gallery-route=${expectedRoute}]`)).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
}

async function expectNoOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test("@museum-05b-isolated-performance tour index exposes 12 artist and six reviewed thematic routes without eager media", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPerformanceProbe(page);
  await installPreferences(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoGallery(page, "/art/tours");
  const firstInteractiveMs = await page.evaluate(() => performance.now());

  await expect(page.getByRole("heading", { level: 1, name: "Eighteen fixed routes for slower looking" })).toBeVisible();
  await expect(page.locator("#artist-tour-index-title + .tour-index-grid > li")).toHaveCount(12);
  await expect(page.locator("#theme-tour-index-title + .tour-index-grid > li")).toHaveCount(6);
  for (const tour of interactions.thematic_tours) await expect(page.getByRole("heading", { name: tour.title.en })).toBeVisible();
  await expect(page.locator("main img")).toHaveCount(0);
  expect(observed.mediaRequests).toEqual([]);
  await expectNoOverflow(page);
  await capture(page, "tours-index-desktop");

  const initialMetrics = await page.evaluate(() => ({
    navigationDurationMs: performance.getEntriesByType("navigation")[0]?.duration ?? 0,
    resourceCount: performance.getEntriesByType("resource").length,
    viewport: { width: window.innerWidth, height: window.innerHeight },
  }));
  const tourLink = page.getByRole("link", { name: "Enter fixed tour" }).first();
  const interactionProxyMs = await tourLink.evaluate(async (element) => {
    const link = element as HTMLAnchorElement;
    return await new Promise<number>((resolve) => {
      const started = performance.now();
      const observer = new MutationObserver(() => {
        if (document.querySelector("main[data-tour-id]")) {
          observer.disconnect();
          resolve(performance.now() - started);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      link.click();
    });
  });
  await expect(page.locator("main[data-tour-id]")).toBeVisible();
  const measured = await page.evaluate(() => {
    return {
      vitals: (window as Window & { __museum05bVitals?: { lcpMs: number | null; cls: number } }).__museum05bVitals,
    };
  });
  expect(firstInteractiveMs).toBeLessThanOrEqual(1_500);
  expect(measured.vitals?.lcpMs).not.toBeNull();
  expect(measured.vitals?.lcpMs ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2_500);
  expect(measured.vitals?.cls ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(0.1);
  expect(interactionProxyMs).toBeLessThanOrEqual(200);
  writeFileSync(metricsPath, `${JSON.stringify({
    schema_version: "1.0.0",
    phase_id: "MUSEUM-05B",
    evidence_class: "controlled_browser_probe",
    real_user_metric: false,
    route: "#/art/tours",
    firstInteractiveMs,
    ...initialMetrics,
    lcpMs: measured.vitals?.lcpMs,
    cls: measured.vitals?.cls,
    interactionProxyMs,
    targets: { firstInteractiveMs: 1_500, lcpMs: 2_500, cls: 0.1, interactionProxyMs: 200 },
    status: "pass",
  }, null, 2)}\n`, "utf8");
  expectCleanRuntime(observed);
});

test("textual artist tour keeps the no-image path complete and prints every closed observation card", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoGallery(page, `/art/tours/${encodeURIComponent(textualTour.id)}?utm_source=discarded&view=print`);
  await expect.poll(() => new URL(page.url()).hash).not.toContain("utm_source");
  await expect(page.locator("main[data-tour-id]")).toHaveAttribute("data-tour-id", textualTour.id);
  expect(await page.locator(".tour-work-list > ol > li").count()).toBeGreaterThanOrEqual(2);
  await expect(page.locator(".tour-step-reason").first()).toBeVisible();
  await expect(page.locator("main img")).toHaveCount(0);
  await page.locator(".tour-work-list details").first().evaluate((element: HTMLDetailsElement) => { element.open = true; });
  const card = page.locator(".observation-card").first();
  await expect(card).toContainText("Date");
  await expect(card).toContainText("Institution");
  await expect(card).toContainText("Automated review passed");
  await expect(card.getByRole("heading", { name: "Evidence links" })).toBeVisible();
  await expect(card.getByRole("heading", { name: "Source links" })).toBeVisible();
  await expect(card.locator("a[href^='https://']").first()).toBeVisible();

  await page.emulateMedia({ media: "print" });
  const closedCardBody = page.locator(".tour-work-list details").nth(1).locator(".observation-card");
  await expect(closedCardBody).toHaveCSS("display", "block");
  await expect(card).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await capture(page, "textual-tour-print-mobile");
  await expectNoOverflow(page);
  expect(observed.mediaRequests).toEqual([]);
  expectCleanRuntime(observed);
});

test("shared detail-region URL restores the actual zoom view and keyboard reset clears it", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPreferences(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await gotoGallery(page, `/art/artworks/${encodeURIComponent(visualHero.artwork_id)}?region=${encodeURIComponent(visualRegion.id)}&utm_medium=discarded`);
  await expect.poll(() => new URL(page.url()).hash).not.toContain("utm_medium");
  const regionButton = page.getByRole("button", { name: "Detail region 1" });
  await expect(regionButton).toHaveAttribute("aria-pressed", "true");
  const viewport = page.getByRole("group", { name: /Zoomable artwork image:/ });
  await expect.poll(async () => {
    const style = await viewport.locator("img").getAttribute("style");
    return Number(/scale\(([^)]+)\)/.exec(style ?? "")?.[1] ?? 1);
  }).toBeGreaterThan(1);
  await expect(page.locator(".artwork-zoom-controls output")).not.toHaveText("Zoom 100%");
  await capture(page, "artwork-detail-region-desktop");

  await viewport.focus();
  await page.keyboard.press("Escape");
  await expect(page.locator(".detail-region-status")).toHaveText("Current: overview");
  await expect(page.locator(".artwork-zoom-controls output")).toHaveText("Zoom 100%");
  await expect.poll(() => new URL(page.url()).hash).not.toContain("region=");
  expectCleanRuntime(observed);
});

test("metadata-only artwork retains cards, lenses, sources, print/share, and no fabricated visual task", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPreferences(page);
  await page.setViewportSize({ width: 360, height: 800 });
  await gotoGallery(page, `/art/artworks/${encodeURIComponent(noImageArtwork.id)}`);
  const main = page.locator(`main[data-artwork-id="${noImageArtwork.id}"]`);
  await expect(main).toHaveAttribute("data-media-decision", noImageArtwork.media.decision);
  await expect(main.locator(".artwork-detail-no-image")).toBeVisible();
  await expect(main.locator("img")).toHaveCount(0);
  await expect(main.locator(".observation-card")).toContainText("Complete metadata and evidence path");
  await expect(main.locator(".observation-card")).toContainText("No visual-detail task is assigned");
  await expect(main.locator(".detail-navigator")).toHaveCount(0);
  await expect(main.locator(".observation-lens-grid details")).toHaveCount(3);
  await expect(main.getByRole("link", { name: "Open print view" })).toBeVisible();
  await expect(main.getByRole("button", { name: "Copy share link" })).toBeVisible();
  await capture(page, "no-image-observation-mobile");
  await expectNoOverflow(page);
  expect(observed.mediaRequests).toEqual([]);
  expectCleanRuntime(observed);
});

test("mixed compare consumes formal lenses and prompts, preserves independent detail state, and prints only a small image", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPreferences(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  const left = encodeURIComponent(visualHero.artwork_id);
  const right = encodeURIComponent(noImageArtwork.id);
  await gotoGallery(page, `/art/compare?left=${left}&right=${right}&tracking=discarded`);
  await expect.poll(() => new URL(page.url()).hash).not.toContain("tracking=");
  await expect(page.locator(".compare-work")).toHaveCount(2);
  await expect(page.locator(".compare-fields")).toContainText("Shared and different fields");
  await page.getByRole("button", { name: "Material lens" }).click();
  await expect(page.getByRole("button", { name: "Material lens" })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => new URL(page.url()).hash).toContain("lens=material");
  await page.getByRole("button", { name: "Detail region 1" }).click();
  await expect.poll(() => new URL(page.url()).hash).toContain("leftRegion=");
  await expect(page.locator(".compare-prompts li")).toHaveCount(3);
  await expect(page.locator(".compare-prompts")).toContainText("Juxtaposition creates no similarity score");
  await capture(page, "compare-mixed-desktop");

  observed.mediaRequests.length = 0;
  await page.getByRole("link", { name: "Open print view" }).click();
  await expect.poll(() => new URL(page.url()).hash).toContain("view=print");
  const printImage = page.locator(".compare-work img");
  await expect(printImage).toHaveCount(1);
  await expect(printImage).toHaveAttribute("src", /\/320w\.jpg$/);
  await expect(printImage).not.toHaveAttribute("srcset");
  expect(observed.mediaRequests.every((url) => /\/320w\.jpg$/.test(url))).toBe(true);
  expectCleanRuntime(observed);
});

test("touch, forced-colors, reduced-motion, invalid routes, and storage boundaries remain usable", async ({ browser }, testInfo) => {
  const context = await createTouchContext(browser, testInfo);
  const page = await context.newPage();
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installPreferences(page);
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await gotoGallery(page, `/art/artworks/${encodeURIComponent(visualHero.artwork_id)}`);
  const regionButton = page.getByRole("button", { name: "Detail region 1" });
  await expect(regionButton).toBeVisible();
  const box = await regionButton.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  await regionButton.tap();
  await expect(regionButton).toHaveAttribute("aria-pressed", "true");
  expect(await regionButton.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
  await expectNoOverflow(page);

  await page.evaluate(() => { window.location.hash = "/art/tours/not-a-formal-tour"; });
  await expect(page.locator("[data-museum05a-status=ready][data-gallery-route=tour]")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "This formal tour was not found" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("[data-museum05a-status=ready][data-gallery-route=tour]")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "This formal tour was not found" })).toBeVisible();
  const storageKeys = await page.evaluate(() => Object.keys(window.localStorage).sort());
  expect(storageKeys).toEqual(["museum-locale", "museum-low-bandwidth"]);
  await context.close();
  expectCleanRuntime(observed);
});

async function createTouchContext(browser: Browser, testInfo: TestInfo) {
  return browser.newContext({
    baseURL: String(testInfo.project.use.baseURL),
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 844 },
  });
}
