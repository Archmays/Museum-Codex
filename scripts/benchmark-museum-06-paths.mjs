import { performance } from "node:perf_hooks";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { findPathways, defaultPathQuery, PATH_ALGORITHM_VERSION } from "../src/features/art-paths/path-algorithm.ts";

const ROOT = resolve(import.meta.dirname, "..");
const OUTPUT = resolve(ROOT, "docs/qa/museum-06/path-benchmark.json");
const RELEASE = resolve(ROOT, "public/releases/art-pathways-1.2.0");
const SEED = "museum-06-path-benchmark-seed-20260716";

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

function percentile(values, percentileValue) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.ceil(percentileValue * sorted.length) - 1)];
}

function artist(index) {
  return {
    id: `artist:synthetic-${index}`,
    labels: { "zh-Hans": `合成节点 ${index}`, en: `Synthetic ${index}` },
    aliases: [],
    periods: ["Synthetic period"],
    regions: ["Synthetic region"],
    life_span: { birth_year: 1800 + (index % 100), death_year: 1880 + (index % 100) },
    public_display: true,
    review_status: "publishable",
    lifecycle_status: "publishable",
    withdrawn: false,
  };
}

function relationship(index, source, target) {
  return {
    id: `art-rel:synthetic-${index}`,
    release_id: "release:art-pathways-1.2.0",
    source_artist_id: `artist:synthetic-${source}`,
    target_artist_id: `artist:synthetic-${target}`,
    type: ["shared_material", "shared_subject", "shared_technique"][index % 3],
    level: "C",
    directed: false,
    is_algorithmic: false,
    computational_similarity: null,
    public_display: true,
    review_status: "publishable",
    lifecycle_status: "publishable",
    withdrawn: false,
    deprecated: false,
    rights_visibility: "public",
    periods: ["Synthetic period"],
    regions: ["Synthetic region"],
    context_ids: [`subject:synthetic-${index % 17}`],
    claim_ids: [`claim:synthetic-${index}`],
    evidence_ids: [`evidence:synthetic-${index}`],
    source_ids: ["source:synthetic"],
    supporting_artwork_ids: [`artwork:synthetic-${index}`],
    evidence_confidence: 0.8 + (index % 20) / 100,
    why_connected: { "zh-Hans": "稳定 seed 合成边。", en: "Stable-seed synthetic edge." },
    does_not_prove: { "zh-Hans": "不证明影响。", en: "Does not prove influence." },
    rights_attribution: ["Synthetic benchmark; not public release data"],
  };
}

function syntheticGraph(vertexCount, edgeCount) {
  const artists = Array.from({ length: vertexCount }, (_, index) => artist(index));
  const relationships = [];
  for (let index = 0; index < edgeCount; index += 1) {
    const source = index % vertexCount;
    const round = Math.floor(index / vertexCount);
    const offset = 1 + ((round * 97 + (index % 11) * 13) % Math.max(2, vertexCount - 1));
    const target = (source + offset) % vertexCount;
    relationships.push(relationship(index, source, target === source ? (target + 1) % vertexCount : target));
  }
  return {
    schema_version: "1.0.0",
    id: `path-graph-input:synthetic-${vertexCount}-${edgeCount}`,
    entity_type: "art_path_graph_input",
    release_id: "release:art-pathways-1.2.0",
    input_release_id: "release:art-gallery-interactions-1.1.0",
    input_release_hash: `sha256:${"0".repeat(64)}`,
    graph_hash: `sha256:${"1".repeat(64)}`,
    artists,
    relationships,
    counts: { artists: vertexCount, relationships: edgeCount, levels: { A: 0, B: 0, C: edgeCount }, directed: 0, algorithmic: 0 },
  };
}

function timedQuery(graph, repetitions) {
  const query = defaultPathQuery(graph.artists[0].id, graph.artists[1].id, "comparison");
  const runs = [];
  let finalResult;
  for (let index = 0; index < repetitions; index += 1) {
    const started = performance.now();
    finalResult = findPathways(graph, query);
    runs.push(performance.now() - started);
  }
  return {
    runs_ms: runs.map((value) => Number(value.toFixed(3))),
    median_ms: Number(median(runs).toFixed(3)),
    status: finalResult.status,
    expansions_used: finalResult.expansions_used,
    path_count: finalResult.paths.length,
  };
}

function main() {
  const current = readJson(resolve(RELEASE, "path-graph-input.json"));
  const index = readJson(resolve(RELEASE, "path-index.json"));
  const currentRuns = [];
  const currentQuery = defaultPathQuery(current.artists[0].id, current.artists[1].id, "comparison");
  for (let indexRun = 0; indexRun < 120; indexRun += 1) {
    const started = performance.now();
    findPathways(current, currentQuery);
    currentRuns.push(performance.now() - started);
  }
  const buildStarted = performance.now();
  let computedPaths = 0;
  for (const pair of index.pairs) {
    for (const mode of ["historical", "context", "comparison"]) {
      computedPaths += findPathways(current, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, mode)).paths.length;
    }
  }
  const defaultBuildMs = performance.now() - buildStarted;
  const oneK = timedQuery(syntheticGraph(1_000, 5_000), 5);
  const tenK = timedQuery(syntheticGraph(10_000, 60_000), 3);
  const fiftyK = timedQuery(syntheticGraph(50_000, 300_000), 1);
  const metrics = {
    phase_id: "MUSEUM-06",
    algorithm_version: PATH_ALGORITHM_VERSION,
    stable_seed: SEED,
    synthetic_fixtures_public_release: false,
    current_12_node_query: {
      runs: currentRuns.length,
      p95_ms: Number(percentile(currentRuns, 0.95).toFixed(3)),
      median_ms: Number(median(currentRuns).toFixed(3)),
    },
    default_66_pairs: { build_ms: Number(defaultBuildMs.toFixed(3)), precomputed_path_count: computedPaths },
    synthetic: { "1k_v_5k_e": oneK, "10k_v_60k_e": tenK, "50k_v_300k_e": fiftyK },
  };
  const failures = [];
  if (metrics.current_12_node_query.p95_ms > 50) failures.push(`current p95 ${metrics.current_12_node_query.p95_ms} ms > 50 ms`);
  if (metrics.default_66_pairs.build_ms > 1_000) failures.push(`66-pair build ${metrics.default_66_pairs.build_ms} ms > 1000 ms`);
  if (oneK.median_ms > 200) failures.push(`1k/5k median ${oneK.median_ms} ms > 200 ms`);
  if (tenK.median_ms > 500) failures.push(`10k/60k median ${tenK.median_ms} ms > 500 ms`);
  if (fiftyK.expansions_used > 10_000 || !["ready", "search_budget_reached"].includes(fiftyK.status)) {
    failures.push(`50k/300k must return ready or search_budget_reached within 10000 expansions`);
  }
  const output = { ok: failures.length === 0, failures, metrics };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(output, null, 2)}\n`);
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
