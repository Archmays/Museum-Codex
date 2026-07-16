import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

type ReleaseArtist = {
  id: string;
  labels: { en: string };
  artwork_ids: string[];
  approved_media_artwork_count: number;
};

type ReleaseArtwork = {
  id: string;
  artist_id: string;
  labels: { en: string };
  media: {
    decision: string;
  };
};

const releaseDirectory = path.resolve("public/releases/art-constellation-1.0.0");
const artists = (JSON.parse(readFileSync(path.join(releaseDirectory, "artists.json"), "utf8")) as {
  artists: ReleaseArtist[];
}).artists;
const artworks = (JSON.parse(readFileSync(path.join(releaseDirectory, "artworks.json"), "utf8")) as {
  artworks: ReleaseArtwork[];
}).artworks;
const approvedArtworks = artworks.filter((artwork) => artwork.media.decision === "approved_self_hosted");
const noImageArtworks = artworks.filter((artwork) => artwork.media.decision !== "approved_self_hosted");
const screenshotDirectory = path.resolve(
  process.env.MUSEUM05_QA_DIR ?? "docs/qa/museum-05a/screenshots",
);

mkdirSync(screenshotDirectory, { recursive: true });

const expectedWebGlDiagnostic = /^\[\.WebGL-[^\]]+\]GL Driver Message \(OpenGL, Performance, GL_CLOSE_PATH_NV, High\): GPU stall due to ReadPixels(?: \(this message will no longer repeat\))?$/;

function screenshotPath(name: string) {
  return path.join(screenshotDirectory, `${name}.png`);
}

async function captureFullPage(page: Page, name: string) {
  const skipLink = page.locator(".skip-link");
  await expect(skipLink).not.toBeFocused();
  // Chromium's stitched full-page capture can paint an off-canvas fixed skip link at tile seams.
  // Hide only its normal (unfocused) state while taking evidence; the focused state remains testable.
  const screenshotStyle = await page.addStyleTag({
    content: ".skip-link:not(:focus) { visibility: hidden !important; }",
  });
  await page.screenshot({ path: screenshotPath(name), fullPage: true });
  await screenshotStyle.evaluate((element: HTMLStyleElement) => {
    element.parentNode?.removeChild(element);
  });
}

function expectedOrigin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observeRuntime(page: Page, origin: string) {
  const consoleIssues: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  const externalRequests: string[] = [];
  const externalImages: string[] = [];
  const runtimeConnections: string[] = [];

  page.on("console", (message) => {
    const expectedDiagnostic = message.type() === "warning" && expectedWebGlDiagnostic.test(message.text());
    if ((message.type() === "error" || message.type() === "warning") && !expectedDiagnostic) {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("requestfailed", (request) => {
    failedRequests.push(`${request.method()} ${request.url()} (${request.failure()?.errorText ?? "unknown"})`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`);
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== origin) {
      externalRequests.push(`${request.resourceType()} ${request.url()}`);
      if (request.resourceType() === "image") externalImages.push(request.url());
    }
    if (/(?:^|\/)(?:api|graphql)(?:\/|$)|websocket/i.test(url.pathname)) {
      runtimeConnections.push(request.url());
    }
  });

  return { consoleIssues, externalImages, externalRequests, failedRequests, httpErrors, runtimeConnections };
}

function expectCleanRuntime(observed: ReturnType<typeof observeRuntime>) {
  expect(observed.consoleIssues).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
  expect(observed.httpErrors).toEqual([]);
  expect(observed.externalRequests).toEqual([]);
  expect(observed.externalImages).toEqual([]);
  expect(observed.runtimeConnections).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

async function gotoMuseum05a(page: Page, route: string) {
  const response = await page.goto(`./#${route}`, { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await expect(page.locator("[data-museum05a-status=ready]")).toBeVisible();
}

async function useEnglish(page: Page) {
  const englishButton = page.getByRole("button", { name: "EN", exact: true });
  if (await englishButton.getAttribute("aria-pressed") !== "true") await englishButton.click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
}

async function installEnglishPreferences(page: Page, lowBandwidth = false) {
  await page.addInitScript(({ low }) => {
    window.localStorage.setItem("museum-locale", "en");
    window.localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

test("artist index exposes 12 reviewed entries, useful filters, and all 12 artist galleries", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglishPreferences(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoMuseum05a(page, "/art/artists");
  await useEnglish(page);

  await expect(page.getByRole("heading", { level: 1, name: "Twelve artists, twelve ways to begin looking" })).toBeVisible();
  await expect(page.locator(".artist-index-card")).toHaveCount(12);
  await expect(page.locator('.artist-index-card[data-image-state="approved"]')).toHaveCount(8);
  await expect(page.locator('.artist-index-card[data-image-state="no-image"]')).toHaveCount(4);
  await expect(page.locator(".gallery-release-tally")).toContainText("44");
  await expect(page.locator(".gallery-release-tally")).toContainText("31");
  await expect(page.locator(".gallery-release-tally")).toContainText("36");
  await captureFullPage(page, "artist-index-desktop");

  await page.getByLabel("Search artists").fill("Durer");
  await expect(page.locator(".artist-index-card")).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 2, name: "Albrecht Dürer" })).toBeVisible();
  await page.getByLabel("Artwork images").selectOption({ label: "No public artwork image now" });
  await expect(page.locator(".artist-index-card")).toHaveCount(0);
  await page.locator(".artist-filter-grid").getByRole("button", { name: "Clear filters" }).click();
  await expect(page.locator(".artist-index-card")).toHaveCount(12);
  await page.getByLabel("Artwork images").selectOption({ label: "No public artwork image now" });
  await expect(page.locator(".artist-index-card")).toHaveCount(4);
  await page.locator(".artist-filter-grid").getByRole("button", { name: "Clear filters" }).click();

  await page.locator(".artist-index-card").first().getByRole("link", { name: "Enter artist gallery" }).click();
  await expect(page.locator('[data-museum05a-status="ready"][data-gallery-route="artist"]')).toBeVisible();
  await expect(page.locator("main#main-content.artist-gallery-page")).toBeFocused();

  for (const artist of artists) {
    await gotoMuseum05a(page, `/art/artists/${encodeURIComponent(artist.id)}`);
    const main = page.locator("main.artist-gallery-page");
    await expect(main.getByRole("heading", { level: 1, name: artist.labels.en })).toBeVisible();
    await expect(main.locator(".artist-work-card")).toHaveCount(artist.artwork_ids.length);
    expect(artist.artwork_ids.length).toBeGreaterThanOrEqual(2);
    expect(artist.artwork_ids.length).toBeLessThanOrEqual(4);
    await expect(main.getByRole("heading", { name: "Sources and rights" })).toBeVisible();
    await expect(main.locator(".artist-source-list li").first()).toBeVisible();
    await expect(main.locator(".gallery-release-tally")).toContainText(/\d+\s*.*\s*C/);
    await expect(main.locator(".artist-related-boundary")).toContainText(/does not prove.*influence/i);
    if (artist.id === "artist:katsushika-hokusai") {
      const galleryImages = main.locator(".artist-work-card img");
      await expect(galleryImages).toHaveCount(4);
      for (let index = 0; index < 4; index += 1) {
        const galleryImage = galleryImages.nth(index);
        await galleryImage.scrollIntoViewIfNeeded();
        await expect.poll(async () => galleryImage.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
      }
      await captureFullPage(page, "artist-gallery-hokusai-desktop");
    }
  }

  await expectNoHorizontalOverflow(page);
  expectCleanRuntime(observed);
});

test("all 44 artwork routes preserve approved and no-image decisions without low-bandwidth image requests", async ({ page }, testInfo) => {
  expect(artists).toHaveLength(12);
  expect(artworks).toHaveLength(44);
  expect(approvedArtworks).toHaveLength(31);
  expect(noImageArtworks).toHaveLength(13);

  const observed = observeRuntime(page, expectedOrigin(testInfo));
  const releaseImageRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/releases\/art-constellation-1\.0\.0\/assets\//.test(new URL(request.url()).pathname)) {
      releaseImageRequests.push(request.url());
    }
  });
  await installEnglishPreferences(page, true);
  await page.setViewportSize({ width: 390, height: 844 });

  for (const artwork of artworks) {
    await gotoMuseum05a(page, `/art/artworks/${encodeURIComponent(artwork.id)}`);
    const main = page.locator(`main[data-artwork-id="${artwork.id}"]`);
    await expect(main).toBeVisible();
    await expect(main).toHaveAttribute("data-media-decision", artwork.media.decision);
    await expect(main.getByRole("heading", { level: 1, name: artwork.labels.en })).toBeVisible();
    await expect(main.getByRole("link", { name: "Visit official artwork source" })).toBeVisible();
    await expect(main.locator(".artwork-claim-list > li").first()).toBeVisible();
    await expect(main.locator(".artwork-source-list li").first()).toBeVisible();
    await expect(main.locator("img")).toHaveCount(0);

    if (artwork.media.decision === "approved_self_hosted") {
      await expect(main.locator(".artwork-zoom-gate")).toBeVisible();
      await expect(main.getByRole("button", { name: "Load this artwork image" })).toBeVisible();
    } else {
      await expect(main.getByRole("img", { name: "No image passed the public-media gate for this record." })).toBeVisible();
    }
    await expectNoHorizontalOverflow(page);
  }

  expect(releaseImageRequests).toEqual([]);
  expectCleanRuntime(observed);
});

test("approved artwork zoom supports buttons and keyboard, exposes rights, and degrades on decode failure", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglishPreferences(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoMuseum05a(page, `/art/artworks/${encodeURIComponent("artwork:met-39799")}`);

  const viewport = page.getByRole("group", { name: /Zoomable artwork image:/ });
  const image = viewport.locator("img");
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute("srcset", /320w.*640w.*960w.*1600w/);
  await expect(image).toHaveAttribute("sizes", "(max-width: 760px) 92vw, 100vw");
  await expect.poll(async () => image.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const zoomIn = page.getByRole("button", { name: "Zoom in" });
  await expect(zoomIn).toBeEnabled();
  await expect(page.locator(".artwork-zoom-controls output")).toHaveText("Zoom 100%");
  await zoomIn.click();
  await expect(page.locator(".artwork-zoom-controls output")).toHaveText("Zoom 125%");
  await viewport.focus();
  await page.keyboard.press("=");
  await expect(page.locator(".artwork-zoom-controls output")).toHaveText("Zoom 150%");
  await page.keyboard.press("ArrowRight");
  await expect(image).toHaveAttribute("style", /translate\(32px, 0px\) scale\(1\.5\)/);
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.locator(".artwork-zoom-controls output")).toHaveText("Zoom 100%");
  await expect(page.locator(".artwork-zoom-figure figcaption")).toContainText("Media attribution and license:");
  await expect(page.locator(".artwork-zoom-figure figcaption")).toContainText("Withdrawal status:");
  await captureFullPage(page, "artwork-detail-desktop");

  await page.route("**/releases/art-gallery-interactions-1.1.0/assets/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/webp", body: "not-an-image" });
  });
  await gotoMuseum05a(page, `/art/artworks/${encodeURIComponent("artwork:met-436528")}`);
  await expect(page.getByRole("img", {
    name: "The image could not be decoded; artwork metadata and the official source remain available.",
  })).toBeVisible();
  await expect(page.locator(".artwork-zoom-unavailable").getByRole("status")).toHaveText(
    "The image could not be decoded; artwork metadata and the official source remain available.",
  );
  await expect(page.getByRole("heading", { level: 1, name: "Irises" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Visit official artwork source" })).toBeVisible();
  await page.unroute("**/releases/art-gallery-interactions-1.1.0/assets/**");

  const mobileArtworkRequests: string[] = [];
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (/\/releases\/art-gallery-interactions-1\.1\.0\/assets\/met-436532\//.test(pathname)) {
      mobileArtworkRequests.push(pathname);
    }
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoMuseum05a(page, `/art/artworks/${encodeURIComponent("artwork:met-436532")}`);
  const mobileImage = page.locator(".artwork-zoom-viewport img");
  await mobileImage.scrollIntoViewIfNeeded();
  await expect.poll(async () => mobileImage.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const mobileCurrentSrc = await mobileImage.evaluate((element) => (element as HTMLImageElement).currentSrc);
  expect(new URL(mobileCurrentSrc).pathname).toMatch(/\/assets\/met-436532\/(?:320|640)w\.jpg$/);
  expect(mobileArtworkRequests).not.toEqual([]);
  expect(mobileArtworkRequests.some((pathname) => /\/1600w\.jpg$/.test(pathname))).toBe(false);

  await expectNoHorizontalOverflow(page);
  expectCleanRuntime(observed);
});

test("comparison keeps URL state, rights, swap, and two independent zoom instances through mobile stacking", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglishPreferences(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  const leftId = "artwork:met-39799";
  const rightId = "artwork:met-436528";
  const query = new URLSearchParams({ left: leftId, right: rightId });
  await gotoMuseum05a(page, `/art/compare?${query.toString()}`);

  const panels = page.locator(".compare-work");
  await expect(panels).toHaveCount(2);
  await expect(page.getByLabel("Choose the left work")).toHaveValue(leftId);
  await expect(page.getByLabel("Choose the right work")).toHaveValue(rightId);
  await expect(page.locator("#compare-selection-status")).toContainText("Two different works selected");
  await expect(page.locator(".compare-rights")).toHaveCount(2);
  await expect(page.locator(".compare-rights").first()).toContainText("CC0");
  await expect(page.getByText(/No AI visual-similarity score is produced/)).toBeVisible();

  const leftPanel = panels.nth(0);
  const rightPanel = panels.nth(1);
  await expect(leftPanel.locator(".artwork-zoom-viewport img")).toBeVisible();
  await expect(rightPanel.locator(".artwork-zoom-viewport img")).toBeVisible();
  await expect(leftPanel.locator("output")).toHaveText("Zoom 100%");
  await expect(rightPanel.locator("output")).toHaveText("Zoom 100%");
  await expect(leftPanel.getByRole("button", { name: "Zoom in" })).toBeEnabled();
  await leftPanel.getByRole("button", { name: "Zoom in" }).click();
  await expect(leftPanel.locator("output")).toHaveText("Zoom 125%");
  await expect(rightPanel.locator("output")).toHaveText("Zoom 100%");
  await captureFullPage(page, "compare-desktop");

  await page.getByRole("button", { name: "Swap works" }).click();
  await expect(page.getByLabel("Choose the left work")).toHaveValue(rightId);
  await expect(page.getByLabel("Choose the right work")).toHaveValue(leftId);
  await expect(panels.nth(0).locator(".compare-work-heading h2")).toHaveText("Irises");
  await expect(panels.nth(1).locator(".compare-work-heading h2")).toContainText("Under the Wave off Kanagawa");

  await page.setViewportSize({ width: 390, height: 844 });
  const leftBox = await panels.nth(0).boundingBox();
  const rightBox = await panels.nth(1).boundingBox();
  expect(leftBox).not.toBeNull();
  expect(rightBox).not.toBeNull();
  expect(rightBox?.y ?? 0).toBeGreaterThanOrEqual((leftBox?.y ?? 0) + (leftBox?.height ?? 0));
  await expectNoHorizontalOverflow(page);
  await captureFullPage(page, "compare-mobile-390");
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);

  expectCleanRuntime(observed);
});

test("360px forced-colors and reduced-motion preferences preserve the complete artist path", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglishPreferences(page);
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 360, height: 800 });
  await gotoMuseum05a(page, "/art/artists");

  await expect(page.locator("html")).toHaveAttribute("data-forced-colors", "active");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator(".artist-index-card")).toHaveCount(12);
  await expectNoHorizontalOverflow(page);
  await captureFullPage(page, "artist-index-forced-colors-360");

  const query = new URLSearchParams({ left: "artwork:met-39799", right: "artwork:met-436528" });
  await gotoMuseum05a(page, `/art/compare?${query.toString()}`);
  await expect(page.locator("main.compare-page")).toHaveAttribute("data-forced-colors", "active");
  await expect(page.locator("main.compare-page")).toHaveAttribute("data-reduced-motion", "true");
  await expect(page.locator("main.compare-page")).toHaveAttribute("data-compact", "true");
  await expect(page.locator(".compare-work")).toHaveCount(2);
  await expectNoHorizontalOverflow(page);

  expectCleanRuntime(observed);
});
