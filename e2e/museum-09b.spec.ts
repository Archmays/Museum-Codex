import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const releaseDirectory = path.resolve("public/releases/art-expansion-batch-01-1.5.0");
const qaDirectory = path.resolve(process.env.MUSEUM09B_QA_DIR ?? "docs/qa/museum-09b-release");
const screenshotDirectory = path.join(qaDirectory, "screenshots");
mkdirSync(screenshotDirectory, { recursive: true });

type PublicArtist = {
  id: string;
  public_slug: string;
  profile_kind: "gallery" | "collection";
  labels: { en: string };
};
type PublicArtwork = {
  id: string;
  public_slug: string;
  artist_id: string;
  labels: { en: string };
  media: { decision: string };
};

const artists = (JSON.parse(readFileSync(path.join(releaseDirectory, "artists.json"), "utf8")) as { artists: PublicArtist[] }).artists;
const artworks = (JSON.parse(readFileSync(path.join(releaseDirectory, "artworks.json"), "utf8")) as { artworks: PublicArtwork[] }).artworks;
const newGallery = artists.find((artist) => artist.id.includes("m09a") && artist.profile_kind === "gallery")!;
const newCollection = artists.find((artist) => artist.id.includes("m09a") && artist.profile_kind === "collection")!;
const selfHosted = artworks.find((artwork) => artwork.id.includes("m09b") && artwork.media.decision === "approved_self_hosted")!;
const externalOnly = artworks.find((artwork) => artwork.id.includes("m09b") && artwork.media.decision === "external_link_only")!;
const metadataOnly = artworks.find((artwork) => artwork.id.includes("m09b") && artwork.media.decision === "metadata_only")!;

const viewports = [
  { width: 360, height: 800, id: "360x800" },
  { width: 390, height: 844, id: "390x844" },
  { width: 412, height: 915, id: "412x915" },
  { width: 768, height: 1024, id: "768x1024" },
  { width: 1024, height: 768, id: "1024x768" },
  { width: 1366, height: 768, id: "1366x768" },
  { width: 1440, height: 900, id: "1440x900" },
] as const;

const routeInventory = [
  "/", "/art", "/art/constellation", "/art/artists",
  `/art/artists/${newGallery.public_slug}`, `/art/artists/${newCollection.public_slug}`,
  `/art/artworks/${selfHosted.public_slug}`, `/art/artworks/${externalOnly.public_slug}`,
  `/art/artworks/${metadataOnly.public_slug}`, "/art/compare", "/art/tours",
  "/art/paths?view=text", "/art/map?view=list", "/art/search", "/about", "/rights",
  "/accessibility", "/unknown-museum-09b-route",
] as const;

type RuntimeObservation = {
  external: string[];
  images: string[];
  rendererChunks: string[];
  failures: string[];
  httpErrors: string[];
  consoleErrors: string[];
};

function expectedOrigin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observe(page: Page, origin: string): RuntimeObservation {
  const result: RuntimeObservation = { external: [], images: [], rendererChunks: [], failures: [], httpErrors: [], consoleErrors: [] };
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== origin) result.external.push(request.url());
    if (request.resourceType() === "image") result.images.push(request.url());
    if (/SigmaGraphRenderer|MapCanvas|maplibre|sigma-/i.test(url.pathname)) result.rendererChunks.push(url.pathname);
  });
  page.on("requestfailed", (request) => result.failures.push(request.url()));
  page.on("response", (response) => {
    if (response.status() >= 400) result.httpErrors.push(`${response.status()} ${response.url()}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error") result.consoleErrors.push(message.text());
  });
  return result;
}

async function installPreferences(page: Page, lowBandwidth = true) {
  await page.addInitScript(({ low }) => {
    const state = window as Window & { __museum09bGeolocationReads?: number };
    state.__museum09bGeolocationReads = 0;
    try {
      Object.defineProperty(navigator, "geolocation", {
        configurable: true,
        get() {
          state.__museum09bGeolocationReads = (state.__museum09bGeolocationReads ?? 0) + 1;
          return undefined;
        },
      });
    } catch {
      // The assertion below still proves that the native API was never called.
    }
    localStorage.setItem("museum-locale", "en");
    localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

async function gotoRoute(page: Page, route: string) {
  await page.goto(`./#${route}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("main#main-content h1")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("main#main-content")).not.toHaveClass(/route-loading/);
}

async function noHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scroll, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.client + 1);
}

async function seriousAccessibilityViolations(page: Page) {
  return page.evaluate(() => {
    const visible = (element: Element) => {
      if (element.closest("[hidden], [aria-hidden='true']")) return false;
      const closedDetails = element.closest("details:not([open])");
      if (closedDetails && !element.closest("summary")) return false;
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    };
    const accessibleText = (element: Element) => {
      const labelledBy = element.getAttribute("aria-labelledby");
      const labelled = labelledBy ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ") : "";
      const labels = "labels" in element
        ? [...((element as HTMLInputElement).labels ?? [])].map((label) => label.textContent ?? "").join(" ")
        : "";
      return [element.getAttribute("aria-label"), labelled, labels, element.getAttribute("alt"), element.getAttribute("title"), element.textContent].join(" ").trim();
    };
    const failures: Array<{ severity: "critical" | "serious"; code: string; detail: string }> = [];
    const mains = [...document.querySelectorAll("main")].filter(visible);
    const h1s = [...document.querySelectorAll("main h1")].filter(visible);
    if (mains.length !== 1) failures.push({ severity: "critical", code: "main_landmark", detail: String(mains.length) });
    if (h1s.length !== 1) failures.push({ severity: "serious", code: "page_heading", detail: String(h1s.length) });
    for (const image of document.querySelectorAll("img")) {
      if (!image.hasAttribute("alt")) failures.push({ severity: "critical", code: "image_alt", detail: image.currentSrc });
    }
    for (const element of document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, summary, [role=dialog]")) {
      if (visible(element) && !accessibleText(element)) failures.push({ severity: "critical", code: "accessible_name", detail: element.outerHTML.slice(0, 160) });
    }
    const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
    for (const id of new Set(ids)) {
      if (ids.filter((candidate) => candidate === id).length > 1) failures.push({ severity: "serious", code: "duplicate_id", detail: id });
    }
    return failures;
  });
}

async function expectControlTargets(page: Page) {
  const undersized = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>([
    "button", "summary", "input:not([type=hidden]):not([type=radio]):not([type=checkbox]):not([type=range])",
    "select", ".primary-nav a", ".site-footer a", "a.primary-button", "a.constellation-entry",
  ].join(","))].flatMap((element) => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    if (style.display === "none" || style.visibility === "hidden" || box.width === 0 || box.height === 0) return [];
    return box.height + 0.5 < 44 || box.width + 0.5 < 44
      ? [`${element.tagName.toLowerCase()}.${element.className}:${box.width.toFixed(1)}x${box.height.toFixed(1)}`]
      : [];
  }));
  expect(undersized).toEqual([]);
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.max(0, Math.ceil(sorted.length * ratio) - 1)] ?? 0;
}

async function capture(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));
  await page.screenshot({
    path: path.join(screenshotDirectory, `${name}.png`),
    fullPage: true,
    style: ".skip-link { visibility: hidden !important; }",
  });
}

test.describe.configure({ timeout: 300_000 });

test("formal M09B routes preserve identity, landmarks, no-image paths, and runtime isolation", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  const runtime = observe(page, expectedOrigin(testInfo));
  const results: Record<string, number> = {};
  for (const route of routeInventory) {
    await gotoRoute(page, route);
    await noHorizontalOverflow(page);
    const violations = await seriousAccessibilityViolations(page);
    expect(violations, route).toEqual([]);
    const publicText = await page.locator("main#main-content").innerText();
    expect(publicText, route).not.toMatch(/M09A|M09B|Batch 01|\bcandidate\b|\breview(?:ed)?\b|\binternal\b|\bMVP\b|\bPhase\b|source adapter/i);
    results[route] = violations.length;
  }
  await gotoRoute(page, "/art/artists");
  await expect(page.locator(".gallery-release-tally")).toContainText("532");
  await expect(page.locator(".artist-results-status")).toContainText("62");
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.failures).toEqual([]);
  expect(runtime.httpErrors).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(await page.evaluate(() => (window as Window & { __museum09bGeolocationReads?: number }).__museum09bGeolocationReads ?? 0)).toBe(0);
  writeFileSync(path.join(qaDirectory, "automated-a11y-results.json"), `${JSON.stringify({
    schema_version: "1.0.0", phase_id: "MUSEUM-09B-RELEASE", automated_engine: "project_dom_accessibility_gate",
    serious: 0, critical: 0, routes: results, real_assistive_technology: "not_available",
    physical_devices: "not_available", status: "pass",
  }, null, 2)}\n`);
});

test("seven required viewports retain 44 CSS pixel controls and reflow", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  const runtime = observe(page, expectedOrigin(testInfo));
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    for (const route of ["/art", "/art/artists", "/art/search", "/art/compare", "/art/map?view=list"]) {
      await gotoRoute(page, route);
      await noHorizontalOverflow(page);
      await expectControlTargets(page);
    }
  }
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
});

test("self-hosted, external-link-only, and metadata-only records retain distinct delivery behavior", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  const runtime = observe(page, expectedOrigin(testInfo));
  await gotoRoute(page, `/art/artworks/${selfHosted.public_slug}`);
  await expect(page.getByRole("heading", { level: 1, name: selfHosted.labels.en })).toBeVisible();
  await expect(page.getByRole("button", { name: "Load this artwork image" })).toBeVisible();
  expect(runtime.images).toEqual([]);
  await page.getByRole("button", { name: "Load this artwork image" }).click();
  await expect(page.getByRole("img")).toBeVisible();
  expect(runtime.images).toHaveLength(1);
  expect(new URL(runtime.images[0]).origin).toBe(expectedOrigin(testInfo));

  const imageCount = runtime.images.length;
  await gotoRoute(page, `/art/artworks/${externalOnly.public_slug}`);
  await expect(page.getByRole("heading", { level: 1, name: externalOnly.labels.en })).toBeVisible();
  await expect(page.locator(".artwork-official-link")).toBeVisible();
  await expect(page.getByRole("button", { name: "Load this artwork image" })).toHaveCount(0);
  await gotoRoute(page, `/art/artworks/${metadataOnly.public_slug}`);
  await expect(page.getByRole("heading", { level: 1, name: metadataOnly.labels.en })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Begin with the object record" })).toBeVisible();
  expect(runtime.images).toHaveLength(imageCount);
  expect(runtime.external).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
});

test("mixed new records compare without a legacy observation card", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  const runtime = observe(page, expectedOrigin(testInfo));
  await gotoRoute(page, `/art/compare?left=${encodeURIComponent(externalOnly.id)}&right=${encodeURIComponent(metadataOnly.id)}`);
  await expect(page.getByRole("heading", { level: 2, name: externalOnly.labels.en })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: metadataOnly.labels.en })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Shared and different fields" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "Begin with the object record" })).toHaveCount(2);
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
});

test("expanded search and visual text equivalents remain local and usable", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  const runtime = observe(page, expectedOrigin(testInfo));
  await gotoRoute(page, "/art/search");
  expect(await page.evaluate(() => performance.getEntriesByType("resource").filter((entry) => entry.name.includes("/search/shards/")).length)).toBe(0);
  await page.getByRole("searchbox").fill(newGallery.labels.en);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: /matches/ })).toBeVisible();
  await expect(page.getByText(newGallery.labels.en, { exact: false }).first()).toBeVisible();
  expect(await page.evaluate(() => performance.getEntriesByType("resource").filter((entry) => entry.name.includes("/search/shards/")).length)).toBeGreaterThan(0);
  for (const route of ["/art/constellation?view=list", "/art/paths?view=text", "/art/map?view=list", "/rights", "/accessibility"]) {
    await gotoRoute(page, route);
  }
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
});

test("@museum-09b-isolated-performance controlled FTI, CLS, interaction, and low-bandwidth transfer pass", async ({ browser }, testInfo) => {
  const desktopFti: number[] = [];
  const mobileFti: number[] = [];
  const cls: number[] = [];
  const transfer: number[] = [];
  const interactions: number[] = [];
  let externalRequestCount = 0;
  let unexpectedMediaPreloadCount = 0;
  let geolocationCallCount = 0;
  for (const viewport of [{ width: 390, height: 844 }, { width: 1366, height: 768 }]) {
    for (let run = 0; run < 3; run += 1) {
      const context = await browser.newContext({ baseURL: String(testInfo.project.use.baseURL), viewport });
      const page = await context.newPage();
      await installPreferences(page, true);
      const runtime = observe(page, expectedOrigin(testInfo));
      await page.addInitScript(() => {
        const state = window as Window & { __museum09bCls?: number };
        state.__museum09bCls = 0;
        new PerformanceObserver((list) => {
          for (const item of list.getEntries()) {
            const shift = item as PerformanceEntry & { value: number; hadRecentInput: boolean };
            if (!shift.hadRecentInput) state.__museum09bCls = (state.__museum09bCls ?? 0) + shift.value;
          }
        }).observe({ type: "layout-shift", buffered: true });
      });
      const started = performance.now();
      await gotoRoute(page, viewport.width < 1000 ? "/art/search" : "/art");
      const duration = performance.now() - started;
      (viewport.width < 1000 ? mobileFti : desktopFti).push(duration);
      if (viewport.width < 1000) {
        interactions.push(...await page.evaluate(async () => {
          const input = document.querySelector<HTMLInputElement>("#museum-search-query");
          const form = document.querySelector<HTMLFormElement>(".search-form");
          if (!input || !form) return [];
          const values: number[] = [];
          for (let index = 0; index < 30; index += 1) {
            const began = performance.now();
            input.value = index % 2 ? "Hua Yan" : "art";
            input.dispatchEvent(new Event("input", { bubbles: true }));
            form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
            values.push(performance.now() - began);
          }
          return values;
        }));
        cls.push(await page.evaluate(() => (window as Window & { __museum09bCls?: number }).__museum09bCls ?? 0));
        transfer.push(await page.evaluate(() => {
          const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
          return (navigation?.transferSize ?? 0) + (performance.getEntriesByType("resource") as PerformanceResourceTiming[])
            .reduce((total, entry) => total + (entry.transferSize || 0), 0);
        }));
      }
      externalRequestCount += runtime.external.length;
      unexpectedMediaPreloadCount += runtime.images.length;
      geolocationCallCount += await page.evaluate(() => (window as Window & { __museum09bGeolocationReads?: number }).__museum09bGeolocationReads ?? 0);
      expect(runtime.consoleErrors).toEqual([]);
      await context.close();
    }
  }
  const metrics = {
    schema_version: "1.0.0", phase_id: "MUSEUM-09B-RELEASE", evidence_class: "controlled_browser_probe",
    real_user_metric: false, environment: "Playwright Chromium preview", cold_runs: 3,
    desktop_first_interactive_median_ms: percentile(desktopFti, 0.5), desktop_first_interactive_p95_ms: percentile(desktopFti, 0.95),
    mobile_first_interactive_median_ms: percentile(mobileFti, 0.5), mobile_first_interactive_p95_ms: percentile(mobileFti, 0.95),
    cls_p95: percentile(cls, 0.95), interaction_runs: interactions.length, interaction_p95_ms: percentile(interactions, 0.95),
    low_bandwidth_initial_transfer_p95_bytes: percentile(transfer, 0.95), external_request_count: externalRequestCount,
    unexpected_media_preload_count: unexpectedMediaPreloadCount, geolocation_call_count: geolocationCallCount, status: "pass",
  };
  expect(metrics.desktop_first_interactive_p95_ms).toBeLessThanOrEqual(1_800);
  expect(metrics.mobile_first_interactive_p95_ms).toBeLessThanOrEqual(2_500);
  expect(metrics.cls_p95).toBeLessThanOrEqual(0.1);
  expect(metrics.interaction_p95_ms).toBeLessThanOrEqual(150);
  expect(metrics.low_bandwidth_initial_transfer_p95_bytes).toBeLessThanOrEqual(250_000);
  expect(metrics.external_request_count).toBe(0);
  expect(metrics.unexpected_media_preload_count).toBe(0);
  expect(metrics.geolocation_call_count).toBe(0);
  writeFileSync(path.join(qaDirectory, "browser-metrics.json"), `${JSON.stringify(metrics, null, 2)}\n`);
});

test("@museum-09b-screenshots captures the twelve bounded release views", async ({ page }) => {
  await installPreferences(page, true);
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoRoute(page, "/art");
  await expect(page.locator(".current-release-scope")).toContainText("62");
  await expect(page.locator(".current-release-scope")).toContainText("532");
  await capture(page, "01-art-landing-desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoRoute(page, "/art/artists"); await capture(page, "02-artist-index-mobile");
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoRoute(page, `/art/artists/${newGallery.public_slug}`); await capture(page, "03-gallery-profile-desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoRoute(page, `/art/artists/${newCollection.public_slug}`); await capture(page, "04-collection-profile-mobile");
  await gotoRoute(page, `/art/artworks/${selfHosted.public_slug}`);
  await page.getByRole("button", { name: "Load this artwork image" }).click();
  await expect(page.getByRole("img")).toBeVisible(); await capture(page, "05-self-hosted-artwork");
  await gotoRoute(page, `/art/artworks/${externalOnly.public_slug}`); await capture(page, "06-external-link-artwork");
  await gotoRoute(page, `/art/artworks/${metadataOnly.public_slug}`); await capture(page, "07-metadata-only-artwork");
  await page.setViewportSize({ width: 768, height: 1024 });
  await gotoRoute(page, `/art/compare?left=${encodeURIComponent(externalOnly.id)}&right=${encodeURIComponent(metadataOnly.id)}`); await capture(page, "08-mixed-compare");
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoRoute(page, "/art/search");
  await page.getByRole("searchbox").fill(newGallery.labels.en);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: /matches/ })).toBeVisible(); await capture(page, "09-expanded-search");
  await gotoRoute(page, "/art/constellation?view=list"); await capture(page, "10-constellation-text");
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoRoute(page, "/art/map?view=list"); await capture(page, "11-map-low-bandwidth-list");
  await gotoRoute(page, "/rights"); await capture(page, "12-rights-and-sources");
});
