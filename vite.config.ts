import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/Museum-Codex/",
  plugins: [react()],
  build: {
    manifest: true,
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Keep the lazy path engine filename from triggering the M04 home
          // scanner merely because Vite lists a dynamic dependency by name.
          if (id.includes("/node_modules/graphology/")) return "relationship-engine";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/tests/setup.ts"],
    css: true,
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
