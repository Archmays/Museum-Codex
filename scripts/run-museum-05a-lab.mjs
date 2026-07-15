#!/usr/bin/env node
/* global PerformanceObserver, performance, localStorage, window, document */

import { chromium } from "playwright";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { URL } from "node:url";
import { execFileSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const defaultOutput = resolve(root, "docs/qa/museum-05a/performance.json");
const sampleCount = 3;
const profiles = [
  {
    id: "desktop-artist-index",
    viewport: { width: 1440, height: 900 },
    route: "#/art/artists",
    lowBandwidth: false,
    cpuRate: 1,
    network: null,
    firstInteractiveTarget: 2000,
    lcpTarget: 2500,
    maxImages: 8,
    maxImageBytes: 2_000_000,
    maxTransferredBytes: 3_000_000,
  },
  {
    id: "mobile-artist-index-low-bandwidth",
    viewport: { width: 390, height: 844 },
    route: "#/art/artists",
    lowBandwidth: true,
    cpuRate: 4,
    network: { latency: 20, downloadThroughput: 500_000, uploadThroughput: 375_000 },
    firstInteractiveTarget: 3500,
    lcpTarget: 2500,
    maxImages: 0,
    maxImageBytes: 0,
    maxTransferredBytes: 3_000_000,
  },
  {
    id: "desktop-artwork-detail",
    viewport: { width: 1366, height: 768 },
    route: "#/art/artworks/artwork%3Amet-334816",
    lowBandwidth: false,
    cpuRate: 1,
    network: null,
    firstInteractiveTarget: 2000,
    lcpTarget: 2500,
    maxImages: 2,
    maxImageBytes: 1_000_000,
    maxTransferredBytes: 3_000_000,
  },
  {
    id: "mobile-artwork-detail",
    viewport: { width: 390, height: 844 },
    route: "#/art/artworks/artwork%3Amet-334816",
    lowBandwidth: false,
    cpuRate: 4,
    network: { latency: 20, downloadThroughput: 500_000, uploadThroughput: 375_000 },
    firstInteractiveTarget: 3500,
    lcpTarget: 3500,
    maxImages: 2,
    maxImageBytes: 750_000,
    maxTransferredBytes: 3_000_000,
  },
  {
    id: "mobile-compare-low-bandwidth",
    viewport: { width: 360, height: 800 },
    route: "#/art/compare?left=artwork%3Amet-334816&right=artwork%3Amet-436243",
    lowBandwidth: true,
    cpuRate: 4,
    network: { latency: 20, downloadThroughput: 500_000, uploadThroughput: 375_000 },
    firstInteractiveTarget: 3500,
    lcpTarget: 2500,
    maxImages: 0,
    maxImageBytes: 0,
    maxTransferredBytes: 3_000_000,
  },
];

function parseArgs(argv) {
  const options = { url: "http://127.0.0.1:4173/Museum-Codex/", output: defaultOutput, samples: sampleCount, printInputContract: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--url") options.url = argv[++index];
    else if (value === "--output") options.output = resolve(root, argv[++index]);
    else if (value === "--samples") options.samples = Number(argv[++index]);
    else if (value === "--print-input-contract") options.printInputContract = true;
    else throw new Error(`unknown argument: ${value}`);
  }
  const url = new URL(options.url);
  if (!/^https?:$/.test(url.protocol) || !url.pathname.endsWith("/")) throw new Error("--url must be an HTTP(S) directory URL");
  if (options.samples !== sampleCount) throw new Error(`--samples is fixed at ${sampleCount}`);
  options.url = url.href;
  return options;
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

function canonicalImplementationInputFiles() {
  const productSourceFiles = walk(resolve(root, "src"))
    .filter((path) => {
      const name = relative(root, path).replaceAll("\\", "/");
      return statSync(path).isFile() && !name.startsWith("src/tests/");
    })
    .map((path) => relative(root, path).replaceAll("\\", "/"));
  return [...new Set([
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    ...productSourceFiles,
    "public/releases/art-constellation-1.0.0/manifest.json",
    "scripts/run-museum-05a-lab.mjs",
    "scripts/validate_museum_05a_performance.py",
  ])].sort();
}

function implementationInput() {
  const names = canonicalImplementationInputFiles();
  const hash = createHash("sha256");
  for (const name of names) {
    const path = resolve(root, name);
    if (!statSync(path).isFile()) throw new Error(`canonical implementation input is missing: ${name}`);
    hash.update(name); hash.update("\0"); hash.update(readFileSync(path)); hash.update("\0");
  }
  return { files: names, hash: `sha256:${hash.digest("hex")}` };
}

function networkProfile(profile) {
  if (!profile.network) {
    return { id: "unthrottled", emulation_enabled: false, connection_type: null };
  }
  return {
    id: "fast_4g",
    emulation_enabled: true,
    connection_type: "cellular4g",
    latency_ms: profile.network.latency,
    download_throughput_bytes_per_second: profile.network.downloadThroughput,
    upload_throughput_bytes_per_second: profile.network.uploadThroughput,
  };
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function p95(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)];
}

function metric(samples, target = null) {
  const result = { samples, median: median(samples), p95: p95(samples) };
  if (target) result.target = { ...target, passed: target.operator === "lte" ? result[target.statistic] <= target.value : result[target.statistic] >= target.value };
  return result;
}

function isExpectedDiagnostic(type, message) {
  return type === "warning" && /^\[\.WebGL-[^\]]+\]GL Driver Message .*GPU stall due to ReadPixels/.test(message);
}

async function sampleProfile(browser, baseUrl, profile) {
  const context = await browser.newContext({ viewport: profile.viewport, serviceWorkers: "block" });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  if (profile.cpuRate > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpuRate });
  if (profile.network) {
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      connectionType: "cellular4g",
      ...profile.network,
    });
  }
  const issues = [];
  const externalRequests = [];
  const baseOrigin = new URL(baseUrl).origin;
  page.on("console", (message) => {
    if (["warning", "error"].includes(message.type()) && !isExpectedDiagnostic(message.type(), message.text())) {
      issues.push(`console ${message.type()}: ${message.text()}`);
    }
  });
  page.on("requestfailed", (request) => issues.push(`request failed: ${request.url()}`));
  page.on("response", (response) => {
    if (response.status() >= 400) issues.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== baseOrigin) externalRequests.push(request.url());
  });
  await page.addInitScript(({ lowBandwidth }) => {
    localStorage.setItem("museum-locale", "en");
    localStorage.setItem("museum-low-bandwidth", String(lowBandwidth));
    window.__MUSEUM05A_LAB__ = { lcp: 0, cls: 0 };
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries.at(-1);
      if (last) window.__MUSEUM05A_LAB__.lcp = last.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) window.__MUSEUM05A_LAB__.cls += entry.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  }, { lowBandwidth: profile.lowBandwidth });
  const started = performance.now();
  const response = await page.goto(`${baseUrl}${profile.route}`, { waitUntil: "domcontentloaded" });
  if (response && response.status() !== 200) issues.push(`navigation HTTP ${response.status()}`);
  await page.locator("[data-museum05a-status=ready]").waitFor({ state: "visible", timeout: 15_000 });
  const firstInteractiveMs = performance.now() - started;
  await page.waitForTimeout(300);
  const browserMetrics = await page.evaluate(() => {
    const resources = performance.getEntriesByType("resource");
    const images = resources.filter((entry) => /\.(?:jpe?g|webp)(?:$|[?#])/i.test(entry.name));
    return {
      lcpMs: window.__MUSEUM05A_LAB__?.lcp ?? 0,
      cls: window.__MUSEUM05A_LAB__?.cls ?? 0,
      imageRequests: images.length,
      imageBytes: images.reduce((total, entry) => total + (entry.transferSize || entry.encodedBodySize || 0), 0),
      transferredBytes: resources.reduce((total, entry) => total + (entry.transferSize || entry.encodedBodySize || 0), 0),
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    };
  });
  await context.close();
  return { firstInteractiveMs, ...browserMetrics, issues, externalRequests };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.printInputContract) {
    process.stdout.write(`${JSON.stringify(implementationInput(), null, 2)}\n`);
    return;
  }
  const inputBeforeLab = implementationInput();
  const browser = await chromium.launch({ headless: true });
  const profileResults = [];
  try {
    for (const profile of profiles) {
      const samples = [];
      for (let index = 0; index < options.samples; index += 1) {
        samples.push(await sampleProfile(browser, options.url, profile));
      }
      const metrics = {
        first_interactive_ms: metric(samples.map((sample) => sample.firstInteractiveMs), { statistic: "median", operator: "lte", value: profile.firstInteractiveTarget }),
        lcp_ms: metric(samples.map((sample) => sample.lcpMs), { statistic: "median", operator: "lte", value: profile.lcpTarget }),
        cls: metric(samples.map((sample) => sample.cls), { statistic: "p95", operator: "lte", value: 0.1 }),
        initial_image_requests: metric(samples.map((sample) => sample.imageRequests), { statistic: "p95", operator: "lte", value: profile.maxImages }),
        initial_image_bytes: metric(samples.map((sample) => sample.imageBytes), { statistic: "p95", operator: "lte", value: profile.maxImageBytes }),
        transferred_bytes: metric(samples.map((sample) => sample.transferredBytes), { statistic: "p95", operator: "lte", value: profile.maxTransferredBytes }),
        horizontal_overflow_px: metric(samples.map((sample) => Math.max(0, sample.scrollWidth - sample.clientWidth)), { statistic: "p95", operator: "lte", value: 0 }),
      };
      const assertions = {
        lcp_observed: samples.every((sample) => sample.lcpMs > 0),
        transfer_observed: samples.every((sample) => sample.transferredBytes > 0),
        no_console_or_network_errors: samples.every((sample) => sample.issues.length === 0),
        no_external_requests: samples.every((sample) => sample.externalRequests.length === 0),
        no_horizontal_overflow: samples.every((sample) => sample.scrollWidth <= sample.clientWidth),
      };
      const targetPass = Object.values(metrics).every((value) => !value.target || value.target.passed);
      profileResults.push({
        profile_id: profile.id,
        viewport: profile.viewport,
        route: profile.route,
        low_bandwidth: profile.lowBandwidth,
        cpu_throttle_rate: profile.cpuRate,
        network_profile: networkProfile(profile),
        sample_count: options.samples,
        metrics,
        assertions,
        issues: samples.flatMap((sample) => sample.issues),
        external_requests: samples.flatMap((sample) => sample.externalRequests),
        status: targetPass && Object.values(assertions).every(Boolean) ? "pass" : "fail",
      });
    }
  } finally {
    await browser.close();
  }
  const input = implementationInput();
  if (input.hash !== inputBeforeLab.hash || JSON.stringify(input.files) !== JSON.stringify(inputBeforeLab.files)) {
    throw new Error("canonical implementation inputs changed during the controlled lab");
  }
  const evidence = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-05A",
    evidence_class: "controlled_lab",
    real_user_metric: false,
    real_device_status: "not_available",
    real_assistive_technology_status: "not_available",
    captured_at: new Date().toISOString(),
    environment: {
      browser: "chromium",
      source_worktree_dirty: execFileSync("git", ["status", "--porcelain"], { cwd: root, encoding: "utf8" }).trim().length > 0,
      implementation_input_files: input.files,
      implementation_input_hash: input.hash,
      tested_url: options.url,
    },
    profiles: profileResults,
    overall_status: profileResults.every((profile) => profile.status === "pass") ? "pass" : "fail",
  };
  mkdirSync(dirname(options.output), { recursive: true });
  writeFileSync(options.output, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  console.log(`[museum-05a-lab] ${evidence.overall_status.toUpperCase()} profiles=${profileResults.length} output=${relative(root, options.output)}`);
  if (evidence.overall_status !== "pass") process.exitCode = 1;
}

main().catch((error) => {
  console.error(`[museum-05a-lab] FAIL ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
