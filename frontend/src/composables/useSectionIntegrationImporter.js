import { computed, onUnmounted, ref, watch } from "vue";

import * as api from "../services/api.js";
import { useStore } from "../store/store.js";
import { convertKeysToCamel } from "../utils/caseConversion.js";
import { resolveResponsiveImageVariants } from "../utils/responsiveImages.js";
import { normalizeServerWallDateTimeValue } from "../utils/revisionTime.js";

export const INTEGRATION_ROOT_COLLECTION_PATH = "$root";
const MAX_OPTION_DEPTH = 8;
const COLLECTION_SCHEMA_PATH_ALIASES = {
  faq: {
    faqItems: "faqs",
  },
  links: {
    items: "items",
  },
};
const COLLECTION_ITEM_FIELD_ALIASES = {
  faq: {
    faqItems: {
      question: "q",
      answer: "a",
    },
    faqs: {
      question: "q",
      answer: "a",
    },
  },
};
const COLLECTION_ITEM_TARGET_FIELD_ALIASES = {
  program: {
    gigs: {
      artist_name: "title",
      artistName: "title",
      gig_title: "title",
      gigTitle: "title",
    },
  },
};
const BILINGUAL_TEXT_SCHEMA = {
  type: "object",
  properties: {
    de: { type: "string" },
    en: { type: "string" },
  },
};
const VIRTUAL_SHARED_COLLECTION_ITEM_SCHEMAS = {
  blog: {
    blogItems: {
      type: "object",
      properties: {
        imageUrl: { type: "string" },
        imageAuthor: { type: "string" },
        imageZoom: { type: "number" },
        imageFocalX: { type: "number" },
        imageFocalY: { type: "number" },
        imageRotation: { type: "number" },
        date: { type: "string" },
        tag: BILINGUAL_TEXT_SCHEMA,
        title: BILINGUAL_TEXT_SCHEMA,
        text: BILINGUAL_TEXT_SCHEMA,
        pageSlug: { type: "string" },
      },
    },
  },
  faq: {
    faqItems: {
      type: "object",
      properties: {
        q: BILINGUAL_TEXT_SCHEMA,
        a: BILINGUAL_TEXT_SCHEMA,
        tag: BILINGUAL_TEXT_SCHEMA,
        startDate: { type: "string" },
        endDate: { type: "string" },
      },
    },
  },
};
const CONTENT_TARGET_EXCLUDED_ROOT_PATHS = new Set([
  "schemaVersion",
  "schema_version",
  "sectionGeneric",
  "section_generic",
  "hideSectionHeader",
  "hide_section_header",
  "hideSectionDescription",
  "hide_section_description",
  "removeSectionPadding",
  "remove_section_padding",
  "removeSectionBackground",
  "remove_section_background",
  "adminNotes",
  "admin_notes",
  "adminTodos",
  "admin_todos",
  "revisionStatus",
  "revision_status",
  "filters",
  "tileFilters",
  "tile_filters",
  "programTileOrder",
  "program_tile_order",
]);
const CONTENT_TARGET_EXCLUDED_ITEM_PATHS = new Set([
  "_id",
]);
const LIST_ITEM_TARGET_RAW_CASE_SECTION_TYPES = new Set([
  "program",
]);
const LIST_TARGET_COLLECTION_ALLOWLIST_BY_SECTION_TYPE = {
  tiles: new Set(["tiles", "typeData.tiles", "type_data.tiles"]),
};
let sectionTypeCatalogPromise = null;
let sectionTypeCatalogCache = new Map();

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isBilingualObject(value) {
  return isPlainObject(value)
    && (Object.prototype.hasOwnProperty.call(value, "de")
      || Object.prototype.hasOwnProperty.call(value, "en"));
}

function cloneDeep(value) {
  if (value === undefined) return undefined;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
}

function normalizeIntegrationOptions(rawOptions) {
  if (!isPlainObject(rawOptions)) return {};
  const normalized = {};
  Object.entries(rawOptions).forEach(([key, value]) => {
    const normalizedKey = String(key || "").trim();
    if (!normalizedKey || !Array.isArray(value)) return;
    normalized[normalizedKey] = cloneDeep(value);
  });
  return normalized;
}

function normalizeIntegrationOptionTypes(rawOptionTypes) {
  if (!isPlainObject(rawOptionTypes)) return {};
  const normalized = {};
  Object.entries(rawOptionTypes).forEach(([key, value]) => {
    const normalizedKey = String(key || "").trim();
    const normalizedValue = String(value || "").trim().toLowerCase();
    if (!normalizedKey) return;
    if (["multi_choice", "multi", "list"].includes(normalizedValue)) {
      normalized[normalizedKey] = "multi_choice";
    } else if (["single_choice", "single", "scalar"].includes(normalizedValue)) {
      normalized[normalizedKey] = "single_choice";
    }
  });
  return normalized;
}

function normalizeStringListValue(value) {
  const values = [];
  const seen = new Set();
  const visit = (entry) => {
    if (Array.isArray(entry)) {
      entry.forEach((nested) => visit(nested));
      return;
    }
    if (entry == null) return;
    const normalized = String(entry).trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    values.push(normalized);
  };
  visit(value);
  return values;
}

function normalizeProgramGigDateTimeValue(value) {
  return normalizeServerWallDateTimeValue(value);
}

function isProgramGigDateTimeTargetSignature(signature) {
  const normalizedSignature = String(signature || "").trim();
  if (!normalizedSignature) return false;
  return ["start", "end", "previous_start", "previous_end"].some((field) =>
    normalizedSignature === field || normalizedSignature.endsWith(`.${field}`)
  );
}

function deepEqual(left, right) {
  try {
    return JSON.stringify(left) === JSON.stringify(right);
  } catch {
    return left === right;
  }
}

function tokenizeObjectPath(path) {
  const tokens = [];
  String(path || "")
    .split(".")
    .forEach((rawPart) => {
      let part = String(rawPart || "");
      if (!part) return;
      while (part.includes("[")) {
        const bracketIndex = part.indexOf("[");
        const head = part.slice(0, bracketIndex);
        if (head) tokens.push(head);
        const rest = part.slice(bracketIndex + 1);
        const closeIndex = rest.indexOf("]");
        if (closeIndex < 0) {
          part = rest;
          break;
        }
        const indexText = rest.slice(0, closeIndex).trim();
        const indexValue = Number.parseInt(indexText, 10);
        if (Number.isFinite(indexValue)) tokens.push(indexValue);
        part = rest.slice(closeIndex + 1);
        if (part.startsWith(".")) part = part.slice(1);
      }
      if (part) tokens.push(part);
    });
  return tokens;
}

function buildPathFromTokens(tokens) {
  if (!Array.isArray(tokens) || tokens.length === 0) return "";
  return tokens
    .map((token, index) => {
      if (typeof token === "number") return `[${token}]`;
      if (index === 0) return String(token);
      return `.${String(token)}`;
    })
    .join("")
    .replace(/\.\[/g, "[");
}

function deepGetPathValue(source, path) {
  if (!source || typeof source !== "object") return undefined;
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return undefined;
  let current = source;
  for (const token of tokens) {
    if (typeof token === "number") {
      if (!Array.isArray(current) || token < 0 || token >= current.length) return undefined;
      current = current[token];
      continue;
    }
    if (!current || typeof current !== "object" || !(token in current)) return undefined;
    current = current[token];
  }
  return current;
}

function deepHasPath(source, path) {
  if (!source || typeof source !== "object") return false;
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return false;
  let current = source;
  for (const token of tokens) {
    if (typeof token === "number") {
      if (!Array.isArray(current) || token < 0 || token >= current.length) return false;
      current = current[token];
      continue;
    }
    if (!current || typeof current !== "object" || !(token in current)) return false;
    current = current[token];
  }
  return true;
}

function ensureArraySize(target, index) {
  while (target.length <= index) {
    target.push({});
  }
}

function deepSetPathValue(target, path, value) {
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return false;
  let current = target;

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const isLast = index === tokens.length - 1;

    if (typeof token === "number") {
      if (!Array.isArray(current)) return false;
      ensureArraySize(current, token);
      if (isLast) {
        current[token] = cloneDeep(value);
        return true;
      }
      const nextToken = tokens[index + 1];
      if (!current[token] || typeof current[token] !== "object") {
        current[token] = typeof nextToken === "number" ? [] : {};
      }
      current = current[token];
      continue;
    }

    if (!current || typeof current !== "object") return false;
    if (isLast) {
      current[token] = cloneDeep(value);
      return true;
    }
    const nextToken = tokens[index + 1];
    if (!current[token] || typeof current[token] !== "object") {
      current[token] = typeof nextToken === "number" ? [] : {};
    }
    current = current[token];
  }
  return false;
}

function normalizeMediaResponsiveVariants(rawVariants) {
  return resolveResponsiveImageVariants(rawVariants);
}

function mergeMediaMetadata(existingMetadata, nextMetadata) {
  const existing = isPlainObject(existingMetadata) ? existingMetadata : {};
  const next = isPlainObject(nextMetadata) ? nextMetadata : {};
  const existingVariants = normalizeMediaResponsiveVariants(existing.responsive_variants);
  const nextVariants = normalizeMediaResponsiveVariants(next.responsive_variants);

  const variantByUrl = new Map();
  existingVariants.forEach((entry) => {
    variantByUrl.set(entry.url, entry);
  });
  nextVariants.forEach((entry) => {
    const prev = variantByUrl.get(entry.url);
    if (!prev || entry.width > prev.width) {
      variantByUrl.set(entry.url, entry);
    }
  });

  const widthExisting = Number(existing.width);
  const widthNext = Number(next.width);
  const width = Number.isFinite(widthNext) && widthNext > 0
    ? Math.round(widthNext)
    : (
      Number.isFinite(widthExisting) && widthExisting > 0
        ? Math.round(widthExisting)
        : undefined
    );
  const heightExisting = Number(existing.height);
  const heightNext = Number(next.height);
  const height = Number.isFinite(heightNext) && heightNext > 0
    ? Math.round(heightNext)
    : (
      Number.isFinite(heightExisting) && heightExisting > 0
        ? Math.round(heightExisting)
        : undefined
    );

  const merged = {
    ...existing,
    ...next,
    responsive_variants: Array.from(variantByUrl.values()).sort((a, b) => a.width - b.width),
  };
  if (width) {
    merged.width = width;
  } else {
    delete merged.width;
  }
  if (height) {
    merged.height = height;
  } else {
    delete merged.height;
  }
  return merged;
}

function cloneMediaMetadata(metadata) {
  const source = isPlainObject(metadata) ? metadata : {};
  return {
    ...source,
    responsive_variants: normalizeMediaResponsiveVariants(source.responsive_variants),
  };
}

function buildMediaMetadataByUrl(mediaEntries = []) {
  const metadataByUrl = new Map();
  (Array.isArray(mediaEntries) ? mediaEntries : []).forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const metadata = {
      responsive_variants: normalizeMediaResponsiveVariants(entry.responsive_variants),
      width: Number(entry.width),
      height: Number(entry.height),
    };
    const hasAnyMetadata = (
      metadata.responsive_variants.length > 0
      || (Number.isFinite(metadata.width) && metadata.width > 0)
      || (Number.isFinite(metadata.height) && metadata.height > 0)
    );
    if (!hasAnyMetadata) return;

    const relatedUrls = Array.from(new Set([
      entry.resolved_url,
      entry.local_url,
      entry.original_url,
    ]
      .map((rawUrl) => String(rawUrl || "").trim())
      .filter((url) => Boolean(url))));
    if (!relatedUrls.length) return;

    let mergedMetadata = metadata;
    relatedUrls.forEach((normalizedUrl) => {
      const previousMetadata = metadataByUrl.get(normalizedUrl);
      if (previousMetadata) {
        mergedMetadata = mergeMediaMetadata(previousMetadata, mergedMetadata);
      }
    });

    relatedUrls.forEach((normalizedUrl) => {
      metadataByUrl.set(normalizedUrl, cloneMediaMetadata(mergedMetadata));
    });
  });
  return metadataByUrl;
}

function enrichImageRowWithMediaMetadata(row, mediaMetadataByUrl, options = {}) {
  if (!row || typeof row !== "object") return;
  if (!(mediaMetadataByUrl instanceof Map) || mediaMetadataByUrl.size === 0) return;

  const keyStyle = String(options?.keyStyle || "snake").trim().toLowerCase() === "camel"
    ? "camel"
    : "snake";
  const keySet = keyStyle === "camel"
    ? {
      imageUrl: "imageUrl",
      imageResponsiveVariants: "responsiveVariants",
      imageWidth: "imageWidth",
      imageHeight: "imageHeight",
    }
    : {
      imageUrl: "image_url",
      imageResponsiveVariants: "image_responsive_variants",
      imageWidth: "image_width",
      imageHeight: "image_height",
    };

  const imageUrl = String(row[keySet.imageUrl] || "").trim();
  if (!imageUrl) return;

  const metadata = mediaMetadataByUrl.get(imageUrl);
  if (!metadata || typeof metadata !== "object") return;

  const existingVariants = normalizeMediaResponsiveVariants(
    Array.isArray(row[keySet.imageResponsiveVariants])
      ? row[keySet.imageResponsiveVariants]
      : []
  );
  const importedVariants = normalizeMediaResponsiveVariants(metadata.responsive_variants);
  const mergedVariantByUrl = new Map();
  existingVariants.forEach((entry) => {
    mergedVariantByUrl.set(entry.url, entry);
  });
  importedVariants.forEach((entry) => {
    const existing = mergedVariantByUrl.get(entry.url);
    if (!existing || entry.width > existing.width) {
      mergedVariantByUrl.set(entry.url, entry);
    }
  });
  if (mergedVariantByUrl.size > 0) {
    const mergedVariants = Array.from(mergedVariantByUrl.values())
      .sort((left, right) => left.width - right.width);
    row[keySet.imageResponsiveVariants] = mergedVariants;
  }

  const existingWidth = Number(row[keySet.imageWidth]);
  const metadataWidth = Number(metadata.width);
  if (
    (!Number.isFinite(existingWidth) || existingWidth <= 0)
    && Number.isFinite(metadataWidth)
    && metadataWidth > 0
  ) {
    row[keySet.imageWidth] = Math.round(metadataWidth);
  }
  const existingHeight = Number(row[keySet.imageHeight]);
  const metadataHeight = Number(metadata.height);
  if (
    (!Number.isFinite(existingHeight) || existingHeight <= 0)
    && Number.isFinite(metadataHeight)
    && metadataHeight > 0
  ) {
    row[keySet.imageHeight] = Math.round(metadataHeight);
  }
}

function resolveWritableSectionTargetPath(sectionSnapshot, targetPath) {
  const normalizedPath = String(targetPath || "").trim();
  if (!normalizedPath) return "";
  const pathTokens = tokenizeObjectPath(normalizedPath);
  if (!pathTokens.length) return normalizedPath;

  const firstToken = pathTokens[0];
  if (typeof firstToken !== "string") return normalizedPath;
  if (firstToken === "typeData" || firstToken === "type_data") return normalizedPath;
  if (deepGetPathValue(sectionSnapshot, normalizedPath) !== undefined) return normalizedPath;

  const nestedCandidates = [
    {
      containerPath: "typeData",
      value: isPlainObject(sectionSnapshot?.typeData) ? sectionSnapshot.typeData : null,
    },
    {
      containerPath: "type_data",
      value: isPlainObject(sectionSnapshot?.type_data) ? sectionSnapshot.type_data : null,
    },
  ];

  const rootCandidates = [
    String(firstToken || "").trim(),
    toSnakeCaseToken(firstToken),
    toCamelCaseToken(firstToken),
  ].filter(Boolean);
  const remainingTokens = pathTokens.slice(1);

  for (const candidate of nestedCandidates) {
    if (!candidate.value) continue;
    for (const rootCandidate of rootCandidates) {
      if (!Object.prototype.hasOwnProperty.call(candidate.value, rootCandidate)) continue;
      return buildPathFromTokens([candidate.containerPath, rootCandidate, ...remainingTokens]);
    }
  }

  return normalizedPath;
}

function formatPathLabel(path) {
  return String(path || "")
    .replace(/\[(\d+)\]/g, " $1 ")
    .replace(/[._]/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function parseIndexedCollectionPath(path) {
  const normalized = String(path || "").trim();
  const match = normalized.match(/^([a-zA-Z0-9_]+)\[(\d+)\](?:\.(.+))?$/);
  if (!match) return null;
  const index = Number.parseInt(match[2], 10);
  if (!Number.isFinite(index) || index < 0) return null;
  return {
    collection: String(match[1] || "").trim(),
    index,
    itemPath: String(match[3] || "").trim(),
  };
}

function normalizeScalarIdentifier(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function normalizeIntegrationPrimaryKeyPath(value) {
  const normalized = String(value || "").trim();
  return normalized.toLowerCase().startsWith("in ")
    ? normalized.slice(3).trim()
    : normalized;
}

function resolveIntegrationItemKeyFromRow(row, primaryKeyPath) {
  if (!isPlainObject(row)) return "";
  const normalizedPath = normalizeIntegrationPrimaryKeyPath(primaryKeyPath);
  const explicitKey = normalizeScalarIdentifier(
    row.integration_item_key
    ?? row.integrationItemKey
    ?? row.template_integration_item_key
    ?? row.templateIntegrationItemKey
    ?? row.review_item_key
    ?? row.reviewItemKey
  );
  if (explicitKey) return explicitKey;
  if (!normalizedPath) return "";
  return normalizeScalarIdentifier(deepGetPathValue(row, normalizedPath));
}

function mappedLinkItemHasContent(item) {
  if (!isPlainObject(item)) return false;
  return Boolean(
    normalizeScalarIdentifier(item.imageUrl)
    || normalizeScalarIdentifier(item.image_url)
    || normalizeScalarIdentifier(item.logoUrl)
    || normalizeScalarIdentifier(item.logo_url)
    || normalizeScalarIdentifier(item.thumbnailUrl)
    || normalizeScalarIdentifier(item.thumbnail_url)
    || normalizeScalarIdentifier(item.icon)
  );
}

function resolveListPrimaryKeyTargetPathByCollectionPath({
  primaryKeySourcePath,
  listMappings,
  sectionSnapshot,
  sectionTypeValue = "",
}) {
  const normalizedPrimaryKeySourcePath = String(primaryKeySourcePath || "").trim();
  if (!normalizedPrimaryKeySourcePath) return {};
  const normalizedListMappingsByCollectionPath = normalizeListMappingsByCollectionPath(listMappings);
  const next = {};
  Object.entries(normalizedListMappingsByCollectionPath).forEach(([collectionPath, mappings]) => {
    if (!collectionPath || !Array.isArray(mappings)) return;
    const keyMapping = mappings.find((mapping) =>
      String(mapping?.source_path || "").trim() === normalizedPrimaryKeySourcePath
      && String(mapping?.target_path || "").trim()
    );
    if (!keyMapping) return;
    const normalizedTargetPath = normalizeCollectionItemTargetPath(
      keyMapping.target_path,
      sectionTypeValue,
      collectionPath,
    );
    if (!normalizedTargetPath) return;
    const resolvedTargetPath = resolveListItemTargetPath(
      sectionSnapshot,
      collectionPath,
      normalizedTargetPath,
    );
    if (!resolvedTargetPath) return;
    next[collectionPath] = resolvedTargetPath;
  });
  return next;
}

function resolvePreferredTileTitle(tile, lang = "de") {
  if (!tile || typeof tile !== "object") return "";
  const title = tile.title;
  if (typeof title === "string" && title.trim()) return title.trim();
  if (title && typeof title === "object") {
    const localized = String(title?.[lang] || "").trim();
    if (localized) return localized;
    const german = String(title?.de || "").trim();
    if (german) return german;
    const english = String(title?.en || "").trim();
    if (english) return english;
  }
  const name = String(tile?.name || "").trim();
  if (name) return name;
  const label = String(tile?.label || "").trim();
  if (label) return label;
  return "";
}

function normalizeSectionTypeValue(rawSectionType, fallback = "text") {
  const normalized = String(rawSectionType || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized || fallback;
}

function splitPathTokenSuffix(token) {
  const normalizedToken = String(token || "").trim();
  if (!normalizedToken) {
    return { base: "", suffix: "" };
  }
  const suffixIndex = normalizedToken.indexOf("--");
  if (suffixIndex < 0) {
    return { base: normalizedToken, suffix: "" };
  }
  return {
    base: normalizedToken.slice(0, suffixIndex),
    suffix: normalizedToken.slice(suffixIndex),
  };
}

function toCanonicalCamelToken(token) {
  const { base, suffix } = splitPathTokenSuffix(token);
  if (!base) return String(token || "").trim();
  const needsConversion = base.includes("_") || base.includes("-");
  const normalizedBase = needsConversion
    ? base
        .toLowerCase()
        .replace(/[-_]+([a-z0-9])/g, (_, char) => char.toUpperCase())
    : base;
  return `${normalizedBase}${suffix}`;
}

function toCanonicalSnakeToken(token) {
  const { base, suffix } = splitPathTokenSuffix(token);
  if (!base) return String(token || "").trim();
  const normalizedBase = base
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
  return `${normalizedBase}${suffix}`;
}

function shouldUseRawListItemTargetKeys(sectionTypeValue, _collectionPath = "") {
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  return LIST_ITEM_TARGET_RAW_CASE_SECTION_TYPES.has(normalizedSectionType);
}

function collectionItemTargetFieldAlias(token, sectionTypeValue, collectionPath) {
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const aliasesByCollection = COLLECTION_ITEM_TARGET_FIELD_ALIASES[normalizedSectionType] || {};
  const normalizedCollectionPath = String(collectionPath || "").trim();
  const collectionTail = tokenizeObjectPath(normalizedCollectionPath)
    .filter((pathToken) => typeof pathToken === "string")
    .pop();
  const collectionCandidates = [
    normalizedCollectionPath,
    collectionTail,
  ].filter(Boolean);

  for (const candidate of collectionCandidates) {
    const aliasMap = aliasesByCollection[candidate];
    if (!aliasMap) continue;
    const directAlias = aliasMap[token];
    if (directAlias) return directAlias;
    const snakeAlias = aliasMap[toCanonicalSnakeToken(token)];
    if (snakeAlias) return snakeAlias;
    const camelAlias = aliasMap[toCanonicalCamelToken(token)];
    if (camelAlias) return camelAlias;
  }
  return token;
}

function normalizeCollectionItemTargetPath(path, sectionTypeValue, collectionPath) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return "";
  const useRawKeys = shouldUseRawListItemTargetKeys(sectionTypeValue, collectionPath);
  const tokens = tokenizeObjectPath(normalizedPath);
  if (!tokens.length) return normalizedPath;

  const normalizedTokens = tokens.map((token, index) => {
    if (typeof token !== "string") return token;
    const normalizedToken = useRawKeys
      ? toCanonicalSnakeToken(token)
      : toCanonicalCamelToken(token);
    return index === 0
      ? collectionItemTargetFieldAlias(normalizedToken, sectionTypeValue, collectionPath)
      : normalizedToken;
  });
  return buildPathFromTokens(normalizedTokens);
}

function collectionItemPathSignature(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return "";
  const tokens = tokenizeObjectPath(normalizedPath);
  if (!tokens.length) return "";
  const signatureTokens = tokens.map((token) => {
    if (typeof token !== "string") return token;
    const { base, suffix } = splitPathTokenSuffix(token);
    if (!base) return token;
    return `${toCanonicalSnakeToken(base)}${String(suffix || "").toLowerCase()}`;
  });
  return buildPathFromTokens(signatureTokens);
}

function normalizeCollectionItemTargetPathByOptions(
  path,
  options,
  sectionTypeValue,
  collectionPath,
) {
  const normalizedPath = normalizeCollectionItemTargetPath(path, sectionTypeValue, collectionPath);
  if (!normalizedPath) return "";
  const optionPaths = Array.isArray(options)
    ? options
        .map((entry) => String(entry?.path || "").trim())
        .filter(Boolean)
    : [];
  if (!optionPaths.length) return normalizedPath;
  if (optionPaths.includes(normalizedPath)) return normalizedPath;

  const targetSignature = collectionItemPathSignature(normalizedPath);
  if (!targetSignature) return normalizedPath;
  const matchedPath = optionPaths.find((optionPath) =>
    collectionItemPathSignature(optionPath) === targetSignature
  );
  return matchedPath || normalizedPath;
}

function mapCollectionItemPathToEditorPath(optionPath, sectionTypeValue, collectionPath) {
  const normalizedPath = String(optionPath || "").trim();
  if (!normalizedPath) return "";
  const pathTokens = tokenizeObjectPath(normalizedPath);
  if (!pathTokens.length) return normalizedPath;

  const firstToken = pathTokens[0];
  if (typeof firstToken !== "string") return normalizedPath;

  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const fieldAliasesByCollection = COLLECTION_ITEM_FIELD_ALIASES[normalizedSectionType] || {};
  const normalizedCollectionPath = String(collectionPath || "").trim();
  const aliasMap = fieldAliasesByCollection[normalizedCollectionPath] || {};
  const nextFirstToken = aliasMap[firstToken] || firstToken;
  if (nextFirstToken === firstToken) return normalizedPath;

  pathTokens[0] = nextFirstToken;
  return pathTokens
    .map((token, index) => {
      if (typeof token === "number") return `[${token}]`;
      if (index === 0) return token;
      return `.${token}`;
    })
    .join("")
    .replace(/\.\[/g, "[");
}

function toSnakeCaseToken(token) {
  return String(token || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
}

function toCamelCaseToken(token) {
  return String(token || "")
    .toLowerCase()
    .replace(/_([a-z0-9])/g, (_, char) => char.toUpperCase());
}

function typeLabel(valueType) {
  if (valueType === "image") return "Image";
  if (valueType === "url") return "URL";
  if (valueType === "number") return "Number";
  if (valueType === "boolean") return "Boolean";
  if (valueType === "list") return "List";
  if (valueType === "date") return "Date";
  if (valueType === "datetime") return "Date/Time";
  if (valueType === "null") return "Empty";
  if (valueType === "undefined") return "Undefined";
  return "Text";
}

function isImagePath(path) {
  const normalized = String(path || "").toLowerCase();
  return normalized.includes("image")
    || normalized.includes("photo")
    || normalized.includes("thumbnail")
    || normalized.includes("cover")
    || normalized.includes("avatar")
    || normalized.includes("logo")
    || normalized.includes("background");
}

function inferDataType(path, value) {
  if (isImagePath(path)) return "image";
  if (value == null) return "null";
  if (Array.isArray(value)) {
    const hasStructuredEntry = value.some((entry) => isPlainObject(entry) || Array.isArray(entry));
    return hasStructuredEntry ? "json" : "list";
  }
  if (isPlainObject(value)) {
    if (isBilingualObject(value)) return "text";
    return "json";
  }
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string") {
    const normalized = value.trim();
    if (/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(normalized)) {
      return "date";
    }
  }
  return "text";
}

function normalizeIntegrationSchemaType(rawType) {
  const value = String(rawType || "").trim().toLowerCase();
  if ([
    "text",
    "number",
    "boolean",
    "date",
    "datetime",
    "url",
    "image",
    "list",
    "json",
    "null",
    "undefined",
  ].includes(value)) {
    return value;
  }
  return "";
}

function optionLabel(path, valueType) {
  return `${formatPathLabel(path)} (${typeLabel(valueType)})`;
}

function collectionItemTargetOptionLabel(path, valueType, sectionTypeValue, collectionPath) {
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const collectionTail = tokenizeObjectPath(String(collectionPath || "").trim())
    .filter((pathToken) => typeof pathToken === "string")
    .pop();
  const pathSignature = collectionItemPathSignature(path);
  if (
    normalizedSectionType === "program"
    && collectionTail === "gigs"
    && (pathSignature === "title" || pathSignature.startsWith("title."))
  ) {
    return `${formatPathLabel(path).replace(/^Title\b/, "Gig Title")} (${typeLabel(valueType)})`;
  }
  if (
    normalizedSectionType === "program"
    && collectionTail === "gigs"
    && pathSignature === "highlight_changes"
  ) {
    return `New Gig (${typeLabel(valueType)})`;
  }
  return optionLabel(path, valueType);
}

function listCollectionLabel(path, count) {
  const normalizedCount = Number.isFinite(Number(count)) ? Number(count) : 0;
  return `${formatPathLabel(path)} (${normalizedCount} item${normalizedCount === 1 ? "" : "s"})`;
}

function shouldSkipContentTargetPath(path, { listItem = false } = {}) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return true;

  const firstToken = tokenizeObjectPath(normalizedPath).find((token) => typeof token === "string");
  const normalizedRoot = String(firstToken || "").trim();
  if (!normalizedRoot) return true;
  if (CONTENT_TARGET_EXCLUDED_ROOT_PATHS.has(normalizedRoot)) return true;
  if (listItem && CONTENT_TARGET_EXCLUDED_ITEM_PATHS.has(normalizedRoot)) return true;
  return false;
}

function isAllowedListTargetCollectionPath(sectionTypeValue, path) {
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const allowlist = LIST_TARGET_COLLECTION_ALLOWLIST_BY_SECTION_TYPE[normalizedSectionType];
  if (!(allowlist instanceof Set) || allowlist.size === 0) return true;

  const normalizedPath = String(path || "").trim();
  return Boolean(normalizedPath && allowlist.has(normalizedPath));
}

function addTypedOption(targetMap, path, valueType) {
  const normalizedPath = String(path || "").trim();
  const normalizedType = String(valueType || "").trim().toLowerCase();
  if (!normalizedPath || !normalizedType || normalizedType === "json") return;
  if (targetMap.has(normalizedPath)) return;
  targetMap.set(normalizedPath, {
    path: normalizedPath,
    type: normalizedType,
    label: optionLabel(normalizedPath, normalizedType),
  });
}

function collectTypedLeafOptionsFromValue(value, basePath = "", out = new Map(), depth = 0) {
  if (depth > MAX_OPTION_DEPTH || value == null) {
    if (basePath && value == null) {
      addTypedOption(out, basePath, inferDataType(basePath, value));
    }
    return out;
  }

  if (Array.isArray(value)) {
    if (basePath) {
      addTypedOption(out, basePath, inferDataType(basePath, value));
    }
    return out;
  }

  if (isPlainObject(value)) {
    if (isBilingualObject(value) && basePath) {
      if (Object.prototype.hasOwnProperty.call(value, "de")) {
        addTypedOption(out, `${basePath}.de`, inferDataType(`${basePath}.de`, value.de));
      }
      if (Object.prototype.hasOwnProperty.call(value, "en")) {
        addTypedOption(out, `${basePath}.en`, inferDataType(`${basePath}.en`, value.en));
      }
      return out;
    }

    Object.entries(value).forEach(([key, child]) => {
      const cleanKey = String(key || "").trim();
      if (!cleanKey) return;
      const nextPath = basePath ? `${basePath}.${cleanKey}` : cleanKey;
      collectTypedLeafOptionsFromValue(child, nextPath, out, depth + 1);
    });
    return out;
  }

  if (basePath) {
    addTypedOption(out, basePath, inferDataType(basePath, value));
  }
  return out;
}

function collectSectionListOptions(sectionValue) {
  if (!isPlainObject(sectionValue)) return [];

  const options = new Map();
  const addOption = (path, listValue) => {
    const normalizedPath = String(path || "").trim();
    if (!normalizedPath || !Array.isArray(listValue)) return;
    options.set(normalizedPath, {
      path: normalizedPath,
      count: listValue.length,
      label: listCollectionLabel(normalizedPath, listValue.length),
    });
  };

  const skipTopLevel = new Set([
    "title",
    "icon",
    "sectionType",
    "sectionGeneric",
    "adminNotes",
    "adminTodos",
    "revisionStatus",
    "filters",
    "tileFilters",
    "programTileOrder",
  ]);

  Object.entries(sectionValue).forEach(([key, value]) => {
    const cleanKey = String(key || "").trim();
    if (!cleanKey || skipTopLevel.has(cleanKey)) return;
    if (Array.isArray(value)) {
      addOption(cleanKey, value);
      return;
    }
    if (!isPlainObject(value)) return;

    // Section content nested under typeData/type_data should be exposed as direct
    // list names so mapping targets stay section-content-centric.
    if (cleanKey !== "typeData" && cleanKey !== "type_data") return;
    Object.entries(value).forEach(([nestedKey, nestedValue]) => {
      const cleanNestedKey = String(nestedKey || "").trim();
      if (!cleanNestedKey || !Array.isArray(nestedValue)) return;
      addOption(cleanNestedKey, nestedValue);
    });
  });

  return Array.from(options.values()).sort((a, b) => a.path.localeCompare(b.path));
}

function schemaNodeType(schemaNode) {
  if (!schemaNode || typeof schemaNode !== "object") return "";
  const raw = schemaNode.type;
  if (typeof raw === "string") return raw.toLowerCase();
  if (Array.isArray(raw)) {
    const found = raw.find((value) => typeof value === "string" && value.toLowerCase() !== "null");
    return typeof found === "string" ? found.toLowerCase() : "";
  }
  return "";
}

function resolveSchemaRef(schemaNode, rootSchema) {
  if (!schemaNode || typeof schemaNode !== "object") return null;

  if (schemaNode.$ref && typeof schemaNode.$ref === "string" && schemaNode.$ref.startsWith("#/")) {
    const segments = schemaNode.$ref.slice(2).split("/");
    let cursor = rootSchema;
    for (const segment of segments) {
      if (!cursor || typeof cursor !== "object") return null;
      cursor = cursor[segment];
    }
    return cursor && typeof cursor === "object" ? cursor : null;
  }

  if (Array.isArray(schemaNode.anyOf) && schemaNode.anyOf.length > 0) {
    return schemaNode.anyOf.find((entry) => schemaNodeType(entry) && schemaNodeType(entry) !== "null") || schemaNode.anyOf[0];
  }
  if (Array.isArray(schemaNode.oneOf) && schemaNode.oneOf.length > 0) {
    return schemaNode.oneOf[0];
  }
  if (Array.isArray(schemaNode.allOf) && schemaNode.allOf.length > 0) {
    return schemaNode.allOf[0];
  }
  return schemaNode;
}

function resolveSchemaNode(schemaNode, rootSchema, depth = 0) {
  if (depth > MAX_OPTION_DEPTH) return null;
  const candidate = resolveSchemaRef(schemaNode, rootSchema);
  if (!candidate) return null;
  if (candidate.$ref) {
    return resolveSchemaNode(candidate, rootSchema, depth + 1);
  }
  const nestedCandidate = resolveSchemaRef(candidate, rootSchema);
  return nestedCandidate || null;
}

function resolveCollectionItemSchemaByPath(sectionSchema, targetCollectionPath, sectionTypeValue = "") {
  const normalizedPath = String(targetCollectionPath || "").trim();
  if (!sectionSchema || !normalizedPath) return null;
  const tokens = tokenizeObjectPath(normalizedPath).filter((token) => typeof token === "string");
  while (tokens.length > 0 && (tokens[0] === "typeData" || tokens[0] === "type_data")) {
    tokens.shift();
  }
  if (!tokens.length) return null;
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const pathAliases = COLLECTION_SCHEMA_PATH_ALIASES[normalizedSectionType] || {};

  let cursor = resolveSchemaNode(sectionSchema, sectionSchema);
  for (const token of tokens) {
    const resolvedCursor = resolveSchemaNode(cursor, sectionSchema);
    if (!resolvedCursor) return null;

    if (schemaNodeType(resolvedCursor) === "array") {
      cursor = resolveSchemaNode(resolvedCursor.items, sectionSchema);
    } else {
      cursor = resolvedCursor;
    }

    const objectNode = resolveSchemaNode(cursor, sectionSchema);
    if (!objectNode || schemaNodeType(objectNode) !== "object") {
      return null;
    }
    const properties = objectNode.properties && typeof objectNode.properties === "object"
      ? objectNode.properties
      : {};
    const alias = pathAliases[token];
    const candidates = [
      token,
      toSnakeCaseToken(token),
      alias,
      toSnakeCaseToken(alias),
    ].filter(Boolean);
    const nextNode = candidates
      .map((candidate) => properties[candidate])
      .find(Boolean);
    if (!nextNode) return null;
    cursor = resolveSchemaNode(nextNode, sectionSchema);
  }

  const resolved = resolveSchemaNode(cursor, sectionSchema);
  if (!resolved || schemaNodeType(resolved) !== "array") return null;
  return resolveSchemaNode(resolved.items, sectionSchema);
}

function resolveVirtualSharedCollectionItemSchema(sectionTypeValue, targetCollectionPath) {
  const normalizedSectionType = normalizeSectionTypeValue(sectionTypeValue, "");
  const normalizedPath = String(targetCollectionPath || "").trim();
  if (!normalizedSectionType || !normalizedPath) return null;
  const schemasByPath = VIRTUAL_SHARED_COLLECTION_ITEM_SCHEMAS[normalizedSectionType] || {};
  return schemasByPath[normalizedPath] || null;
}

function collectTypedOptionsFromSchema(
  schemaNode,
  rootSchema,
  basePath = "",
  out = new Map(),
  depth = 0,
  options = {},
) {
  if (depth > MAX_OPTION_DEPTH) return out;
  const { useRawKeys = false } = options || {};
  const resolved = resolveSchemaNode(schemaNode, rootSchema);
  if (!resolved) return out;
  const nodeType = schemaNodeType(resolved);

  if (nodeType === "object") {
    const properties = resolved.properties && typeof resolved.properties === "object"
      ? resolved.properties
      : {};
    Object.entries(properties).forEach(([key, childSchema]) => {
      const normalizedKey = useRawKeys ? String(key || "") : toCamelCaseToken(key);
      const nextPath = basePath ? `${basePath}.${normalizedKey}` : normalizedKey;
      collectTypedOptionsFromSchema(childSchema, rootSchema, nextPath, out, depth + 1, options);
    });
    return out;
  }

  if (nodeType === "array") {
    const itemNode = resolveSchemaNode(resolved.items, rootSchema);
    const itemType = schemaNodeType(itemNode);
    if (!itemType || itemType === "object" || itemType === "array") {
      return out;
    }
    addTypedOption(out, basePath, inferDataType(basePath, []));
    return out;
  }

  if (!basePath) return out;
  let sampleValue = "";
  if (nodeType === "integer" || nodeType === "number") sampleValue = 0;
  if (nodeType === "boolean") sampleValue = true;
  if (nodeType === "null") sampleValue = null;
  addTypedOption(out, basePath, inferDataType(basePath, sampleValue));
  return out;
}

function collectTypedLeafOptionsFromListRows(listRows) {
  const merged = new Map();
  if (!Array.isArray(listRows)) return merged;
  listRows.forEach((entry) => {
    if (!isPlainObject(entry)) return;
    const rowOptions = collectTypedLeafOptionsFromValue(entry);
    rowOptions.forEach((option, path) => {
      if (!path || !option) return;
      if (merged.has(path)) return;
      merged.set(path, option);
    });
  });
  return merged;
}

async function getSectionTypeCatalog() {
  if (sectionTypeCatalogCache.size > 0) {
    return sectionTypeCatalogCache;
  }
  if (!sectionTypeCatalogPromise) {
    sectionTypeCatalogPromise = api.getSectionTypes()
      .then((response) => {
        const nextMap = new Map();
        const types = Array.isArray(response?.types) ? response.types : [];
        types.forEach((entry) => {
          const normalizedType = normalizeSectionTypeValue(entry?.type);
          const schema = entry?.schema && typeof entry.schema === "object" ? entry.schema : null;
          if (schema) {
            nextMap.set(normalizedType, schema);
          }
        });
        sectionTypeCatalogCache = nextMap;
        return sectionTypeCatalogCache;
      })
      .catch((err) => {
        console.error("Failed to load section type schemas for integration mapping:", err);
        sectionTypeCatalogCache = new Map();
        return sectionTypeCatalogCache;
      })
      .finally(() => {
        sectionTypeCatalogPromise = null;
      });
  }
  return sectionTypeCatalogPromise;
}

function toBilingualValue(value) {
  if (isPlainObject(value)) {
    const de = String(value.de || value.en || "").trim();
    const en = String(value.en || value.de || "").trim();
    return { de, en };
  }
  const text = value == null ? "" : String(value).trim();
  return { de: text, en: text };
}

function hasBilingualValue(value) {
  const normalized = toBilingualValue(value);
  return Boolean(normalized.de || normalized.en);
}

function collectCollectionPaths(value, basePath = "", out = new Set(), depth = 0) {
  if (depth > 8 || value == null) return out;

  if (Array.isArray(value)) {
    if (basePath) out.add(basePath);
    return out;
  }

  if (!isPlainObject(value)) return out;

  Object.entries(value).forEach(([key, child]) => {
    const cleanKey = String(key || "").trim();
    if (!cleanKey) return;
    const nextPath = basePath ? `${basePath}.${cleanKey}` : cleanKey;
    collectCollectionPaths(child, nextPath, out, depth + 1);
  });
  return out;
}

function getRootKey(path) {
  const [firstToken] = tokenizeObjectPath(path);
  return typeof firstToken === "string" ? firstToken : "";
}

function resolveIntegrationSourceValue(rawData, sourcePath) {
  const normalizedPath = String(sourcePath || "").trim();
  if (!normalizedPath) return undefined;

  if (Array.isArray(rawData)) {
    const firstRow = rawData.find((entry) => entry && typeof entry === "object");
    if (!firstRow) return undefined;
    return deepGetPathValue(firstRow, normalizedPath);
  }
  if (isPlainObject(rawData)) {
    return deepGetPathValue(rawData, normalizedPath);
  }
  return undefined;
}

function resolveScalarSourceValue(rawData, sourcePath) {
  return resolveIntegrationSourceValue(rawData, sourcePath);
}

function resolveCollectionRows(rawData, sourceCollectionPath) {
  const normalizedPath = String(sourceCollectionPath || "").trim();
  if (!normalizedPath) return [];

  if (normalizedPath === INTEGRATION_ROOT_COLLECTION_PATH) {
    if (Array.isArray(rawData)) return rawData.filter((entry) => isPlainObject(entry));
    if (isPlainObject(rawData)) return [rawData];
    return [];
  }

  if (Array.isArray(rawData)) {
    const rows = [];
    rawData.forEach((entry) => {
      if (!isPlainObject(entry)) return;
      const nested = deepGetPathValue(entry, normalizedPath);
      if (Array.isArray(nested)) {
        rows.push(...nested.filter((row) => isPlainObject(row)));
      } else if (isPlainObject(nested)) {
        rows.push(nested);
      }
    });
    return rows;
  }

  if (!isPlainObject(rawData)) return [];
  const nested = deepGetPathValue(rawData, normalizedPath);
  if (Array.isArray(nested)) return nested.filter((row) => isPlainObject(row));
  if (isPlainObject(nested)) return [nested];
  return [];
}

function resolveListItemTargetPath(sectionSnapshot, targetCollectionPath, targetItemPath) {
  const normalizedCollectionPath = String(targetCollectionPath || "").trim();
  const normalizedItemPath = String(targetItemPath || "").trim();
  if (!normalizedCollectionPath || !normalizedItemPath) return normalizedItemPath;

  const collectionRows = deepGetPathValue(sectionSnapshot, normalizedCollectionPath);
  const sampleRow = Array.isArray(collectionRows)
    ? collectionRows.find((entry) => isPlainObject(entry))
    : null;
  if (!sampleRow) {
    // When the collection is still empty, keep the configured target path as-is.
    // This avoids accidental casing transforms such as imageUrl -> image_url.
    return normalizedItemPath;
  }

  const tokens = tokenizeObjectPath(normalizedItemPath);
  if (!tokens.length) return normalizedItemPath;

  let cursor = sampleRow;
  const resolvedTokens = [];

  tokens.forEach((token) => {
    if (typeof token === "number") {
      resolvedTokens.push(token);
      if (Array.isArray(cursor) && token >= 0 && token < cursor.length) {
        cursor = cursor[token];
      } else {
        cursor = null;
      }
      return;
    }

    const rawToken = String(token || "").trim();
    if (!rawToken) return;

    if (isPlainObject(cursor)) {
      const candidates = [
        rawToken,
        toSnakeCaseToken(rawToken),
        toCamelCaseToken(rawToken),
      ].filter(Boolean);
      const resolvedKey = candidates.find((candidate) =>
        Object.prototype.hasOwnProperty.call(cursor, candidate)
      ) || rawToken;
      resolvedTokens.push(resolvedKey);
      cursor = cursor[resolvedKey];
      return;
    }

    resolvedTokens.push(rawToken);
    cursor = null;
  });

  return buildPathFromTokens(resolvedTokens);
}

function normalizeScalarMappings(rawMappings) {
  if (!Array.isArray(rawMappings)) return [];
  return rawMappings
    .map((mapping) => {
      if (!isPlainObject(mapping)) return null;
      const source = convertKeysToCamel(mapping);
      return {
        source_path: String(source?.sourcePath || "").trim(),
        target_path: String(source?.targetPath || "").trim(),
      };
    })
    .filter((mapping) => mapping.source_path && mapping.target_path);
}

function normalizeListMappingsByCollectionPath(rawMappingsByCollectionPath) {
  if (!isPlainObject(rawMappingsByCollectionPath)) return {};
  const normalized = {};

  Object.entries(rawMappingsByCollectionPath).forEach(([collectionPath, rawRows]) => {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath || !Array.isArray(rawRows)) return;

    const normalizedRows = rawRows
      .map((mapping) => {
        if (!isPlainObject(mapping)) return null;
        const source = convertKeysToCamel(mapping);
        return {
          source_path: String(source?.sourcePath || "").trim(),
          target_path: String(source?.targetPath || "").trim(),
        };
      })
      .filter((mapping) => mapping.source_path && mapping.target_path);

    if (normalizedRows.length > 0) {
      normalized[normalizedCollectionPath] = normalizedRows;
    }
  });

  return normalized;
}

function normalizeHiddenListTargetPathsByCollectionPath(rawHiddenMap, sectionTypeValue = "") {
  if (!isPlainObject(rawHiddenMap)) return {};
  const normalized = {};

  Object.entries(rawHiddenMap).forEach(([collectionPath, rawHiddenPaths]) => {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath || !Array.isArray(rawHiddenPaths)) return;

    const seenPathSignatures = new Set();
    const hiddenPaths = rawHiddenPaths
      .map((path) => normalizeCollectionItemTargetPath(
        String(path || "").trim(),
        sectionTypeValue,
        normalizedCollectionPath,
      ))
      .filter(Boolean)
      .filter((path) => {
        const signature = collectionItemPathSignature(path);
        if (!signature || seenPathSignatures.has(signature)) return false;
        seenPathSignatures.add(signature);
        return true;
      });

    if (hiddenPaths.length > 0) {
      normalized[normalizedCollectionPath] = hiddenPaths;
    }
  });

  return normalized;
}

function normalizeIntegrationListFilters(rawFilters) {
  if (!Array.isArray(rawFilters)) return [];
  const seenIds = new Set();
  return rawFilters
    .map((entry, index) => {
      if (!isPlainObject(entry)) return null;
      const source = convertKeysToCamel(entry);
      let id = String(source.id || source.filterId || "").trim();
      if (!id) id = `filter-${index + 1}`;
      if (seenIds.has(id)) {
        let suffix = 2;
        let candidate = `${id}-${suffix}`;
        while (seenIds.has(candidate)) {
          suffix += 1;
          candidate = `${id}-${suffix}`;
        }
        id = candidate;
      }
      seenIds.add(id);
      const sourcePath = String(source.sourcePath || "").trim();
      const targetPath = String(source.targetPath || "").trim();
      const rawName = String(source.name || "").trim();
      const adminScopeRaw = source.adminScopeValue ?? "";
      const adminScopeValue = String(adminScopeRaw || "").trim();
      return {
        id,
        name: rawName || sourcePath,
        source_path: sourcePath,
        target_path: targetPath,
        enabled: source.enabled == null ? true : Boolean(source.enabled),
        admin_scope_value: adminScopeValue || null,
      };
    })
    .filter(Boolean);
}

function normalizeFilterValue(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value).trim();
  if (isBilingualObject(value)) {
    const de = String(value.de || "").trim();
    const en = String(value.en || "").trim();
    return de || en;
  }
  return "";
}

function collectDistinctFilterValuesFromRows(rows, sourcePath) {
  const normalizedSourcePath = String(sourcePath || "").trim();
  if (!normalizedSourcePath || !Array.isArray(rows)) return [];
  const seen = new Set();
  rows.forEach((row) => {
    const rawValue = deepGetPathValue(row, normalizedSourcePath);
    const normalizedValue = normalizeFilterValue(rawValue);
    if (!normalizedValue) return;
    seen.add(normalizedValue);
  });
  return Array.from(seen).sort((left, right) => left.localeCompare(right));
}

function ensureAtLeastOneScalarMapping(mappingsRef) {
  if (!Array.isArray(mappingsRef.value) || mappingsRef.value.length === 0) {
    mappingsRef.value = [{ source_path: "", target_path: "" }];
  }
}

export function useSectionIntegrationImporter({
  sectionKey,
  sectionData,
  sectionType,
  forcedMode = ref(""),
  fixedCollectionPaths = ref([]),
  mappingStorageKey = ref("sectionIntegrationMapping"),
  applyContentPatch = ref(null),
  persistMappingPatch = ref(null),
}) {
  const { state, updateSection, setFaqItems } = useStore();

  const availableIntegrations = ref([]);
  const selectedIntegration = ref("");
  const integrationContext = ref({
    template_key: "",
    integration_visibility: "enabled",
    integrations_enabled: true,
    expected_return_type: "auto",
  });
  const integrationContextLoaded = ref(false);
  const integrationPreview = ref(null);
  const integrationSchema = ref(null);
  const loadingIntegrations = ref(false);
  const importing = ref(false);
  const loadingMediaImportability = ref(false);
  const importStatus = ref(null);
  const mediaImportability = ref({
    has_media_urls: false,
    media_url_count: 0,
    fetched_at: null,
  });

  const scalarMappings = ref([{ source_path: "", target_path: "" }]);
  const listMappingsByCollectionPath = ref({});
  const hiddenListTargetPathsByCollectionPath = ref({});
  const listFilters = ref([]);
  const mappingMode = ref("auto");
  const lastImportRevertPatch = ref(null);
  const sectionTypeSchema = ref(null);
  const listFilterSourceRows = ref([]);
  const listFilterScopeValuesBySourcePath = ref({});
  const loadingListFilterScopeValues = ref(false);
  const listFilterRowsIntegrationId = ref("");
  const collectionItemOptionCache = new Map();
  const localMappingStateHydrating = ref(false);
  const loadingPersistedMapping = ref(false);
  const lastPersistedMappingSignature = ref("");
  let persistMappingTimer = null;

  const selectedIntegrationDetails = computed(() =>
    availableIntegrations.value.find((entry) => String(entry?.id || "").trim() === String(selectedIntegration.value || "").trim())
  );

  const isIntegrationEnabled = computed(() =>
    integrationContext.value?.integrations_enabled !== false
  );
  const normalizedSectionType = computed(() => normalizeSectionTypeValue(sectionType.value, ""));
  const forcedImportModeValue = computed(() => {
    const normalized = String(forcedMode?.value || forcedMode || "").trim().toLowerCase();
    return normalized === "list" || normalized === "object" ? normalized : "";
  });
  const mappingStorageField = computed(() => {
    const normalized = String(mappingStorageKey?.value || mappingStorageKey || "").trim();
    return normalized || "sectionIntegrationMapping";
  });
  const cacheStateField = computed(() => {
    const base = String(mappingStorageField.value || "sectionIntegrationMapping").trim();
    if (!base) return "sectionIntegrationCacheState";
    return `${base}CacheState`;
  });
  const cacheState = computed(() => {
    const value = sectionData.value?.[cacheStateField.value];
    return isPlainObject(value) ? value : {};
  });
  const fixedCollectionPathSet = computed(() => {
    const raw = Array.isArray(fixedCollectionPaths?.value)
      ? fixedCollectionPaths.value
      : Array.isArray(fixedCollectionPaths)
        ? fixedCollectionPaths
        : [];
    return new Set(
      raw
        .map((entry) => String(entry || "").trim())
        .filter(Boolean)
    );
  });

  const activeImportMode = computed(() => {
    if (forcedImportModeValue.value) {
      return forcedImportModeValue.value;
    }
    const expected = String(integrationContext.value?.expected_return_type || "auto").trim().toLowerCase();
    if (expected === "list" || expected === "object") {
      return expected;
    }
    if (mappingMode.value === "list" || mappingMode.value === "object") {
      return mappingMode.value;
    }
    const integrationReturnType = String(selectedIntegrationDetails.value?.return_type || "").trim().toLowerCase();
    if (integrationReturnType === "list") {
      return "list";
    }
    return "object";
  });

  const isListMode = computed(() => activeImportMode.value === "list");
  const isObjectMode = computed(() => activeImportMode.value === "object");
  const isSectionTemplateBuilder = computed(() =>
    String(state.pageSlug || "").startsWith("__template_section__/")
  );
  const canEditListTargetVisibility = computed(() =>
    isSectionTemplateBuilder.value && isListMode.value
  );
  const supportsListFilters = computed(() =>
    normalizedSectionType.value === "tiles" && isListMode.value
  );
  const hasMediaUrls = computed(() => mediaImportability.value?.has_media_urls === true);
  const mediaUrlCount = computed(() => Number(mediaImportability.value?.media_url_count || 0));

  function sortOptions(entriesMap) {
    return Array.from(entriesMap.values()).sort((a, b) => a.path.localeCompare(b.path));
  }

  const scalarTargetOptions = computed(() => {
    const schemaOptions = collectTypedOptionsFromSchema(sectionTypeSchema.value, sectionTypeSchema.value);
    return Array.from(schemaOptions.values())
      .filter((entry) => entry && !shouldSkipContentTargetPath(entry.path))
      .map((entry) => {
        const path = String(entry.path || "").trim();
        const value = deepGetPathValue(sectionData.value, path);
        const valueType = value === undefined
          ? String(entry.type || "text")
          : inferDataType(path, value);
        return {
          path,
          type: valueType,
          label: optionLabel(path, valueType),
        };
      })
      .filter((entry) => entry.type !== "json")
      .sort((a, b) => a.path.localeCompare(b.path));
  });

  const collectionTargetOptions = computed(() => {
    const fixedPaths = fixedCollectionPathSet.value;
    const directListOptions = collectSectionListOptions(sectionData.value);
    const visibleDirectListOptions = directListOptions.filter((entry) =>
      entry && !shouldSkipContentTargetPath(entry.path)
      && isAllowedListTargetCollectionPath(sectionType.value, entry.path)
    );
    const filteredDirectListOptions = fixedPaths.size > 0
      ? visibleDirectListOptions.filter((entry) => fixedPaths.has(String(entry?.path || "").trim()))
      : visibleDirectListOptions;
    if (filteredDirectListOptions.length > 0) {
      return filteredDirectListOptions.map((entry) => ({
        path: entry.path,
        label: entry.label,
      }));
    }

    let paths = Array.from(collectCollectionPaths(sectionData.value)).filter(Boolean);
    paths = paths.filter((path) =>
      !shouldSkipContentTargetPath(path)
      && isAllowedListTargetCollectionPath(sectionType.value, path)
    );
    if (fixedPaths.size > 0) {
      paths = paths.filter((path) => fixedPaths.has(String(path || "").trim()));
    }
    return Array.from(paths)
      .sort((a, b) => a.localeCompare(b))
      .map((path) => ({ path, label: listCollectionLabel(path, 0) }));
  });

  const integrationLeafOptions = computed(() => {
    const typedOptions = collectTypedLeafOptionsFromValue(integrationPreview.value?.preview_item);
    integrationSchemaOptions.value.forEach((entry, path) => {
      if (!typedOptions.has(path)) {
        typedOptions.set(path, entry);
      } else {
        typedOptions.set(path, {
          ...typedOptions.get(path),
          ...entry,
        });
      }
    });
    return sortOptions(typedOptions);
  });

  const listItemSourceOptions = computed(() => {
    const previewItem = integrationPreview.value?.preview_item;
    const typedOptions = collectTypedLeafOptionsFromValue(previewItem);
    integrationSchemaOptions.value.forEach((entry, path) => {
      if (!typedOptions.has(path)) {
        typedOptions.set(path, entry);
      } else {
        typedOptions.set(path, {
          ...typedOptions.get(path),
          ...entry,
        });
      }
    });
    return sortOptions(typedOptions);
  });

  const integrationSchemaOptions = computed(() => {
    const options = new Map();
    const fields = Array.isArray(integrationSchema.value?.fields)
      ? integrationSchema.value.fields
      : [];
    fields.forEach((field) => {
      const path = String(field?.path || "").trim();
      const fieldType = normalizeIntegrationSchemaType(field?.effective_type);
      if (!path || !fieldType || fieldType === "json" || fieldType === "undefined") return;
      const collectedOptions = Array.isArray(field?.options) ? field.options : [];
      const collectsOptions = Boolean(field?.collect_options);
      options.set(path, {
        path,
        type: fieldType,
        label: optionLabel(path, fieldType),
        required: Boolean(field?.required),
        collectsOptions,
        options: cloneDeep(collectedOptions),
        optionType: String(field?.option_type || "").trim(),
      });
    });
    return options;
  });

  function getCollectionItemTargetOptions(targetCollectionPath) {
    const normalizedPath = String(targetCollectionPath || "").trim();
    if (!normalizedPath) return [];

    const cachedOptions = collectionItemOptionCache.get(normalizedPath);
    if (Array.isArray(cachedOptions) && cachedOptions.length > 0) {
      return cachedOptions.filter((entry) => entry && !shouldSkipContentTargetPath(entry.path, { listItem: true }));
    }

    let schemaItem = resolveCollectionItemSchemaByPath(sectionTypeSchema.value, normalizedPath, sectionType.value);
    if (!schemaItem) {
      const fallbackToken = tokenizeObjectPath(normalizedPath)
        .filter((token) => typeof token === "string")
        .pop();
      if (fallbackToken) {
        schemaItem = resolveCollectionItemSchemaByPath(sectionTypeSchema.value, fallbackToken, sectionType.value);
      }
    }
    if (!schemaItem) {
      schemaItem = resolveVirtualSharedCollectionItemSchema(sectionType.value, normalizedPath);
    }
    if (!schemaItem) return [];

    const useRawKeys = shouldUseRawListItemTargetKeys(sectionType.value, normalizedPath);
    const schemaOptions = collectTypedOptionsFromSchema(
      schemaItem,
      sectionTypeSchema.value,
      "",
      new Map(),
      0,
      { useRawKeys },
    );
    const stableOptions = Array.from(schemaOptions.entries())
      .map(([optionPath, entry]) => {
        const editorPath = mapCollectionItemPathToEditorPath(
          optionPath,
          sectionType.value,
          normalizedPath,
        );
        const normalizedEditorPath = normalizeCollectionItemTargetPath(
          editorPath,
          sectionType.value,
          normalizedPath,
        );
        if (!normalizedEditorPath) return null;
        const optionType = String(entry?.type || "text");
        return {
          path: normalizedEditorPath,
          type: optionType,
          label: collectionItemTargetOptionLabel(
            normalizedEditorPath,
            optionType,
            sectionType.value,
            normalizedPath,
          ),
        };
      })
      .filter((entry) => entry && !shouldSkipContentTargetPath(entry.path, { listItem: true }))
      .sort((a, b) => a.path.localeCompare(b.path));

    if (stableOptions.length > 0) {
      collectionItemOptionCache.set(normalizedPath, stableOptions);
    }
    return stableOptions;
  }

  const hiddenListTargetPathSignaturesByCollectionPath = computed(() => {
    const normalizedHiddenPaths = normalizeHiddenListTargetPathsByCollectionPath(
      hiddenListTargetPathsByCollectionPath.value,
      sectionType.value,
    );
    const next = {};
    Object.entries(normalizedHiddenPaths).forEach(([collectionPath, hiddenPaths]) => {
      next[collectionPath] = new Set(
        hiddenPaths
          .map((path) => collectionItemPathSignature(path))
          .filter(Boolean)
      );
    });
    return next;
  });

  function isListTargetPathHidden(collectionPath, targetPath) {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    const normalizedTargetPath = String(targetPath || "").trim();
    if (!normalizedCollectionPath || !normalizedTargetPath) return false;
    const hiddenSignatures = hiddenListTargetPathSignaturesByCollectionPath.value[normalizedCollectionPath];
    if (!(hiddenSignatures instanceof Set) || hiddenSignatures.size === 0) return false;
    const pathSignature = collectionItemPathSignature(normalizeCollectionItemTargetPath(
      normalizedTargetPath,
      sectionType.value,
      normalizedCollectionPath,
    ));
    if (!pathSignature) return false;
    return hiddenSignatures.has(pathSignature);
  }

  function buildListTargetOptionsForMappings(collectionPath, mappings = []) {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath) return [];
    const allOptions = getCollectionItemTargetOptions(normalizedCollectionPath);
    if (allOptions.length === 0) return [];

    const hiddenSignatures = hiddenListTargetPathSignaturesByCollectionPath.value[normalizedCollectionPath];
    if (!(hiddenSignatures instanceof Set) || hiddenSignatures.size === 0) {
      return allOptions;
    }

    const visibleOptions = allOptions.filter((option) => {
      const signature = collectionItemPathSignature(option?.path);
      if (!signature) return true;
      return !hiddenSignatures.has(signature);
    });

    const mappedTargetPaths = Array.isArray(mappings)
      ? mappings
          .map((mapping) => String(mapping?.target_path || "").trim())
          .filter(Boolean)
      : [];

    const visibleSignatures = new Set(
      visibleOptions
        .map((option) => collectionItemPathSignature(option?.path))
        .filter(Boolean)
    );
    const selectedHiddenOptions = [];

    mappedTargetPaths.forEach((mappedTargetPath) => {
      const normalizedMappedPath = normalizeCollectionItemTargetPathByOptions(
        mappedTargetPath,
        allOptions,
        sectionType.value,
        normalizedCollectionPath,
      );
      const mappedSignature = collectionItemPathSignature(normalizedMappedPath);
      if (!mappedSignature || !hiddenSignatures.has(mappedSignature) || visibleSignatures.has(mappedSignature)) {
        return;
      }
      const matchingOption = allOptions.find((option) =>
        collectionItemPathSignature(option?.path) === mappedSignature
      );
      const optionPath = String(matchingOption?.path || normalizedMappedPath).trim();
      if (!optionPath) return;
      const optionType = String(matchingOption?.type || "text").trim().toLowerCase() || "text";
      const baseLabel = String(matchingOption?.label || optionLabel(optionPath, optionType)).trim();
      selectedHiddenOptions.push({
        path: optionPath,
        type: optionType,
        label: `${baseLabel} [Hidden]`,
        hidden: true,
      });
      visibleSignatures.add(mappedSignature);
    });

    return [
      ...visibleOptions,
      ...selectedHiddenOptions,
    ];
  }

  const listTargetVisibilityGroups = computed(() =>
    collectionTargetOptions.value
      .map((collectionOption) => {
        const collectionPath = String(collectionOption?.path || "").trim();
        if (!collectionPath) return null;
        const options = getCollectionItemTargetOptions(collectionPath)
          .map((option) => ({
            ...option,
            hidden: isListTargetPathHidden(collectionPath, option?.path),
          }));
        if (options.length === 0) return null;
        return {
          path: collectionPath,
          label: String(collectionOption?.label || formatPathLabel(collectionPath)).trim() || formatPathLabel(collectionPath),
          options,
        };
      })
      .filter(Boolean)
  );

  function setListTargetPathHidden(collectionPath, targetPath, hidden = true) {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath) return;
    const normalizedTargetPath = normalizeCollectionItemTargetPath(
      String(targetPath || "").trim(),
      sectionType.value,
      normalizedCollectionPath,
    );
    if (!normalizedTargetPath) return;
    const targetSignature = collectionItemPathSignature(normalizedTargetPath);
    if (!targetSignature) return;

    const current = normalizeHiddenListTargetPathsByCollectionPath(
      hiddenListTargetPathsByCollectionPath.value,
      sectionType.value,
    );
    const existingPaths = Array.isArray(current[normalizedCollectionPath])
      ? current[normalizedCollectionPath]
      : [];
    const nextPaths = existingPaths.filter((path) =>
      collectionItemPathSignature(path) !== targetSignature
    );

    if (hidden) {
      nextPaths.push(normalizedTargetPath);
    }

    const next = { ...current };
    if (nextPaths.length > 0) {
      next[normalizedCollectionPath] = nextPaths;
    } else {
      delete next[normalizedCollectionPath];
    }

    hiddenListTargetPathsByCollectionPath.value = next;
  }

  function syncListMappingsByCollectionPath() {
    const availablePaths = collectionTargetOptions.value
      .map((entry) => String(entry?.path || "").trim())
      .filter(Boolean);
    const availablePathSet = new Set(availablePaths);
    const current = isPlainObject(listMappingsByCollectionPath.value)
      ? listMappingsByCollectionPath.value
      : {};
    const next = {};

    availablePaths.forEach((collectionPath) => {
      const targetOptions = getCollectionItemTargetOptions(collectionPath);
      const existingRows = Array.isArray(current[collectionPath])
        ? current[collectionPath]
            .map((mapping) => ({
              source_path: String(mapping?.source_path || "").trim(),
              target_path: normalizeCollectionItemTargetPathByOptions(
                String(mapping?.target_path || "").trim(),
                targetOptions,
                sectionType.value,
                collectionPath,
              ),
            }))
            .filter((mapping) => mapping.source_path || mapping.target_path)
        : [];
      next[collectionPath] = existingRows.length ? existingRows : [{ source_path: "", target_path: "" }];
    });

    listMappingsByCollectionPath.value = next;
    Array.from(collectionItemOptionCache.keys()).forEach((cacheKey) => {
      if (!availablePathSet.has(cacheKey)) {
        collectionItemOptionCache.delete(cacheKey);
      }
    });
  }

  function addListMappingRow(collectionPath, row = null) {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath) return;
    const current = isPlainObject(listMappingsByCollectionPath.value)
      ? listMappingsByCollectionPath.value
      : {};
    const existingRows = Array.isArray(current[normalizedCollectionPath])
      ? current[normalizedCollectionPath]
      : [];
    const nextRow = isPlainObject(row)
      ? {
          source_path: String(row.source_path || "").trim(),
          target_path: String(row.target_path || "").trim(),
        }
      : { source_path: "", target_path: "" };
    const rowsForAppend = nextRow.source_path && nextRow.target_path
      ? existingRows.filter((mapping) =>
          String(mapping?.source_path || "").trim()
          && String(mapping?.target_path || "").trim()
        )
      : existingRows;

    listMappingsByCollectionPath.value = {
      ...current,
      [normalizedCollectionPath]: [
        ...rowsForAppend,
        nextRow,
      ],
    };
  }

  function removeListMappingRow(collectionPath, index) {
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath) return;
    const current = isPlainObject(listMappingsByCollectionPath.value)
      ? listMappingsByCollectionPath.value
      : {};
    const existingRows = Array.isArray(current[normalizedCollectionPath])
      ? [...current[normalizedCollectionPath]]
      : [];
    if (index < 0 || index >= existingRows.length) return;
    existingRows.splice(index, 1);

    listMappingsByCollectionPath.value = {
      ...current,
      [normalizedCollectionPath]: existingRows.length ? existingRows : [{ source_path: "", target_path: "" }],
    };
  }

  const listMappingGroups = computed(() =>
    collectionTargetOptions.value.map((collectionOption) => {
      const path = String(collectionOption?.path || "").trim();
      const label = String(collectionOption?.label || formatPathLabel(path)).trim() || formatPathLabel(path);
      const mappings = Array.isArray(listMappingsByCollectionPath.value?.[path])
        ? listMappingsByCollectionPath.value[path]
        : [{ source_path: "", target_path: "" }];
      const targetOptions = buildListTargetOptionsForMappings(path, mappings);
      return {
        path,
        label,
        mappings,
        targetOptions,
      };
    })
  );

  const preferredListFilterCollectionPath = computed(() => {
    const availablePaths = collectionTargetOptions.value
      .map((entry) => String(entry?.path || "").trim())
      .filter(Boolean);
    if (availablePaths.length === 0) return "";
    if (normalizedSectionType.value === "tiles") {
      if (availablePaths.includes("tiles")) return "tiles";
      const tilesAlias = availablePaths.find((path) => path.endsWith(".tiles"));
      if (tilesAlias) return tilesAlias;
    }
    return availablePaths[0];
  });

  function resolveListFilterTargetPath(sourcePath) {
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedSourcePath) return "";
    const collectionPath = preferredListFilterCollectionPath.value;
    if (!collectionPath) return "";
    const mappings = Array.isArray(listMappingsByCollectionPath.value?.[collectionPath])
      ? listMappingsByCollectionPath.value[collectionPath]
      : [];
    const matchingMapping = mappings.find((mapping) =>
      String(mapping?.source_path || "").trim() === normalizedSourcePath
      && String(mapping?.target_path || "").trim()
    );
    if (!matchingMapping) return "";
    const targetOptions = getCollectionItemTargetOptions(collectionPath);
    const normalizedTargetPath = normalizeCollectionItemTargetPathByOptions(
      matchingMapping.target_path,
      targetOptions,
      sectionType.value,
      collectionPath,
    );
    if (!normalizedTargetPath) return "";
    return resolveListItemTargetPath(
      sectionData.value,
      collectionPath,
      normalizedTargetPath,
    );
  }

  function normalizeListFiltersForState(rawFilters) {
    return normalizeIntegrationListFilters(rawFilters).map((entry) => {
      const sourcePath = String(entry?.source_path || "").trim();
      const preferredCollectionPath = preferredListFilterCollectionPath.value;
      const targetOptions = preferredCollectionPath
        ? getCollectionItemTargetOptions(preferredCollectionPath)
        : [];
      const resolvedTargetPath = sourcePath
        ? resolveListFilterTargetPath(sourcePath)
        : normalizeCollectionItemTargetPathByOptions(
          String(entry?.target_path || "").trim(),
          targetOptions,
          sectionType.value,
          preferredCollectionPath,
        );
      return {
        ...entry,
        source_path: sourcePath,
        target_path: String(resolvedTargetPath || "").trim(),
      };
    });
  }

  function ensureListFilterScopeValuesForSourcePath(sourcePath) {
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedSourcePath) return;
    const distinctValues = collectDistinctFilterValuesFromRows(
      listFilterSourceRows.value,
      normalizedSourcePath,
    );
    listFilterScopeValuesBySourcePath.value = {
      ...(isPlainObject(listFilterScopeValuesBySourcePath.value)
        ? listFilterScopeValuesBySourcePath.value
        : {}),
      [normalizedSourcePath]: distinctValues,
    };
  }

  function refreshListFilterTargetPaths() {
    listFilters.value = normalizeListFiltersForState(listFilters.value);
  }

  function addListFilter() {
    const nextIndex = listFilters.value.length + 1;
    listFilters.value = [
      ...listFilters.value,
      {
        id: `filter-${Date.now()}-${nextIndex}`,
        name: `Filter ${nextIndex}`,
        source_path: "",
        target_path: "",
        enabled: true,
        admin_scope_value: null,
      },
    ];
  }

  function removeListFilter(index) {
    if (index < 0 || index >= listFilters.value.length) return;
    const next = [...listFilters.value];
    next.splice(index, 1);
    listFilters.value = normalizeIntegrationListFilters(next);
  }

  function updateListFilter(index, patch = {}) {
    if (index < 0 || index >= listFilters.value.length || !isPlainObject(patch)) return;
    const current = listFilters.value[index] || {};
    const hasSourcePathPatch = Object.prototype.hasOwnProperty.call(patch, "source_path");
    const sourcePath = hasSourcePathPatch
      ? String(patch.source_path || "").trim()
      : String(current.source_path || "").trim();
    const resolvedTargetPath = sourcePath ? resolveListFilterTargetPath(sourcePath) : "";
    const nextTargetPath = hasSourcePathPatch
      ? String(resolvedTargetPath || "").trim()
      : String(resolvedTargetPath || patch.target_path || current.target_path || "").trim();
    const merged = {
      ...current,
      ...patch,
      source_path: sourcePath,
      target_path: nextTargetPath,
      enabled: Object.prototype.hasOwnProperty.call(patch, "enabled")
        ? Boolean(patch.enabled)
        : (current.enabled == null ? true : Boolean(current.enabled)),
      admin_scope_value: Object.prototype.hasOwnProperty.call(patch, "admin_scope_value")
        ? (String(patch.admin_scope_value || "").trim() || null)
        : (String(current.admin_scope_value || "").trim() || null),
    };
    const next = [...listFilters.value];
    next[index] = merged;
    listFilters.value = normalizeIntegrationListFilters(next);
    if (sourcePath) ensureListFilterScopeValuesForSourcePath(sourcePath);
  }

  function getListFilterScopeValues(sourcePath) {
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedSourcePath) return [];
    const values = listFilterScopeValuesBySourcePath.value?.[normalizedSourcePath];
    return Array.isArray(values) ? values : [];
  }

  async function loadListFilterScopeValues(force = false) {
    if (!supportsListFilters.value) {
      listFilterSourceRows.value = [];
      listFilterScopeValuesBySourcePath.value = {};
      listFilterRowsIntegrationId.value = "";
      return;
    }
    const integrationId = String(selectedIntegration.value || "").trim();
    if (!integrationId) {
      listFilterSourceRows.value = [];
      listFilterScopeValuesBySourcePath.value = {};
      listFilterRowsIntegrationId.value = "";
      return;
    }
    if (!force && listFilterRowsIntegrationId.value === integrationId && listFilterSourceRows.value.length > 0) {
      return;
    }

    loadingListFilterScopeValues.value = true;
    try {
      const response = await api.getEffectiveIntegrationData(integrationId);
      listFilterSourceRows.value = resolveCollectionRows(response?.data, INTEGRATION_ROOT_COLLECTION_PATH);
      listFilterRowsIntegrationId.value = integrationId;

      const distinctBySourcePath = {};
      const uniqueSourcePaths = new Set(
        (Array.isArray(listFilters.value) ? listFilters.value : [])
          .map((entry) => String(entry?.source_path || "").trim())
          .filter(Boolean)
      );
      uniqueSourcePaths.forEach((sourcePath) => {
        distinctBySourcePath[sourcePath] = collectDistinctFilterValuesFromRows(
          listFilterSourceRows.value,
          sourcePath,
        );
      });
      listFilterScopeValuesBySourcePath.value = distinctBySourcePath;
    } catch (err) {
      console.error("Failed to load list filter scope values:", err);
      listFilterSourceRows.value = [];
      listFilterScopeValuesBySourcePath.value = {};
      listFilterRowsIntegrationId.value = "";
    } finally {
      loadingListFilterScopeValues.value = false;
    }
  }

  const overwrittenFieldIndicators = computed(() => {
    const overwrittenPaths = Array.isArray(cacheState.value?.overwritten_paths)
      ? cacheState.value.overwritten_paths
      : [];
    const appliedValues = isPlainObject(cacheState.value?.applied_values)
      ? cacheState.value.applied_values
      : {};
    const normalizedSectionType = normalizeSectionTypeValue(sectionType.value, "");
    const cacheIntegrationId = String(cacheState.value?.integration_id || "").trim();
    const integrationForOverrides = (
      (cacheIntegrationId
        ? availableIntegrations.value.find((entry) => String(entry?.id || "").trim() === cacheIntegrationId)
        : null)
      || selectedIntegrationDetails.value
      || null
    );
    const integrationPrimaryKeySourcePath = String(
      cacheState.value?.integration_output_primary_key_path
      || integrationForOverrides?.output_primary_key_path
      || ""
    ).trim();
    const cachedPrimaryKeyTargetPathByCollection = isPlainObject(cacheState.value?.list_primary_key_paths)
      ? cacheState.value.list_primary_key_paths
      : {};
    const fallbackPrimaryKeyTargetPathByCollection = resolveListPrimaryKeyTargetPathByCollectionPath({
      primaryKeySourcePath: integrationPrimaryKeySourcePath,
      listMappings: listMappingsByCollectionPath.value,
      sectionSnapshot: sectionData.value,
      sectionTypeValue: sectionType.value,
    });

    return overwrittenPaths
      .map((path) => String(path || "").trim())
      .filter(Boolean)
      .map((path) => {
        const indexedPath = parseIndexedCollectionPath(path);
        if (indexedPath && indexedPath.collection === "tiles") {
          if (normalizedSectionType !== "tiles") return null;
          // Tile rows are reorderable, so index-based comparisons are not reliable.
          // Only compare when the integration has an explicit External ID mapping.
          if (!integrationPrimaryKeySourcePath) return null;

          const primaryKeyTargetPath = String(
            cachedPrimaryKeyTargetPathByCollection.tiles
            || fallbackPrimaryKeyTargetPathByCollection.tiles
            || ""
          ).trim();
          if (!primaryKeyTargetPath) return null;

          const importedTiles = Array.isArray(appliedValues.tiles) ? appliedValues.tiles : [];
          const importedTile = importedTiles[indexedPath.index];
          const importedTileIdentifier = normalizeScalarIdentifier(
            deepGetPathValue(importedTile, primaryKeyTargetPath)
          );
          if (!importedTileIdentifier) return null;

          const currentTiles = Array.isArray(sectionData.value?.tiles) ? sectionData.value.tiles : [];
          const currentTile = currentTiles.find((candidate) => {
            const candidateIdentifier = normalizeScalarIdentifier(
              deepGetPathValue(candidate, primaryKeyTargetPath)
            );
            return candidateIdentifier && candidateIdentifier === importedTileIdentifier;
          });
          const importedValue = indexedPath.itemPath
            ? deepGetPathValue(importedTile, indexedPath.itemPath)
            : importedTile;
          const currentValue = indexedPath.itemPath
            ? deepGetPathValue(currentTile, indexedPath.itemPath)
            : currentTile;
          const tileTitle = resolvePreferredTileTitle(currentTile || importedTile, state.lang);
          const itemLabel = indexedPath.itemPath ? formatPathLabel(indexedPath.itemPath) : "Tile";
          const tileLabel = tileTitle || `Tile #${indexedPath.index + 1}`;
          return {
            path,
            label: indexedPath.itemPath ? `${tileLabel} - ${itemLabel}` : tileLabel,
            importedValue,
            currentValue,
            isLocalOverride: !deepEqual(currentValue, importedValue),
          };
        }

        const importedValue = appliedValues[path];
        const currentValue = deepGetPathValue(sectionData.value, path);
        const isLocalOverride = !deepEqual(currentValue, importedValue);
        return {
          path,
          label: formatPathLabel(path),
          importedValue,
          currentValue,
          isLocalOverride,
        };
      })
      .filter(Boolean);
  });

  function mappingSignature(payload) {
    try {
      return JSON.stringify(payload || {});
    } catch {
      return "";
    }
  }

  function normalizePersistedMappingPayload(rawPayload) {
    if (!isPlainObject(rawPayload)) {
      return {
        active_mode: "auto",
        selected_integration_id: "",
        scalar_mappings: [],
        list_mappings_by_collection_path: {},
        list_filters: [],
        hidden_list_target_paths_by_collection_path: {},
      };
    }
    const sourcePayload = convertKeysToCamel(rawPayload);
    const activeMode = String(sourcePayload.activeMode || "auto")
      .trim()
      .toLowerCase();
    const selectedIntegrationId = String(sourcePayload.selectedIntegrationId || "").trim();
    const scalarMap = normalizeScalarMappings(sourcePayload.scalarMappings);
    const listMap = normalizeListMappingsByCollectionPath(sourcePayload.listMappingsByCollectionPath);
    const listFiltersRaw = sourcePayload.listFilters;
    const listFilters = normalizeIntegrationListFilters(listFiltersRaw);
    const hiddenListTargetsByCollectionPath = normalizeHiddenListTargetPathsByCollectionPath(
      sourcePayload.hiddenListTargetPathsByCollectionPath,
      sectionType.value,
    );
    return {
      active_mode: activeMode === "list" || activeMode === "object" ? activeMode : "auto",
      selected_integration_id: selectedIntegrationId,
      scalar_mappings: scalarMap,
      list_mappings_by_collection_path: listMap,
      list_filters: listFilters,
      hidden_list_target_paths_by_collection_path: hiddenListTargetsByCollectionPath,
    };
  }

  function buildPersistedMappingPayload() {
    const selectedIntegrationId = String(selectedIntegration.value || "").trim();
    const modeValue = forcedImportModeValue.value
      || (mappingMode.value === "list" || mappingMode.value === "object"
        ? mappingMode.value
        : "auto");
    const effectiveModeValue = modeValue === "auto" ? activeImportMode.value : modeValue;
    const normalizedScalarMappings = effectiveModeValue === "list"
      ? []
      : normalizeScalarMappings(scalarMappings.value);
    const normalizedListMappings = effectiveModeValue === "object"
      ? {}
      : normalizeListMappingsByCollectionPath(listMappingsByCollectionPath.value);
    const normalizedListFilters = effectiveModeValue === "object"
      ? []
      : normalizeListFiltersForState(listFilters.value);
    const normalizedHiddenListTargetPaths = effectiveModeValue === "object"
      ? {}
      : normalizeHiddenListTargetPathsByCollectionPath(
        hiddenListTargetPathsByCollectionPath.value,
        sectionType.value,
      );

    if (
      !selectedIntegrationId
      && normalizedScalarMappings.length === 0
      && Object.keys(normalizedListMappings).length === 0
      && normalizedListFilters.length === 0
      && Object.keys(normalizedHiddenListTargetPaths).length === 0
      && modeValue === "auto"
    ) {
      return {};
    }

    return {
      active_mode: modeValue,
      selected_integration_id: selectedIntegrationId || null,
      scalar_mappings: normalizedScalarMappings,
      list_mappings_by_collection_path: normalizedListMappings,
      list_filters: normalizedListFilters,
      hidden_list_target_paths_by_collection_path: normalizedHiddenListTargetPaths,
    };
  }

  function applyPersistedMappingPayload(rawPayload) {
    const normalized = normalizePersistedMappingPayload(rawPayload);
    localMappingStateHydrating.value = true;
    try {
      mappingMode.value = forcedImportModeValue.value || normalized.active_mode;
      selectedIntegration.value = normalized.selected_integration_id || "";
      scalarMappings.value = normalized.scalar_mappings.length > 0
        ? normalized.scalar_mappings
        : [{ source_path: "", target_path: "" }];
      listMappingsByCollectionPath.value = normalized.list_mappings_by_collection_path;
      hiddenListTargetPathsByCollectionPath.value = normalized.hidden_list_target_paths_by_collection_path;
      syncListMappingsByCollectionPath();
      listFilters.value = normalizeListFiltersForState(normalized.list_filters);
      ensureAtLeastOneScalarMapping(scalarMappings);
      lastPersistedMappingSignature.value = mappingSignature(buildPersistedMappingPayload());
    } finally {
      localMappingStateHydrating.value = false;
      loadingPersistedMapping.value = false;
    }
  }

  function clearPersistMappingTimer() {
    if (persistMappingTimer) {
      clearTimeout(persistMappingTimer);
      persistMappingTimer = null;
    }
  }

  function persistMappingNow() {
    if (!state.canAdminGeneral) return;
    const currentSectionKey = String(sectionKey.value || "").trim();
    if (!currentSectionKey) return;
    const payload = buildPersistedMappingPayload();
    const signature = mappingSignature(payload);
    if (signature === lastPersistedMappingSignature.value) return;
    lastPersistedMappingSignature.value = signature;
    const patch = { [mappingStorageField.value]: payload };
    const customMappingPatchHandler = (
      (persistMappingPatch && typeof persistMappingPatch.value === "function" && persistMappingPatch.value)
      || (typeof persistMappingPatch === "function" ? persistMappingPatch : null)
    );
    if (customMappingPatchHandler) {
      void customMappingPatchHandler(cloneDeep(patch));
      return;
    }
    updateSection(
      currentSectionKey,
      patch,
      { revisionKind: "content" },
    );
  }

  function queuePersistMapping() {
    if (localMappingStateHydrating.value || loadingPersistedMapping.value) return;
    clearPersistMappingTimer();
    persistMappingTimer = setTimeout(() => {
      persistMappingTimer = null;
      persistMappingNow();
    }, 220);
  }

  function addScalarMapping() {
    scalarMappings.value.push({ source_path: "", target_path: "" });
  }

  function removeScalarMapping(index) {
    if (index < 0 || index >= scalarMappings.value.length) return;
    scalarMappings.value.splice(index, 1);
    ensureAtLeastOneScalarMapping(scalarMappings);
  }

  async function loadSectionTypeSchema() {
    const catalog = await getSectionTypeCatalog();
    sectionTypeSchema.value = catalog.get(normalizeSectionTypeValue(sectionType.value)) || null;
  }

  async function loadAvailableIntegrations() {
    loadingIntegrations.value = true;
    try {
      const currentSectionId = state.sectionIds?.[sectionKey.value] || null;
      const response = await api.listIntegrationsForSection(sectionType.value, {
        sectionId: currentSectionId,
      });
      availableIntegrations.value = Array.isArray(response?.integrations) ? response.integrations : [];
      integrationContext.value = {
        template_key: String(response?.context?.template_key || "").trim(),
        integration_visibility: ["disabled", "template_only", "enabled"].includes(response?.context?.integration_visibility)
          ? response.context.integration_visibility
          : "enabled",
        integrations_enabled: response?.context?.integrations_enabled !== false,
        expected_return_type: ["auto", "list", "object"].includes(response?.context?.expected_return_type)
          ? response.context.expected_return_type
          : "auto",
      };
      if (!integrationContext.value.integrations_enabled) {
        selectedIntegration.value = "";
        integrationPreview.value = null;
        integrationSchema.value = null;
        return;
      }
      const validIds = new Set(
        availableIntegrations.value
          .map((entry) => String(entry?.id || "").trim())
          .filter(Boolean)
      );
      if (!validIds.has(String(selectedIntegration.value || "").trim())) {
        selectedIntegration.value = "";
        integrationPreview.value = null;
        integrationSchema.value = null;
      }
    } catch (err) {
      console.error("Failed to load integrations:", err);
      availableIntegrations.value = [];
      integrationContext.value = {
        template_key: "",
        integration_visibility: "enabled",
        integrations_enabled: true,
        expected_return_type: "auto",
      };
      selectedIntegration.value = "";
      integrationPreview.value = null;
      integrationSchema.value = null;
    } finally {
      integrationContextLoaded.value = true;
      loadingIntegrations.value = false;
    }
  }

  async function loadIntegrationPreview() {
    importStatus.value = null;
    if (!selectedIntegration.value) {
      integrationPreview.value = null;
      return;
    }
    try {
      integrationPreview.value = await api.getIntegrationDataPreview(selectedIntegration.value);
    } catch (err) {
      console.error("Failed to load integration preview:", err);
      integrationPreview.value = null;
    }
  }

  async function loadIntegrationSchema() {
    if (!selectedIntegration.value) {
      integrationSchema.value = null;
      return;
    }
    try {
      integrationSchema.value = await api.getIntegrationSchema(selectedIntegration.value);
    } catch (err) {
      console.error("Failed to load integration schema:", err);
      integrationSchema.value = null;
    }
  }

  function coerceValueForTargetPath(targetPath, value, targetSnapshot = sectionData.value) {
    const normalizedPath = String(targetPath || "").trim();
    if (!normalizedPath) return cloneDeep(value);
    const targetSignature = collectionItemPathSignature(normalizedPath);
    if (targetSignature === "genre_selection" || targetSignature.endsWith(".genre_selection")) {
      return normalizeStringListValue(value);
    }
    if (
      normalizedSectionType.value === "program"
      && isProgramGigDateTimeTargetSignature(targetSignature)
    ) {
      return normalizeProgramGigDateTimeValue(value);
    }
    if (normalizedPath.endsWith(".de") || normalizedPath.endsWith(".en")) {
      return value == null ? "" : String(value);
    }
    const currentValue = deepGetPathValue(targetSnapshot, normalizedPath);
    if (isBilingualObject(currentValue)) {
      return toBilingualValue(value);
    }
    return cloneDeep(value);
  }

  function getIntegrationSchemaTypeForPath(sourcePath) {
    const normalizedPath = String(sourcePath || "").trim();
    if (!normalizedPath) return "";
    const schemaEntry = integrationSchemaOptions.value.get(normalizedPath);
    return normalizeIntegrationSchemaType(schemaEntry?.type);
  }

  function coerceIntegrationValueForSchema(sourcePath, value) {
    const schemaType = getIntegrationSchemaTypeForPath(sourcePath);
    if (!schemaType || value == null) return cloneDeep(value);

    if (schemaType === "number") {
      if (typeof value === "number" && Number.isFinite(value)) return value;
      if (typeof value === "string") {
        const normalized = value.trim();
        if (!normalized) return value;
        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : value;
      }
      return value;
    }

    if (schemaType === "boolean") {
      if (typeof value === "boolean") return value;
      if (typeof value === "string") {
        const normalized = value.trim().toLowerCase();
        if (["true", "1", "yes", "on"].includes(normalized)) return true;
        if (["false", "0", "no", "off"].includes(normalized)) return false;
      }
      return value;
    }

    if (["text", "date", "datetime", "url", "image"].includes(schemaType)) {
      if (typeof value === "string") return value;
      if (typeof value === "number" || typeof value === "boolean") return String(value);
      return value;
    }

    if (schemaType === "list" && !Array.isArray(value)) {
      return [cloneDeep(value)];
    }

    return cloneDeep(value);
  }

  function buildCacheStatePayload({
    touchedTargetPaths = [],
    nextDataSnapshot = {},
    appliedValuesByPath = {},
    fetchedAt = null,
    mappingModeValue = activeImportMode.value,
    integrationOutputPrimaryKeyPath = "",
    listPrimaryKeyPaths = {},
    integrationOptions = {},
    integrationOptionTypes = {},
    integrationMapping = {},
  } = {}) {
    const uniquePaths = Array.from(
      new Set(
        (Array.isArray(touchedTargetPaths) ? touchedTargetPaths : [])
          .map((path) => String(path || "").trim())
          .filter(Boolean)
      )
    );
    const appliedValues = {};
    uniquePaths.forEach((path) => {
      const hasExplicitAppliedValue = Object.prototype.hasOwnProperty.call(appliedValuesByPath, path);
      appliedValues[path] = hasExplicitAppliedValue
        ? cloneDeep(appliedValuesByPath[path])
        : cloneDeep(deepGetPathValue(nextDataSnapshot, path));
    });
    return {
      overwritten_paths: uniquePaths,
      applied_values: appliedValues,
      options: normalizeIntegrationOptions(integrationOptions),
      option_types: normalizeIntegrationOptionTypes(integrationOptionTypes),
      integration_mapping: isPlainObject(integrationMapping) && Object.keys(integrationMapping).length > 0
        ? normalizePersistedMappingPayload(integrationMapping)
        : {},
      integration_output_primary_key_path: String(integrationOutputPrimaryKeyPath || "").trim(),
      list_primary_key_paths: isPlainObject(listPrimaryKeyPaths) ? listPrimaryKeyPaths : {},
      source_changed: false,
      source_changed_paths: [],
      cache_id: null,
      source_hash: "",
      source_etag: null,
      fetched_at: fetchedAt || new Date().toISOString(),
      import_mode: mappingModeValue,
      integration_id: String(selectedIntegration.value || "").trim() || null,
    };
  }

  function buildSectionLocalImporterPatch(patch) {
    const normalizedPatch = isPlainObject(patch) ? patch : {};
    const normalizedType = normalizeSectionTypeValue(sectionType.value, "");
    if (normalizedType === "blog") {
      return Object.fromEntries(
        Object.entries(normalizedPatch).filter(([key]) =>
          key !== "blogItems" && key !== "blogTags"
        )
      );
    }
    if (normalizedType === "faq") {
      return Object.fromEntries(
        Object.entries(normalizedPatch).filter(([key]) =>
          key !== "faqItems" && key !== "faqTags"
        )
      );
    }
    return normalizedPatch;
  }

  function syncLocalStateAfterImport(patch) {
    const normalizedPatch = isPlainObject(patch) ? patch : {};
    const normalizedType = normalizeSectionTypeValue(sectionType.value, "");
    const sectionLocalPatch = buildSectionLocalImporterPatch(normalizedPatch);
    const applyPatchValues = (target) => {
      if (!isPlainObject(target) || !isPlainObject(sectionLocalPatch)) return false;
      Object.entries(sectionLocalPatch).forEach(([key, value]) => {
        target[key] = cloneDeep(value);
      });
      return true;
    };

    const currentSectionKey = String(sectionKey.value || "").trim();
    const sectionStateEntry = (
      currentSectionKey && isPlainObject(state.sectionsData?.[currentSectionKey])
        ? state.sectionsData[currentSectionKey]
        : null
    );
    if (sectionStateEntry) {
      applyPatchValues(sectionStateEntry);
    }
    const sectionPropEntry = isPlainObject(sectionData.value) ? sectionData.value : null;
    if (sectionPropEntry && sectionPropEntry !== sectionStateEntry) {
      applyPatchValues(sectionPropEntry);
    }

    if (currentSectionKey && sectionStateEntry) {
      // Replace object identity so section-local watches (`watch(section, ...)`) react immediately.
      state.sectionsData[currentSectionKey] = {
        ...sectionStateEntry,
      };
    }

    if (normalizedType === "faq" && Array.isArray(patch?.faqItems)) {
      const scopeTag = toBilingualValue(sectionData.value?.scope);
      const faqItems = cloneDeep(patch.faqItems).map((item) => {
        if (!isPlainObject(item) || !hasBilingualValue(scopeTag)) return item;
        const normalizedItem = convertKeysToCamel(item);
        if (hasBilingualValue(normalizedItem.tag)) return item;
        return {
          ...item,
          tag: scopeTag,
        };
      });
      setFaqItems(faqItems, true, currentSectionKey || "faq");
    }
  }

  async function applyImporterContentPatch(patch) {
    const customPatchHandler = (
      (applyContentPatch && typeof applyContentPatch.value === "function" && applyContentPatch.value)
      || (typeof applyContentPatch === "function" ? applyContentPatch : null)
    );
    if (customPatchHandler) {
      await customPatchHandler(cloneDeep(patch));
      return;
    }
    const sectionPatch = buildSectionLocalImporterPatch(patch);
    if (Object.keys(sectionPatch).length > 0) {
      updateSection(sectionKey.value, sectionPatch, { revisionKind: "content" });
    }
  }

  async function importMappedRawData(rawData, options = {}) {
    const nextData = cloneDeep(sectionData.value || {});
    const touchedRoots = new Set();
    const touchedTargetPaths = new Set();
    const changedMappedRows = [];
    const appliedImportedValuesByPath = {};
    const integrationOptions = normalizeIntegrationOptions(options?.integrationOptions);
    const integrationOptionTypes = normalizeIntegrationOptionTypes(options?.integrationOptionTypes);
    const mediaMetadataByUrl = options?.mediaMetadataByUrl instanceof Map
      ? options.mediaMetadataByUrl
      : new Map();
    let appliedScalarCount = 0;
    let appliedListFieldCount = 0;
    let appliedListCount = 0;

    const normalizedMappingsByCollectionPath = normalizeListMappingsByCollectionPath(listMappingsByCollectionPath.value);
    if (isListMode.value && Object.keys(normalizedMappingsByCollectionPath).length > 0) {
      const sourceRows = resolveCollectionRows(rawData, INTEGRATION_ROOT_COLLECTION_PATH);

      Object.entries(normalizedMappingsByCollectionPath).forEach(([targetCollectionPath, listMappings]) => {
        if (!targetCollectionPath || !Array.isArray(listMappings) || listMappings.length === 0) return;
        const targetOptions = getCollectionItemTargetOptions(targetCollectionPath);
        const collectionPathTokens = tokenizeObjectPath(targetCollectionPath);
        const collectionPathTailToken = collectionPathTokens.length > 0
          ? collectionPathTokens[collectionPathTokens.length - 1]
          : "";
        const collectionPathTail = typeof collectionPathTailToken === "string"
          ? collectionPathTailToken
          : "";
        const preserveRawSourceRow = (
          (normalizedSectionType.value === "tiles" && collectionPathTail === "tiles")
          || (
            normalizedSectionType.value === "program"
            && (collectionPathTail === "gigs" || collectionPathTail === "stages")
          )
        );
        const integrationPrimaryKeyPath = selectedIntegrationDetails.value?.output_primary_key_path || "";

        const mappedRows = sourceRows
          .map((row, rowIndex) => {
            const mappedRow = preserveRawSourceRow && isPlainObject(row)
              ? cloneDeep(row)
              : {};
            const integrationItemKey = resolveIntegrationItemKeyFromRow(row, integrationPrimaryKeyPath);
            if (preserveRawSourceRow && integrationItemKey && !normalizeScalarIdentifier(mappedRow.integration_item_key)) {
              mappedRow.integration_item_key = integrationItemKey;
            }
            let mappedFieldCountForRow = 0;

            listMappings.forEach((mapping) => {
              const sourceValue = coerceIntegrationValueForSchema(
                mapping.source_path,
                resolveIntegrationSourceValue(row, mapping.source_path),
              );
              if (sourceValue == null) return;
              const normalizedItemTargetPath = normalizeCollectionItemTargetPathByOptions(
                mapping.target_path,
                targetOptions,
                sectionType.value,
                targetCollectionPath,
              );
              if (!normalizedItemTargetPath) return;
              const rawItemTargetPath = resolveListItemTargetPath(
                nextData,
                targetCollectionPath,
                normalizedItemTargetPath,
              );
              const resolvedAbsoluteTargetPath = resolveWritableSectionTargetPath(
                nextData,
                `${targetCollectionPath}[${rowIndex}].${rawItemTargetPath}`,
              );
              const importedValue = coerceValueForTargetPath(
                resolvedAbsoluteTargetPath,
                sourceValue,
                nextData,
              );
              const finalValue = importedValue;
              const normalizedCollectionPrefix = `${targetCollectionPath}[${rowIndex}].`;
              const rowTargetPath = resolvedAbsoluteTargetPath.startsWith(normalizedCollectionPrefix)
                ? resolvedAbsoluteTargetPath.slice(normalizedCollectionPrefix.length)
                : resolveListItemTargetPath(nextData, targetCollectionPath, normalizedItemTargetPath);
              if (deepSetPathValue(mappedRow, rowTargetPath, finalValue)) {
                mappedFieldCountForRow += 1;
                const absoluteRowPath = `${targetCollectionPath}[${rowIndex}].${rowTargetPath}`;
                touchedTargetPaths.add(absoluteRowPath);
                appliedImportedValuesByPath[absoluteRowPath] = cloneDeep(importedValue);
              }
            });

            if (
              normalizedSectionType.value === "program"
              && collectionPathTail === "gigs"
            ) {
              enrichImageRowWithMediaMetadata(mappedRow, mediaMetadataByUrl, { keyStyle: "snake" });
            } else if (
              normalizedSectionType.value === "program"
              && collectionPathTail === "stages"
            ) {
              enrichImageRowWithMediaMetadata(mappedRow, mediaMetadataByUrl, { keyStyle: "snake" });
            } else if (collectionPathTail === "items") {
              enrichImageRowWithMediaMetadata(mappedRow, mediaMetadataByUrl, { keyStyle: "camel" });
            }

            if (
              normalizedSectionType.value === "links"
              && collectionPathTail === "items"
              && !mappedLinkItemHasContent(mappedRow)
            ) {
              return null;
            }

            if (mappedFieldCountForRow > 0) return mappedRow;
            if (preserveRawSourceRow && isPlainObject(row) && Object.keys(row).length > 0) {
              return mappedRow;
            }
            return null;
          })
          .filter(Boolean);

        if (!deepSetPathValue(nextData, targetCollectionPath, mappedRows)) return;
        const rootKey = getRootKey(targetCollectionPath);
        if (rootKey) touchedRoots.add(rootKey);
        touchedTargetPaths.add(targetCollectionPath);
        appliedListCount += 1;
        appliedListFieldCount += listMappings.length;

        const beforeRows = deepGetPathValue(sectionData.value || {}, targetCollectionPath);
        if (!deepEqual(beforeRows, mappedRows)) {
          changedMappedRows.push({
            path: targetCollectionPath,
            oldValue: cloneDeep(beforeRows),
            newValue: cloneDeep(mappedRows),
          });
        }
      });
    }

    const normalizedObjectMappings = isObjectMode.value ? normalizeScalarMappings(scalarMappings.value) : [];
    normalizedObjectMappings.forEach((mapping) => {
      const sourceValue = coerceIntegrationValueForSchema(
        mapping.source_path,
        resolveScalarSourceValue(rawData, mapping.source_path),
      );
      if (sourceValue == null) return;
      const resolvedTargetPath = resolveWritableSectionTargetPath(nextData, mapping.target_path);
      const beforeValue = deepGetPathValue(nextData, resolvedTargetPath);
      const importedValue = coerceValueForTargetPath(resolvedTargetPath, sourceValue, nextData);
      const finalValue = importedValue;
      const didSet = deepSetPathValue(nextData, resolvedTargetPath, finalValue);
      if (!didSet) return;
      const rootKey = getRootKey(resolvedTargetPath);
      if (rootKey) touchedRoots.add(rootKey);
      touchedTargetPaths.add(resolvedTargetPath);
      appliedImportedValuesByPath[resolvedTargetPath] = cloneDeep(importedValue);
      appliedScalarCount += 1;
      if (!deepEqual(beforeValue, finalValue)) {
        changedMappedRows.push({
          path: resolvedTargetPath,
          oldValue: cloneDeep(beforeValue),
          newValue: cloneDeep(finalValue),
        });
      }
    });

    if (!touchedRoots.size) {
      return {
        ok: false,
        message: "No valid mappings found. Configure at least one mapping pair.",
      };
    }

    const patch = {};
    const revertPatch = {};
    touchedRoots.forEach((rootKey) => {
      revertPatch[rootKey] = cloneDeep(sectionData.value?.[rootKey]);
      patch[rootKey] = cloneDeep(nextData[rootKey]);
    });

    const persistedMappingPayload = buildPersistedMappingPayload();
    patch[mappingStorageField.value] = cloneDeep(persistedMappingPayload);
    patch[cacheStateField.value] = buildCacheStatePayload({
      touchedTargetPaths: Array.from(touchedTargetPaths),
      nextDataSnapshot: nextData,
      appliedValuesByPath: appliedImportedValuesByPath,
      fetchedAt: options?.fetchedAt || new Date().toISOString(),
      integrationOutputPrimaryKeyPath: selectedIntegrationDetails.value?.output_primary_key_path || "",
      listPrimaryKeyPaths: resolveListPrimaryKeyTargetPathByCollectionPath({
        primaryKeySourcePath: selectedIntegrationDetails.value?.output_primary_key_path || "",
        listMappings: listMappingsByCollectionPath.value,
        sectionSnapshot: nextData,
        sectionTypeValue: sectionType.value,
      }),
      integrationOptions,
      integrationOptionTypes,
      integrationMapping: persistedMappingPayload,
    });

    await applyImporterContentPatch(patch);
    syncLocalStateAfterImport(patch);
    lastImportRevertPatch.value = revertPatch;
    return {
      ok: true,
      patch,
      appliedScalarCount,
      appliedListCount,
      appliedListFieldCount,
      changedMappedRows,
    };
  }

  async function importFromIntegration() {
    if (!selectedIntegration.value) return;
    importing.value = true;
    importStatus.value = null;

    try {
      const response = await api.getEffectiveIntegrationData(selectedIntegration.value);
      const importSourceData = response?.data;
      const integrationOptions = normalizeIntegrationOptions(response?.options);
      const integrationOptionTypes = normalizeIntegrationOptionTypes(response?.option_types);
      const fetchedAt = Object.prototype.hasOwnProperty.call(response || {}, "fetched_at")
        ? response?.fetched_at || null
        : null;
      const mediaMetadataByUrl = buildMediaMetadataByUrl(response?.media_entries);
      const importResult = await importMappedRawData(importSourceData, {
        sourceChanged: false,
        fetchedAt: fetchedAt || new Date().toISOString(),
        integrationOptions,
        integrationOptionTypes,
        mediaMetadataByUrl,
      });

      if (!importResult?.ok) {
        importStatus.value = {
          type: "error",
          message: importResult?.message || "No valid mappings found.",
        };
        return;
      }

      const importSummaryParts = [];
      if (importResult.appliedScalarCount > 0) {
        importSummaryParts.push(`${importResult.appliedScalarCount} object field mapping(s)`);
      }
      if (importResult.appliedListCount > 0 || importResult.appliedListFieldCount > 0) {
        importSummaryParts.push(`${importResult.appliedListCount} mapped list(s), ${importResult.appliedListFieldCount} item field mapping(s)`);
      }
      const baseMessage = importSummaryParts.length
        ? `Imported integration data (${importSummaryParts.join("; ")}).`
        : "Imported integration data.";
      importStatus.value = {
        type: "success",
        message: baseMessage,
      };
    } catch (err) {
      console.error("Failed to import integration data:", err);
      importStatus.value = {
        type: "error",
        message: err?.message || "Failed to import integration data.",
      };
    } finally {
      importing.value = false;
    }
  }

  async function loadMediaImportability() {
    if (!selectedIntegration.value) {
      mediaImportability.value = {
        has_media_urls: false,
        media_url_count: 0,
        fetched_at: null,
      };
      return;
    }
    loadingMediaImportability.value = true;
    try {
      const response = await api.getIntegrationMediaImportability(selectedIntegration.value);
      mediaImportability.value = {
        has_media_urls: response?.has_media_urls === true,
        media_url_count: Number(response?.media_url_count || 0),
        fetched_at: response?.fetched_at || null,
      };
    } catch (err) {
      console.error("Failed to load integration media importability:", err);
      mediaImportability.value = {
        has_media_urls: false,
        media_url_count: 0,
        fetched_at: null,
      };
    } finally {
      loadingMediaImportability.value = false;
    }
  }

  function resetImporterMappings() {
    localMappingStateHydrating.value = true;
    try {
      mappingMode.value = forcedImportModeValue.value || "auto";
      selectedIntegration.value = "";
      integrationPreview.value = null;
      integrationSchema.value = null;
      scalarMappings.value = [{ source_path: "", target_path: "" }];
      listMappingsByCollectionPath.value = {};
      listFilters.value = [];
      listFilterSourceRows.value = [];
      listFilterScopeValuesBySourcePath.value = {};
      listFilterRowsIntegrationId.value = "";
      syncListMappingsByCollectionPath();
      ensureAtLeastOneScalarMapping(scalarMappings);
    } finally {
      localMappingStateHydrating.value = false;
    }
  }

  function clearImporter() {
    const normalizedListMappingsByCollectionPath = normalizeListMappingsByCollectionPath(
      listMappingsByCollectionPath.value
    );
    const mappedCollectionPaths = Object.keys(normalizedListMappingsByCollectionPath);
    const revertPatch = isPlainObject(lastImportRevertPatch.value)
      ? cloneDeep(lastImportRevertPatch.value)
      : null;
    const hasRevertPatch = Boolean(revertPatch && Object.keys(revertPatch).length > 0);
    const clearedCacheState = {
      overwritten_paths: [],
      applied_values: {},
      options: {},
      option_types: {},
      integration_output_primary_key_path: "",
      list_primary_key_paths: {},
      source_changed: false,
      source_changed_paths: [],
      cache_id: null,
      source_hash: "",
      source_etag: null,
      fetched_at: new Date().toISOString(),
      import_mode: activeImportMode.value,
      integration_id: null,
      integration_mapping: {},
    };

    if (mappedCollectionPaths.length > 0) {
      const nextData = cloneDeep(sectionData.value || {});
      const touchedRoots = new Set();
      mappedCollectionPaths.forEach((collectionPath) => {
        if (!collectionPath) return;
        if (!deepSetPathValue(nextData, collectionPath, [])) return;
        const rootKey = getRootKey(collectionPath);
        if (rootKey) touchedRoots.add(rootKey);
      });
      if (touchedRoots.size > 0) {
        const clearPatch = {};
        touchedRoots.forEach((rootKey) => {
          clearPatch[rootKey] = cloneDeep(nextData[rootKey]);
        });
        clearPatch[cacheStateField.value] = clearedCacheState;
        void applyImporterContentPatch(clearPatch);
        syncLocalStateAfterImport(clearPatch);
      }
      importStatus.value = {
        type: "success",
        message: "Cleared imported list items.",
      };
    } else if (hasRevertPatch) {
      revertPatch[cacheStateField.value] = clearedCacheState;
      void applyImporterContentPatch(revertPatch);
      syncLocalStateAfterImport(revertPatch);
      importStatus.value = {
        type: "success",
        message: "Reverted the last import.",
      };
    } else {
      void applyImporterContentPatch({ [cacheStateField.value]: clearedCacheState });
      importStatus.value = {
        type: "success",
        message: "Cleared imported cache state.",
      };
    }
    lastImportRevertPatch.value = null;
  }

  async function initializeImporterForSection() {
    if (!state.canAdminGeneral) return;
    loadingPersistedMapping.value = true;
    integrationContextLoaded.value = false;
    lastImportRevertPatch.value = null;
    try {
      collectionItemOptionCache.clear();
      await Promise.all([
        loadSectionTypeSchema(),
        loadAvailableIntegrations(),
      ]);
      applyPersistedMappingPayload(sectionData.value?.[mappingStorageField.value]);
      await loadIntegrationPreview();
      await loadIntegrationSchema();
      await loadMediaImportability();
      await loadListFilterScopeValues(true);
    } finally {
      if (loadingPersistedMapping.value) {
        loadingPersistedMapping.value = false;
      }
    }
  }

  watch(
    () => selectedIntegration.value,
    async (nextValue, previousValue) => {
      if (nextValue === previousValue) return;
      if (localMappingStateHydrating.value) return;
      if (!integrationContext.value?.integrations_enabled) return;
      await loadIntegrationPreview();
      await loadIntegrationSchema();
      await loadMediaImportability();
      await loadListFilterScopeValues(true);
      queuePersistMapping();
    },
  );

  watch(
    () => [sectionKey.value, sectionType.value],
    async () => {
      await initializeImporterForSection();
    },
    { immediate: true },
  );

  watch(
    () => state.canAdminGeneral,
    async (canAdminGeneral) => {
      if (!canAdminGeneral) return;
      await initializeImporterForSection();
    },
  );

  watch(
    () => mappingSignature(sectionData.value?.[mappingStorageField.value] || {}),
    async (nextSignature) => {
      if (!state.canAdminGeneral) return;
      if (loadingPersistedMapping.value || localMappingStateHydrating.value) return;
      if (nextSignature === lastPersistedMappingSignature.value) return;
      applyPersistedMappingPayload(sectionData.value?.[mappingStorageField.value]);
      await loadIntegrationPreview();
      await loadIntegrationSchema();
      await loadMediaImportability();
      await loadListFilterScopeValues(true);
    },
  );

  watch(
    () => [
      mappingMode.value,
      scalarMappings.value,
      listMappingsByCollectionPath.value,
      hiddenListTargetPathsByCollectionPath.value,
      listFilters.value,
    ],
    () => {
      queuePersistMapping();
    },
    { deep: true },
  );

  watch(
    () => collectionTargetOptions.value.map((entry) => entry.path).join("|"),
    () => {
      syncListMappingsByCollectionPath();
      refreshListFilterTargetPaths();
    },
    { immediate: true },
  );

  watch(
    () => supportsListFilters.value,
    async (enabled) => {
      if (!enabled) {
        listFilterSourceRows.value = [];
        listFilterScopeValuesBySourcePath.value = {};
        listFilterRowsIntegrationId.value = "";
        return;
      }
      await loadListFilterScopeValues(true);
    },
    { immediate: true },
  );

  watch(
    () => listMappingsByCollectionPath.value,
    () => {
      refreshListFilterTargetPaths();
    },
    { deep: true },
  );

  watch(
    () => listFilters.value.map((entry) => String(entry?.source_path || "").trim()).join("|"),
    () => {
      const nextValues = {};
      const uniqueSourcePaths = new Set(
        (Array.isArray(listFilters.value) ? listFilters.value : [])
          .map((entry) => String(entry?.source_path || "").trim())
          .filter(Boolean)
      );
      uniqueSourcePaths.forEach((sourcePath) => {
        nextValues[sourcePath] = collectDistinctFilterValuesFromRows(listFilterSourceRows.value, sourcePath);
      });
      listFilterScopeValuesBySourcePath.value = nextValues;
    },
    { immediate: true },
  );

  onUnmounted(() => {
    clearPersistMappingTimer();
  });

  return {
    availableIntegrations,
    selectedIntegration,
    integrationContext,
    integrationContextLoaded,
    isIntegrationEnabled,
    isListMode,
    isObjectMode,
    activeImportMode,
    hasMediaUrls,
    mediaUrlCount,
    integrationPreview,
    mediaImportability,
    loadingIntegrations,
    loadingMediaImportability,
    importing,
    importStatus,
    scalarMappings,
    listMappingsByCollectionPath,
    hiddenListTargetPathsByCollectionPath,
    listFilters,
    listMappingGroups,
    listTargetVisibilityGroups,
    canEditListTargetVisibility,
    scalarTargetOptions,
    collectionTargetOptions,
    integrationLeafOptions,
    listItemSourceOptions,
    supportsListFilters,
    loadingListFilterScopeValues,
    loadAvailableIntegrations,
    loadIntegrationPreview,
    loadMediaImportability,
    importFromIntegration,
    clearImporter,
    addScalarMapping,
    removeScalarMapping,
    addListMappingRow,
    removeListMappingRow,
    setListTargetPathHidden,
    addListFilter,
    removeListFilter,
    updateListFilter,
    getListFilterScopeValues,
    getCollectionItemTargetOptions,
    formatPathLabel,
    cacheStateField,
    overwrittenFieldIndicators,
  };
}
