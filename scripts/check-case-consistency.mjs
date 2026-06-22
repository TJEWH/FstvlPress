#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

const FRONTEND_ROOT = path.resolve("frontend/src");
const BACKEND_ROOT = path.resolve("backend/app");

const SKIP_DIRS = new Set(["node_modules", ".git", "dist", ".venv", "__pycache__"]);
const FRONTEND_EXTENSIONS = new Set([".js", ".ts", ".vue"]);
const BACKEND_EXTENSIONS = new Set([".py"]);

const FORBIDDEN_BACKEND_CAMEL_KEYS = [
  "pageSlug",
  "itemUrl",
  "sourceRouteRef",
  "sourceType",
  "sourceKind",
  "parentRoute",
  "sectionTemplateRef",
  "sourcePath",
  "targetPath",
  "linkUrl",
  "imageUrl",
  "iconPack",
  "startDate",
  "endDate",
  "useProgramGigs",
  "stageParentRoute",
  "artistParentRoute",
  "stageItemPageTemplatePath",
  "artistItemPageTemplatePath",
];

const ALLOWLIST = {
  frontendMixedFallback: new Set([]),
  backendCamelKey: new Set([
    // Design metadata keys are intentional identifier domains, not payload schema fields.
    path.resolve("backend/app/routers/v1/admin_design.py"),
  ]),
};

function normalizeKey(value) {
  return String(value || "").replace(/_/g, "").toLowerCase();
}

function isSnakeKey(value) {
  return /_/.test(String(value || ""));
}

function isCamelKey(value) {
  return /[A-Z]/.test(String(value || ""));
}

async function walkFiles(rootPath, extensions, files = []) {
  let entries = [];
  try {
    entries = await fs.readdir(rootPath, { withFileTypes: true });
  } catch {
    return files;
  }

  for (const entry of entries) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const fullPath = path.join(rootPath, entry.name);
    if (entry.isDirectory()) {
      await walkFiles(fullPath, extensions, files);
      continue;
    }
    if (entry.isFile() && extensions.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

function isCommentLine(text, isPython = false) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return true;
  if (isPython) return trimmed.startsWith("#");
  return trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*");
}

function collectFrontendMixedFallbackFindings(filePath, lines) {
  if (ALLOWLIST.frontendMixedFallback.has(filePath)) return [];

  const findings = [];
  const pattern = /(?:[A-Za-z0-9_$]+\.)*([A-Za-z0-9_]+)\s*(\?\?|\|\|)\s*(?:[A-Za-z0-9_$]+\.)*([A-Za-z0-9_]+)/g;

  for (let i = 0; i < lines.length; i += 1) {
    const rawLine = lines[i];
    const line = rawLine.replace(/\?\./g, ".");
    if (!line.includes("||") && !line.includes("??")) continue;
    if (isCommentLine(line, false)) continue;

    let match = null;
    while ((match = pattern.exec(line)) !== null) {
      const left = match[1];
      const right = match[3];
      if (normalizeKey(left) !== normalizeKey(right)) continue;
      const mixed = (isSnakeKey(left) && isCamelKey(right)) || (isSnakeKey(right) && isCamelKey(left));
      if (!mixed) continue;
      findings.push({
        kind: "frontend-mixed-fallback",
        file: filePath,
        line: i + 1,
        snippet: rawLine.trim(),
      });
    }
  }

  return findings;
}

function collectBackendMixedGetFallbackFindings(filePath, lines) {
  const findings = [];
  const pattern = /get\(\s*["']([A-Za-z0-9_]+)["']\s*\)\s*or\s*[^\n]*get\(\s*["']([A-Za-z0-9_]+)["']\s*\)/;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.includes("get(") || !line.includes(" or ")) continue;
    if (isCommentLine(line, true)) continue;
    const match = line.match(pattern);
    if (!match) continue;
    const left = match[1];
    const right = match[2];
    if (normalizeKey(left) !== normalizeKey(right)) continue;
    const mixed = (isSnakeKey(left) && isCamelKey(right)) || (isSnakeKey(right) && isCamelKey(left));
    if (!mixed) continue;
    findings.push({
      kind: "backend-mixed-get-fallback",
      file: filePath,
      line: i + 1,
      snippet: line.trim(),
    });
  }

  return findings;
}

function collectBackendForbiddenCamelKeyFindings(filePath, lines) {
  if (ALLOWLIST.backendCamelKey.has(filePath)) return [];

  const findings = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (isCommentLine(line, true)) continue;
    for (const key of FORBIDDEN_BACKEND_CAMEL_KEYS) {
      if (line.includes(`"${key}"`) || line.includes(`'${key}'`)) {
        findings.push({
          kind: "backend-forbidden-camel-key",
          file: filePath,
          line: i + 1,
          snippet: line.trim(),
        });
      }
    }
  }
  return findings;
}

async function readLines(filePath) {
  const content = await fs.readFile(filePath, "utf8");
  return content.split(/\r?\n/);
}

function printFindings(findings) {
  if (!findings.length) {
    console.log("Case consistency check passed.");
    return;
  }

  console.error("Case consistency check failed:\n");
  for (const finding of findings) {
    const relativePath = path.relative(process.cwd(), finding.file);
    console.error(`- [${finding.kind}] ${relativePath}:${finding.line}`);
    console.error(`  ${finding.snippet}`);
  }
}

async function main() {
  const frontendFiles = await walkFiles(FRONTEND_ROOT, FRONTEND_EXTENSIONS);
  const backendFiles = await walkFiles(BACKEND_ROOT, BACKEND_EXTENSIONS);

  const findings = [];

  for (const filePath of frontendFiles) {
    const lines = await readLines(filePath);
    findings.push(...collectFrontendMixedFallbackFindings(filePath, lines));
  }

  for (const filePath of backendFiles) {
    const lines = await readLines(filePath);
    findings.push(...collectBackendMixedGetFallbackFindings(filePath, lines));
    findings.push(...collectBackendForbiddenCamelKeyFindings(filePath, lines));
  }

  printFindings(findings);
  if (findings.length) {
    process.exitCode = 1;
  }
}

await main();
