const STEP_HEADING_PATTERN = /^##\s+Step\s+\d+\s*:\s*(.+)$/gim;
const FRONTMATTER_BOUNDARY = "---";
const TUTORIAL_SCOPE_OPTIONS = Object.freeze(["content", "design", "admin_design", "admin_general"]);
const ROLE_RANK = Object.freeze({
  no_access: 0,
  content: 1,
  design: 2,
  admin_design: 3,
  admin_general: 4,
});

function normalizeLineEndings(text) {
  return String(text || "").replace(/\r\n?/g, "\n");
}

function escapeFrontmatterValue(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.replace(/"/g, '\\"');
}

function normalizeScope(scope, fallback = "content", allowedScopes = null) {
  const value = String(scope || "").trim();
  const allowedValues = Array.isArray(allowedScopes) && allowedScopes.length > 0
    ? allowedScopes
    : TUTORIAL_SCOPE_OPTIONS;
  return allowedValues.includes(value) ? value : fallback;
}

function normalizeStep(step, index = 0) {
  return {
    id: String(step?.id || `step-${index + 1}`),
    url: String(step?.url || "/admin").trim() || "/admin",
    short_description: String(step?.short_description || `Step ${index + 1}`).trim(),
    long_description: String(step?.long_description || "").trim(),
    order: Number.isFinite(Number(step?.order)) ? Number(step.order) : index,
  };
}

function slugifyFilename(value, fallback = "workflow") {
  const slug = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || fallback;
}

function splitFrontmatter(markdown) {
  const text = normalizeLineEndings(markdown).trim();
  if (!text.startsWith(`${FRONTMATTER_BOUNDARY}\n`)) {
    return { frontmatter: "", body: text };
  }
  const closeIndex = text.indexOf(`\n${FRONTMATTER_BOUNDARY}`, FRONTMATTER_BOUNDARY.length + 1);
  if (closeIndex < 0) {
    return { frontmatter: "", body: text };
  }
  return {
    frontmatter: text.slice(FRONTMATTER_BOUNDARY.length + 1, closeIndex),
    body: text.slice(closeIndex + FRONTMATTER_BOUNDARY.length + 1).trim(),
  };
}

function parseFrontmatter(text) {
  const meta = {};
  const lines = normalizeLineEndings(text).split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) continue;
    const key = match[1].trim();
    const value = match[2] || "";
    if (value.trim() === "|") {
      const parts = [];
      index += 1;
      while (index < lines.length && (/^\s+/.test(lines[index]) || !lines[index].trim())) {
        parts.push(lines[index].replace(/^ {2}/, ""));
        index += 1;
      }
      index -= 1;
      meta[key] = parts.join("\n").trim();
      continue;
    }
    meta[key] = value.trim().replace(/^"|"$/g, "").replace(/\\"/g, '"');
  }
  return meta;
}

function parseStepBlock(heading, block, index) {
  const lines = normalizeLineEndings(block).split("\n");
  const urlIndex = lines.findIndex((line) => /^URL:\s*/i.test(line));
  if (urlIndex < 0) {
    throw new Error(`Step ${index + 1} is missing a URL line.`);
  }
  const url = lines[urlIndex].replace(/^URL:\s*/i, "").trim();
  if (!url) {
    throw new Error(`Step ${index + 1} has an empty URL.`);
  }
  const longDescription = [
    ...lines.slice(0, urlIndex),
    ...lines.slice(urlIndex + 1),
  ].join("\n").trim();
  return {
    id: `import-step-${Date.now()}-${index}`,
    url,
    short_description: heading.trim(),
    long_description: longDescription,
    order: index,
  };
}

export function tutorialToMarkdown(tutorial) {
  const title = String(tutorial?.title || "Untitled Workflow").trim() || "Untitled Workflow";
  const description = String(tutorial?.description || "").trim();
  const scope = normalizeScope(tutorial?.scope, "content");
  const steps = (Array.isArray(tutorial?.steps) ? tutorial.steps : [])
    .map((step, index) => normalizeStep(step, index))
    .sort((left, right) => (left.order ?? 0) - (right.order ?? 0));

  const frontmatter = [
    FRONTMATTER_BOUNDARY,
    `title: "${escapeFrontmatterValue(title)}"`,
    description
      ? `description: |\n${description.split("\n").map((line) => `  ${line}`).join("\n")}`
      : "description: \"\"",
    `scope: ${scope}`,
    FRONTMATTER_BOUNDARY,
  ].join("\n");

  const body = steps.map((step, index) => {
    const parts = [
      `## Step ${index + 1}: ${step.short_description}`,
      "",
      `URL: ${step.url}`,
    ];
    if (step.long_description) {
      parts.push("", step.long_description);
    }
    return parts.join("\n");
  }).join("\n\n");

  return `${frontmatter}\n\n${body}\n`;
}

export function parseTutorialMarkdown(markdown, { defaultScope = "content", allowedScopes = null } = {}) {
  const { frontmatter, body } = splitFrontmatter(markdown);
  const meta = parseFrontmatter(frontmatter);
  const title = String(meta.title || "").trim();
  if (!title) {
    throw new Error("Workflow markdown is missing a frontmatter title.");
  }

  const matches = Array.from(body.matchAll(STEP_HEADING_PATTERN));
  if (matches.length === 0) {
    throw new Error("Workflow markdown must include at least one step heading.");
  }

  const steps = matches.map((match, index) => {
    const blockStart = (match.index || 0) + match[0].length;
    const blockEnd = index + 1 < matches.length ? matches[index + 1].index : body.length;
    return parseStepBlock(match[1], body.slice(blockStart, blockEnd), index);
  });

  const scope = normalizeScope(meta.scope, defaultScope, allowedScopes);
  return {
    title,
    description: String(meta.description || "").trim(),
    scope,
    steps,
  };
}

export function downloadTutorialMarkdown(tutorial) {
  if (typeof window === "undefined" || typeof Blob === "undefined") return;
  const markdown = tutorialToMarkdown(tutorial);
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slugifyFilename(tutorial?.title)}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function allowedScopesForRole(role) {
  const rank = ROLE_RANK[String(role || "").trim()] ?? 0;
  return TUTORIAL_SCOPE_OPTIONS
    .filter((scope) => (ROLE_RANK[scope] ?? 0) <= rank);
}
