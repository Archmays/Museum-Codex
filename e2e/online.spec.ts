import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const qaDir = path.resolve("docs/qa/museum-02a");
mkdirSync(qaDir, { recursive: true });

function observePage(page: Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`);
  });
  return { consoleErrors, failedRequests, httpErrors };
}

function expectCleanPage(observed: ReturnType<typeof observePage>) {
  expect(observed.consoleErrors).toEqual([]);
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

async function expectOnlyFirstPartyResources(page: Page) {
  const result = await page.evaluate(() => {
    const pageOrigin = window.location.origin;
    const resourceOrigins = performance.getEntriesByType("resource").map((entry) => new URL(entry.name).origin);
    return {
      allFirstParty: resourceOrigins.every((origin) => origin === pageOrigin),
      mediaElements: document.querySelectorAll("img, video, audio, source, object, embed").length,
    };
  });
  expect(result.allFirstParty).toBe(true);
  expect(result.mediaElements).toBe(0);
}

async function expectSevenHallHome(page: Page) {
  await expect(page.locator(".hall-grid > .hall-portal")).toHaveCount(7);
  const arms = page.getByRole("article", { name: /武器博物馆，正在整理器物与历史线索/ });
  await expect(arms).toBeVisible();
  await expect(arms.getByRole("heading", { name: "武器博物馆" })).toBeVisible();
  await expect(arms.locator("a")).toHaveCount(0);
  await expect(arms.locator(".hall-motif-arms")).toHaveAttribute("aria-hidden", "true");
  await expect(page.locator(".hall-grid > a")).toHaveCount(1);
  await expect(page.locator(".hall-grid > a")).toHaveAttribute("href", "#/art");
}

test("desktop seven-hall home, language, keyboard, and resources", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  const response = await page.goto("./#/", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  await expect(page).toHaveTitle(/博物馆|Museum/);
  await expect(page.getByRole("heading", { name: "让知识的连接，成为参观的入口" })).toBeVisible();
  await expectSevenHallHome(page);
  await expectNoHorizontalOverflow(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  expect(new URL(page.url()).hash).toBe("#/");

  await page.reload({ waitUntil: "networkidle" });
  const keyboardOrder = [
    page.getByRole("link", { name: "跳到主要内容" }),
    page.getByRole("link", { name: "博物馆 首页" }),
    page.getByRole("link", { name: "首页", exact: true }),
    page.getByRole("link", { name: "美术馆", exact: true }),
    page.getByRole("link", { name: "关于", exact: true }).first(),
    page.getByRole("link", { name: "无障碍", exact: true }).first(),
    page.getByRole("button", { name: "中" }),
    page.getByRole("button", { name: "EN" }),
    page.getByRole("button", { name: "低带宽" }),
  ];
  for (const control of keyboardOrder) {
    await page.keyboard.press("Tab");
    await expect(control).toBeFocused();
  }
  await page.getByRole("button", { name: "EN" }).click();
  await expect(page.getByRole("heading", { name: "Let connections become the way in" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Museum of Arms & Armor" })).toBeVisible();
  await expect(page.getByText("Objects and historical threads in preparation")).toBeVisible();
  await page.getByRole("button", { name: "中" }).click();
  await expectOnlyFirstPartyResources(page);
  await page.screenshot({ path: path.join(qaDir, "desktop-home-1440x900.png"), fullPage: true });
  expectCleanPage(observed);
});

test("seven-card home reflows at every required responsive size", async ({ page }) => {
  const observed = observePage(page);
  const viewports = [
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 360, height: 800 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto("./#/", { waitUntil: "networkidle" });
    await expectSevenHallHome(page);
    await expectNoHorizontalOverflow(page);
    if (viewport.width > 760) {
      const centerDelta = await page.locator(".hall-grid > .hall-portal:last-child").evaluate((lastCard) => {
        const card = lastCard.getBoundingClientRect();
        const grid = lastCard.parentElement?.getBoundingClientRect();
        return grid ? Math.abs((card.left + card.right) / 2 - (grid.left + grid.right) / 2) : Number.POSITIVE_INFINITY;
      });
      expect(centerDelta).toBeLessThanOrEqual(1);
    }
    if (viewport.width === 390) {
      await page.getByRole("button", { name: "低带宽" }).click();
      await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "low");
      await expect(page.locator(".hero-orbit")).toBeHidden();
      await expect(page.locator(".constellation")).toBeHidden();
      await page.getByRole("button", { name: "低带宽" }).click();
      await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "full");
      await page.screenshot({ path: path.join(qaDir, "mobile-home-390x844.png"), fullPage: true });
    }
    await expectOnlyFirstPartyResources(page);
  }
  expectCleanPage(observed);
});

test("Art foyer remains available while the Arms route fails closed", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("./#/art", { waitUntil: "networkidle" });
  await expect(page.getByText("当前序厅介绍美术馆未来的探索方式，正式馆藏正在整理。")).toBeVisible();
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "在一件作品前，打开许多条路" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("./#/arms", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "这里还没有展厅" })).toBeVisible();
  await expect(page.getByRole("link", { name: "返回博物馆首页" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expectCleanPage(observed);
});

test("About, Accessibility, reduced motion, forced colors, and 360 layout regress cleanly", async ({ page }) => {
  const observed = observePage(page);
  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "none" });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("./#/about", { waitUntil: "networkidle" });
  await expect(page.getByText(/本项目内容未授予再利用许可/)).toBeVisible();
  await expect(page.getByText(/第三方馆藏内容尚未上线/)).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  const animationDuration = await page.locator(".page-intro > *").first().evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).animationDuration),
  );
  expect(animationDuration).toBeLessThanOrEqual(0.001);
  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "active" });
  expect(await page.evaluate(() => matchMedia("(forced-colors: active)").matches)).toBe(true);
  await expect(page.locator(".ambient-field")).toBeHidden();

  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "none" });
  await page.goto("./#/accessibility", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "一座能被更多方式参观的博物馆" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开启低带宽模式" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expectCleanPage(observed);
});

test("seven-museum introduction remains readable without JavaScript", async ({ browser }, testInfo) => {
  const baseURL = testInfo.project.use.baseURL;
  expect(baseURL).toBeTruthy();
  const context = await browser.newContext({
    baseURL: String(baseURL),
    javaScriptEnabled: false,
    viewport: { width: 1024, height: 768 },
  });
  const page = await context.newPage();
  const observed = observePage(page);
  const response = await page.goto("./#/", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  const fallback = page.locator(".noscript-fallback");
  await expect(fallback.getByRole("heading", { name: "博物馆 · Museum" })).toBeVisible();
  await expect(fallback.getByText(/七个分馆/)).toBeVisible();
  await expect(fallback.getByText(/Seven museums/)).toBeVisible();
  await expectNoHorizontalOverflow(page);
  const contrast = await fallback.evaluate((element) => {
    const parse = (value: string) => (value.match(/\d+/g) ?? []).slice(0, 3).map(Number);
    const luminance = (rgb: number[]) => {
      const values = rgb.map((channel) => {
        const normalized = channel / 255;
        return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * (values[0] ?? 0) + 0.7152 * (values[1] ?? 0) + 0.0722 * (values[2] ?? 0);
    };
    const foreground = luminance(parse(getComputedStyle(element).color));
    const background = luminance([8, 16, 21]);
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
  expectCleanPage(observed);
  await context.close();
});
