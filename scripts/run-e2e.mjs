import { spawnSync } from "node:child_process";
import { extname } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const ISOLATED_RUNS = [
  ["@museum-07-isolated-performance", "museum-07-performance"],
  ["@museum-05b-isolated-performance", "museum-05b-performance"],
  ["@museum-06-isolated-performance", "museum-06-performance"],
];
const ISOLATED_PATTERN = ISOLATED_RUNS.map(([tag]) => tag).join("|");
const requestedOutput = process.env.PLAYWRIGHT_JSON_OUTPUT;

function outputPath(label) {
  if (!requestedOutput) return undefined;
  const extension = extname(requestedOutput);
  const stem = extension ? requestedOutput.slice(0, -extension.length) : requestedOutput;
  return `${stem}-${label}${extension || ".json"}`;
}

function run(args, label) {
  const output = outputPath(label);
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

for (const [tag, label] of ISOLATED_RUNS) {
  run(["--grep", tag], label);
  await delay(1_000);
}
run(["--grep-invert", ISOLATED_PATTERN], "functional");
