import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { performance } from "node:perf_hooks";

import {
  normalizeSearchText,
  searchRecords,
} from "../src/features/art-search/search-model.ts";

const ROOT = resolve(import.meta.dirname, "..");
const RELEASE = join(ROOT, "public", "releases", "art-v1-candidate-1.4.0");
const OUTPUT = join(ROOT, "docs", "qa", "museum-08", "search-performance.json");
const CURRENT_LIMIT_MS = 80;
const SYNTHETIC_LIMIT_MS = 120;

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function percentile(values, ratio) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.max(0, Math.ceil(ordered.length * ratio) - 1)] ?? 0;
}

function loadCurrentRecords() {
  const manifestPath = join(RELEASE, "search", "manifest.json");
  if (!existsSync(manifestPath)) throw new Error(`missing ${manifestPath}`);
  const manifest = readJson(manifestPath);
  const records = manifest.shards.flatMap((reference) =>
    readJson(join(RELEASE, reference.path)).records
  );
  if (records.length !== manifest.counts.records) {
    throw new Error(`search record closure mismatch: ${records.length}/${manifest.counts.records}`);
  }
  return { manifest, records };
}

function syntheticRecords(records, count = 1_000) {
  return Array.from({ length: count }, (_, index) => {
    const source = records[index % records.length];
    const suffix = String(index).padStart(4, "0");
    return {
      ...source,
      id: `search-record:synthetic-benchmark-${suffix}`,
      stable_id: `synthetic-benchmark:${suffix}`,
      labels: { ...source.labels },
      description: { ...source.description },
      values: source.values.map((value) => ({ ...value })),
      withdrawal_status: index % 97 === 0 ? "withdrawn" : "active",
    };
  });
}

function benchmark(records, queries, runs) {
  const timings = [];
  const digests = [];
  for (let index = 0; index < runs + 10; index += 1) {
    const query = queries[index % queries.length];
    const started = performance.now();
    const results = searchRecords(records, query, index % 2 ? "en" : "zh-CN");
    const elapsed = performance.now() - started;
    if (index >= 10) {
      timings.push(elapsed);
      digests.push(createHash("sha256")
        .update(JSON.stringify(results.map((item) => [item.record.stable_id, item.matchReason, item.rankTuple])))
        .digest("hex"));
    }
  }
  return {
    runs,
    median_ms: percentile(timings, 0.5),
    p95_ms: percentile(timings, 0.95),
    max_ms: Math.max(...timings),
    deterministic_digest: createHash("sha256").update(digests.join("\n")).digest("hex"),
    first_result_time_ms: timings[0] ?? 0,
  };
}

function main() {
  const { manifest, records } = loadCurrentRecords();
  const queries = [
    "Dürer",
    "丢勒",
    "art",
    "map",
    "portrait",
    "日本",
    "Paris",
    "source",
    normalizeSearchText(records[0].values[0].text).slice(0, 6),
  ];
  const current = benchmark(records, queries, 80);
  const synthetic = benchmark(syntheticRecords(records), queries, 80);
  const repeat = benchmark(syntheticRecords(records), queries, 80);
  const failures = [];
  if (current.p95_ms > CURRENT_LIMIT_MS) {
    failures.push(`current query p95 ${current.p95_ms.toFixed(3)} ms > ${CURRENT_LIMIT_MS} ms`);
  }
  if (synthetic.p95_ms > SYNTHETIC_LIMIT_MS) {
    failures.push(`1000-record query p95 ${synthetic.p95_ms.toFixed(3)} ms > ${SYNTHETIC_LIMIT_MS} ms`);
  }
  if (synthetic.deterministic_digest !== repeat.deterministic_digest) {
    failures.push("synthetic ranking digest changed on byte-identical repeat");
  }
  const report = {
    schema_version: "1.0.0",
    phase_id: "MUSEUM-08",
    evidence_class: "controlled_node_benchmark",
    environment: `${process.platform}-${process.arch}; Node ${process.version}`,
    status: failures.length ? "fail" : "pass",
    failures,
    normalization: manifest.normalization,
    current_release: {
      record_count: records.length,
      limit_p95_ms: CURRENT_LIMIT_MS,
      ...current,
    },
    synthetic_1000: {
      record_count: 1_000,
      fixed_input: true,
      public_build: false,
      limit_p95_ms: SYNTHETIC_LIMIT_MS,
      ...synthetic,
    },
    deterministic_repeat: synthetic.deterministic_digest === repeat.deterministic_digest,
  };
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (failures.length) process.exitCode = 1;
}

main();
