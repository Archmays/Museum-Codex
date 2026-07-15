import assert from "node:assert/strict";
import test from "node:test";

import {
  measurement,
  nearestRankP95,
  normalizeLocalUrl,
  parseArgs,
  verifyRawResult,
} from "../scripts/run-museum-04-scale-lab.mjs";

test("nearest-rank p95 and median measurement match the evidence contract", () => {
  assert.equal(nearestRankP95([4, 1, 3, 2, 5]), 5);
  assert.deepEqual(measurement([100, 80, 90], "ms", {
    statistic: "median",
    operator: "lte",
    value: 100,
  }), {
    unit: "ms",
    samples: [100, 80, 90],
    median: 90,
    p95: 100,
    target: { statistic: "median", operator: "lte", value: 100, passed: true },
  });
  assert.throws(
    () => measurement([101, 102, 103], "ms", { statistic: "p95", operator: "lte", value: 100 }),
    /hard target failed/,
  );
});

test("CLI remains bounded and existing-server URLs must be loopback", () => {
  assert.deepEqual(parseArgs(["--samples", "5", "--url", "http://localhost:4173"]), {
    samples: 5,
    url: "http://localhost:4173",
    port: null,
    output: null,
    help: false,
  });
  assert.equal(normalizeLocalUrl("http://127.0.0.1:4173"), "http://127.0.0.1:4173/");
  assert.throws(() => parseArgs(["--samples", "2"]), /integer from 3 to 20/);
  assert.throws(() => parseArgs(["--url", "http://localhost:4173", "--port", "4174"]), /cannot be combined/);
  assert.throws(() => normalizeLocalUrl("https://example.com"), /localhost or a loopback/);
});

test("raw harness boundaries fail closed", () => {
  const validOneThousand = {
    status: "pass",
    synthetic: true,
    shipped: false,
    profile: "1k",
    vertices: 1_000,
    edges: 5_000,
    interactive_ready: true,
    continuous_force_layout: false,
    rendering_mode: "capped_progressive",
    visible_rendered: { vertices: 150, edges: 600 },
    renderer_ready_ms: 1_000,
    interaction_ms: 80,
    node_selection_ms: 40,
    filter_ms: 80,
    fps: 55,
  };
  assert.doesNotThrow(() => verifyRawResult("1k", validOneThousand));
  assert.doesNotThrow(() => verifyRawResult("1k", {
    ...validOneThousand,
    interaction_ms: 105.1,
    node_selection_ms: 105.1,
    fps: 29.19,
  }));
  assert.throws(
    () => verifyRawResult("1k", { ...validOneThousand, visible_rendered: { vertices: 151, edges: 600 } }),
    /visible cap/,
  );
  assert.throws(
    () => verifyRawResult("1k", { ...validOneThousand, interactive_ready: false }),
    /interactive-ready boundary/,
  );

  const validFiftyThousand = {
    status: "pass",
    synthetic: true,
    shipped: false,
    profile: "50k",
    vertices: 50_000,
    edges: 300_000,
    continuous_force_layout: false,
    mobile_full_render_request: "refused",
    actual_full_webgl_render: false,
    rendered_300k_edges: false,
    safe_fallback: true,
    no_freeze: true,
    no_blank_page: true,
    constructed_vertices: 50_000,
    constructed_edges: 300_000,
    model_storage_bytes: 2_600_000,
    model_checksum: "uint32:0123abcd",
    planned_vertex_chunks: 334,
    planned_edge_chunks: 500,
    planned_vertices: 50_000,
    planned_edges: 300_000,
    max_vertices_per_chunk: 150,
    max_edges_per_chunk: 600,
    work_slice_limit_ms: 50,
    yield_count: 110,
    fallback_visible_during_work: true,
    fallback_visible_after_work: true,
    model_build_ms: 1_500,
    chunk_plan_ms: 0.2,
    max_work_slice_ms: 10,
    fallback_paint_ms: 20,
    js_heap_mb: 80,
  };
  assert.doesNotThrow(() => verifyRawResult("50k", validFiftyThousand));
  assert.throws(
    () => verifyRawResult("50k", { ...validFiftyThousand, mobile_full_render_request: "allowed" }),
    /was not refused/,
  );
  assert.throws(
    () => verifyRawResult("50k", { ...validFiftyThousand, max_work_slice_ms: 51 }),
    /exceeded 50 ms/,
  );
});
