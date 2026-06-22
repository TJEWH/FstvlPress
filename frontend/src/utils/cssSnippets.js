import { buildResponsiveMediaQuery } from "./responsiveViewport.js";

export function escapeCssAttrValue(value) {
  return String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"');
}

export function splitCssSelectorList(selectorText) {
  const selectors = [];
  let current = "";
  let parenDepth = 0;
  let bracketDepth = 0;
  let quote = "";
  let escaped = false;

  for (const char of String(selectorText || "")) {
    current += char;

    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = "";
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (char === "[") {
      bracketDepth += 1;
      continue;
    }
    if (char === "]") {
      bracketDepth = Math.max(0, bracketDepth - 1);
      continue;
    }
    if (char === "(") {
      parenDepth += 1;
      continue;
    }
    if (char === ")") {
      parenDepth = Math.max(0, parenDepth - 1);
      continue;
    }
    if (char === "," && parenDepth === 0 && bracketDepth === 0) {
      selectors.push(current.slice(0, -1).trim());
      current = "";
    }
  }

  const tail = current.trim();
  if (tail) selectors.push(tail);
  return selectors.filter(Boolean);
}

export function sectionIdFromSnippetContext(contextKey) {
  const raw = String(contextKey || "").trim();
  if (!raw.startsWith("section:")) return "";
  return raw.slice("section:".length).trim();
}

export function sectionSnippetContextKey(sectionId) {
  const normalized = String(sectionId || "").trim();
  return normalized ? `section:${normalized}` : "";
}

export function buildSectionScopeSelector(sectionId) {
  const normalized = String(sectionId || "").trim();
  if (!normalized) return "";
  return `[data-section-id="${escapeCssAttrValue(normalized)}"].grid-item-content > :not(.section-admin-tabs-host)`;
}

export function scopeCssBlock(cssText, scopeSelector) {
  const source = String(cssText || "");
  const len = source.length;
  let i = 0;
  let out = "";

  while (i < len) {
    if (source.startsWith("/*", i)) {
      const commentEnd = source.indexOf("*/", i + 2);
      if (commentEnd === -1) {
        out += source.slice(i);
        break;
      }
      out += source.slice(i, commentEnd + 2);
      i = commentEnd + 2;
      continue;
    }

    const tokenStart = i;
    while (i < len && source[i] !== "{" && source[i] !== ";") i += 1;

    if (i >= len) {
      out += source.slice(tokenStart);
      break;
    }

    const token = source.slice(tokenStart, i);
    const trimmedToken = token.trim();
    const boundary = source[i];

    if (boundary === ";") {
      out += source.slice(tokenStart, i + 1);
      i += 1;
      continue;
    }

    const openBrace = i;
    i += 1;
    let depth = 1;
    while (i < len && depth > 0) {
      if (source.startsWith("/*", i)) {
        const commentEnd = source.indexOf("*/", i + 2);
        if (commentEnd === -1) {
          i = len;
          break;
        }
        i = commentEnd + 2;
        continue;
      }
      if (source[i] === "{") depth += 1;
      else if (source[i] === "}") depth -= 1;
      i += 1;
    }

    const closeBrace = Math.max(openBrace + 1, i - 1);
    const body = source.slice(openBrace + 1, closeBrace);

    if (!trimmedToken) {
      out += `${token}{${body}}`;
      continue;
    }

    if (trimmedToken.startsWith("@")) {
      const atRule = trimmedToken.split(/\s+/, 1)[0].toLowerCase();
      if (["@media", "@supports", "@container", "@layer"].includes(atRule)) {
        out += `${trimmedToken}{${scopeCssBlock(body, scopeSelector)}}`;
      } else {
        out += `${trimmedToken}{${body}}`;
      }
      continue;
    }

    const scopedSelectors = splitCssSelectorList(trimmedToken)
      .map((selector) => {
        if (selector.includes("&")) return selector.split("&").join(scopeSelector);
        if (selector.startsWith(scopeSelector)) return selector;
        if (selector === ":root") return scopeSelector;
        return `${scopeSelector} ${selector}`;
      })
      .join(", ");

    out += `${scopedSelectors}{${body}}`;
  }

  return out;
}

export function scopeSectionCustomCss(cssText, scopeSelector) {
  const css = String(cssText || "");
  if (!css.trim() || !scopeSelector) return "";
  if (!css.includes("{")) return "";
  try {
    return scopeCssBlock(css, scopeSelector);
  } catch (err) {
    console.error("Failed to scope section custom CSS, skipping block:", err);
    return "";
  }
}

export function scopedCssForSnippet(snippet) {
  const css = String(snippet?.css || "").trim();
  if (!css) return "";

  const contextKey = String(snippet?.context_key || "").trim();
  if (!contextKey) return css;

  const sectionId = sectionIdFromSnippetContext(contextKey);
  const scopeSelector = buildSectionScopeSelector(sectionId);
  if (!scopeSelector) return "";

  if (!css.includes("{")) return `${scopeSelector} { ${css} }`;
  try {
    return scopeCssBlock(css, scopeSelector);
  } catch (err) {
    console.error("Failed to scope CSS snippet, skipping snippet:", err);
    return "";
  }
}

export function collectScopedCssSnippetGroups(snippets) {
  const groups = {
    desktop: [],
    tablet: [],
    mobile: [],
  };

  for (const snippet of Array.isArray(snippets) ? snippets : []) {
    if (snippet?.active === false) continue;
    const css = scopedCssForSnippet(snippet);
    if (!css) continue;
    const mediaScope = String(snippet?.media_scope || "").trim();
    if (mediaScope === "tablet") groups.tablet.push(css);
    else if (mediaScope === "mobile") groups.mobile.push(css);
    else groups.desktop.push(css);
  }

  return groups;
}

export function buildCssSnippetsStyleText(snippets, { simulatedViewport = "", responsiveConfig = null } = {}) {
  const groups = collectScopedCssSnippetGroups(snippets);
  const desktopCss = groups.desktop.join("\n");
  const tabletCss = groups.tablet.join("\n");
  const mobileCss = groups.mobile.join("\n");
  const tabletQuery = buildResponsiveMediaQuery("tablet", responsiveConfig);
  const mobileQuery = buildResponsiveMediaQuery("mobile", responsiveConfig);
  let combined = "";

  if (desktopCss) combined += `/* Snippets: Desktop/All */\n${desktopCss}\n`;
  if (tabletCss) combined += `/* Snippets: Tablet */\n@media ${tabletQuery} {\n${tabletCss}\n}\n`;
  if (mobileCss) combined += `/* Snippets: Mobile */\n@media ${mobileQuery} {\n${mobileCss}\n}\n`;
  if (simulatedViewport === "tablet" && tabletCss) {
    combined += `/* Snippets: Tablet (simulated) */\n${tabletCss}\n`;
  } else if (simulatedViewport === "mobile" && mobileCss) {
    combined += `/* Snippets: Mobile (simulated) */\n${mobileCss}\n`;
  }

  return combined;
}
