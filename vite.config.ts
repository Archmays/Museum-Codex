import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/Museum-Codex/",
  plugins: [react()],
  build: {
    manifest: true,
    sourcemap: false,
    target: "es2022",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/tests/setup.ts"],
    css: true,
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
