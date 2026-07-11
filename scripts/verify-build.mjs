import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const dist = join(root, "dist");
const indexPath = join(dist, "index.html");
const failures = [];

if (!existsSync(indexPath)) {
  failures.push("dist/index.html is missing");
} else {
  const html = readFileSync(indexPath, "utf8");
  const resourceUrls = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1]);
  const externalResources = resourceUrls.filter((url) => /^(?:https?:)?\/\//i.test(url));
  const rootAssetUrls = resourceUrls.filter((url) => url.startsWith("/assets/"));
  if (externalResources.length) failures.push(`external HTML resources: ${externalResources.join(", ")}`);
  if (rootAssetUrls.length) failures.push(`root-relative asset paths: ${rootAssetUrls.join(", ")}`);

  for (const url of resourceUrls.filter((value) => value.startsWith("/Museum-Codex/"))) {
    const relativeUrl = url.slice("/Museum-Codex/".length).split(/[?#]/)[0];
    if (!relativeUrl || relativeUrl.endsWith("/")) continue;
    if (!existsSync(join(dist, relativeUrl))) failures.push(`missing built resource for ${url}`);
  }
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = join(directory, entry.name);
    return entry.isDirectory() ? walk(fullPath) : [fullPath];
  });
}

if (existsSync(dist)) {
  for (const file of walk(dist)) {
    if (!new Set([".html", ".css", ".js", ".svg"]).has(extname(file))) continue;
    const text = readFileSync(file, "utf8");
    const runtimePatterns = [
      /(?:src|href)=["']https?:\/\//i,
      /url\(\s*["']?https?:\/\//i,
      /(?:fetch|new\s+WebSocket|EventSource)\(\s*["']https?:\/\//i,
      /@import\s+["']https?:\/\//i,
    ];
    if (runtimePatterns.some((pattern) => pattern.test(text))) {
      failures.push(`external runtime dependency pattern in ${relative(dist, file)}`);
    }
  }

  const bytes = walk(dist).reduce((total, file) => total + statSync(file).size, 0);
  console.log(`[build-check] files=${walk(dist).length} bytes=${bytes}`);
}

if (failures.length) {
  console.error(failures.map((failure) => `[build-check] ${failure}`).join("\n"));
  process.exit(1);
}

console.log("[build-check] PASS base path, resource closure, and external runtime scan");
