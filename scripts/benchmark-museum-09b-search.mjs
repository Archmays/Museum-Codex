import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { performance } from "node:perf_hooks";

import { normalizeSearchText, searchRecords } from "../src/features/art-search/search-model.ts";

const ROOT = resolve(import.meta.dirname, "..");
const RELEASE = join(ROOT, "public", "releases", "art-expansion-batch-01-1.5.1");
const OUTPUT = join(ROOT, "docs", "qa", "museum-09b-ux-01", "search-performance.json");
const RUNS = 80;

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function percentile(values, ratio) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.max(0, Math.ceil(ordered.length * ratio) - 1)] ?? 0;
}

function loadRecords() {
  const manifest = readJson(join(RELEASE, "search", "manifest.json"));
  const records = manifest.shards.flatMap((reference) => readJson(join(RELEASE, reference.path)).records);
  if (records.length !== manifest.counts.records) throw new Error("search record closure mismatch");
  return { manifest, records };
}

function syntheticRecords(records, count) {
  return Array.from({ length: count }, (_, index) => {
    const source = records[index % records.length];
    const suffix = String(index).padStart(5, "0");
    return {
      ...source,
      id: `search-record:synthetic-m09b-${suffix}`,
      stable_id: `synthetic-m09b:${suffix}`,
      labels: { ...source.labels },
      description: { ...source.description },
      values: source.values.map((value) => ({ ...value })),
      withdrawal_status: index % 211 === 0 ? "withdrawn" : "active",
    };
  });
}

function benchmark(records, queries) {
  const timings = [];
  const digests = [];
  for (let index = 0; index < RUNS + 10; index += 1) {
    const started = performance.now();
    const results = searchRecords(records, queries[index % queries.length], index % 2 ? "en" : "zh-CN");
    const elapsed = performance.now() - started;
    if (index >= 10) {
      timings.push(elapsed);
      digests.push(createHash("sha256").update(JSON.stringify(results.map((item) => [item.record.stable_id, item.matchReason, item.rankTuple]))).digest("hex"));
    }
  }
  return {
    runs: RUNS,
    median_ms: percentile(timings, 0.5),
    p95_ms: percentile(timings, 0.95),
    max_ms: Math.max(...timings),
    deterministic_digest: createHash("sha256").update(digests.join("\n")).digest("hex"),
  };
}

function main() {
  const { manifest, records } = loadRecords();
  const queries = ["Dürer", "丢勒", "portrait", "Amsterdam", "source", "map", normalizeSearchText(records[0].values[0].text).slice(0, 6)];
  const current = benchmark(records, queries);
  const syntheticInput = syntheticRecords(records, 5_000);
  const synthetic = benchmark(syntheticInput, queries);
  const repeat = benchmark(syntheticInput, queries);
  const failures = [];
  if (current.p95_ms > 80) failures.push(`current query p95 ${current.p95_ms.toFixed(3)} ms > 80 ms`);
  if (synthetic.p95_ms > 120) failures.push(`5000-record query p95 ${synthetic.p95_ms.toFixed(3)} ms > 120 ms`);
  if (synthetic.deterministic_digest !== repeat.deterministic_digest) failures.push("deterministic ranking digest mismatch");
  const report = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-09B-UX-01",
    evidence_class: "controlled_node_benchmark",
    environment: `${process.platform}-${process.arch}; Node ${process.version}`,
    normalization: manifest.normalization,
    current_release: { record_count: records.length, limit_p95_ms: 80, ...current },
    synthetic_5000: { record_count: 5_000, fixed_input: true, public_build: false, limit_p95_ms: 120, ...synthetic },
    deterministic_repeat: synthetic.deterministic_digest === repeat.deterministic_digest,
    failures,
    status: failures.length ? "fail" : "pass",
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
