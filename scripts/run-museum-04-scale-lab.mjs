import { execFileSync, spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { cpus, platform, release, totalmem } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { createRequire } from "node:module";
import { setTimeout } from "node:timers";
import { fileURLToPath, URL } from "node:url";
import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const HARNESS_CONFIG = join(ROOT, "benchmarks", "museum-04", "vite.config.ts");
const VITE_CLI = join(ROOT, "node_modules", "vite", "bin", "vite.js");
const VIEWPORT = { width: 390, height: 844 };
const CPU_THROTTLE_RATE = 4;
const FAST_4G = {
  name: "fast_4g",
  latencyMs: 20,
  downloadBitsPerSecond: 4_000_000,
  uploadBitsPerSecond: 3_000_000,
};
const PROFILE_COUNTS = {
  "1k": { vertices: 1_000, edges: 5_000 },
  "10k": { vertices: 10_000, edges: 60_000 },
  "50k": { vertices: 50_000, edges: 300_000 },
};
const VISIBLE_CAPS = {
  mobile: { vertices: 150, edges: 600 },
  desktop: { vertices: 300, edges: 1_200 },
};
const RELEASE_PERFORMANCE_CONTRACT_PATH = "public/releases/art-constellation-0.1.0/performance-contract.json";
const SCALE_IMPLEMENTATION_INPUT_FILES = [
  "benchmarks/museum-04/main.ts",
  "museum_pipeline/art/public_release.py",
  "package-lock.json",
  RELEASE_PERFORMANCE_CONTRACT_PATH,
  "schemas/art/release/art-constellation-artifact.schema.json",
  "scripts/generate_museum_04_scale_fixture.py",
  "scripts/run-museum-04-scale-lab.mjs",
  "scripts/validate_museum_04_performance_evidence.py",
];
const FIFTY_K_MODEL_STORAGE_BYTES = 50_000 * Uint32Array.BYTES_PER_ELEMENT
  + 300_000 * Uint32Array.BYTES_PER_ELEMENT * 2;
const GOVERNANCE_FIELDS = [
  "claim_ids",
  "computational_similarity",
  "curatorial_relevance",
  "evidence_confidence",
  "evidence_ids",
  "evidence_level",
  "historical_relationship_strength",
  "limitations",
  "source_ids",
];
const require = createRequire(import.meta.url);

function usage() {
  return `Usage: node scripts/run-museum-04-scale-lab.mjs [options]

Options:
  --samples <n>  Cold samples per profile (minimum 3, default 3)
  --url <url>    Use an existing localhost harness server
  --port <n>     Port for the managed Vite server (default: free port)
  --output <p>   Write validated JSON; otherwise print to stdout
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

function normalizeLocalUrl(value) {
  const url = new URL(value);
  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  if (!new Set(["http:", "https:"]).has(url.protocol) || !loopbackHosts.has(url.hostname)) {
    throw new Error("--url must use HTTP(S) on localhost or a loopback address");
  }
  url.search = "";
  url.hash = "";
  if (!url.pathname.endsWith("/")) url.pathname += "/";
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
      throw new Error(`Vite server exited before becoming ready${stderr.value ? `: ${stderr.value.trim()}` : ""}`);
    }
    try {
      const response = await globalThis.fetch(url, { signal: globalThis.AbortSignal.timeout(1_500) });
      if (response.ok) return;
    } catch {
      // The server may still be starting or pre-bundling dependencies.
    }
    await delay(200);
  }
  throw new Error(`Timed out waiting for benchmark server at ${url}${stderr.value ? `: ${stderr.value.trim()}` : ""}`);
}

async function startHarnessServer(requestedPort) {
  if (!existsSync(HARNESS_CONFIG) || !statSync(HARNESS_CONFIG).isFile()) {
    throw new Error(`Benchmark Vite config is missing: ${HARNESS_CONFIG}`);
  }
  if (!existsSync(VITE_CLI) || !statSync(VITE_CLI).isFile()) {
    throw new Error(`Local Vite CLI is missing: ${VITE_CLI}`);
  }
  const port = requestedPort ?? await freePort();
  const stderr = { value: "" };
  const child = spawn(
    process.execPath,
    [VITE_CLI, "--config", HARNESS_CONFIG, "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
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
  const url = `http://127.0.0.1:${port}/`;
  try {
    await waitForServer(url, child, stderr);
  } catch (error) {
    child.kill();
    throw error;
  }
  return { child, url };
}

async function stopHarnessServer(child) {
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

async function configureLab(page) {
  const session = await page.context().newCDPSession(page);
  await session.send("Network.enable");
  await session.send("Network.setCacheDisabled", { cacheDisabled: true });
  await session.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: FAST_4G.latencyMs,
    downloadThroughput: FAST_4G.downloadBitsPerSecond / 8,
    uploadThroughput: FAST_4G.uploadBitsPerSecond / 8,
    connectionType: "cellular4g",
  });
  await session.send("Emulation.setCPUThrottlingRate", { rate: CPU_THROTTLE_RATE });
  await session.send("Performance.enable");
  return session;
}

async function readHeapMb(session) {
  const response = await session.send("Performance.getMetrics");
  const metric = response.metrics.find((candidate) => candidate.name === "JSHeapUsedSize");
  if (!metric || !Number.isFinite(metric.value)) throw new Error("Chromium did not expose JSHeapUsedSize");
  return metric.value / (1024 * 1024);
}

function verifyRawResult(profile, result) {
  const counts = PROFILE_COUNTS[profile];
  assert(result && typeof result === "object", `${profile}: benchmark result is missing`);
  assert(result.status === "pass", `${profile}: harness status=${String(result.status)} error=${String(result.error ?? "none")}`);
  assert(result.profile === profile, `${profile}: result profile mismatch`);
  assert(result.synthetic === true && result.shipped === false, `${profile}: synthetic/non-shipping flags are invalid`);
  assert(result.vertices === counts.vertices && result.edges === counts.edges, `${profile}: vertex/edge counts are invalid`);
  assert(result.continuous_force_layout === false, `${profile}: continuous force layout must remain disabled`);
  if (profile === "1k") {
    assert(result.interactive_ready === true, "1k: renderer did not expose the interactive-ready boundary");
    assert(result.visible_rendered?.vertices === 150 && result.visible_rendered?.edges === 600, "1k: visible cap must be 150/600");
    assert(result.rendering_mode === "capped_progressive", "1k: renderer must use capped progressive mode");
    finiteNonNegative(result.renderer_ready_ms, "1k.renderer_ready_ms");
    finiteNonNegative(result.interaction_ms, "1k.interaction_ms");
    finiteNonNegative(result.node_selection_ms, "1k.node_selection_ms");
    finiteNonNegative(result.filter_ms, "1k.filter_ms");
    finiteNonNegative(result.fps, "1k.fps");
  } else if (profile === "10k") {
    assert(result.actual_full_renderer === false, "10k: full renderer must remain disabled");
    assert(result.partitioned_index === true && result.search_ready === true, "10k: partition/search boundary failed");
    assert(result.local_neighborhood_rendered === true, "10k: capped local neighborhood was not rendered");
    assert(result.visible_rendered?.vertices === 150 && result.visible_rendered?.edges === 600, "10k: visible cap must be 150/600");
    for (const field of ["model_build_ms", "index_build_ms", "filtered_render_ms"]) {
      finiteNonNegative(result[field], `10k.${field}`);
    }
  } else {
    assert(result.mobile_full_render_request === "refused", "50k: mobile full render request was not refused");
    assert(result.actual_full_webgl_render === false && result.rendered_300k_edges === false, "50k: full WebGL rendering occurred");
    assert(result.safe_fallback === true && result.no_freeze === true && result.no_blank_page === true, "50k: executed fallback boundary failed");
    assert(result.constructed_vertices === 50_000 && result.constructed_edges === 300_000, "50k: model construction counts are invalid");
    assert(result.model_storage_bytes === FIFTY_K_MODEL_STORAGE_BYTES, "50k: model storage bytes are invalid");
    assert(/^uint32:[0-9a-f]{8}$/.test(result.model_checksum), "50k: model checksum is invalid");
    assert(result.planned_vertex_chunks === 334 && result.planned_edge_chunks === 500, "50k: chunk counts are invalid");
    assert(result.planned_vertices === 50_000 && result.planned_edges === 300_000, "50k: planned totals are invalid");
    assert(result.max_vertices_per_chunk === 150 && result.max_edges_per_chunk === 600, "50k: chunk caps are invalid");
    assert(result.work_slice_limit_ms === 50 && result.max_work_slice_ms <= result.work_slice_limit_ms, "50k: bounded work slice exceeded 50 ms");
    assert(result.yield_count === 110, "50k: model construction did not yield at every bounded slice");
    assert(result.fallback_visible_during_work === true && result.fallback_visible_after_work === true, "50k: fallback was blank during executed work");
    for (const field of ["model_build_ms", "chunk_plan_ms", "max_work_slice_ms", "fallback_paint_ms", "js_heap_mb"]) {
      finiteNonNegative(result[field], `50k.${field}`);
    }
  }
}

async function sampleProfile(browser, baseUrl, profile, sampleIndex) {
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
    serviceWorkers: "block",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  const session = await configureLab(page);
  const url = new URL(baseUrl);
  url.searchParams.set("profile", profile);
  url.searchParams.set("sample", String(sampleIndex));
  const navigationStarted = performance.now();
  try {
    const response = await page.goto(url.toString(), { waitUntil: "domcontentloaded", timeout: 90_000 });
    assert(response?.ok(), `${profile}: navigation failed with HTTP ${response?.status() ?? "none"}`);
    if (profile === "1k") {
      await page.waitForFunction(
        () => {
          const result = globalThis.__MUSEUM04_SCALE_BENCHMARK__;
          return result?.interactive_ready === true || result?.status === "fail";
        },
        undefined,
        { timeout: 120_000 },
      );
    }
    const navigationFirstInteractiveMs = performance.now() - navigationStarted;
    await page.waitForFunction(
      () => {
        const result = globalThis.__MUSEUM04_SCALE_BENCHMARK__;
        return result?.status === "pass" || result?.status === "fail";
      },
      undefined,
      { timeout: 120_000 },
    );
    const result = await page.evaluate(() => globalThis.__MUSEUM04_SCALE_BENCHMARK__);
    if (result && typeof result === "object" && (profile === "10k" || result.js_heap_mb === null)) {
      result.js_heap_mb = await readHeapMb(session);
    }
    verifyRawResult(profile, result);
    assert(errors.length === 0, `${profile}: browser errors: ${errors.join(" | ")}`);
    return { ...result, navigation_first_interactive_ms: navigationFirstInteractiveMs };
  } finally {
    await context.close();
  }
}

function median(samples) {
  const ordered = [...samples].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 === 0 ? (ordered[middle - 1] + ordered[middle]) / 2 : ordered[middle];
}

function nearestRankP95(samples) {
  const ordered = [...samples].sort((left, right) => left - right);
  return ordered[Math.max(0, Math.ceil(0.95 * ordered.length) - 1)];
}

function measurement(samples, unit, target = null) {
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

function fixtureSampleHash(profile) {
  const output = execFileSync(
    "python",
    [join(ROOT, "scripts", "generate_museum_04_scale_fixture.py"), "--profile", profile],
    { cwd: ROOT, encoding: "utf8", windowsHide: true },
  );
  const hash = JSON.parse(output).sample_hash;
  assert(/^sha256:[0-9a-f]{64}$/.test(hash), `${profile}: deterministic generator did not return a sample hash`);
  return hash;
}

function commonProfile(profile, sampleCount) {
  return {
    profile,
    ...PROFILE_COUNTS[profile],
    fixture_sample_hash: fixtureSampleHash(profile),
    synthetic: true,
    shipped: false,
    full_initial_render: false,
    visible_caps: VISIBLE_CAPS,
    governance_fields_preserved: GOVERNANCE_FIELDS,
    sample_count: sampleCount,
  };
}

function sha256File(relativePath) {
  return `sha256:${createHash("sha256").update(readFileSync(resolve(ROOT, relativePath))).digest("hex")}`;
}

function implementationInputHash() {
  const digest = createHash("sha256");
  for (const relativePath of SCALE_IMPLEMENTATION_INPUT_FILES) {
    digest.update(relativePath, "utf8");
    digest.update("\0");
    digest.update(readFileSync(resolve(ROOT, relativePath)));
    digest.update("\0");
  }
  return `sha256:${digest.digest("hex")}`;
}

function aggregateProfiles(samplesByProfile) {
  const one = samplesByProfile["1k"];
  const ten = samplesByProfile["10k"];
  const fifty = samplesByProfile["50k"];
  assert(
    fifty.every((sample) => sample.model_checksum === fifty[0].model_checksum),
    "50k: deterministic model checksum drifted between samples",
  );
  return [
    {
      ...commonProfile("1k", one.length),
      actual_renderer: true,
      renderer: "sigma@3.0.3",
      device_class: "mobile",
      rendering_mode: "capped_progressive",
      visible_rendered: { vertices: 150, edges: 600 },
      no_crash: true,
      interactions_pass: true,
      metrics: {
        first_interactive_ms: measurement(
          one.map((sample) => sample.navigation_first_interactive_ms),
          "ms",
          { statistic: "median", operator: "lte", value: 5_000 },
        ),
        interaction_ms: measurement(one.map((sample) => sample.interaction_ms), "ms"),
      },
      supplemental_metrics: {
        renderer_ready_ms: measurement(one.map((sample) => sample.renderer_ready_ms), "ms"),
        node_selection_ms: measurement(one.map((sample) => sample.node_selection_ms), "ms"),
        filter_ms: measurement(one.map((sample) => sample.filter_ms), "ms"),
        fps: measurement(one.map((sample) => sample.fps), "fps"),
        js_heap_mb: measurement(one.map((sample) => sample.js_heap_mb), "MB"),
      },
    },
    {
      ...commonProfile("10k", ten.length),
      actual_full_renderer: false,
      full_render_request_allowed: false,
      partitioned_index: true,
      search_ready: true,
      local_neighborhood_rendered: true,
      strategy: "partition_search_then_render_capped_neighborhood",
      visible_rendered: { vertices: 150, edges: 600 },
      metrics: {
        model_build_ms: measurement(ten.map((sample) => sample.model_build_ms), "ms"),
        index_build_ms: measurement(ten.map((sample) => sample.index_build_ms), "ms"),
        filtered_render_ms: measurement(ten.map((sample) => sample.filtered_render_ms), "ms"),
        js_heap_mb: measurement(ten.map((sample) => sample.js_heap_mb), "MB"),
      },
    },
    {
      ...commonProfile("50k", fifty.length),
      actual_full_webgl_render: false,
      rendered_300k_edges: false,
      full_render_request_allowed: false,
      safe_fallback: true,
      no_freeze: true,
      no_blank_page: true,
      mobile_full_render_request: "refused",
      strategy: "refuse_full_render_use_partition_or_list",
      model_execution: "bounded_typed_array_model_and_chunk_plan",
      model_facts: {
        constructed_vertices: 50_000,
        constructed_edges: 300_000,
        storage_bytes: FIFTY_K_MODEL_STORAGE_BYTES,
        checksum: fifty[0].model_checksum,
      },
      chunk_plan: {
        vertex_chunks: 334,
        edge_chunks: 500,
        planned_vertices: 50_000,
        planned_edges: 300_000,
        max_vertices_per_chunk: 150,
        max_edges_per_chunk: 600,
      },
      work_slice_limit_ms: 50,
      fallback_visible_during_work: true,
      assertion_basis: {
        safe_fallback: "executed_exact_model_and_bounded_plan_without_webgl",
        no_freeze: "each_model_work_slice_at_or_below_50ms_with_frame_yields",
        no_blank_page: "fallback_visible_before_during_and_after_model_work",
      },
      metrics: {
        model_build_ms: measurement(fifty.map((sample) => sample.model_build_ms), "ms"),
        chunk_plan_ms: measurement(fifty.map((sample) => sample.chunk_plan_ms), "ms"),
        max_work_slice_ms: measurement(
          fifty.map((sample) => sample.max_work_slice_ms),
          "ms",
          { statistic: "p95", operator: "lte", value: 50 },
        ),
        fallback_paint_ms: measurement(fifty.map((sample) => sample.fallback_paint_ms), "ms"),
        yield_count: measurement(fifty.map((sample) => sample.yield_count), "count"),
        js_heap_mb: measurement(fifty.map((sample) => sample.js_heap_mb), "MB"),
      },
    },
  ];
}

function gitMetadata() {
  const commitSha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8", windowsHide: true }).trim();
  const status = execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8", windowsHide: true });
  assert(/^[0-9a-f]{40}$/.test(commitSha), "git rev-parse did not return a full commit SHA");
  return { commitSha, dirty: status.trim().length > 0 };
}

function buildEvidence(samplesByProfile, browserVersion) {
  const git = gitMetadata();
  const playwrightVersion = require("@playwright/test/package.json").version;
  return {
    schema_version: "1.0.0",
    benchmark_id: "museum-04-synthetic-scale",
    evidence_class: "controlled_lab_not_rum",
    real_user_metric: false,
    real_device_status: "not_available",
    real_device_note: "No physical approximately 4 GB Android device was exposed to this runtime.",
    captured_at: new Date().toISOString(),
    environment: {
      host_os: `${platform()} ${release()}`,
      cpu: cpus()[0]?.model || "CPU model not exposed",
      memory_gb: Number((totalmem() / (1024 ** 3)).toFixed(2)),
      browser: "Chromium",
      browser_version: browserVersion,
      node_version: process.version,
      playwright_version: playwrightVersion,
      runner: "scripts/run-museum-04-scale-lab.mjs",
      measurement_method: "Playwright Chromium; fresh context and disabled cache per sample; navigation start to the rendered interactive-ready boundary; post-ready interaction and FPS QA excluded from first-interactive timing",
      commit_sha: git.commitSha,
      source_worktree_dirty: git.dirty,
      implementation_input_files: SCALE_IMPLEMENTATION_INPUT_FILES,
      implementation_input_hash: implementationInputHash(),
    },
    lab_configuration: {
      viewport: VIEWPORT,
      cpu_throttle_rate: CPU_THROTTLE_RATE,
      network_profile: FAST_4G.name,
      network: {
        latency_ms: FAST_4G.latencyMs,
        download_bits_per_second: FAST_4G.downloadBitsPerSecond,
        upload_bits_per_second: FAST_4G.uploadBitsPerSecond,
      },
      cold_browser_context_per_sample: true,
      synthetic_data_generated_in_browser: true,
    },
    release_performance_contract: {
      path: RELEASE_PERFORMANCE_CONTRACT_PATH,
      sha256: sha256File(RELEASE_PERFORMANCE_CONTRACT_PATH),
    },
    profiles: aggregateProfiles(samplesByProfile),
    overall_status: "pass",
  };
}

function validateWithPython(evidence) {
  const code = [
    "import json, sys",
    "from scripts.validate_museum_04_performance_evidence import validate_scale",
    "errors = validate_scale(json.load(sys.stdin))",
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
    throw new Error(`assembled scale evidence failed the Python contract: ${(result.stdout || result.stderr).trim()}`);
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
    let baseUrl;
    if (options.url) {
      baseUrl = normalizeLocalUrl(options.url);
      await waitForServer(baseUrl, null, { value: "" });
    } else {
      server = await startHarnessServer(options.port);
      baseUrl = server.url;
    }
    console.error(`[museum-04-scale-lab] harness=${baseUrl} samples=${options.samples}`);
    browser = await chromium.launch({
      headless: true,
      args: ["--enable-precise-memory-info"],
    });
    const browserVersion = browser.version();
    const samplesByProfile = { "1k": [], "10k": [], "50k": [] };
    for (const profile of Object.keys(PROFILE_COUNTS)) {
      for (let sampleIndex = 0; sampleIndex < options.samples; sampleIndex += 1) {
        console.error(`[museum-04-scale-lab] profile=${profile} cold-sample=${sampleIndex + 1}/${options.samples}`);
        samplesByProfile[profile].push(await sampleProfile(browser, baseUrl, profile, sampleIndex));
      }
    }
    const evidence = buildEvidence(samplesByProfile, browserVersion);
    validateWithPython(evidence);
    if (options.output) {
      writeEvidence(options.output, evidence);
      console.error(`[museum-04-scale-lab] wrote=${options.output}`);
    } else {
      process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`);
    }
    return evidence;
  } finally {
    await browser?.close();
    await stopHarnessServer(server?.child);
  }
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`[museum-04-scale-lab] ${error.message}`);
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
    console.error(`[museum-04-scale-lab] FAIL ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}

export {
  aggregateProfiles,
  buildEvidence,
  implementationInputHash,
  measurement,
  nearestRankP95,
  normalizeLocalUrl,
  parseArgs,
  run,
  verifyRawResult,
};
