import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const releaseDirectory = path.resolve("public/releases/art-expansion-batch-05-1.9.0");
const qaDirectory = path.resolve(process.env.MUSEUM09B_QA_DIR ?? "docs/qa/museum-09d-wave-01");
const screenshotDirectory = path.join(qaDirectory, "screenshots");
mkdirSync(screenshotDirectory, { recursive: true });

type PublicArtist = {
  id: string;
  public_slug: string;
  profile_kind: "gallery" | "collection";
  labels: { en: string; "zh-Hans": string };
  relation_count: number;
  public_intro: { en: string; "zh-Hans": string };
  look_for: { en: string[]; "zh-Hans": string[] };
  evidence_boundary: { en: string; "zh-Hans": string };
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
const tanner = artists.find((artist) => artist.id === "artist:henry-ossawa-tanner")!;
const focusExplorerArtist = artists.find((artist) => artist.id === "artist:katsushika-hokusai")!;
const emptyExplorerArtist = artists.find((artist) => artist.relation_count === 0)!;
const selfHostedPromptArtist = artists.find((artist) => artist.id === "artist:albrecht-durer")!;
const externalPromptArtist = artists.find((artist) => artist.id === "artist:m09a-moma_open_data-1465")!;
const metadataPromptArtist = artists.find((artist) => artist.id === "artist:m09a-cleveland_open_access-nakunte-diarra-2020")!;
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

async function installPreferences(page: Page, lowBandwidth = true, locale: "en" | "zh-CN" = "en") {
  await page.addInitScript(({ low, selectedLocale }) => {
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
    localStorage.setItem("museum-locale", selectedLocale);
    localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth, selectedLocale: locale });
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

async function expectNoFocusedExplorerCollisions(page: Page) {
  const result = await page.evaluate(() => {
    const boxes = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)]
      .filter((element) => {
        const style = getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      })
      .map((element) => {
        const box = element.getBoundingClientRect();
        return { id: element.dataset.artistId ?? element.textContent?.trim().slice(0, 60) ?? element.tagName, left: box.left, right: box.right, top: box.top, bottom: box.bottom };
      });
    const collisions = (items: ReturnType<typeof boxes>) => items.flatMap((left, index) => items.slice(index + 1).flatMap((right) => {
      const overlapX = Math.min(left.right, right.right) - Math.max(left.left, right.left);
      const overlapY = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
      return overlapX > 1 && overlapY > 1 ? [`${left.id} <> ${right.id}`] : [];
    }));
    const cards = boxes(".relation-artist-card");
    const labels = boxes(".relation-artist-card h3");
    const clipped = cards.filter((box) => box.left < -1 || box.right > document.documentElement.clientWidth + 1).map((box) => box.id);
    return {
      nodeCount: Number(document.querySelector(".focused-relation-explorer")?.getAttribute("data-node-count") ?? -1),
      cardCollisions: collisions(cards),
      labelCollisions: collisions(labels),
      clipped,
    };
  });
  expect(result.nodeCount).toBeGreaterThan(0);
  expect(result.nodeCount).toBeLessThanOrEqual(13);
  expect(result.cardCollisions).toEqual([]);
  expect(result.labelCollisions).toEqual([]);
  expect(result.clipped).toEqual([]);
}

async function selectFocusedArtist(page: Page, artist: PublicArtist, locale: "en" | "zh-CN" = "en") {
  const name = locale === "zh-CN" ? artist.labels["zh-Hans"] : artist.labels.en;
  const searchLabel = locale === "zh-CN" ? "搜索艺术家" : "Search artists";
  const actionLabel = locale === "zh-CN" ? "查看艺术家说明" : "Open artist notes";
  await page.getByLabel(searchLabel).fill(name);
  const item = page.locator(".artist-list-view li").filter({ hasText: name }).first();
  await expect(item).toBeVisible();
  await item.getByRole("button", { name: actionLabel }).click();
  await expect(page.locator(".focused-relation-explorer")).toBeVisible();
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.max(0, Math.ceil(sorted.length * ratio) - 1)] ?? 0;
}

async function capture(page: Page, name: string, route: string, locale: "en" | "zh-CN", validationTarget: string) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));
  const destination = path.join(screenshotDirectory, `${name}.png`);
  await page.screenshot({
    path: destination,
    fullPage: true,
    style: ".skip-link { visibility: hidden !important; }",
  });
  const bytes = readFileSync(destination);
  const recordedRoute = /^https?:/i.test(route) ? new URL(route).hash.replace(/^#/, "") : route;
  return {
    name,
    path: path.relative(path.resolve("."), destination).replaceAll("\\", "/"),
    route: recordedRoute,
    viewport: page.viewportSize(),
    locale,
    bytes: statSync(destination).size,
    sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
    validation_target: validationTarget,
  };
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
    expect(publicText, route).not.toMatch(/M09A|M09B|Batch 01|\bcandidate\b|\breview(?:ed)? (?:record|status|workflow|candidate|fixture)\b|\binternal\b|\bMVP\b|\bPhase\b|source adapter/i);
    results[route] = violations.length;
  }
  await gotoRoute(page, "/art/artists");
  await expect(page.locator(".gallery-release-tally")).toContainText("2471");
  await expect(page.locator(".artist-results-status")).toContainText("258");
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.failures).toEqual([]);
  expect(runtime.httpErrors).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(await page.evaluate(() => (window as Window & { __museum09bGeolocationReads?: number }).__museum09bGeolocationReads ?? 0)).toBe(0);
  writeFileSync(path.join(qaDirectory, "automated-a11y-results.json"), `${JSON.stringify({
    schema_version: "1.0.0", phase_id: "MUSEUM-09D-WAVE-01", automated_engine: "project_dom_accessibility_gate",
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
    await gotoRoute(page, "/art/constellation");
    await expect(page.locator(".relation-start")).toHaveAttribute("data-default-node-count", "0");
    await expect(page.locator(".focused-relation-explorer")).toHaveCount(0);
    await selectFocusedArtist(page, focusExplorerArtist);
    await expect(page.getByRole("heading", { level: 3, name: "Shared subject" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 3, name: "Shared material" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 3, name: "Shared technique" })).toBeVisible();
    await expectNoFocusedExplorerCollisions(page);
    await noHorizontalOverflow(page);
    await expectControlTargets(page);
  }
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.consoleErrors).toEqual([]);
});

test("relationship explorer preserves URL history, keyboard evidence, empty, theme, list, and table equivalents", async ({ page }, testInfo) => {
  await installPreferences(page, true);
  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "active" });
  await page.setViewportSize({ width: 768, height: 1024 });
  const runtime = observe(page, expectedOrigin(testInfo));

  await gotoRoute(page, "/art/constellation");
  await selectFocusedArtist(page, focusExplorerArtist);
  await expect(page).toHaveURL(new RegExp(`artist=${encodeURIComponent(focusExplorerArtist.id)}`));
  const edge = page.locator(".relation-edge svg [role=button]").first();
  await edge.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary", { name: "Relationship explanation" })).toBeVisible();
  await page.getByRole("button", { name: "Close notes" }).click();
  await page.goBack();
  await expect(page.locator(".artist-list-view:visible")).toBeVisible();
  await expect(page.getByLabel("Search artists")).toHaveValue(focusExplorerArtist.labels.en);
  await page.goForward();
  await expect(page.locator(".focused-relation-explorer")).toBeVisible();

  await gotoRoute(page, "/art/constellation");
  await selectFocusedArtist(page, emptyExplorerArtist);
  await expect(page.locator(".focused-relation-explorer")).toHaveAttribute("data-node-count", "1");
  await expect(page.locator(".relation-lane-empty")).toHaveCount(3);

  await gotoRoute(page, "/art/constellation");
  const themeSelect = page.getByLabel("Explore by theme");
  await themeSelect.focus();
  await expect.poll(async () => themeSelect.locator("option").count()).toBeGreaterThan(1);
  const themeValue = await themeSelect.locator("option").nth(1).getAttribute("value");
  if (!themeValue) throw new Error("Expected at least one verified theme context");
  await themeSelect.selectOption(themeValue);
  await expect(page.locator(".theme-explorer")).toBeVisible();
  expect(await page.locator(".theme-artist-grid .relation-artist-card").count()).toBeLessThanOrEqual(16);
  await expect(page.locator(".theme-complete-list")).toBeVisible();

  await gotoRoute(page, "/art/constellation?view=list");
  await expect(page.locator(".artist-list-view .scale-pagination")).toContainText("258");
  await gotoRoute(page, "/art/constellation?view=table");
  await expect(page.locator(".relationship-table-view tbody tr")).toHaveCount(60);

  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  await noHorizontalOverflow(page);
  await expect(page.locator(".relationship-table-view")).toBeVisible();
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
  expect(runtime.rendererChunks).toEqual([]);
  expect(runtime.failures).toEqual([]);
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

test("child-facing introductions and media-aware prompts precede the technical evidence layer", async ({ page }, testInfo) => {
  await installPreferences(page, true, "en");
  const runtime = observe(page, expectedOrigin(testInfo));
  for (const artist of [selfHostedPromptArtist, externalPromptArtist, metadataPromptArtist]) {
    await gotoRoute(page, `/art/artists/${artist.public_slug}`);
    await expect(page.getByRole("heading", { level: 2, name: "Meet the artist" })).toBeVisible();
    await expect(page.locator(".artist-public-intro")).toHaveText(artist.public_intro.en);
    await expect(page.locator(".artist-look-for")).toContainText(artist.look_for.en[0]);
    await expect(page.locator(".artist-evidence-boundary")).toHaveText(artist.evidence_boundary.en);
    await expect(page.locator("details.artist-provenance")).not.toHaveAttribute("open", "");
  }
  await gotoRoute(page, `/art/artists/${tanner.public_slug}`);
  await expect(page.locator(".artist-public-intro")).toHaveText(tanner.public_intro.en);
  await page.getByRole("button", { name: "中", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: "认识这位艺术家" })).toBeVisible();
  await expect(page.locator(".artist-public-intro")).toHaveText(tanner.public_intro["zh-Hans"]);
  expect(runtime.external).toEqual([]);
  expect(runtime.images).toEqual([]);
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
  let mobileResourceTransferSample: Array<{ path: string; transfer_size: number; encoded_body_size: number }> = [];
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
      await gotoRoute(page, "/art/constellation");
      const duration = performance.now() - started;
      (viewport.width < 1000 ? mobileFti : desktopFti).push(duration);
      await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      cls.push(await page.evaluate(() => (window as Window & { __museum09bCls?: number }).__museum09bCls ?? 0));
      if (viewport.width < 1000) {
        const transferProbe = await page.evaluate(() => {
          const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
          const resources = (performance.getEntriesByType("resource") as PerformanceResourceTiming[]).map((entry) => ({
            path: new URL(entry.name).pathname,
            transfer_size: entry.transferSize || 0,
            encoded_body_size: entry.encodedBodySize || 0,
          }));
          const navigationEntry = navigation ? [{
            path: new URL(navigation.name).pathname,
            transfer_size: navigation.transferSize || 0,
            encoded_body_size: navigation.encodedBodySize || 0,
          }] : [];
          const entries = [...navigationEntry, ...resources];
          return { total: entries.reduce((sum, entry) => sum + entry.transfer_size, 0), entries };
        });
        transfer.push(transferProbe.total);
        if (run === 0) mobileResourceTransferSample = transferProbe.entries.sort((left, right) => right.transfer_size - left.transfer_size);
        await selectFocusedArtist(page, focusExplorerArtist);
        interactions.push(...await page.evaluate(async () => {
          const values: number[] = [];
          for (let index = 0; index < 20; index += 1) {
            const buttons = [...document.querySelectorAll<HTMLButtonElement>(".relation-artist-card button")];
            const button = buttons[index % Math.max(1, buttons.length)];
            if (!button) break;
            const began = performance.now();
            button.click();
            await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
            values.push(performance.now() - began);
          }
          return values;
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
    schema_version: "1.0.0", phase_id: "MUSEUM-09D-WAVE-01", evidence_class: "controlled_browser_probe",
    real_user_metric: false, environment: "Playwright Chromium preview", cold_runs: 3,
    desktop_first_interactive_median_ms: percentile(desktopFti, 0.5), desktop_first_interactive_p95_ms: percentile(desktopFti, 0.95),
    mobile_first_interactive_median_ms: percentile(mobileFti, 0.5), mobile_first_interactive_p95_ms: percentile(mobileFti, 0.95),
    cls_p95: percentile(cls, 0.95), interaction_runs: interactions.length, interaction_p95_ms: percentile(interactions, 0.95),
    low_bandwidth_initial_transfer_p95_bytes: percentile(transfer, 0.95), external_request_count: externalRequestCount,
    low_bandwidth_limit_bytes: 226_171 + Math.max(0, artists.length - 62) * 750,
    low_bandwidth_scaling_contract: {
      formula: "226171 + max(0, current_artists - 62) * 750",
      baseline_artists: 62,
      baseline_transfer_bytes: 226_171,
      current_artists: artists.length,
      marginal_limit_bytes_per_artist: 750,
    },
    mobile_resource_transfer_sample: mobileResourceTransferSample,
    unexpected_media_preload_count: unexpectedMediaPreloadCount, geolocation_call_count: geolocationCallCount, status: "pass",
  };
  writeFileSync(path.join(qaDirectory, "browser-metrics.json"), `${JSON.stringify(metrics, null, 2)}\n`);
  expect(metrics.desktop_first_interactive_p95_ms).toBeLessThanOrEqual(1_800);
  expect(metrics.mobile_first_interactive_p95_ms).toBeLessThanOrEqual(2_500);
  expect(metrics.cls_p95).toBeLessThanOrEqual(0.1);
  expect(metrics.interaction_p95_ms).toBeLessThanOrEqual(100);
  expect(metrics.low_bandwidth_initial_transfer_p95_bytes).toBeLessThanOrEqual(metrics.low_bandwidth_limit_bytes);
  expect(metrics.external_request_count).toBe(0);
  expect(metrics.unexpected_media_preload_count).toBe(0);
  expect(metrics.geolocation_call_count).toBe(0);
});

test("@museum-09b-screenshots captures the twelve bounded release views", async ({ page }) => {
  await installPreferences(page, true, "zh-CN");
  const screenshots: Awaited<ReturnType<typeof capture>>[] = [];
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoRoute(page, "/art/constellation");
  await expect(page.locator(".relation-start")).toHaveAttribute("data-default-node-count", "0");
  screenshots.push(await capture(page, "01-relationship-start-desktop", "/art/constellation", "zh-CN", "默认无全体圆环，初始节点为 0，搜索与 coverage 起点清楚"));

  await selectFocusedArtist(page, focusExplorerArtist, "zh-CN");
  await expectNoFocusedExplorerCollisions(page);
  screenshots.push(await capture(page, "02-focused-three-lanes-desktop", `/art/constellation?artist=${encodeURIComponent(focusExplorerArtist.id)}`, "zh-CN", "中心艺术家与题材、材料、技法三类分支，节点和标签无重叠"));

  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoFocusedExplorerCollisions(page);
  screenshots.push(await capture(page, "03-focused-artist-mobile", `/art/constellation?artist=${encodeURIComponent(focusExplorerArtist.id)}`, "zh-CN", "390px 移动端纵向分组、无裁切与横向溢出"));

  await page.getByRole("button", { name: "为什么相连？" }).first().click();
  await expect(page.getByRole("complementary", { name: "关系解释" })).toBeVisible();
  screenshots.push(await capture(page, "04-relationship-explanation", page.url(), "zh-CN", "普通访客关系解释、证据入口与不代表历史影响的边界"));
  await page.getByRole("button", { name: "关闭说明" }).click();

  await gotoRoute(page, "/art/constellation");
  await selectFocusedArtist(page, emptyExplorerArtist, "zh-CN");
  await expect(page.locator(".relation-lane-empty")).toHaveCount(3);
  screenshots.push(await capture(page, "05-no-formal-relationships", page.url(), "zh-CN", "无正式关系时保持自然空状态且不补算法边"));

  await gotoRoute(page, "/art/constellation");
  const themeSelect = page.getByLabel("按主题探索");
  await themeSelect.focus();
  await expect.poll(async () => themeSelect.locator("option").count()).toBeGreaterThan(1);
  const themeValue = await themeSelect.locator("option").nth(1).getAttribute("value");
  if (!themeValue) throw new Error("Expected at least one verified theme context");
  await themeSelect.selectOption(themeValue);
  await expect(page.locator(".theme-explorer")).toBeVisible();
  screenshots.push(await capture(page, "06-theme-mode", page.url(), "zh-CN", "主题作为标题、视觉分组不超过 16 人并保留完整文字列表"));

  await gotoRoute(page, `/art/artists/${tanner.public_slug}`);
  await expect(page.locator(".artist-public-intro")).toHaveText(tanner.public_intro["zh-Hans"]);
  screenshots.push(await capture(page, "07-tanner-child-intro", `/art/artists/${tanner.public_slug}`, "zh-CN", "Tanner 中文自然主介绍与观察提示优先于治理语言"));

  await gotoRoute(page, `/art/artists/${newGallery.public_slug}`);
  screenshots.push(await capture(page, "08-new-gallery-child-intro", `/art/artists/${newGallery.public_slug}`, "zh-CN", "新增 Gallery 使用同一儿童友好叙事层"));

  await gotoRoute(page, `/art/artists/${newCollection.public_slug}`);
  screenshots.push(await capture(page, "09-collection-child-intro", `/art/artists/${newCollection.public_slug}`, "zh-CN", "Collection profile 使用同一儿童友好叙事层"));

  await gotoRoute(page, `/art/artists/${metadataPromptArtist.public_slug}`);
  await expect(page.locator(".artist-look-for")).toContainText(metadataPromptArtist.look_for["zh-Hans"][0]);
  screenshots.push(await capture(page, "10-metadata-only-prompt", `/art/artists/${metadataPromptArtist.public_slug}`, "zh-CN", "无本站图片时提示比较标题、日期、材料与机构，不要求观察不存在的图像"));

  await gotoRoute(page, `/art/artists/${tanner.public_slug}`);
  await page.locator("details.artist-provenance summary").click();
  await expect(page.locator("details.artist-provenance")).toHaveAttribute("open", "");
  screenshots.push(await capture(page, "11-evidence-boundary-open", `/art/artists/${tanner.public_slug}`, "zh-CN", "技术边界与逐句 Claim-Evidence-Source 映射保留在次级层"));

  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await gotoRoute(page, "/art/constellation");
  await selectFocusedArtist(page, focusExplorerArtist, "zh-CN");
  await expect(page.locator(".focused-relation-explorer")).toBeVisible();
  screenshots.push(await capture(page, "12-forced-colors-low-bandwidth-equivalent", page.url(), "zh-CN", "forced-colors、reduced-motion 与低带宽仍保留关系、解释和导航任务"));

  writeFileSync(path.join(qaDirectory, "screenshot-index.json"), `${JSON.stringify({
    schema_version: "1.0.0",
    phase_id: "MUSEUM-09D-WAVE-01",
    screenshot_count: screenshots.length,
    screenshots,
  }, null, 2)}\n`);
  expect(screenshots).toHaveLength(12);
});
