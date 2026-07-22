import { spawnSync } from "node:child_process";
import { extname } from "node:path";
import { pathToFileURL } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const ISOLATED_RUNS = [
  ["@museum-09b-isolated-performance", "museum-09b-performance", "e2e/museum-09b.spec.ts"],
  ["@museum-08-isolated-performance", "museum-08-performance", "e2e/museum-08.spec.ts"],
  ["@museum-07-isolated-performance", "museum-07-performance", "e2e/museum-07.spec.ts"],
  ["@museum-05b-isolated-performance", "museum-05b-performance", "e2e/museum-05b.spec.ts"],
  ["@museum-06-isolated-performance", "museum-06-performance", "e2e/museum-06.spec.ts"],
];
const ISOLATED_PATTERN = ISOLATED_RUNS.map(([tag]) => tag).join("|");
const TARGETED_SPEC_ORDER = [
  "e2e/museum-05a.spec.ts",
  "e2e/museum-05b.spec.ts",
  "e2e/museum-06.spec.ts",
  "e2e/museum-07.spec.ts",
  "e2e/museum-08.spec.ts",
  "e2e/museum-09b.spec.ts",
  "e2e/online.spec.ts",
];
const SUITE_SPECS = {
  constellation: ["e2e/museum-05a.spec.ts", "e2e/museum-09b.spec.ts"],
  gallery: ["e2e/museum-05a.spec.ts", "e2e/museum-05b.spec.ts", "e2e/museum-09b.spec.ts"],
  paths: ["e2e/museum-06.spec.ts", "e2e/museum-09b.spec.ts"],
  map: ["e2e/museum-07.spec.ts", "e2e/museum-09b.spec.ts"],
  search: ["e2e/museum-08.spec.ts", "e2e/museum-09b.spec.ts"],
  online: ["e2e/online.spec.ts"],
  shell: TARGETED_SPEC_ORDER,
};

export function selectAffectedSpecs(rawSuites) {
  if (!rawSuites) return [];
  const suites = JSON.parse(rawSuites);
  if (!Array.isArray(suites) || suites.some((suite) => typeof suite !== "string")) {
    throw new TypeError("MUSEUM_BROWSER_SUITES must be a JSON array of suite names");
  }
  const unknown = suites.filter((suite) => !Object.hasOwn(SUITE_SPECS, suite));
  if (unknown.length) throw new Error(`Unknown browser suite(s): ${unknown.join(", ")}`);
  const selected = new Set(["e2e/museum-09b.spec.ts"]);
  for (const suite of suites) {
    for (const spec of SUITE_SPECS[suite]) selected.add(spec);
  }
  return TARGETED_SPEC_ORDER.filter((spec) => selected.has(spec));
}

function outputPath(label, requestedOutput) {
  if (!requestedOutput) return undefined;
  const extension = extname(requestedOutput);
  const stem = extension ? requestedOutput.slice(0, -extension.length) : requestedOutput;
  return `${stem}-${label}${extension || ".json"}`;
}

function run(args, label, requestedOutput) {
  const output = outputPath(label, requestedOutput);
  const result = spawnSync(
    process.execPath,
    ["node_modules/@playwright/test/cli.js", "test", ...args],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        ...(output ? { PLAYWRIGHT_JSON_OUTPUT: output } : {}),
      },
      stdio: "inherit",
      windowsHide: true,
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

async function main() {
  const requestedOutput = process.env.PLAYWRIGHT_JSON_OUTPUT;
  const selectedSpecs = selectAffectedSpecs(process.env.MUSEUM_BROWSER_SUITES);
  if (process.argv.includes("--print-selected-specs")) {
    console.log(JSON.stringify(selectedSpecs));
    return;
  }

  for (const [tag, label, spec] of ISOLATED_RUNS) {
    if (selectedSpecs.length && !selectedSpecs.includes(spec)) continue;
    run([...selectedSpecs, "--grep", tag], label, requestedOutput);
    await delay(1_000);
  }
  run([...selectedSpecs, "--grep-invert", ISOLATED_PATTERN], "functional", requestedOutput);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
