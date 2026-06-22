function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeIndexToken(token) {
  if (typeof token === "number") return "*";
  if (token === "*") return "*";
  return String(token || "");
}

function normalizeComparableStringToken(token) {
  return String(token || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
}

function parsePathTokens(path) {
  const raw = String(path || "").trim();
  if (!raw) return [];
  const tokens = [];
  const normalized = raw.replace(/\[(\d+|\*)\]/g, ".$1");
  normalized
    .split(".")
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      if (part === "*") {
        tokens.push("*");
        return;
      }
      if (/^\d+$/.test(part)) {
        tokens.push(Number(part));
        return;
      }
      tokens.push(part);
    });
  return tokens;
}

function buildPathFromTokens(tokens) {
  if (!Array.isArray(tokens) || tokens.length === 0) return "";
  return tokens
    .map((token, index) => {
      if (typeof token === "number") return `[${token}]`;
      if (token === "*") return "[*]";
      if (index === 0) return String(token);
      return `.${String(token)}`;
    })
    .join("")
    .replace(/\.\[/g, "[");
}

function deepGetByTokens(root, tokens) {
  let current = root;
  for (const token of tokens) {
    if (current == null) return undefined;
    if (typeof token === "number") {
      if (!Array.isArray(current)) return undefined;
      current = current[token];
      continue;
    }
    if (typeof current !== "object") return undefined;
    current = current[token];
  }
  return current;
}

function deepEqual(a, b) {
  if (Object.is(a, b)) return true;
  if (typeof a !== typeof b) return false;
  if (a == null || b == null) return a === b;
  if (typeof a !== "object") return a === b;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    for (let idx = 0; idx < a.length; idx += 1) {
      if (!deepEqual(a[idx], b[idx])) return false;
    }
    return true;
  }
  const aKeys = Object.keys(a);
  const bKeys = Object.keys(b);
  if (aKeys.length !== bKeys.length) return false;
  for (const key of aKeys) {
    if (!Object.prototype.hasOwnProperty.call(b, key)) return false;
    if (!deepEqual(a[key], b[key])) return false;
  }
  return true;
}

function tokensEqualWithWildcard(left, right) {
  if (left.length !== right.length) return false;
  for (let idx = 0; idx < left.length; idx += 1) {
    const leftToken = left[idx];
    const rightToken = right[idx];
    const leftNormalized = normalizeIndexToken(leftToken);
    const rightNormalized = normalizeIndexToken(rightToken);
    if (leftNormalized === "*" && typeof rightToken === "number") continue;
    if (rightNormalized === "*" && typeof leftToken === "number") continue;
    if (
      typeof leftToken === "string"
      && typeof rightToken === "string"
      && leftNormalized !== "*"
      && rightNormalized !== "*"
    ) {
      if (normalizeComparableStringToken(leftToken) !== normalizeComparableStringToken(rightToken)) return false;
      continue;
    }
    if (leftNormalized !== rightNormalized) return false;
  }
  return true;
}

function isPrefixWithWildcard(prefixTokens, targetTokens) {
  if (prefixTokens.length > targetTokens.length) return false;
  for (let idx = 0; idx < prefixTokens.length; idx += 1) {
    const prefixToken = prefixTokens[idx];
    const targetToken = targetTokens[idx];
    const prefixNormalized = normalizeIndexToken(prefixToken);
    const targetNormalized = normalizeIndexToken(targetToken);
    if (prefixNormalized === "*" && typeof targetToken === "number") continue;
    if (
      typeof prefixToken === "string"
      && typeof targetToken === "string"
      && prefixNormalized !== "*"
    ) {
      if (normalizeComparableStringToken(prefixToken) !== normalizeComparableStringToken(targetToken)) return false;
      continue;
    }
    if (prefixNormalized !== targetNormalized) return false;
  }
  return true;
}

function findFirstNumericIndex(tokens) {
  return tokens.findIndex((token) => typeof token === "number" || token === "*");
}

function isCollectionOrItemRootPrefix(candidateTokens, targetTokens) {
  if (!isPrefixWithWildcard(candidateTokens, targetTokens)) return false;
  if (candidateTokens.length >= targetTokens.length) return false;
  const firstIndex = findFirstNumericIndex(targetTokens);
  if (firstIndex < 0) return false;
  return candidateTokens.length <= firstIndex + 1;
}

function collectCacheStates(sectionData) {
  if (!isPlainObject(sectionData)) return [];
  return Object.entries(sectionData)
    .filter(([key, value]) => /integration.*mapping.*cache.*state/i.test(String(key || "")) && isPlainObject(value))
    .map(([key, value]) => ({
      key,
      overwrittenPaths: Array.isArray(value.overwritten_paths)
        ? value.overwritten_paths.map((path) => String(path || "").trim()).filter(Boolean)
        : [],
      appliedValues: isPlainObject(value.applied_values) ? value.applied_values : {},
    }));
}

function normalizeMappingRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .map((row) => {
      const sourcePath = row?.source_path != null ? row.source_path : row?.sourcePath;
      const targetPath = row?.target_path != null ? row.target_path : row?.targetPath;
      return {
        sourcePath: String(sourcePath || "").trim(),
        targetPath: String(targetPath || "").trim(),
      };
    })
    .filter((row) => row.sourcePath && row.targetPath);
}

function collectMappingStates(sectionData) {
  if (!isPlainObject(sectionData)) return [];
  return Object.entries(sectionData)
    .filter(([key, value]) => {
      const normalizedKey = String(key || "");
      if (!/integration.*mapping/i.test(normalizedKey)) return false;
      if (/cache.*state/i.test(normalizedKey)) return false;
      return isPlainObject(value);
    })
    .map(([key, value]) => {
      const rawScalarMappings = value.scalar_mappings != null
        ? value.scalar_mappings
        : value.scalarMappings;
      const scalarMappings = normalizeMappingRows(rawScalarMappings);
      const rawListMappings = isPlainObject(value.list_mappings_by_collection_path)
        ? value.list_mappings_by_collection_path
        : isPlainObject(value.listMappingsByCollectionPath)
          ? value.listMappingsByCollectionPath
          : {};
      const listMappings = [];
      Object.entries(rawListMappings).forEach(([collectionPath, mappings]) => {
        const normalizedCollectionPath = String(collectionPath || "").trim();
        if (!normalizedCollectionPath) return;
        normalizeMappingRows(mappings).forEach((mapping) => {
          listMappings.push({
            ...mapping,
            collectionPath: normalizedCollectionPath,
          });
        });
      });
      return {
        key,
        scalarMappings,
        listMappings,
      };
    });
}

function pathCandidateMatchesTarget(candidatePath, targetPath, { includeDescendants = false } = {}) {
  const candidateTokens = parsePathTokens(candidatePath);
  const targetTokens = parsePathTokens(targetPath);
  if (!candidateTokens.length || !targetTokens.length) return false;
  if (tokensEqualWithWildcard(candidateTokens, targetTokens)) return true;

  if (
    isPrefixWithWildcard(candidateTokens, targetTokens)
    && !isCollectionOrItemRootPrefix(candidateTokens, targetTokens)
  ) {
    return true;
  }

  if (
    includeDescendants
    && isPrefixWithWildcard(targetTokens, candidateTokens)
    && !isCollectionOrItemRootPrefix(targetTokens, candidateTokens)
  ) {
    return true;
  }

  return false;
}

function buildListMappingCandidatePath(collectionPath, targetPath) {
  const collectionTokens = parsePathTokens(collectionPath);
  const targetTokens = parsePathTokens(targetPath);
  if (!collectionTokens.length || !targetTokens.length) return "";
  return buildPathFromTokens([...collectionTokens, "*", ...targetTokens]);
}

export function resolveSectionIntegrationLockState(sectionData, targetPath, options = {}) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath) {
    return {
      locked: false,
      sourceKey: null,
      sourceType: null,
      matchedPath: "",
    };
  }

  const mappingStates = collectMappingStates(sectionData);
  for (const mappingState of mappingStates) {
    for (const mapping of mappingState.scalarMappings) {
      if (pathCandidateMatchesTarget(mapping.targetPath, normalizedTargetPath, options)) {
        return {
          locked: true,
          sourceKey: mappingState.key,
          sourceType: "mapping",
          matchedPath: mapping.targetPath,
        };
      }
    }
    for (const mapping of mappingState.listMappings) {
      const candidatePath = buildListMappingCandidatePath(mapping.collectionPath, mapping.targetPath);
      if (pathCandidateMatchesTarget(candidatePath, normalizedTargetPath, options)) {
        return {
          locked: true,
          sourceKey: mappingState.key,
          sourceType: "mapping",
          matchedPath: candidatePath,
        };
      }
    }
  }

  const cacheStates = collectCacheStates(sectionData);
  for (const cacheState of cacheStates) {
    const cachePaths = new Set([
      ...cacheState.overwrittenPaths,
      ...Object.keys(cacheState.appliedValues || {}),
    ]);
    for (const cachePath of cachePaths) {
      if (pathCandidateMatchesTarget(cachePath, normalizedTargetPath, options)) {
        return {
          locked: true,
          sourceKey: cacheState.key,
          sourceType: "cache",
          matchedPath: cachePath,
        };
      }
    }
  }

  return {
    locked: false,
    sourceKey: null,
    sourceType: null,
    matchedPath: "",
  };
}

export function isSectionIntegrationFieldLocked(sectionData, targetPath, options = {}) {
  return resolveSectionIntegrationLockState(sectionData, targetPath, options).locked;
}

function resolveImportedValue(appliedValues, targetTokens) {
  const entries = Object.entries(appliedValues || {})
    .map(([path, value]) => ({
      path: String(path || "").trim(),
      tokens: parsePathTokens(path),
      value,
    }))
    .filter((entry) => entry.path && entry.tokens.length > 0)
    .sort((left, right) => right.tokens.length - left.tokens.length);

  for (const entry of entries) {
    if (tokensEqualWithWildcard(entry.tokens, targetTokens)) {
      return { resolved: true, value: entry.value, specificity: entry.tokens.length };
    }
    if (isPrefixWithWildcard(entry.tokens, targetTokens)) {
      const remainder = targetTokens.slice(entry.tokens.length);
      return {
        resolved: true,
        value: deepGetByTokens(entry.value, remainder),
        specificity: entry.tokens.length,
      };
    }
  }
  return { resolved: false, value: undefined, specificity: -1 };
}

export function resolveSectionIntegrationFieldState(sectionData, targetPath) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath) {
    return {
      overwritten: false,
      isLocalOverride: false,
      importedValue: undefined,
      currentValue: undefined,
      sourceKey: null,
    };
  }

  const targetTokens = parsePathTokens(normalizedTargetPath);
  const currentValue = deepGetByTokens(sectionData, targetTokens);
  const cacheStates = collectCacheStates(sectionData);

  let bestMatch = null;

  cacheStates.forEach((cacheState) => {
    const matchedOverwrittenPath = cacheState.overwrittenPaths.find((overwrittenPath) => {
      const overwrittenTokens = parsePathTokens(overwrittenPath);
      if (!overwrittenTokens.length) return false;
      return (
        tokensEqualWithWildcard(overwrittenTokens, targetTokens)
        || isPrefixWithWildcard(overwrittenTokens, targetTokens)
        || isPrefixWithWildcard(targetTokens, overwrittenTokens)
      );
    });
    if (!matchedOverwrittenPath) return;

    const importedMatch = resolveImportedValue(cacheState.appliedValues, targetTokens);
    const candidate = {
      overwritten: true,
      isLocalOverride: importedMatch.resolved
        ? !deepEqual(currentValue, importedMatch.value)
        : false,
      importedValue: importedMatch.value,
      currentValue,
      sourceKey: cacheState.key,
      specificity: importedMatch.specificity,
    };

    if (!bestMatch) {
      bestMatch = candidate;
      return;
    }
    if (candidate.isLocalOverride && !bestMatch.isLocalOverride) {
      bestMatch = candidate;
      return;
    }
    if (candidate.specificity > bestMatch.specificity) {
      bestMatch = candidate;
    }
  });

  if (bestMatch) return bestMatch;

  return {
    overwritten: false,
    isLocalOverride: false,
    importedValue: undefined,
    currentValue,
    sourceKey: null,
  };
}
