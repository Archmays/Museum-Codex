import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const qaDir = path.resolve(process.env.MUSEUM_QA_DIR ?? "docs/qa/museum-04");
const screenshotPrefix = process.env.MUSEUM04_QA_PREFIX ?? "";
mkdirSync(qaDir, { recursive: true });

function screenshotPath(name: string) {
  return path.join(qaDir, `${screenshotPrefix}${name}.png`);
}

function observePage(page: Page) {
  const consoleIssues: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  page.on("console", (message) => {
    const expectedBrowserDiagnostic = message.type() === "warning"
      && /^\[\.WebGL-[^\]]+\]GL Driver Message \(OpenGL, Performance, GL_CLOSE_PATH_NV, High\): GPU stall due to ReadPixels(?: \(this message will no longer repeat\))?$/.test(message.text());
    if ((message.type() === "error" || message.type() === "warning") && !expectedBrowserDiagnostic) {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("requestfailed", (request) => {
    failedRequests.push(`${request.method()} ${request.url()} (${request.failure()?.errorText ?? "unknown"})`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`);
  });
  return { consoleIssues, failedRequests, httpErrors };
}

function expectCleanPage(observed: ReturnType<typeof observePage>) {
  expect(observed.consoleIssues).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
  expect(observed.httpErrors).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

async function revealDeferredListForFullPageCapture(page: Page) {
  await page.addStyleTag({
    content: ".constellation-controls, .constellation-workspace, .artist-list-view > ol > li { content-visibility: visible !important; contain-intrinsic-size: none !important; }",
  });
}

async function expectStaticSameOriginRuntime(page: Page) {
  const result = await page.evaluate(() => {
    const pageOrigin = window.location.origin;
    const resourceUrls = performance.getEntriesByType("resource").map((entry) => entry.name);
    return {
      externalResources: resourceUrls.filter((url) => new URL(url).origin !== pageOrigin),
      runtimeConnections: resourceUrls.filter((url) => /(?:api|graphql|websocket)/i.test(url)),
    };
  });
  expect(result.externalResources).toEqual([]);
  expect(result.runtimeConnections).toEqual([]);
}

async function openConstellation(page: Page) {
  const response = await page.goto("./#/art/constellation", { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await expect(page.locator("main[data-museum04-status=ready]")).toBeVisible();
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/relationship|comparison/i);
}

test("desktop graph, equivalent views, relationship evidence, rights, and URL state", async ({ page }) => {
  const observed = observePage(page);
  const releaseRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/releases/art-gallery-interactions-1.1.0/")) {
      releaseRequests.push(new URL(request.url()).pathname.split("/").at(-1) ?? "");
    }
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  let response = await page.goto("./#/", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.locator(".hall-grid > .hall-portal")).toHaveCount(7);
  await page.reload({ waitUntil: "networkidle" });
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  response = await page.goto("./#/art", { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await expect(page.getByRole("link", { name: /Enter the Constellation of Art/i })).toBeVisible();
  await openConstellation(page);

  await expect(page.locator("main[data-view=graph]")).toBeVisible();
  const liveRegion = page.locator(".sr-only[aria-live=polite]");
  await expect(liveRegion).toHaveCSS("position", "absolute");
  await expect(liveRegion).toHaveCSS("width", "1px");
  await expect(page.locator(".artist-navigator button")).toHaveCount(12);
  await expect(page.getByText("The initial state has no visible edges.", { exact: false })).toBeVisible();
  await expect(page.getByText("C curatorial comparison: 36 edges", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Algorithmic similarity: off/).first()).toBeVisible();
  await expect(page.locator(".constellation-canvas")).toBeVisible();
  expect(releaseRequests).toEqual(expect.arrayContaining([
    "manifest.json",
    "graph-summary.json",
    "artists.json",
    "layout.json",
    "facets.json",
    "search-index.json",
  ]));
  expect(releaseRequests).not.toEqual(expect.arrayContaining([
    "relationships.json",
    "artworks.json",
    "media-index.json",
    "attributions.json",
    "withdrawal-mapping.json",
    "evidence.json",
    "rights.json",
  ]));
  expect(releaseRequests.filter((name) => /\.(?:jpe?g|webp)$/i.test(name))).toEqual([]);
  await page.locator(".constellation-workspace").screenshot({ path: screenshotPath("desktop-initial") });

  const firstArtist = page.locator(".artist-navigator button").first();
  await firstArtist.click();
  await expect(page.locator(".constellation-detail-panel")).toBeVisible();
  await expect(page.locator("#constellation-panel-accessible-title")).toHaveCSS("position", "absolute");
  await expect(page.getByRole("button", { name: "Close notes" })).toBeFocused();
  await expect(page.locator(".related-relation-list button").first()).toBeVisible();
  await expect(page.locator(".artist-representative img")).toBeVisible();
  await expect(page.locator(".artist-representative img")).toHaveAttribute(
    "src",
    /\/releases\/art-gallery-interactions-1\.1\.0\/assets\//,
  );
  expect(releaseRequests).toEqual(expect.arrayContaining([
    "media-index.json", "attributions.json", "withdrawal-mapping.json",
  ]));
  await expect(page).toHaveURL(/focus=/);
  await page.screenshot({ path: screenshotPath("focused-artist") });

  await page.locator(".related-relation-list button").first().click();
  await expect(page.getByRole("heading", { name: "What this relationship means" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What it does not mean" })).toBeVisible();
  await expect(page.locator(".identifier-closure code").first()).toBeVisible();
  await expect(page.locator(".artwork-metadata-list li").first()).toBeVisible();
  await expect(page.locator(".evidence-list li").first()).toBeVisible();
  await expect(page.locator(".source-list li").first()).toBeVisible();
  await expect(page).toHaveURL(/relation=/);
  await page.screenshot({ path: screenshotPath("relationship-explanation") });

  await page.getByRole("button", { name: "Close notes" }).click();
  await page.getByRole("button", { name: "Clear search and filters" }).click();
  const graphTab = page.getByRole("tab", { name: /Graph/ });
  await graphTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Artist list/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".artist-list-view li")).toHaveCount(12);
  await page.screenshot({ path: screenshotPath("desktop-list") });
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Relationship table/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".relationship-table-view tbody tr")).toHaveCount(36);

  await page.getByLabel("Relationship level").selectOption("A");
  await expect(page.getByText(/no verified A or B relationships/i)).toBeVisible();
  await page.getByRole("button", { name: "Clear search and filters" }).click();
  await page.getByRole("tab", { name: /Artist list/ }).click();
  const firstName = (await page.locator(".artist-list-view h2").first().textContent())?.trim() ?? "";
  expect(firstName.length).toBeGreaterThan(0);
  await page.getByLabel("Search artists").fill(firstName);
  await expect(page.locator(".artist-list-view li")).toHaveCount(1);
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("main[data-museum04-status=ready]")).toBeVisible();
  await expect(page.locator(".artist-list-view li")).toHaveCount(1);

  await page.getByRole("button", { name: "Open rights and third-party notices" }).click();
  await expect(page.getByText(/242 self-hosted derivatives for 31 artworks/)).toBeVisible();
  await expect(page.locator(".notice-list li")).not.toHaveCount(0);
  await expect(page.locator(".panel-actions a")).toHaveCount(2);
  await page.screenshot({ path: screenshotPath("rights-panel") });
  await expectNoHorizontalOverflow(page);
  await expectStaticSameOriginRuntime(page);
  expectCleanPage(observed);
});

test("Art landing and 1366-wide constellation remain complete without overflow", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 1366, height: 768 });
  const response = await page.goto("./#/art", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("link", { name: /Enter the Constellation of Art/i })).toBeVisible();
  await page.screenshot({ path: screenshotPath("art-landing"), fullPage: true });
  await page.getByRole("link", { name: /Enter the Constellation of Art/i }).click();
  await expect(page.locator("main[data-museum04-status=ready]")).toBeVisible();
  await expect(page.getByLabel("Artistic tradition")).toBeVisible();
  await expect(page.getByLabel("Context type")).toBeVisible();
  await page.locator(".artist-navigator button").first().click();
  await expect(page.locator(".constellation-detail-panel")).toBeVisible();
  await expect(page.locator(".artist-representative img")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectStaticSameOriginRuntime(page);
  expectCleanPage(observed);
});

test("About, rights, and accessibility routes expose their public controls", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 390, height: 844 });

  let response = await page.goto("./#/about", { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Not an ordinary encyclopedia or image library" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Current art data scope" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Read third-party notices" })).toHaveAttribute(
    "href",
    /\/Museum-Codex\/THIRD_PARTY_NOTICES\.md$/,
  );
  await expect(page.getByRole("link", { name: "Rights request and withdrawal" })).toHaveAttribute(
    "href",
    "https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml",
  );
  await expectNoHorizontalOverflow(page);

  response = await page.goto("./#/accessibility", { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1, name: "A museum that welcomes more ways of visiting" })).toBeVisible();
  const bandwidthButton = page.getByRole("button", { name: "Turn on low-bandwidth mode" });
  await expect(bandwidthButton).toHaveAttribute("aria-pressed", "false");
  await bandwidthButton.click();
  await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "low");
  await expect(page.getByRole("button", { name: "Turn off low-bandwidth mode" })).toHaveAttribute("aria-pressed", "true");
  await expectNoHorizontalOverflow(page);
  await expectStaticSameOriginRuntime(page);
  expectCleanPage(observed);
});

test("390px graph and low-bandwidth list preserve focus and URL state", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await openConstellation(page);
  await expect(page.locator("main[data-view=graph]")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: screenshotPath("mobile-graph"), fullPage: true });

  await page.locator(".artist-navigator button").nth(1).click();
  await expect(page).toHaveURL(/focus=/);
  await expect(page.locator(".constellation-detail-panel")).toBeVisible();
  const panelBox = await page.locator(".constellation-detail-panel").boundingBox();
  expect(panelBox).not.toBeNull();
  expect((panelBox?.y ?? 0) + (panelBox?.height ?? 0)).toBeGreaterThanOrEqual(840);
  expect(panelBox?.width ?? 0).toBeGreaterThanOrEqual(380);
  await expect(page.locator(".related-relation-list button").first()).toBeVisible();
  const representativeImage = page.locator(".artist-representative img");
  await expect(representativeImage).toBeVisible();
  await representativeImage.evaluate((element: HTMLImageElement) => element.decode());
  await expect.poll(
    async () => representativeImage.evaluate((element: HTMLImageElement) => element.naturalWidth),
  ).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Close notes" }).click();
  await page.locator(".bandwidth-button").click();
  await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "low");
  await expect(page.locator("main[data-view=list]")).toBeVisible();
  await expect(page.getByRole("tab", { name: /Graph/ })).toBeDisabled();
  await expect(page.locator(".artist-list-view li.is-selected")).toHaveCount(1);
  const lowBandwidthListTab = page.getByRole("tab", { name: /Artist list/ });
  await lowBandwidthListTab.focus();
  await page.keyboard.press("Home");
  await expect(lowBandwidthListTab).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /Relationship table/ })).toBeFocused();
  await expect(page.getByRole("tab", { name: /Relationship table/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowRight");
  await expect(lowBandwidthListTab).toBeFocused();
  await expect(lowBandwidthListTab).toHaveAttribute("aria-selected", "true");
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("main[data-view=list]")).toBeVisible();
  await expect(page.locator(".artist-list-view li.is-selected")).toHaveCount(1);
  await expect(page.locator(".constellation-detail-panel")).toBeVisible();
  await expect(page.locator(".constellation-detail-panel img")).toHaveCount(0);
  await page.route("**/releases/art-gallery-interactions-1.1.0/assets/**", async (route) => {
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
    await route.continue();
  });
  await page.getByRole("button", { name: "Load this artwork image" }).click();
  const imageStatus = page.locator(".artwork-image-status");
  await expect(imageStatus).toBeFocused();
  await expect(imageStatus).toHaveText("Loading the artwork image.");
  await expect(page.locator(".constellation-detail-panel img")).toBeVisible();
  await expect(imageStatus).toHaveText("Artwork image loaded.");
  await page.unroute("**/releases/art-gallery-interactions-1.1.0/assets/**");
  await page.getByRole("button", { name: "Close notes" }).click();
  await revealDeferredListForFullPageCapture(page);
  await page.screenshot({ path: screenshotPath("mobile-list"), fullPage: true });
  await expectNoHorizontalOverflow(page);
  await expectStaticSameOriginRuntime(page);
  expectCleanPage(observed);
});

test("forced colors, reduced motion, and unavailable WebGL fall back to text", async ({ page }) => {
  const observed = observePage(page);
  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "active" });
  await page.setViewportSize({ width: 360, height: 800 });
  await openConstellation(page);
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("html")).toHaveAttribute("data-forced-colors", "active");
  await expect(page.locator("main[data-view=list]")).toBeVisible();
  await expect(page.locator(".artist-list-view li")).toHaveCount(12);
  const forcedColorsListTab = page.getByRole("tab", { name: /Artist list/ });
  await forcedColorsListTab.focus();
  await page.keyboard.press("Home");
  await expect(forcedColorsListTab).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /Relationship table/ })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(forcedColorsListTab).toBeFocused();
  await revealDeferredListForFullPageCapture(page);
  await page.screenshot({ path: screenshotPath("forced-colors-list"), fullPage: true });
  await expectNoHorizontalOverflow(page);
  expectCleanPage(observed);

  const webglPage = await page.context().newPage();
  const webglObserved = observePage(webglPage);
  await webglPage.addInitScript(() => {
    const original = Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype, "getContext")
      ?.value as typeof HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (contextId: string, ...args: unknown[]) {
      if (contextId === "webgl" || contextId === "webgl2" || contextId === "experimental-webgl") return null;
      return original.call(this, contextId as never, ...args as []) as never;
    };
  });
  await webglPage.setViewportSize({ width: 390, height: 844 });
  await openConstellation(webglPage);
  await expect(webglPage.locator("main[data-view=list]")).toBeVisible();
  await expect(webglPage.locator(".artist-list-view li")).toHaveCount(12);
  await expect(webglPage.getByRole("tab", { name: /Graph/ })).toBeDisabled();
  await expect(webglPage.locator(".constellation-status-line")).toContainText("WebGL is not reliably available");
  await webglPage.waitForTimeout(250);
  await expect(webglPage.locator(".constellation-status-line")).toContainText("WebGL is not reliably available");
  await expect(webglPage.locator(".constellation-canvas")).toHaveCount(0);
  await expectNoHorizontalOverflow(webglPage);
  expectCleanPage(webglObserved);
});

test("no-script portal, Art, and rights content are available over HTTP 200", async ({ browser }, testInfo) => {
  const baseURL = String(testInfo.project.use.baseURL);
  const context = await browser.newContext({
    baseURL,
    javaScriptEnabled: false,
    viewport: { width: 1024, height: 768 },
  });
  const page = await context.newPage();
  const observed = observePage(page);
  const response = await page.goto("./#/art/constellation", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  const fallback = page.locator(".noscript-fallback");
  await expect(fallback.getByRole("heading", { name: "博物馆 · Museum" })).toBeVisible();
  await expect(fallback.getByRole("heading", {
    name: "艺术星海与数字展厅 / Constellation & digital galleries",
  })).toBeVisible();
  await expect(fallback.getByRole("heading", { name: "权利与署名 / Rights & attribution" })).toBeVisible();
  await expect(fallback.getByText(/self-hosted derivatives that passed identity, rights, byte, and quality gates/i)).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expectCleanPage(observed);
  await context.close();
});
