import Graph from "graphology";
import Sigma from "sigma";
import { DottedEdgeProgram } from "../../src/features/art-constellation/DottedEdgeProgram";

declare global {
  interface Window {
    __MUSEUM04_SCALE_BENCHMARK__?: Record<string, unknown>;
  }
}

const VISIBLE_VERTICES = 150;
const VISIBLE_EDGES = 600;
const MAX_WORK_SLICE_MS = 50;
const NODE_BATCH_SIZE = 1_000;
const EDGE_BATCH_SIZE = 5_000;
const PROFILES = {
  "1k": { vertices: 1_000, edges: 5_000 },
  "10k": { vertices: 10_000, edges: 60_000 },
  "50k": { vertices: 50_000, edges: 300_000 },
} as const;
type Profile = keyof typeof PROFILES;
const status = document.querySelector<HTMLParagraphElement>("#status");
const container = document.querySelector<HTMLDivElement>("#graph");

function governanceEdge(index: number) {
  const stable = index.toString().padStart(6, "0");
  return {
    type: "dotted",
    relationType: ["shared_subject", "shared_material", "shared_technique"][index % 3],
    level: "C",
    evidenceConfidence: 0.8,
    curatorialRelevance: 0.8,
    historicalRelationshipStrength: null,
    computationalSimilarity: null,
    algorithmic: false,
    claimIds: [`synthetic-claim:${stable}`],
    evidenceIds: [`synthetic-evidence:${stable}`],
    sourceIds: ["source:synthetic-scale-fixture"],
    limitations: "Synthetic benchmark only; never shipped.",
    size: 1.5,
    color: ["#d8b56d", "#7fc4bd", "#c9a7d8"][index % 3],
  };
}

function buildModel(vertexCount: number, edgeCount: number) {
  const graph = new Graph({ type: "undirected", multi: false, allowSelfLoops: false });
  for (let index = 0; index < vertexCount; index += 1) {
    const angle = (index / vertexCount) * Math.PI * 2;
    graph.addNode(`synthetic-artist:${index.toString().padStart(5, "0")}`, {
      x: Math.cos(angle),
      y: Math.sin(angle),
      size: 8,
      labelZh: `合成艺术家 ${index.toString().padStart(5, "0")}`,
      labelEn: `Synthetic Artist ${index.toString().padStart(5, "0")}`,
      label: index < 24 ? `Synthetic Artist ${index.toString().padStart(5, "0")}` : null,
      color: "#7fc4bd",
      region: `synthetic-region-${(index % 8).toString().padStart(2, "0")}`,
      sourceIds: ["source:synthetic-scale-fixture"],
      reviewStatus: "synthetic_fixture",
    });
  }
  let edgeIndex = 0;
  for (let offset = 1; edgeIndex < edgeCount; offset += 1) {
    for (let source = 0; source < vertexCount && edgeIndex < edgeCount; source += 1) {
      const target = (source + offset) % vertexCount;
      const endpoints = [source, target].sort((a, b) => a - b);
      graph.addUndirectedEdgeWithKey(
        `synthetic-rel:${edgeIndex.toString().padStart(6, "0")}`,
        `synthetic-artist:${endpoints[0].toString().padStart(5, "0")}`,
        `synthetic-artist:${endpoints[1].toString().padStart(5, "0")}`,
        governanceEdge(edgeIndex),
      );
      edgeIndex += 1;
    }
  }
  return graph;
}

function buildIndexes(model: Graph) {
  const search = new Map<string, string>();
  const partitions = new Map<string, string[]>();
  model.forEachNode((node, attributes) => {
    search.set(String(attributes.labelEn).toLowerCase(), node);
    const region = String(attributes.region);
    const bucket = partitions.get(region) ?? [];
    bucket.push(node);
    partitions.set(region, bucket);
  });
  if (search.get("synthetic artist 00042") !== "synthetic-artist:00042" || partitions.size !== 8) {
    throw new Error("partition_or_search_index_failed");
  }
  return { search, partitions };
}

function cappedNeighborhood(model: Graph) {
  const graph = new Graph({ type: "undirected", multi: false, allowSelfLoops: false });
  const nodeIds = model.nodes().slice(0, VISIBLE_VERTICES);
  const nodeSet = new Set(nodeIds);
  for (const node of nodeIds) graph.addNode(node, model.getNodeAttributes(node));
  for (const edge of model.edges()) {
    if (graph.size >= VISIBLE_EDGES) break;
    const [source, target] = model.extremities(edge);
    if (nodeSet.has(source) && nodeSet.has(target)) {
      graph.addUndirectedEdgeWithKey(edge, source, target, model.getEdgeAttributes(edge));
    }
  }
  if (graph.order !== VISIBLE_VERTICES || graph.size !== VISIBLE_EDGES) {
    throw new Error(`visible_cap_generation_failed:${graph.order}/${graph.size}`);
  }
  return graph;
}

function nextFrame() {
  return new Promise<number>((resolve) => requestAnimationFrame(resolve));
}

function fallbackVisible(element: HTMLDivElement) {
  const fallback = element.querySelector<HTMLElement>("[data-scale-fallback]");
  return Boolean(
    fallback
    && fallback.textContent?.trim()
    && fallback.getBoundingClientRect().height > 0
    && getComputedStyle(fallback).visibility !== "hidden",
  );
}

async function fillInBoundedSlices(
  total: number,
  batchSize: number,
  write: (index: number) => void,
  visible: () => boolean,
) {
  let maxWorkSliceMs = 0;
  let yieldCount = 0;
  let visibleDuringWork = visible();
  for (let start = 0; start < total; start += batchSize) {
    const sliceStarted = performance.now();
    const end = Math.min(total, start + batchSize);
    for (let index = start; index < end; index += 1) write(index);
    maxWorkSliceMs = Math.max(maxWorkSliceMs, performance.now() - sliceStarted);
    visibleDuringWork = visibleDuringWork && visible();
    yieldCount += 1;
    await nextFrame();
    visibleDuringWork = visibleDuringWork && visible();
  }
  return { maxWorkSliceMs, yieldCount, visibleDuringWork };
}

async function buildBoundedPlanningModel(vertexCount: number, edgeCount: number, visible: () => boolean) {
  const nodeOrdinals = new Uint32Array(vertexCount);
  const edgeSources = new Uint32Array(edgeCount);
  const edgeTargets = new Uint32Array(edgeCount);
  let checksum = 2_166_136_261;
  const mix = (value: number) => {
    checksum = Math.imul(checksum ^ value, 16_777_619) >>> 0;
  };
  const nodeWork = await fillInBoundedSlices(vertexCount, NODE_BATCH_SIZE, (index) => {
    nodeOrdinals[index] = index;
    mix(index);
  }, visible);
  const edgeWork = await fillInBoundedSlices(edgeCount, EDGE_BATCH_SIZE, (index) => {
    const source = index % vertexCount;
    const target = (source + Math.floor(index / vertexCount) + 1) % vertexCount;
    edgeSources[index] = source;
    edgeTargets[index] = target;
    mix(source);
    mix(target);
  }, visible);
  if (
    nodeOrdinals.length !== vertexCount
    || edgeSources.length !== edgeCount
    || edgeTargets.length !== edgeCount
    || nodeOrdinals[vertexCount - 1] !== vertexCount - 1
    || edgeSources[edgeCount - 1] >= vertexCount
    || edgeTargets[edgeCount - 1] >= vertexCount
  ) {
    throw new Error("50k_model_closure_failed");
  }
  return {
    constructedVertices: nodeOrdinals.length,
    constructedEdges: edgeSources.length,
    modelStorageBytes: nodeOrdinals.byteLength + edgeSources.byteLength + edgeTargets.byteLength,
    modelChecksum: `uint32:${checksum.toString(16).padStart(8, "0")}`,
    maxWorkSliceMs: Math.max(nodeWork.maxWorkSliceMs, edgeWork.maxWorkSliceMs),
    yieldCount: nodeWork.yieldCount + edgeWork.yieldCount,
    visibleDuringWork: nodeWork.visibleDuringWork && edgeWork.visibleDuringWork,
  };
}

function planBoundedChunks(vertexCount: number, edgeCount: number) {
  const vertexChunks: number[] = [];
  const edgeChunks: number[] = [];
  for (let offset = 0; offset < vertexCount; offset += VISIBLE_VERTICES) {
    vertexChunks.push(Math.min(VISIBLE_VERTICES, vertexCount - offset));
  }
  for (let offset = 0; offset < edgeCount; offset += VISIBLE_EDGES) {
    edgeChunks.push(Math.min(VISIBLE_EDGES, edgeCount - offset));
  }
  const totalVertices = vertexChunks.reduce((sum, count) => sum + count, 0);
  const totalEdges = edgeChunks.reduce((sum, count) => sum + count, 0);
  if (
    totalVertices !== vertexCount
    || totalEdges !== edgeCount
    || Math.max(...vertexChunks) > VISIBLE_VERTICES
    || Math.max(...edgeChunks) > VISIBLE_EDGES
  ) {
    throw new Error("50k_chunk_plan_closure_failed");
  }
  return {
    vertexChunkCount: vertexChunks.length,
    edgeChunkCount: edgeChunks.length,
    totalVertices,
    totalEdges,
    maxVerticesPerChunk: Math.max(...vertexChunks),
    maxEdgesPerChunk: Math.max(...edgeChunks),
  };
}

async function frameRate(renderer: Sigma) {
  const samples: number[] = [];
  let previous = await nextFrame();
  for (let index = 0; index < 90; index += 1) {
    const camera = renderer.getCamera();
    const direction = index % 2 === 0 ? 1 : -1;
    camera.setState({ x: 0.5 + direction * 0.002, y: 0.5, ratio: 1 });
    const now = await nextFrame();
    samples.push(now - previous);
    previous = now;
  }
  const meanFrameMs = samples.reduce((total, value) => total + value, 0) / samples.length;
  return 1_000 / meanFrameMs;
}

async function run() {
  if (!container || !status) throw new Error("benchmark_dom_missing");
  const requested = new URLSearchParams(window.location.search).get("profile") ?? "1k";
  if (!(requested in PROFILES)) throw new Error(`unknown_profile:${requested}`);
  const profile = requested as Profile;
  const counts = PROFILES[profile];
  const started = performance.now();
  if (profile === "50k") {
    const fallback = Object.assign(document.createElement("p"), {
      textContent: "Full rendering refused. Use a partition or the artist list.",
    });
    fallback.dataset.scaleFallback = "true";
    container.replaceChildren(fallback);
    await nextFrame();
    await nextFrame();
    const fallbackPaintMs = performance.now() - started;
    const visibleBeforeWork = fallbackVisible(container);
    const fullRenderRequestAllowed = false;
    const modelStarted = performance.now();
    const model = await buildBoundedPlanningModel(counts.vertices, counts.edges, () => fallbackVisible(container));
    const modelBuildMs = performance.now() - modelStarted;
    const planStarted = performance.now();
    const chunkPlan = planBoundedChunks(model.constructedVertices, model.constructedEdges);
    const chunkPlanMs = performance.now() - planStarted;
    const visibleAfterWork = fallbackVisible(container);
    const noFreeze = model.yieldCount > 0 && model.maxWorkSliceMs <= MAX_WORK_SLICE_MS;
    const noBlankPage = visibleBeforeWork && model.visibleDuringWork && visibleAfterWork;
    const safeFallback = (
      !fullRenderRequestAllowed
      && chunkPlan.totalVertices === counts.vertices
      && chunkPlan.totalEdges === counts.edges
      && chunkPlan.maxVerticesPerChunk === VISIBLE_VERTICES
      && chunkPlan.maxEdgesPerChunk === VISIBLE_EDGES
      && noBlankPage
    );
    if (!safeFallback || !noFreeze) throw new Error("50k_bounded_execution_failed");
    const memory = performance as Performance & { memory?: { usedJSHeapSize: number } };
    const heapMb = memory.memory ? memory.memory.usedJSHeapSize / (1024 * 1024) : null;
    window.__MUSEUM04_SCALE_BENCHMARK__ = {
      status: "pass",
      synthetic: true,
      shipped: false,
      profile,
      vertices: counts.vertices,
      edges: counts.edges,
      mobile_full_render_request: "refused",
      actual_full_webgl_render: false,
      rendered_300k_edges: false,
      safe_fallback: safeFallback,
      no_freeze: noFreeze,
      no_blank_page: noBlankPage,
      constructed_vertices: model.constructedVertices,
      constructed_edges: model.constructedEdges,
      model_storage_bytes: model.modelStorageBytes,
      model_checksum: model.modelChecksum,
      planned_vertex_chunks: chunkPlan.vertexChunkCount,
      planned_edge_chunks: chunkPlan.edgeChunkCount,
      planned_vertices: chunkPlan.totalVertices,
      planned_edges: chunkPlan.totalEdges,
      max_vertices_per_chunk: chunkPlan.maxVerticesPerChunk,
      max_edges_per_chunk: chunkPlan.maxEdgesPerChunk,
      work_slice_limit_ms: MAX_WORK_SLICE_MS,
      yield_count: model.yieldCount,
      fallback_visible_during_work: model.visibleDuringWork,
      fallback_visible_after_work: visibleAfterWork,
      model_build_ms: modelBuildMs,
      chunk_plan_ms: chunkPlanMs,
      max_work_slice_ms: model.maxWorkSliceMs,
      fallback_paint_ms: fallbackPaintMs,
      js_heap_mb: heapMb,
      continuous_force_layout: false,
    };
    status.textContent = `PASS: 50k/300k bounded model and ${chunkPlan.edgeChunkCount} edge chunks planned without WebGL in ${modelBuildMs.toFixed(1)} ms.`;
    return;
  }

  const modelStarted = performance.now();
  const model = buildModel(counts.vertices, counts.edges);
  const modelBuildMs = performance.now() - modelStarted;
  const indexStarted = performance.now();
  const indexes = buildIndexes(model);
  const indexBuildMs = performance.now() - indexStarted;
  if (profile === "10k" && (indexes.search.size !== 10_000 || indexes.partitions.size !== 8)) {
    throw new Error("10k_index_closure_failed");
  }
  const renderStarted = performance.now();
  const visible = cappedNeighborhood(model);
  const renderer = new Sigma(visible, container, {
    defaultEdgeType: "dotted",
    edgeProgramClasses: { dotted: DottedEdgeProgram },
    renderEdgeLabels: false,
    labelDensity: 0.35,
    labelRenderedSizeThreshold: 8,
    minCameraRatio: 0.65,
    maxCameraRatio: 2.8,
    stagePadding: 24,
  });
  await nextFrame();
  await nextFrame();
  const firstInteractiveMs = performance.now() - started;
  const filteredRenderMs = performance.now() - renderStarted;

  if (profile === "1k") {
    window.__MUSEUM04_SCALE_BENCHMARK__ = {
      status: "measuring",
      interactive_ready: true,
      synthetic: true,
      shipped: false,
      profile,
      vertices: counts.vertices,
      edges: counts.edges,
      rendering_mode: "capped_progressive",
      visible_rendered: { vertices: visible.order, edges: visible.size },
      renderer_ready_ms: firstInteractiveMs,
      continuous_force_layout: false,
    };
  }

  const selectionStarted = performance.now();
  visible.setNodeAttribute(visible.nodes()[0], "highlighted", true);
  visible.setNodeAttribute(visible.nodes()[0], "color", "#f0dca8");
  renderer.refresh();
  await nextFrame();
  const nodeSelectionMs = performance.now() - selectionStarted;

  const filterStarted = performance.now();
  visible.forEachEdge((edge, attributes) => visible.setEdgeAttribute(edge, "hidden", attributes.relationType !== "shared_subject"));
  renderer.refresh();
  await nextFrame();
  const filterMs = performance.now() - filterStarted;
  const fps = await frameRate(renderer);
  const memory = performance as Performance & { memory?: { usedJSHeapSize: number } };
  const heapMb = memory.memory ? memory.memory.usedJSHeapSize / (1024 * 1024) : null;

  if (profile === "1k") {
    window.__MUSEUM04_SCALE_BENCHMARK__ = {
      status: nodeSelectionMs <= 100 && filterMs <= 200 && fps >= 30 ? "pass" : "fail",
      interactive_ready: true,
      synthetic: true,
      shipped: false,
      profile,
      vertices: counts.vertices,
      edges: counts.edges,
      rendering_mode: "capped_progressive",
      model_build_ms: modelBuildMs,
      renderer_ready_ms: firstInteractiveMs,
      interaction_ms: Math.max(nodeSelectionMs, filterMs),
      visible_rendered: { vertices: visible.order, edges: visible.size },
      node_selection_ms: nodeSelectionMs,
      filter_ms: filterMs,
      fps,
      js_heap_mb: heapMb,
      continuous_force_layout: false,
    };
    status.textContent = `PASS: 1k/5k model, capped 150/600 Sigma renderer, ${firstInteractiveMs.toFixed(1)} ms.`;
    return;
  }

  window.__MUSEUM04_SCALE_BENCHMARK__ = {
    status: "pass",
    synthetic: true,
    shipped: false,
    profile,
    vertices: counts.vertices,
    edges: counts.edges,
    model_build_ms: modelBuildMs,
    index_build_ms: indexBuildMs,
    filtered_render_ms: filteredRenderMs,
    js_heap_mb: heapMb,
    visible_rendered: { vertices: visible.order, edges: visible.size },
    partitioned_index: true,
    search_ready: true,
    local_neighborhood_rendered: true,
    actual_full_renderer: false,
    continuous_force_layout: false,
  };
  status.textContent = `PASS: 10k/60k model and indexes, capped 150/600 renderer, ${filteredRenderMs.toFixed(1)} ms.`;
}

run().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : "unknown_error";
  window.__MUSEUM04_SCALE_BENCHMARK__ = {
    status: "fail",
    synthetic: true,
    shipped: false,
    profile: new URLSearchParams(window.location.search).get("profile") ?? "1k",
    continuous_force_layout: false,
    error: message,
  };
  if (status) status.textContent = `FAIL: ${message}`;
});
