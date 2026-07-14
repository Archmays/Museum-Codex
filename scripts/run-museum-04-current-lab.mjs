/* global PerformanceObserver, performance, requestAnimationFrame, document, location, HTMLButtonElement, HTMLSelectElement, HTMLElement, Event, KeyboardEvent, WheelEvent, clearTimeout */

import { execFileSync, spawn, spawnSync } from "node:child_process";
import { existsSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { cpus, platform, release, totalmem } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { setTimeout } from "node:timers";
import { fileURLToPath, URL } from "node:url";
import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const DIST_INDEX = join(ROOT, "dist", "index.html");
const VITE_CLI = join(ROOT, "node_modules", "vite", "bin", "vite.js");
const BUDGET_RUNNER = join(ROOT, "scripts", "verify-museum-04-budgets.mjs");
const APP_BASE_PATH = "/Museum-Codex/";
const require = createRequire(import.meta.url);

const NETWORKS = {
  fast_4g: {
    latencyMs: 20,
    downloadBitsPerSecond: 4_000_000,
    uploadBitsPerSecond: 3_000_000,
    connectionType: "cellular4g",
  },
  constrained_network: {
    latencyMs: 150,
    downloadBitsPerSecond: 1_600_000,
    uploadBitsPerSecond: 750_000,
    connectionType: "cellular4g",
  },
  unthrottled: null,
};

const CURRENT_PROFILES = [
  { id: "mobile-390x844", viewport: { width: 390, height: 844 }, deviceClass: "mobile", cpu: 4, network: "fast_4g", initialExperience: "graph" },
  { id: "mobile-360x800", viewport: { width: 360, height: 800 }, deviceClass: "mobile", cpu: 6, network: "constrained_network", initialExperience: "list" },
  { id: "desktop-1366x768", viewport: { width: 1366, height: 768 }, deviceClass: "desktop", cpu: 1, network: "unthrottled", initialExperience: "graph" },
  { id: "desktop-1440x900", viewport: { width: 1440, height: 900 }, deviceClass: "desktop", cpu: 1, network: "unthrottled", initialExperience: "graph" },
];

const METRIC_UNITS = {
  route_load_ms: "ms",
  data_load_ms: "ms",
  chunk_load_ms: "ms",
  first_interactive_ms: "ms",
  node_selection_ms: "ms",
  filter_ms: "ms",
  relationship_detail_ms: "ms",
  keyboard_focus_ms: "ms",
  list_switch_ms: "ms",
  fps: "fps",
  js_heap_mb: "MB",
  cls: "score",
  long_tasks_count: "count",
  transferred_bytes: "bytes",
  gzip_bytes: "bytes",
  lcp_ms: "ms",
  interaction_proxy_ms: "ms",
};

function usage() {
  return `Usage: node scripts/run-museum-04-current-lab.mjs [options]

Options:
  --samples <n>  Cold samples per viewport (minimum 3, default 3)
  --url <url>    Use an existing loopback HTTP(S) or live HTTPS deployment
  --port <n>     Port for the managed local Vite preview (default: free port)
  --output <p>   Write validated JSON to this explicit path; otherwise print JSON
  --help         Show this help
`;
}

function parseArgs(argv) {
  const options = { samples: 3, url: null, port: null, output: null, help: false };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      options.help = true;
      continue;
    }
    if (!["--samples", "--url", "--port", "--output"].includes(argument)) {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = argv[index + 1];
    if (!value) throw new Error(`${argument} requires a value`);
    index += 1;
    if (argument === "--samples") options.samples = Number(value);
    if (argument === "--url") options.url = value;
    if (argument === "--port") options.port = Number(value);
    if (argument === "--output") options.output = isAbsolute(value) ? value : resolve(process.cwd(), value);
  }
  if (!Number.isInteger(options.samples) || options.samples < 3 || options.samples > 20) {
    throw new Error("--samples must be an integer from 3 to 20");
  }
  if (options.port !== null && (!Number.isInteger(options.port) || options.port < 1 || options.port > 65_535)) {
    throw new Error("--port must be an integer from 1 to 65535");
  }
  if (options.url && options.port !== null) throw new Error("--url and --port cannot be combined");
  return options;
}

function normalizeTargetUrl(value) {
  const url = new URL(value);
  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  if (url.username || url.password) throw new Error("--url must not contain credentials");
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopbackHosts.has(url.hostname))) {
    throw new Error("--url must use HTTPS, or HTTP on localhost or a loopback address");
  }
  url.search = "";
  url.hash = "";
  if (!url.pathname.endsWith("/")) url.pathname += "/";
  return url.toString();
}

function routeUrl(baseUrl) {
  const url = new URL(baseUrl);
  url.hash = "/art/constellation";
  return url.toString();
}

async function freePort() {
  return await new Promise((resolvePort, reject) => {
    const server = createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Could not allocate a local TCP port"));
        return;
      }
      server.close((error) => error ? reject(error) : resolvePort(address.port));
    });
  });
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function waitForServer(url, child, stderr) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (child && child.exitCode !== null) {
      throw new Error(`Preview server exited before becoming ready${stderr.value ? `: ${stderr.value.trim()}` : ""}`);
    }
    try {
      const response = await globalThis.fetch(url, { signal: globalThis.AbortSignal.timeout(1_500) });
      if (response.ok) return;
    } catch {
      // A managed or explicitly supplied server may still be starting.
    }
    await delay(200);
  }
  throw new Error(`Timed out waiting for the current-graph target at ${url}${stderr.value ? `: ${stderr.value.trim()}` : ""}`);
}

async function startPreviewServer(requestedPort) {
  if (!existsSync(DIST_INDEX) || !statSync(DIST_INDEX).isFile()) {
    throw new Error("Managed preview requires a completed production build at dist/index.html; run npm run build first");
  }
  if (!existsSync(VITE_CLI) || !statSync(VITE_CLI).isFile()) {
    throw new Error(`Local Vite CLI is missing: ${VITE_CLI}`);
  }
  const port = requestedPort ?? await freePort();
  const stderr = { value: "" };
  const child = spawn(
    process.execPath,
    [VITE_CLI, "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    {
      cwd: ROOT,
      env: { ...process.env, NO_COLOR: "1" },
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    },
  );
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => {
    stderr.value = `${stderr.value}${chunk}`.slice(-16_384);
  });
  const url = `http://127.0.0.1:${port}${APP_BASE_PATH}`;
  try {
    await waitForServer(url, child, stderr);
  } catch (error) {
    child.kill();
    throw error;
  }
  return { child, url };
}

async function stopPreviewServer(child) {
  if (!child || child.exitCode !== null) return;
  child.kill();
  await Promise.race([
    new Promise((resolveExit) => child.once("exit", resolveExit)),
    delay(3_000),
  ]);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function finiteNonNegative(value, field) {
  assert(typeof value === "number" && Number.isFinite(value) && value >= 0, `${field} must be finite and non-negative`);
  return value;
}

function nearestRankP95(samples) {
  const ordered = [...samples].sort((left, right) => left - right);
  return ordered[Math.max(0, Math.ceil(0.95 * ordered.length) - 1)];
}

function median(samples) {
  const ordered = [...samples].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 === 0 ? (ordered[middle - 1] + ordered[middle]) / 2 : ordered[middle];
}

function measurement(samples, unit, target = null) {
  assert(samples.length >= 3, "measurement requires at least three samples");
  samples.forEach((sample, index) => finiteNonNegative(sample, `measurement.samples[${index}]`));
  const result = {
    unit,
    samples,
    median: median(samples),
    p95: nearestRankP95(samples),
  };
  if (target) {
    const actual = result[target.statistic];
    const passed = target.operator === "lte" ? actual <= target.value : actual >= target.value;
    result.target = { ...target, passed };
    assert(passed, `hard target failed: ${actual} ${target.operator} ${target.value}`);
  }
  return result;
}

function profileTargets(profile) {
  const mobile = profile.deviceClass === "mobile";
  const targets = {
    first_interactive_ms: { statistic: "median", operator: "lte", value: mobile ? 2_500 : 1_500 },
    lcp_ms: { statistic: "median", operator: "lte", value: 2_500 },
    interaction_proxy_ms: { statistic: "p95", operator: "lte", value: 200 },
    node_selection_ms: { statistic: "p95", operator: "lte", value: 100 },
    filter_ms: { statistic: "p95", operator: "lte", value: 200 },
    relationship_detail_ms: { statistic: "p95", operator: "lte", value: 200 },
    keyboard_focus_ms: { statistic: "p95", operator: "lte", value: 100 },
    fps: { statistic: "p95", operator: "gte", value: mobile ? 30 : 45 },
    cls: { statistic: "p95", operator: "lte", value: 0.1 },
  };
  if (mobile) targets.js_heap_mb = { statistic: "p95", operator: "lte", value: 150 };
  return targets;
}

function extractBudgetReport(stdout) {
  const marker = "\n[museum-04-budget]";
  const end = stdout.indexOf(marker);
  const jsonText = (end === -1 ? stdout : stdout.slice(0, end)).trim();
  const report = JSON.parse(jsonText);
  assert(report?.status === "pass", "deterministic static budget report did not pass");
  assert(report?.algorithm === "node:zlib gzip level 9; each file compressed independently", "unexpected gzip algorithm");
  assert(Number.isInteger(report?.constellationRoute?.gzipBytes) && report.constellationRoute.gzipBytes > 0, "route gzip total is missing");
  return report;
}

function readStaticBudget() {
  const result = spawnSync(process.execPath, [BUDGET_RUNNER, "--json"], {
    cwd: ROOT,
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`deterministic static budget gate failed: ${(result.stderr || result.stdout).trim()}`);
  }
  return extractBudgetReport(result.stdout);
}

async function configureLab(page, profile) {
  const session = await page.context().newCDPSession(page);
  await session.send("Network.enable");
  await session.send("Network.setCacheDisabled", { cacheDisabled: true });
  const network = NETWORKS[profile.network];
  await session.send("Network.emulateNetworkConditions", network ? {
    offline: false,
    latency: network.latencyMs,
    downloadThroughput: network.downloadBitsPerSecond / 8,
    uploadThroughput: network.uploadBitsPerSecond / 8,
    connectionType: network.connectionType,
  } : {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
    connectionType: "none",
  });
  await session.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
  await session.send("Performance.enable");
  return session;
}

async function readHeapMb(session) {
  const response = await session.send("Performance.getMetrics");
  const metric = response.metrics.find((candidate) => candidate.name === "JSHeapUsedSize");
  if (!metric || !Number.isFinite(metric.value)) throw new Error("Chromium did not expose JSHeapUsedSize");
  return metric.value / (1024 * 1024);
}

async function installPerformanceObservers(context) {
  await context.addInitScript(() => {
    const state = { lcp: 0, lcpElement: null, cls: 0, longTasks: 0 };
    Object.defineProperty(globalThis, "__MUSEUM04_CURRENT_LAB__", {
      configurable: true,
      value: state,
    });
    const observe = (type, callback) => {
      try {
        const observer = new PerformanceObserver((list) => callback(list.getEntries()));
        observer.observe({ type, buffered: true });
      } catch {
        // The runner validates required outputs and fails if Chromium omits LCP.
      }
    };
    observe("largest-contentful-paint", (entries) => {
      for (const entry of entries) {
        if (entry.startTime < state.lcp) continue;
        state.lcp = entry.startTime;
        state.lcpElement = entry.element ? {
          tag: entry.element.tagName,
          class_name: entry.element.className,
          text: entry.element.textContent?.trim().slice(0, 120) ?? "",
          size: entry.size,
        } : null;
      }
    });
    observe("layout-shift", (entries) => {
      for (const entry of entries) {
        if (!entry.hadRecentInput) state.cls += entry.value;
      }
    });
    observe("longtask", (entries) => {
      state.longTasks += entries.length;
    });
  });
}

async function measureUiAction(page, operation) {
  return await page.evaluate(async (requestedOperation) => {
    const waitFor = async (predicate, label) => {
      const deadline = performance.now() + 5_000;
      while (!predicate()) {
        if (performance.now() > deadline) throw new Error(`Timed out waiting for ${label}`);
        await new Promise((resolveFrame) => requestAnimationFrame(resolveFrame));
      }
    };
    const tabs = () => [...document.querySelectorAll(".view-tabs [role='tab']")];
    const start = performance.now();
    if (requestedOperation === "select_artist") {
      const button = document.querySelector(".artist-navigator button, .artist-list-view button");
      if (!(button instanceof HTMLButtonElement)) throw new Error("Artist selection button is missing");
      button.click();
      await waitFor(
        () => Boolean(document.querySelector(".constellation-detail-panel:not([hidden])")),
        "artist panel",
      );
    } else if (requestedOperation === "select_relationship") {
      const button = document.querySelector(".related-relation-list button");
      if (!(button instanceof HTMLButtonElement)) throw new Error("Related relationship button is missing");
      button.click();
      await waitFor(
        () => {
          const panel = document.querySelector(".constellation-detail-panel[data-panel-kind='relationship']:not([hidden])");
          const title = panel?.querySelector("#constellation-panel-content-title");
          const close = panel?.querySelector(".panel-close");
          if (!(panel instanceof HTMLElement) || !(title instanceof HTMLElement) || !(close instanceof HTMLButtonElement)) return false;
          const bounds = title.getBoundingClientRect();
          return title.textContent?.trim() && bounds.width > 0 && bounds.height > 0 && document.activeElement === close;
        },
        "visible, focused relationship explanation",
      );
    } else if (requestedOperation === "filter") {
      const select = document.querySelector(".filter-grid select");
      if (!(select instanceof HTMLSelectElement)) throw new Error("Relationship-type filter is missing");
      select.value = "shared_subject";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      await waitFor(() => /[?&]types=shared_subject(?:&|$)/.test(location.hash), "filtered URL state");
    } else if (requestedOperation === "reset_filter") {
      const select = document.querySelector(".filter-grid select");
      if (!(select instanceof HTMLSelectElement)) throw new Error("Relationship-type filter is missing");
      select.value = "all";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      await waitFor(() => !/[?&]types=/.test(location.hash), "reset filter URL state");
    } else if (requestedOperation === "list_switch") {
      const listTab = tabs()[1];
      if (!(listTab instanceof HTMLButtonElement)) throw new Error("List view tab is missing");
      listTab.click();
      await waitFor(
        () => document.querySelector("main")?.dataset.view === "list" && Boolean(document.querySelector(".artist-list-view")),
        "artist list view",
      );
    } else if (requestedOperation === "keyboard_focus") {
      const listTab = tabs()[1];
      const tableTab = tabs()[2];
      if (!(listTab instanceof HTMLButtonElement) || !(tableTab instanceof HTMLButtonElement)) {
        throw new Error("Keyboard view tabs are missing");
      }
      listTab.focus();
      listTab.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
      await waitFor(
        () => document.activeElement === tableTab,
        "keyboard focus",
      );
    } else {
      throw new Error(`Unknown UI operation: ${requestedOperation}`);
    }
    return performance.now() - start;
  }, operation);
}

async function measureViewFps(page, experience, durationMs = 1_000) {
  return await page.evaluate(async ({ requestedDuration, requestedExperience }) => {
    const target = document.querySelector(
      requestedExperience === "graph" ? ".constellation-canvas" : ".artist-list-view",
    );
    if (!(target instanceof HTMLElement) || (requestedExperience === "graph" && !target.querySelector("canvas"))) {
      throw new Error(`${requestedExperience} experience is missing for FPS sampling`);
    }
    return await new Promise((resolveFps, reject) => {
      const frames = [];
      const timeout = setTimeout(() => reject(new Error("FPS sampling timed out")), requestedDuration + 5_000);
      const tick = (timestamp) => {
        frames.push(timestamp);
        target.dispatchEvent(new WheelEvent("wheel", {
          bubbles: true,
          cancelable: true,
          clientX: target.clientWidth / 2,
          clientY: target.clientHeight / 2,
          deltaY: frames.length % 2 === 0 ? -12 : 12,
        }));
        if (frames.length < 2 || timestamp - frames[0] < requestedDuration) {
          requestAnimationFrame(tick);
          return;
        }
        clearTimeout(timeout);
        resolveFps(((frames.length - 1) * 1_000) / (frames.at(-1) - frames[0]));
      };
      requestAnimationFrame(tick);
    });
  }, { requestedDuration: durationMs, requestedExperience: experience });
}

async function readInitialTimings(page, experience) {
  return await page.evaluate((requestedExperience) => {
    const firstMark = (name) => performance.getEntriesByName(name, "mark")[0]?.startTime ?? null;
    const route = firstMark("museum04-route-module");
    const data = firstMark("museum04-initial-data-ready");
    const experienceReady = firstMark("museum04-experience-ready");
    const routeChunk = performance.getEntriesByType("resource")
      .find((entry) => /ArtConstellationPage/i.test(entry.name));
    const graphChunk = performance.getEntriesByType("resource")
      .find((entry) => /SigmaGraphRenderer/i.test(entry.name));
    return {
      route_load_ms: route,
      data_load_ms: route === null || data === null ? null : data - route,
      chunk_load_ms: (requestedExperience === "graph" ? graphChunk : routeChunk)?.duration ?? null,
      first_interactive_ms: experienceReady,
    };
  }, experience);
}

async function readPageSignals(page) {
  return await page.evaluate(() => {
    const state = globalThis.__MUSEUM04_CURRENT_LAB__;
    const entries = [
      ...performance.getEntriesByType("navigation"),
      ...performance.getEntriesByType("resource"),
    ];
    return {
      lcp_ms: state?.lcp ?? null,
      lcp_element: state?.lcpElement ?? null,
      cls: state?.cls ?? null,
      long_tasks_count: state?.longTasks ?? null,
      transferred_bytes: entries.reduce((total, entry) => total + (entry.transferSize ?? 0), 0),
    };
  });
}

function verifyRawSample(sample) {
  for (const field of Object.keys(METRIC_UNITS)) finiteNonNegative(sample[field], field);
  for (const field of ["route_load_ms", "chunk_load_ms", "first_interactive_ms", "fps", "lcp_ms", "transferred_bytes", "gzip_bytes"]) {
    assert(sample[field] > 0, `${field} must be greater than zero`);
  }
  assert(sample.first_interactive_ms >= sample.route_load_ms, "first interactive must not precede route-module evaluation");
  return sample;
}

async function sampleProfile(browser, baseUrl, profile, gzipBytes) {
  const context = await browser.newContext({
    viewport: profile.viewport,
    deviceScaleFactor: 1,
    serviceWorkers: "block",
  });
  await installPerformanceObservers(context);
  const page = await context.newPage();
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("requestfailed", (request) => browserErrors.push(`requestfailed: ${request.url()} (${request.failure()?.errorText ?? "unknown"})`));
  page.on("response", (response) => {
    if (response.status() >= 400) browserErrors.push(`http-${response.status()}: ${response.url()}`);
  });
  const session = await configureLab(page, profile);
  try {
    const response = await page.goto(routeUrl(baseUrl), { waitUntil: "domcontentloaded", timeout: 60_000 });
    assert(response?.ok(), `${profile.id}: navigation failed with HTTP ${response?.status() ?? "none"}`);
    await page.locator(`main[data-museum04-status='ready'][data-view='${profile.initialExperience}']`).waitFor({ timeout: 60_000 });
    await page.waitForFunction(
      () => performance.getEntriesByName("museum04-experience-ready", "mark").length > 0,
      undefined,
      { timeout: 60_000 },
    );
    if (profile.initialExperience === "graph") {
      await page.locator(".constellation-canvas canvas").first().waitFor({ timeout: 30_000 });
    } else {
      await page.locator(".artist-list-view").waitFor({ timeout: 30_000 });
      assert(await page.locator(".constellation-canvas canvas").count() === 0, `${profile.id}: compact fallback loaded a canvas`);
    }
    await delay(100);
    const initial = await readInitialTimings(page, profile.initialExperience);
    const initialSignals = await readPageSignals(page);

    const nodeSelectionMs = await measureUiAction(page, "select_artist");
    await page.waitForFunction(() => /[?&]focus=/.test(location.hash), undefined, { timeout: 10_000 });
    await page.locator(".related-relation-list button").first().waitFor({ timeout: 30_000 });
    const relationshipDetailMs = await measureUiAction(page, "select_relationship");
    await page.waitForFunction(() => /[?&]relation=/.test(location.hash), undefined, { timeout: 10_000 });
    await page.locator("#relation-context-title").waitFor({ timeout: 30_000 });
    await page.locator(".panel-close").click();
    await page.locator(".constellation-detail-panel").waitFor({ state: "hidden", timeout: 10_000 });

    const filterMs = await measureUiAction(page, "filter");
    await measureUiAction(page, "reset_filter");
    if (profile.initialExperience === "list") {
      await page.locator(".view-tabs [role='tab']").nth(2).click();
      await page.locator("main[data-view='table'] .relationship-table-view").waitFor({ timeout: 10_000 });
    }
    const listSwitchMs = await measureUiAction(page, "list_switch");
    const keyboardFocusMs = await measureUiAction(page, "keyboard_focus");
    await page.locator("main[data-view='table'] .relationship-table-view").waitFor({ timeout: 10_000 });

    if (profile.initialExperience === "graph") {
      await page.locator(".view-tabs [role='tab']").nth(0).click();
      await page.locator("main[data-view='graph'] .constellation-canvas canvas").first().waitFor({ timeout: 30_000 });
    } else {
      await page.locator(".view-tabs [role='tab']").nth(1).click();
      await page.locator("main[data-view='list'] .artist-list-view").waitFor({ timeout: 10_000 });
      const sigmaRequests = await page.evaluate(() => performance.getEntriesByType("resource")
        .filter((entry) => /SigmaGraphRenderer/i.test(entry.name)).length);
      assert(sigmaRequests === 0, `${profile.id}: compact list fallback requested the Sigma chunk`);
    }
    const fps = await measureViewFps(page, profile.initialExperience);
    const jsHeapMb = await readHeapMb(session);
    const finalSignals = await readPageSignals(page);
    const interactionProxyMs = Math.max(
      nodeSelectionMs,
      filterMs,
      relationshipDetailMs,
      keyboardFocusMs,
      listSwitchMs,
    );
    assert(browserErrors.length === 0, `${profile.id}: browser errors: ${browserErrors.join(" | ")}`);
    return verifyRawSample({
      ...initial,
      node_selection_ms: nodeSelectionMs,
      filter_ms: filterMs,
      relationship_detail_ms: relationshipDetailMs,
      keyboard_focus_ms: keyboardFocusMs,
      list_switch_ms: listSwitchMs,
      fps,
      js_heap_mb: jsHeapMb,
      lcp_ms: initialSignals.lcp_ms,
      lcp_element: initialSignals.lcp_element,
      cls: initialSignals.cls,
      long_tasks_count: finalSignals.long_tasks_count,
      transferred_bytes: finalSignals.transferred_bytes,
      gzip_bytes: gzipBytes,
      interaction_proxy_ms: interactionProxyMs,
    });
  } finally {
    await context.close();
  }
}

function aggregateRuns(samplesByProfile) {
  return CURRENT_PROFILES.map((profile) => {
    const samples = samplesByProfile[profile.id];
    assert(Array.isArray(samples) && samples.length >= 3, `${profile.id}: at least three cold samples are required`);
    const targets = profileTargets(profile);
    const metrics = {};
    for (const [metricName, unit] of Object.entries(METRIC_UNITS)) {
      try {
        metrics[metricName] = measurement(
          samples.map((sample) => sample[metricName]),
          unit,
          targets[metricName] ?? null,
        );
      } catch (error) {
        throw new Error(
          `${profile.id}.${metricName}: ${error instanceof Error ? error.message : String(error)}`,
          { cause: error },
        );
      }
    }
    return {
      profile_id: profile.id,
      viewport: profile.viewport,
      device_class: profile.deviceClass,
      initial_experience: profile.initialExperience,
      cpu_throttle_rate: profile.cpu,
      network_profile: profile.network,
      sample_count: samples.length,
      metrics,
    };
  });
}

function gitMetadata() {
  const commitSha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8", windowsHide: true }).trim();
  const status = execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8", windowsHide: true });
  assert(/^[0-9a-f]{40}$/.test(commitSha), "git rev-parse did not return a full commit SHA");
  return { commitSha, dirty: status.trim().length > 0 };
}

function buildEvidence(samplesByProfile, browserVersion, budget, testedUrl) {
  const git = gitMetadata();
  const playwrightVersion = require("@playwright/test/package.json").version;
  return {
    schema_version: "1.0.0",
    benchmark_id: "museum-04-current-graph",
    evidence_class: "controlled_lab_not_rum",
    real_user_metric: false,
    real_device_status: "not_available",
    real_device_note: "No physical approximately 4 GB Android device was exposed to this runtime; Chromium CDP throttling is a lab proxy only.",
    captured_at: new Date().toISOString(),
    environment: {
      host_os: `${platform()} ${release()}`,
      cpu: cpus()[0]?.model || "CPU model not exposed",
      memory_gb: Number((totalmem() / (1024 ** 3)).toFixed(2)),
      browser: "Chromium",
      browser_version: browserVersion,
      node_version: process.version,
      playwright_version: playwrightVersion,
      runner: "scripts/run-museum-04-current-lab.mjs",
      measurement_method: "Playwright Chromium; fresh context, disabled cache, CDP CPU/network controls, PerformanceObserver, Resource Timing, and deterministic static gzip",
      commit_sha: git.commitSha,
      source_worktree_dirty: git.dirty,
    },
    lab_configuration: {
      tested_url: testedUrl,
      cold_browser_context_per_sample: true,
      browser_cache_disabled: true,
      service_workers_blocked: true,
      real_user_monitoring: false,
      analytics_or_telemetry_added: false,
      profiles: CURRENT_PROFILES.map((profile) => ({
        profile_id: profile.id,
        viewport: profile.viewport,
        initial_experience: profile.initialExperience,
        cpu_throttle_rate: profile.cpu,
        network_profile: profile.network,
        network: NETWORKS[profile.network] ? {
          latency_ms: NETWORKS[profile.network].latencyMs,
          download_bits_per_second: NETWORKS[profile.network].downloadBitsPerSecond,
          upload_bits_per_second: NETWORKS[profile.network].uploadBitsPerSecond,
        } : null,
      })),
      metric_definitions: {
        route_load_ms: "Navigation time origin to museum04-route-module evaluation.",
        data_load_ms: "museum04-route-module to museum04-initial-data-ready.",
        chunk_load_ms: "Resource Timing duration for the mode-specific lazy experience chunk: SigmaGraphRenderer for graph profiles and ArtConstellationPage for the compact semantic-list profile.",
        first_interactive_ms: "Navigation time origin to the first museum04-experience-ready mark for the graph or semantic-list path.",
        node_selection_ms: "Artist activation in the graph navigator or equivalent semantic list to the visible artist panel; URL focus persistence is asserted separately.",
        filter_ms: "Relationship-type change to committed URL filter state.",
        relationship_detail_ms: "Relationship activation to the visible relationship-specific title with panel close focus established; URL relation persistence and deferred evidence closure are asserted separately.",
        keyboard_focus_ms: "ArrowRight on the selected List tab to focus on the Relationship Table tab; selected state and rendered equivalent table are asserted separately.",
        list_switch_ms: "List-tab activation to rendered artist-list equivalent view.",
        fps: "requestAnimationFrame rate during repeated wheel input for one second on the active experience: Sigma canvas for graph profiles or the semantic artist list for the 360px compact profile.",
        interaction_proxy_ms: "Maximum of node selection, filter, meaningful relationship panel, keyboard focus, and list-switch response in each sample; controlled script proxy, not INP or RUM.",
        lcp_ms: "Buffered LargestContentfulPaint before the first interaction.",
        cls: "Cumulative layout-shift score from navigation through initial experience readiness, before scripted interaction begins and excluding entries with recent input.",
        long_tasks_count: "Count of PerformanceObserver longtask entries across the sampled flow.",
        transferred_bytes: "Navigation plus resource transferSize across initial and exercised deferred-detail requests.",
        gzip_bytes: "Deterministic route JS, CSS, and initial-data gzip total from the static level-9 budget gate.",
        js_heap_mb: "Chromium CDP JSHeapUsedSize after the sampled flow.",
      },
      deterministic_gzip_budget: {
        algorithm: budget.algorithm,
        home_initial_gzip_bytes: budget.homeInitial.gzipBytes,
        constellation_route_gzip_bytes: budget.constellationRoute.gzipBytes,
        initial_data_gzip_bytes: budget.constellationRoute.initialDataGzipBytes,
        graph_summary_gzip_bytes: budget.graphSummary.gzipBytes,
        manifest: budget.manifest,
        status: budget.status,
      },
    },
    runs: aggregateRuns(samplesByProfile),
    overall_status: "pass",
  };
}

function validateWithPython(evidence) {
  const code = [
    "import json, sys",
    "from scripts.validate_museum_04_performance_evidence import validate_current_graph",
    "errors = validate_current_graph(json.load(sys.stdin))",
    "print('\\n'.join(errors))",
    "raise SystemExit(1 if errors else 0)",
  ].join("; ");
  const result = spawnSync("python", ["-c", code], {
    cwd: ROOT,
    encoding: "utf8",
    input: JSON.stringify(evidence),
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`assembled current-graph evidence failed the Python contract: ${(result.stdout || result.stderr).trim()}`);
  }
}

function writeEvidence(path, evidence) {
  const parent = dirname(path);
  if (!existsSync(parent) || !statSync(parent).isDirectory()) {
    throw new Error(`--output parent directory does not exist: ${parent}`);
  }
  writeFileSync(path, `${JSON.stringify(evidence, null, 2)}\n`, { encoding: "utf8", flag: "w" });
}

async function run(options) {
  let server = null;
  let browser = null;
  try {
    const budget = readStaticBudget();
    let baseUrl;
    if (options.url) {
      baseUrl = normalizeTargetUrl(options.url);
      await waitForServer(baseUrl, null, { value: "" });
    } else {
      server = await startPreviewServer(options.port);
      baseUrl = server.url;
    }
    console.error(`[museum-04-current-lab] target=${baseUrl} samples=${options.samples}`);
    browser = await chromium.launch({
      headless: true,
      args: ["--enable-precise-memory-info"],
    });
    const browserVersion = browser.version();
    const samplesByProfile = Object.fromEntries(CURRENT_PROFILES.map((profile) => [profile.id, []]));
    for (const profile of CURRENT_PROFILES) {
      for (let sampleIndex = 0; sampleIndex < options.samples; sampleIndex += 1) {
        console.error(`[museum-04-current-lab] profile=${profile.id} cold-sample=${sampleIndex + 1}/${options.samples}`);
        const sample = await sampleProfile(browser, baseUrl, profile, budget.constellationRoute.gzipBytes);
        samplesByProfile[profile.id].push(sample);
        console.error(
          `[museum-04-current-lab] profile=${profile.id} sample=${sampleIndex + 1} ` +
          `route=${sample.route_load_ms.toFixed(1)}ms data=${sample.data_load_ms.toFixed(1)}ms ` +
          `chunk=${sample.chunk_load_ms.toFixed(1)}ms interactive=${sample.first_interactive_ms.toFixed(1)}ms lcp=${sample.lcp_ms.toFixed(1)}ms ` +
          `lcpElement=${JSON.stringify(sample.lcp_element)} ` +
          `node=${sample.node_selection_ms.toFixed(1)}ms relation=${sample.relationship_detail_ms.toFixed(1)}ms ` +
          `filter=${sample.filter_ms.toFixed(1)}ms list=${sample.list_switch_ms.toFixed(1)}ms ` +
          `keyboard=${sample.keyboard_focus_ms.toFixed(1)}ms fps=${sample.fps.toFixed(1)}`,
        );
      }
    }
    const evidence = buildEvidence(samplesByProfile, browserVersion, budget, baseUrl);
    validateWithPython(evidence);
    if (options.output) {
      writeEvidence(options.output, evidence);
      console.error(`[museum-04-current-lab] wrote=${options.output}`);
    } else {
      process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`);
    }
    return evidence;
  } finally {
    await browser?.close();
    await stopPreviewServer(server?.child);
  }
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`[museum-04-current-lab] ${error.message}`);
    console.error(usage());
    process.exitCode = 2;
    return;
  }
  if (options.help) {
    process.stdout.write(usage());
    return;
  }
  try {
    await run(options);
  } catch (error) {
    console.error(`[museum-04-current-lab] FAIL ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}

export {
  CURRENT_PROFILES,
  METRIC_UNITS,
  aggregateRuns,
  buildEvidence,
  extractBudgetReport,
  measurement,
  nearestRankP95,
  normalizeTargetUrl,
  parseArgs,
  profileTargets,
  routeUrl,
  run,
  validateWithPython,
  verifyRawSample,
};
