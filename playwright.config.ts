import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "docs/qa/museum-02a/playwright-results.json" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173/Museum-Codex/",
    trace: "retain-on-failure",
  },
});
