import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const screenshotDirectory = path.resolve(process.env.MUSEUM06_QA_DIR ?? "docs/qa/museum-06/screenshots");
const metricsPath = path.resolve("docs/qa/museum-06/browser-metrics.json");
mkdirSync(screenshotDirectory, { recursive: true });

const comparisonRoute = "/art/paths?from=artist%3Aalbrecht-durer&to=artist%3Afrancisco-de-goya&mode=comparison&maxHops=6&path=1&view=text";
const expectedWebGlDiagnostic = /^\[\.WebGL-[^\]]+\]GL Driver Message/;

function expectedOrigin(testInfo: TestInfo) {
  return new URL(String(testInfo.project.use.baseURL)).origin;
}

function observeRuntime(page: Page, origin: string) {
  const consoleIssues: string[] = [];
  const externalRequests: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  page.on("console", (message) => {
    if ((message.type() === "warning" || message.type() === "error") && !expectedWebGlDiagnostic.test(message.text())) {
      consoleIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== origin) externalRequests.push(`${request.resourceType()} ${request.url()}`);
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  page.on("response", (response) => { if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`); });
  return { consoleIssues, externalRequests, failedRequests, httpErrors };
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
    localStorage.setItem("museum-low-bandwidth", String(low));
  }, { low: lowBandwidth });
}

async function installVitals(page: Page) {
  await page.addInitScript(() => {
    const target = window as Window & { __museum06Vitals?: { cls: number } };
    target.__museum06Vitals = { cls: 0 };
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput && target.__museum06Vitals) target.__museum06Vitals.cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
}

async function gotoPath(page: Page, route = comparisonRoute) {
  const response = await page.goto(`./#${route}`, { waitUntil: "networkidle" });
  if (response) expect(response.status()).toBe(200);
  await expect(page.locator("main.path-page")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "What explainable relations connect A to B?" })).toBeVisible();
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

test("comparison route provides graph and complete text-equivalent evidence navigation", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await gotoPath(page, comparisonRoute.replace("view=text", "view=graph"));
  await expect(page.getByRole("radio", { name: /Comparison path/ })).toBeChecked();
  await expect(page.getByRole("tablist", { name: "Alternative paths" }).getByRole("tab")).toHaveCount(3);
  await expect(page.locator(".path-graph svg")).toBeVisible();
  await expect(page.locator(".path-graph-edges line.is-path")).not.toHaveCount(0);
  await expect(page.locator(".path-graph-nodes g.is-context")).not.toHaveCount(0);
  await expect(page.locator(".path-graph-nodes g.is-path").first()).toContainText("1");
  await expect(page.locator(".path-text-equivalent > ol > li")).not.toHaveCount(0);
  await page.getByText("Claim → Evidence → Source").first().click();
  await expect(page.locator(".path-closure-grid").first()).toContainText("Evidence");
  await expect(page.locator(".path-closure-grid a[href^='https://']").first()).toBeVisible();
  await page.getByText("Context · Supporting works · Rights and attribution").first().click();
  await expect(page.locator(".path-support-grid a[href*='#/art/artworks/']").first()).toBeVisible();
  await expect(page.locator(".path-step-facts").first()).toContainText("Undirected");
  await expect(page.locator(".path-step-facts").first()).toContainText("active");
  await expect(page.locator(".path-method-notice")).toContainText("not the truest or most important");
  await expect(page.locator(".path-method-notice")).toContainText("not prove acquaintance, influence, instruction, or transmission");
  await capture(page, "path-comparison-graph-desktop");
  await expectNoOverflow(page);
  expectCleanRuntime(observed);
});

test("historical and context modes retain accurate no-path states while budget remains distinct", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page, true);
  await gotoPath(page, "/art/paths?from=artist%3Aalbrecht-durer&to=artist%3Afrancisco-de-goya&mode=historical&maxHops=6&path=1&view=text");
  await expect(page.getByRole("radio", { name: /Historical path/ })).toBeChecked();
  await expect(page.locator(".path-status")).toHaveText(/No displayable path exists in the current release/);
  await expect(page.getByRole("tablist", { name: "Alternative paths" })).toHaveCount(0);
  await page.getByRole("radio", { name: /Context path/ }).click();
  await page.getByRole("button", { name: "Find paths" }).click();
  await expect(page.getByRole("radio", { name: /Context path/ })).toBeChecked();
  await expect(page.locator(".path-status")).toHaveText(/No displayable path exists/);
  await expect(page.locator(".path-status")).not.toContainText("budget");
  expectCleanRuntime(observed);
});

test("invalid, identical, reversed, and refreshed URL states remain deterministic and allowlisted", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page, true);
  await gotoPath(page, "/art/paths?from=artist%3Aunreviewed&to=artist%3Afrancisco-de-goya&mode=comparison&maxHops=6&path=1&view=text&tracking=discarded");
  await expect(page.locator(".path-status")).toHaveText("The start ID is not one of the 12 formal artists.");
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => { window.location.hash = "/art/paths?from=artist%3Aalbrecht-durer&to=artist%3Aalbrecht-durer&mode=comparison&maxHops=6&path=1&view=text"; });
  await expect(page.locator(".path-status")).toHaveText("Start and end must differ.");
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => { window.location.hash = "/art/paths?from=artist%3Afrancisco-de-goya&to=artist%3Aalbrecht-durer&mode=comparison&maxHops=6&path=2&view=text"; });
  await expect(page.locator("#path-results-title")).toHaveText(/Francisco de Goya.*Albrecht Dürer/);
  await expect(page.getByRole("tab", { name: /Path 2/ })).toHaveAttribute("aria-selected", "true");
  await page.getByText("Claim → Evidence → Source").first().click();
  await expect(page.locator(".path-closure-grid a[href^='https://']").first()).toBeVisible();
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByRole("tab", { name: /Path 2/ })).toHaveAttribute("aria-selected", "true");
  const printHref = await page.getByRole("link", { name: "Open print view" }).getAttribute("href");
  expect(printHref).not.toMatch(/tracking|utm_|claim=/i);
  expectCleanRuntime(observed);
});

test("mobile, keyboard, forced colors, reduced motion, print, and WebGL fallback are usable", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await page.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoPath(page, comparisonRoute.replace("view=text", "view=graph"));
  await expect(page.locator(".path-fallback-note")).toContainText("text view is active");
  await expect(page.getByRole("button", { name: "Graph view" })).toBeDisabled();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  const runBox = await page.getByRole("button", { name: "Find paths" }).boundingBox();
  expect(runBox?.height ?? 0).toBeGreaterThanOrEqual(44);
  await expectNoOverflow(page);
  await capture(page, "path-text-mobile-forced-colors");
  await page.getByRole("link", { name: "Open print view" }).click();
  await expect.poll(() => page.url()).toContain("view=print");
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".path-query")).toHaveCSS("display", "none");
  await expect(page.locator(".path-text-equivalent")).toBeVisible();
  await capture(page, "path-print-mobile");
  expectCleanRuntime(observed);
});

test("@museum-06-isolated-performance controlled interaction, heap, CLS, requests, and storage remain within M06 budgets", async ({ page }, testInfo) => {
  const observed = observeRuntime(page, expectedOrigin(testInfo));
  await installEnglish(page);
  await installVitals(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const heapUsed = async () => {
    const result = await session.send("Performance.getMetrics");
    return result.metrics.find((metric) => metric.name === "JSHeapUsedSize")?.value ?? 0;
  };
  await page.goto("./#/art", { waitUntil: "networkidle" });
  const heapBefore = await heapUsed();
  await page.evaluate((route) => { window.location.hash = route; }, comparisonRoute);
  await expect(page.getByRole("tablist", { name: "Alternative paths" })).toBeVisible();
  const interactionRuns = await page.evaluate(async () => {
    const buttons = [...document.querySelectorAll<HTMLButtonElement>(".path-alternatives button")];
    const runs: number[] = [];
    for (let index = 0; index < 30; index += 1) {
      const started = performance.now();
      buttons[index % buttons.length].click();
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      runs.push(performance.now() - started);
    }
    return runs;
  });
  const heapAfter = await heapUsed();
  const cls = await page.evaluate(() => (window as Window & { __museum06Vitals?: { cls: number } }).__museum06Vitals?.cls ?? 0);
  const sorted = [...interactionRuns].sort((left, right) => left - right);
  const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
  const storageKeys = await page.evaluate(() => Object.keys(localStorage).sort());
  expect(storageKeys).toEqual(["museum-locale", "museum-low-bandwidth"]);
  expect(p95).toBeLessThanOrEqual(150);
  expect(Math.max(0, heapAfter - heapBefore)).toBeLessThanOrEqual(25 * 1024 * 1024);
  expect(cls).toBeLessThanOrEqual(0.1);
  expectCleanRuntime(observed);
  const metrics = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-06",
    evidence_class: "controlled_browser_probe",
    real_user_metric: false,
    route: "#/art/paths",
    route_interaction_runs: interactionRuns.length,
    route_interaction_p95_ms: Number(p95.toFixed(3)),
    route_interaction_median_ms: Number(sorted[Math.floor(sorted.length / 2)].toFixed(3)),
    mobile_heap_increment_bytes: Math.max(0, heapAfter - heapBefore),
    cls,
    external_request_count: observed.externalRequests.length,
    analytics_request_count: 0,
    storage_keys: storageKeys,
    status: "pass",
  };
  writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
});
