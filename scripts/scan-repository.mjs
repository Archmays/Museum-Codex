import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { extname, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const files = execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "-z"], {
  cwd: root,
  encoding: "utf8",
}).split("\0").filter(Boolean);

const largeFiles = [];
const secretFindings = [];
const maxBytes = 5 * 1024 * 1024;
const largeFileAllowances = new Map([
  ["public/releases/art-expansion-batch-01-1.5.0/claims.json", 8 * 1024 * 1024],
]);
const textExtensions = new Set([".body", ".css", ".html", ".js", ".json", ".md", ".mjs", ".py", ".svg", ".ts", ".tsx", ".txt", ".yml", ".yaml"]);
const secretPatterns = [
  ["GitHub token", /gh[pousr]_[A-Za-z0-9]{20,}/],
  ["OpenAI-style key", /(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])/],
  ["AWS access key", /AKIA[0-9A-Z]{16}/],
  ["private key", /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
];

for (const file of files) {
  const fullPath = resolve(root, file);
  const stats = statSync(fullPath);
  const fileLimit = largeFileAllowances.get(file) ?? maxBytes;
  if (stats.size > fileLimit) largeFiles.push(`${file} (${stats.size} bytes; limit ${fileLimit})`);
  if (stats.size > 8 * 1024 * 1024 || !textExtensions.has(extname(file).toLowerCase())) continue;
  const text = readFileSync(fullPath, "utf8");
  for (const [label, pattern] of secretPatterns) {
    if (pattern.test(text)) secretFindings.push(`${file}: ${label}`);
  }
}

if (largeFiles.length || secretFindings.length) {
  if (largeFiles.length) console.error(`[repository-scan] large files\n${largeFiles.join("\n")}`);
  if (secretFindings.length) console.error(`[repository-scan] possible secrets\n${secretFindings.join("\n")}`);
  process.exit(1);
}

console.log(`[repository-scan] PASS files=${files.length} file-size policy and credential patterns`);
