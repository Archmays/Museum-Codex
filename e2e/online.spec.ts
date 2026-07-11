import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const qaDir = path.resolve("docs/qa/museum-01");

function observePage(page: Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  return { consoleErrors, failedRequests };
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test("desktop home, language, keyboard, and resources", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  const response = await page.goto("./#/", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  await expect(page).toHaveTitle(/博物馆|Museum/);
  await expect(page.getByRole("heading", { name: "让知识的连接，成为参观的入口" })).toBeVisible();
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
  await page.getByRole("button", { name: "中" }).click();
  await page.screenshot({ path: path.join(qaDir, "desktop-home-1440x900.png"), fullPage: true });
  expect(observed.consoleErrors).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
});

test("mobile home at 390 by 844", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./#/", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "让知识的连接，成为参观的入口" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.getByRole("button", { name: "低带宽" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "low");
  await expect(page.locator(".hero-orbit")).toBeHidden();
  await expect(page.locator(".constellation")).toBeHidden();
  await page.getByRole("button", { name: "低带宽" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-bandwidth", "full");
  await page.screenshot({ path: path.join(qaDir, "mobile-home-390x844.png"), fullPage: true });
  expect(observed.consoleErrors).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
});

test("art foyer survives refresh and 1024 layout", async ({ page }) => {
  const observed = observePage(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("./#/art", { waitUntil: "networkidle" });
  await expect(page.getByText("当前序厅介绍美术馆未来的探索方式，正式馆藏正在整理。")).toBeVisible();
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "在一件作品前，打开许多条路" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: path.join(qaDir, "art-foyer-1024x768.png"), fullPage: true });
  expect(observed.consoleErrors).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
});

test("about, rights, reduced motion, and 360 layout", async ({ page }) => {
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
  await page.screenshot({ path: path.join(qaDir, "about-rights-360x800.png"), fullPage: true });
  expect(observed.consoleErrors).toEqual([]);
  expect(observed.failedRequests).toEqual([]);
});

test("basic museum introduction remains readable without JavaScript", async ({ browser }, testInfo) => {
  const baseURL = testInfo.project.use.baseURL;
  expect(baseURL).toBeTruthy();
  const context = await browser.newContext({
    baseURL: String(baseURL),
    javaScriptEnabled: false,
    viewport: { width: 1024, height: 768 },
  });
  const page = await context.newPage();
  const response = await page.goto("./#/", { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  const fallback = page.locator(".noscript-fallback");
  await expect(fallback.getByRole("heading", { name: "博物馆 · Museum" })).toBeVisible();
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
  await context.close();
});
