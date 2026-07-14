import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  root: import.meta.dirname,
  base: "/",
  server: {
    fs: { allow: [resolve(import.meta.dirname, "../..") ] },
  },
});
