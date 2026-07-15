import assert from "node:assert/strict";
import test from "node:test";

import {
  CURRENT_PROFILES,
  METRIC_UNITS,
  aggregateRuns,
  buildEvidence,
  classifyResourceUrl,
  extractBudgetReport,
  isFailingConsoleType,
  isExpectedBrowserDiagnostic,
  measurement,
  nearestRankP95,
  normalizeTargetUrl,
  parseArgs,
  routeUrl,
  validateWithPython,
  verifyRawSample,
} from "../scripts/run-museum-04-current-lab.mjs";

test("resource classification catches initial images and deferred governance DTOs", () => {
  assert.equal(classifyResourceUrl("https://example.test/releases/x/assets/work/320w.webp?hash=1"), "image");
  assert.equal(classifyResourceUrl("https://example.test/releases/x/media-index.json"), "deferred_data");
  assert.equal(classifyResourceUrl("https://example.test/releases/x/withdrawal-mapping.json#v1"), "deferred_data");
  assert.equal(classifyResourceUrl("https://example.test/releases/x/artists.json"), null);
});

test("browser console warnings and errors both fail the controlled lab", () => {
  assert.equal(isFailingConsoleType("warning"), true);
  assert.equal(isFailingConsoleType("error"), true);
  assert.equal(isFailingConsoleType("log"), false);
  assert.equal(isExpectedBrowserDiagnostic("warning", "application warning"), false);
  assert.equal(
    isExpectedBrowserDiagnostic("warning", "[.WebGL-0x123]GL Driver Message (OpenGL, Performance, GL_CLOSE_PATH_NV, High): GPU stall due to ReadPixels"),
    true,
  );
  assert.equal(
    isExpectedBrowserDiagnostic("error", "[.WebGL-0x123]GL Driver Message (OpenGL, Performance, GL_CLOSE_PATH_NV, High): GPU stall due to ReadPixels"),
    false,
  );
});

test("nearest-rank p95 and hard-target measurement match the Python contract", () => {
  assert.equal(nearestRankP95([4, 1, 3, 2, 5]), 5);
  assert.deepEqual(measurement([100, 80, 90], "ms", {
    statistic: "p95",
    operator: "lte",
    value: 100,
  }), {
    unit: "ms",
    samples: [100, 80, 90],
    median: 90,
    p95: 100,
    target: { statistic: "p95", operator: "lte", value: 100, passed: true },
  });
  assert.throws(
    () => measurement([101, 102, 103], "ms", { statistic: "p95", operator: "lte", value: 100 }),
    /hard target failed/,
  );
});

test("CLI is bounded and targets allow loopback HTTP or live HTTPS only", () => {
  assert.deepEqual(parseArgs(["--samples", "5", "--url", "https://archmays.github.io/Museum-Codex/"]), {
    samples: 5,
    url: "https://archmays.github.io/Museum-Codex/",
    port: null,
    output: null,
    help: false,
  });
  assert.equal(normalizeTargetUrl("http://127.0.0.1:4173/Museum-Codex?x=1#/art"), "http://127.0.0.1:4173/Museum-Codex/");
  assert.equal(normalizeTargetUrl("https://archmays.github.io/Museum-Codex"), "https://archmays.github.io/Museum-Codex/");
  assert.equal(routeUrl("https://archmays.github.io/Museum-Codex/"), "https://archmays.github.io/Museum-Codex/#/art/constellation");
  assert.throws(() => normalizeTargetUrl("http://example.com/Museum-Codex/"), /HTTPS/);
  assert.throws(() => normalizeTargetUrl("https://user:secret@example.com/"), /credentials/);
  assert.throws(() => parseArgs(["--samples", "2"]), /integer from 3 to 20/);
  assert.throws(() => parseArgs(["--url", "http://localhost:4173", "--port", "4174"]), /cannot be combined/);
});

test("deterministic gzip budget stdout is parsed without treating the PASS line as JSON", () => {
  const report = {
    algorithm: "node:zlib gzip level 9; each file compressed independently",
    constellationRoute: { gzipBytes: 123_456 },
    mediaDelivery: {
      artworkRows: 44,
      mediaRecords: 273,
      physicalFiles: 242,
      physicalBytes: 35_907_176,
      initialMediaRequests: 0,
      initialMediaBytes: 0,
    },
    status: "pass",
  };
  assert.deepEqual(
    extractBudgetReport(`${JSON.stringify(report)}\n[museum-04-budget] PASS home and route gates\n`),
    report,
  );
  assert.throws(
    () => extractBudgetReport(JSON.stringify({ ...report, status: "fail" })),
    /did not pass/,
  );
});

function passingSample(profile) {
  const mobile = profile.deviceClass === "mobile";
  return {
    route_load_ms: 200,
    data_load_ms: 100,
    chunk_load_ms: 80,
    first_interactive_ms: mobile ? 1_200 : 900,
    node_selection_ms: 40,
    filter_ms: 60,
    relationship_detail_ms: 70,
    keyboard_focus_ms: 35,
    list_switch_ms: 45,
    fps: 55,
    js_heap_mb: 80,
    cls: 0.02,
    long_tasks_count: 1,
    transferred_bytes: 220_000,
    gzip_bytes: 180_000,
    lcp_ms: 1_000,
    interaction_proxy_ms: 70,
    initial_image_requests: 0,
    initial_image_bytes: 0,
    deferred_image_requests: 1,
    deferred_image_bytes: 16_000,
    initial_deferred_data_requests: 0,
    deferred_data_requests: 3,
  };
}

function samplesByProfile() {
  return Object.fromEntries(CURRENT_PROFILES.map((profile) => [
    profile.id,
    [0.9, 1, 1.1].map((factor) => Object.fromEntries(
      Object.entries(passingSample(profile)).map(([name, value]) => [name, name === "gzip_bytes" ? value : value * factor]),
    )),
  ]));
}

test("raw sample and four-profile aggregation fail closed", () => {
  const sample = passingSample(CURRENT_PROFILES[0]);
  assert.equal(verifyRawSample(sample), sample);
  assert.throws(() => verifyRawSample({ ...sample, lcp_ms: null }), /lcp_ms must be finite/);
  const runs = aggregateRuns(samplesByProfile());
  assert.equal(runs.length, 4);
  assert.deepEqual(runs.map((run) => run.viewport), CURRENT_PROFILES.map((profile) => profile.viewport));
  assert.deepEqual(runs.map((run) => run.initial_experience), CURRENT_PROFILES.map((profile) => profile.initialExperience));
  assert.deepEqual(Object.keys(runs[0].metrics), Object.keys(METRIC_UNITS));
  assert.equal(runs[0].metrics.node_selection_ms.target.passed, true);
  assert.equal(runs[0].metrics.initial_image_requests.target.value, 0);
  assert.equal(runs[0].metrics.initial_image_bytes.target.passed, true);
  assert.equal(runs[0].metrics.initial_deferred_data_requests.target.passed, true);
});

test("assembled evidence validates through the canonical Python contract", () => {
  const budget = {
    algorithm: "node:zlib gzip level 9; each file compressed independently",
    manifest: ".vite/manifest.json",
    homeInitial: { gzipBytes: 90_000 },
    constellationRoute: { gzipBytes: 180_000, initialDataGzipBytes: 8_000 },
    graphSummary: { gzipBytes: 1_500 },
    mediaDelivery: {
      artworkRows: 44,
      mediaRecords: 273,
      physicalFiles: 242,
      physicalBytes: 35_907_176,
      initialMediaRequests: 0,
      initialMediaBytes: 0,
    },
    status: "pass",
  };
  const evidence = buildEvidence(
    samplesByProfile(),
    "test-chromium",
    budget,
    "http://127.0.0.1:4173/Museum-Codex/",
  );
  assert.equal(evidence.real_user_metric, false);
  assert.equal(evidence.real_device_status, "not_available");
  assert.equal(evidence.lab_configuration.analytics_or_telemetry_added, false);
  assert.equal(evidence.lab_configuration.media_delivery.physical_derivative_count, 242);
  assert.equal(evidence.lab_configuration.media_delivery.initial_image_bytes_target, 0);
  assert.ok(evidence.environment.implementation_input_files.includes("src/i18n/translations.ts"));
  assert.doesNotThrow(() => validateWithPython(evidence));
});
