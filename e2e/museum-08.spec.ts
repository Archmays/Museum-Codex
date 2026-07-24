import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const qaDirectory = path.resolve(process.env.MUSEUM08_QA_DIR ?? "docs/qa/museum-08");
const screenshotDirectory = path.join(qaDirectory, "screenshots");
mkdirSync(screenshotDirectory, { recursive: true });

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
  "/",
  "/art",
  "/art/constellation",
  "/art/artists",
  "/art/artists/artist:albrecht-durer",
  "/art/artworks/artwork:met-54876",
  "/art/compare",
  "/art/tours",
  "/art/tours/tour:artist-albrecht-durer",
  "/art/paths",
  "/art/map?view=list",
  "/art/search",
  "/about",
  "/rights",
  "/accessibility",
  "/unknown-museum-route",
] as const;

type RuntimeObservation = {
  external: string[];
  images: string[];
  rendererChunks: string[];
  failures: string[];
  httpErrors: string[];
};

function origin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observe(page: Page, expectedOrigin: string): RuntimeObservation {
  const result: RuntimeObservation = {
    external: [],
    images: [],
    rendererChunks: [],
    failures: [],
    httpErrors: [],
  };
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== expectedOrigin) result.external.push(request.url());
    if (request.resourceType() === "image") result.images.push(request.url());
    if (/SigmaGraphRenderer|MapCanvas|maplibre|sigma-/i.test(url.pathname)) {
      result.rendererChunks.push(url.pathname);
    }
  });
  page.on("requestfailed", (request) => result.failures.push(request.url()));
  page.on("response", (response) => {
    if (response.status() >= 400) result.httpErrors.push(`${response.status()} ${response.url()}`);
  });
  return result;
}

async function installPreferences(page: Page, lowBandwidth = true) {
  await page.addInitScript(({ low }) => {
    const state = window as Window & { __museum08GeolocationReads?: number };
    state.__museum08GeolocationReads = 0;
    try {
      Object.defineProperty(navigator, "geolocation", {
        configurable: true,
        get() {
          state.__museum08GeolocationReads = (state.__museum08GeolocationReads ?? 0) + 1;
          return undefined;
        },
      });
    } catch {
      // The runtime gate still checks that the native API is never called.
    }
    localStorage.setItem("museum-locale", "en");
    localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

async function gotoRoute(page: Page, route: string) {
  await page.goto(`./#${route}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("main#main-content h1")).toBeVisible({ timeout: 20_000 });
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
    const text = (element: Element) => {
      const labelledBy = element.getAttribute("aria-labelledby");
      const labelled = labelledBy
        ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ")
        : "";
      const controlLabels = "labels" in element
        ? [...((element as HTMLInputElement).labels ?? [])].map((label) => label.textContent ?? "").join(" ")
        : "";
      return [
        element.getAttribute("aria-label"),
        labelled,
        controlLabels,
        element.getAttribute("alt"),
        element.getAttribute("title"),
        (element as HTMLElement).innerText,
        element.textContent,
      ].join(" ").trim();
    };
    const failures: Array<{ severity: "critical" | "serious"; code: string; detail: string }> = [];
    const mains = [...document.querySelectorAll("main")].filter(visible);
    if (mains.length !== 1) failures.push({ severity: "critical", code: "main_landmark", detail: String(mains.length) });
    const h1s = [...document.querySelectorAll("main h1")].filter(visible);
    if (h1s.length !== 1) failures.push({ severity: "serious", code: "page_heading", detail: String(h1s.length) });
    if (!document.querySelector("header.site-header")) failures.push({ severity: "serious", code: "site_header", detail: "missing" });
    if (!document.querySelector("nav.primary-nav")) failures.push({ severity: "serious", code: "primary_navigation", detail: "missing" });
    if (!document.querySelector("footer.site-footer")) failures.push({ severity: "serious", code: "site_footer", detail: "missing" });

    const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
    for (const id of new Set(ids)) {
      if (ids.filter((candidate) => candidate === id).length > 1) {
        failures.push({ severity: "serious", code: "duplicate_id", detail: id });
      }
    }
    for (const image of document.querySelectorAll("img")) {
      if (!image.hasAttribute("alt")) failures.push({ severity: "critical", code: "image_alt", detail: image.currentSrc });
    }
    for (const element of document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, summary, [role=dialog]")) {
      if (visible(element) && !text(element)) {
        failures.push({ severity: "critical", code: "accessible_name", detail: element.outerHTML.slice(0, 160) });
      }
    }
    for (const table of document.querySelectorAll("table")) {
      if (visible(table) && !table.querySelector("caption") && !table.getAttribute("aria-label") && !table.getAttribute("aria-labelledby")) {
        failures.push({ severity: "serious", code: "table_name", detail: table.className });
      }
    }
    return failures;
  });
}

async function expectControlTargets(page: Page) {
  const undersized = await page.evaluate(() => {
    const selectors = [
      "button",
      "summary",
      "input:not([type=hidden]):not([type=radio]):not([type=checkbox]):not([type=range])",
      "select",
      ".primary-nav a",
      ".site-footer a",
      "a.primary-button",
      "a.constellation-entry",
    ].join(",");
    return [...document.querySelectorAll<HTMLElement>(selectors)].flatMap((element) => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      if (style.display === "none" || style.visibility === "hidden" || box.width === 0 || box.height === 0) return [];
      return box.height + 0.5 < 44 || box.width + 0.5 < 44
        ? [`${element.tagName.toLowerCase()}.${element.className}:${box.width.toFixed(1)}x${box.height.toFixed(1)}`]
        : [];
    });
  });
  expect(undersized).toEqual([]);
}

async function capture(page: Page, name: string) {
  await page.evaluate(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  });
  await page.waitForFunction(() => {
    const skip = document.querySelector(".skip-link");
    return !skip || skip.getBoundingClientRect().bottom <= 0;
  });
  await page.screenshot({
    path: path.join(screenshotDirectory, `${name}.png`),
    fullPage: true,
    style: ".skip-link { visibility: hidden !important; }",
  });
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.max(0, Math.ceil(sorted.length * ratio) - 1)] ?? 0;
}

test.describe.configure({ timeout: 240_000 });

test("all formal route templates keep landmarks, names, text fallbacks, and mobile reflow", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  const runtime = observe(page, origin(testInfo));
  const results: Record<string, number> = {};
  for (const route of routeInventory) {
    await gotoRoute(page, route);
    await noHorizontalOverflow(page);
    const violations = await seriousAccessibilityViolations(page);
    expect(violations, route).toEqual([]);
    results[route] = violations.length;
  }
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(await page.evaluate(() =>
    (window as Window & { __museum08GeolocationReads?: number }).__museum08GeolocationReads ?? 0
  )).toBe(0);
  writeFileSync(
    path.join(qaDirectory, "automated-a11y-results.json"),
    `${JSON.stringify({
      schema_version: "1.0.0",
      phase_id: "MUSEUM-08",
      automated_engine: "project_dom_accessibility_gate",
      serious: 0,
      critical: 0,
      routes: results,
      real_assistive_technology: "not_available",
      physical_devices: "not_available",
      status: "pass",
    }, null, 2)}\n`,
    "utf8",
  );
});

for (const viewport of viewports) {
  test(`viewport ${viewport.id} keeps core controls visible and at least 44 CSS pixels`, async ({ page }, testInfo) => {
    await installPreferences(page, true);
    await page.setViewportSize(viewport);
    const runtime = observe(page, origin(testInfo));
    for (const route of ["/art", "/art/search", "/art/compare", "/art/map?view=list"]) {
      await gotoRoute(page, route);
      await noHorizontalOverflow(page);
      await expectControlTargets(page);
    }
    expect(runtime.external).toEqual([]);
    expect(runtime.images).toEqual([]);
  });
}

test("keyboard, focus, forced colors, reduced motion, 200 percent reflow, orientation, and virtual keyboard layout remain usable", async ({ page }) => {
  await installPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await gotoRoute(page, "/");
  await page.keyboard.press("Tab");
  await expect(page.locator(".skip-link")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#main-content")).toBeFocused();
  await page.getByRole("link", { name: "Art Museum" }).click();
  await expect(page.locator("main#main-content")).toBeFocused();
  await noHorizontalOverflow(page);

  await page.setViewportSize({ width: 640, height: 900 });
  await gotoRoute(page, "/art/paths?view=text");
  await noHorizontalOverflow(page);
  await expect(page.locator(".path-text-equivalent")).toBeVisible();

  await page.setViewportSize({ width: 844, height: 390 });
  await noHorizontalOverflow(page);
  await page.setViewportSize({ width: 390, height: 500 });
  await gotoRoute(page, "/art/search");
  const search = page.getByRole("searchbox");
  await search.focus();
  await search.evaluate((element) => element.scrollIntoView({ block: "center" }));
  const box = await search.boundingBox();
  expect((box?.y ?? 501) + (box?.height ?? 0)).toBeLessThanOrEqual(500);

  await page.emulateMedia({ media: "print", forcedColors: "none", reducedMotion: "reduce" });
  await expect(page.locator(".print-masthead")).toBeVisible();
  await expect(page.locator("main#main-content h1")).toBeVisible();
});

test("low-bandwidth search and visual routes make no media, renderer, external, or unexpected preload request", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  const runtime = observe(page, origin(testInfo));
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoRoute(page, "/art/search");
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.external).toEqual([]);
  expect(runtime.httpErrors).toEqual([]);
  expect(runtime.failures).toEqual([]);
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(await page.locator("img").count()).toBe(0);
  expect(await page.evaluate(() =>
    performance.getEntriesByType("resource").filter((entry) => entry.name.includes("/search/shards/")).length
  )).toBe(0);

  await page.getByRole("searchbox").fill("Dürer");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: /matches/ })).toBeVisible();
  expect(await page.evaluate(() =>
    performance.getEntriesByType("resource").filter((entry) => entry.name.includes("/search/shards/")).length
  )).toBeGreaterThan(0);

  for (const route of ["/art/constellation", "/art/map", "/art/tours", "/art/compare", "/art/paths"]) {
    await gotoRoute(page, route);
  }
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.external).toEqual([]);
  const keys = await page.evaluate(() => Object.keys(localStorage).sort());
  expect(keys).toEqual(["museum-locale", "museum-low-bandwidth"]);
});

test("missing route chunks retain a natural recovery path instead of a blank shell", async ({ page }) => {
  await installPreferences(page, true);
  await gotoRoute(page, "/");
  await page.route("**/assets/*.js", async (route) => {
    if (/ArtSearchPage/i.test(new URL(route.request().url()).pathname)) await route.abort("failed");
    else await route.continue();
  });
  await page.evaluate(() => { window.location.hash = "#/art/search"; });
  await expect(page.getByRole("heading", { level: 1, name: "This part did not load completely" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("route file");
  await page.getByRole("link", { name: "Back to Art foyer" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "One work can open many paths" })).toBeVisible();
});

test("stale search release can retry and withdrawn or missing stable IDs fail naturally", async ({ page }) => {
  await installPreferences(page, true);
  let failedOnce = false;
  await page.route("**/releases/art-expansion-batch-05-1.9.0/search/manifest.json", async (route) => {
    if (!failedOnce) {
      failedOnce = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    } else {
      await route.continue();
    }
  });
  await page.goto("./#/art/search", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 2, name: "Search material is unavailable" })).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Index shards load on the first search" })).toBeVisible();

  await gotoRoute(page, "/art/artworks/artwork:synthetic-withdrawn-record");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/formal record.*found/i);
  await expect(page.getByRole("link", { name: /artist index/i })).toBeVisible();
});

test("failed artwork bytes preserve metadata and the no-image equivalent", async ({ page }) => {
  await installPreferences(page, true);
  await page.route("**/releases/**/assets/**/*", (route) => route.abort("failed"));
  await gotoRoute(page, "/art/artworks/artwork:met-54876");
  await page.getByRole("button", { name: "Load this artwork image" }).click();
  await expect(page.getByRole("img", { name: /image could not be decoded/i })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: /Two Tori-oi/i })).toBeVisible();
  await expect(page.locator(".artwork-object-record")).toBeVisible();
});

test("no-script document preserves museum, art, and rights entry information", async ({ browser }, testInfo) => {
  const context = await browser.newContext({
    baseURL: String(testInfo.project.use.baseURL),
    javaScriptEnabled: false,
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await page.goto("./", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1, name: "博物馆 · Museum" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Artist connections/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Rights/ })).toBeVisible();
  await noHorizontalOverflow(page);
  await context.close();
});

test("@museum-08-isolated-performance controlled candidate FTI, CLS, interaction, and low-bandwidth transfer pass", async ({ browser }, testInfo) => {
  const desktopFti: number[] = [];
  const mobileFti: number[] = [];
  const cls: number[] = [];
  const transfer: number[] = [];
  const interactions: number[] = [];
  let externalRequestCount = 0;
  let unexpectedMediaPreloadCount = 0;
  let geolocationCallCount = 0;
  for (let run = 0; run < 3; run += 1) {
    const context = await browser.newContext({
      baseURL: String(testInfo.project.use.baseURL),
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    await installPreferences(page, true);
    const runtime = observe(page, origin(testInfo));
    await page.addInitScript(() => {
      const state = window as Window & { __museum08Cls?: number };
      state.__museum08Cls = 0;
      new PerformanceObserver((list) => {
        for (const item of list.getEntries()) {
          const shift = item as PerformanceEntry & { value: number; hadRecentInput: boolean };
          if (!shift.hadRecentInput) state.__museum08Cls = (state.__museum08Cls ?? 0) + shift.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
    });
    const started = performance.now();
    await gotoRoute(page, "/art/search");
    mobileFti.push(performance.now() - started);
    const runs = await page.evaluate(async () => {
      const input = document.querySelector<HTMLInputElement>("#museum-search-query");
      const form = document.querySelector<HTMLFormElement>(".search-form");
      if (!input || !form) return [];
      const values: number[] = [];
      for (let index = 0; index < 30; index += 1) {
        const began = performance.now();
        input.value = index % 2 ? "Dürer" : "art";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
        values.push(performance.now() - began);
      }
      return values;
    });
    interactions.push(...runs);
    cls.push(await page.evaluate(() => (window as Window & { __museum08Cls?: number }).__museum08Cls ?? 0));
    transfer.push(await page.evaluate(() => {
      const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      return (navigation?.transferSize ?? 0) + performance.getEntriesByType("resource")
        .reduce((total, entry) => total + ((entry as PerformanceResourceTiming).transferSize || 0), 0);
    }));
    expect(runtime.external).toEqual([]);
    expect(runtime.images).toEqual([]);
    externalRequestCount += runtime.external.length;
    unexpectedMediaPreloadCount += runtime.images.length;
    geolocationCallCount += await page.evaluate(() =>
      (window as Window & { __museum08GeolocationReads?: number }).__museum08GeolocationReads ?? 0
    );
    await context.close();
  }
  for (let run = 0; run < 3; run += 1) {
    const context = await browser.newContext({
      baseURL: String(testInfo.project.use.baseURL),
      viewport: { width: 1366, height: 768 },
    });
    const page = await context.newPage();
    await installPreferences(page, false);
    const runtime = observe(page, origin(testInfo));
    const started = performance.now();
    await gotoRoute(page, "/art");
    desktopFti.push(performance.now() - started);
    expect(runtime.external).toEqual([]);
    expect(runtime.images).toEqual([]);
    externalRequestCount += runtime.external.length;
    unexpectedMediaPreloadCount += runtime.images.length;
    geolocationCallCount += await page.evaluate(() =>
      (window as Window & { __museum08GeolocationReads?: number }).__museum08GeolocationReads ?? 0
    );
    await context.close();
  }
  const metrics = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-08",
    evidence_class: "controlled_browser_probe",
    real_user_metric: false,
    environment: "Playwright Chromium local preview",
    cold_runs: 3,
    desktop_first_interactive_median_ms: percentile(desktopFti, 0.5),
    desktop_first_interactive_p95_ms: percentile(desktopFti, 0.95),
    mobile_first_interactive_median_ms: percentile(mobileFti, 0.5),
    mobile_first_interactive_p95_ms: percentile(mobileFti, 0.95),
    cls_p95: percentile(cls, 0.95),
    interaction_runs: interactions.length,
    interaction_p95_ms: percentile(interactions, 0.95),
    low_bandwidth_initial_transfer_p95_bytes: percentile(transfer, 0.95),
    external_request_count: externalRequestCount,
    unexpected_media_preload_count: unexpectedMediaPreloadCount,
    geolocation_call_count: geolocationCallCount,
    status: "pass",
  };
  expect(metrics.desktop_first_interactive_p95_ms).toBeLessThanOrEqual(1800);
  expect(metrics.mobile_first_interactive_p95_ms).toBeLessThanOrEqual(2500);
  expect(metrics.cls_p95).toBeLessThanOrEqual(0.1);
  expect(metrics.interaction_p95_ms).toBeLessThanOrEqual(150);
  expect(metrics.low_bandwidth_initial_transfer_p95_bytes).toBeLessThanOrEqual(250000);
  writeFileSync(path.join(qaDirectory, "browser-metrics.json"), `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
});

test("controlled Fast 4G and Slow 4G probes retain the metadata-first task", async ({ browser }, testInfo) => {
  const profiles = [
    { id: "fast_4g", latency: 20, downloadThroughput: 4 * 1024 * 1024 / 8, uploadThroughput: 3 * 1024 * 1024 / 8 },
    { id: "slow_4g", latency: 150, downloadThroughput: 1.6 * 1024 * 1024 / 8, uploadThroughput: 750 * 1024 / 8 },
  ];
  const results = [];
  for (const profile of profiles) {
    const context = await browser.newContext({
      baseURL: String(testInfo.project.use.baseURL),
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    await installPreferences(page, true);
    const runtime = observe(page, origin(testInfo));
    const session = await context.newCDPSession(page);
    await session.send("Network.enable");
    await session.send("Network.setCacheDisabled", { cacheDisabled: true });
    await session.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: profile.latency,
      downloadThroughput: profile.downloadThroughput,
      uploadThroughput: profile.uploadThroughput,
      connectionType: "cellular4g",
    });
    const started = performance.now();
    await gotoRoute(page, "/art/search");
    const firstInteractiveMs = performance.now() - started;
    const resources = await page.evaluate(() => {
      const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      const entries = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
      return {
        request_count: entries.length + (navigation ? 1 : 0),
        transferred_bytes: (navigation?.transferSize ?? 0) +
          entries.reduce((sum, item) => sum + (item.transferSize || 0), 0),
      };
    });
    expect(runtime.external).toEqual([]);
    expect(runtime.images).toEqual([]);
    expect(runtime.rendererChunks).toEqual([]);
    expect(await page.getByRole("searchbox").isEnabled()).toBe(true);
    results.push({
      profile: profile.id,
      latency_ms: profile.latency,
      download_bytes_per_second: profile.downloadThroughput,
      first_interactive_ms: firstInteractiveMs,
      ...resources,
      external_request_count: runtime.external.length,
      media_request_count: runtime.images.length,
      renderer_request_count: runtime.rendererChunks.length,
    });
    await context.close();
  }
  writeFileSync(
    path.join(qaDirectory, "network-profiles.json"),
    `${JSON.stringify({
      schema_version: "1.0.0",
      phase_id: "MUSEUM-08",
      evidence_class: "controlled_chromium_network_emulation",
      real_user_metric: false,
      profiles: results,
      status: "pass",
    }, null, 2)}\n`,
    "utf8",
  );
});

test("@museum-08-screenshots captures bounded candidate evidence", async ({ page }) => {
  await installPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoRoute(page, "/art");
  await capture(page, "art-foyer-390x844");
  await gotoRoute(page, "/art/search");
  await capture(page, "search-empty-390x844");
  await page.getByRole("searchbox").fill("Dürer");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: /matches/ })).toBeVisible();
  await capture(page, "search-results-390x844");
  await page.setViewportSize({ width: 768, height: 1024 });
  await gotoRoute(page, "/art/compare");
  await capture(page, "compare-stacked-768x1024");
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoRoute(page, "/art/map?view=list");
  await capture(page, "map-low-bandwidth-list-1440x900");
});
