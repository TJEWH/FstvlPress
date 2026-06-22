function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepGet(source, path) {
  if (!source || typeof source !== "object") return undefined;
  const parts = String(path || "")
    .split(".")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) return undefined;
  let current = source;
  for (const part of parts) {
    if (!current || typeof current !== "object" || !(part in current)) {
      return undefined;
    }
    current = current[part];
  }
  return current;
}

function isLeafValue(value) {
  if (value == null) return true;
  if (Array.isArray(value)) {
    return value.every((entry) => !isPlainObject(entry) && !Array.isArray(entry));
  }
  return !isPlainObject(value);
}

function addKeyPath(out, value) {
  const key = String(value || "").trim();
  if (key) out.add(key);
}

function collectNestedKeyPaths(value, out, prefix = "", depth = 0) {
  if (depth > 6 || value == null) return;

  if (Array.isArray(value)) {
    if (prefix) addKeyPath(out, prefix);
    const nestedSample = value.find((entry) => isPlainObject(entry) || Array.isArray(entry));
    if (nestedSample !== undefined) {
      collectNestedKeyPaths(nestedSample, out, prefix, depth + 1);
    }
    return;
  }

  if (!isPlainObject(value)) {
    if (prefix) addKeyPath(out, prefix);
    return;
  }

  if (prefix) addKeyPath(out, prefix);

  Object.entries(value).forEach(([key, child]) => {
    const cleanKey = String(key || "").trim();
    if (!cleanKey) return;
    const nextPrefix = prefix ? `${prefix}.${cleanKey}` : cleanKey;
    addKeyPath(out, nextPrefix);
    if (isPlainObject(child) || Array.isArray(child)) {
      collectNestedKeyPaths(child, out, nextPrefix, depth + 1);
    }
  });
}

export function buildIntegrationMappingKeys(preview, options = {}) {
  const keys = new Set();

  const availableKeys = Array.isArray(preview?.available_keys) ? preview.available_keys : [];
  availableKeys.forEach((key) => addKeyPath(keys, key));

  collectNestedKeyPaths(preview?.preview_item, keys);

  const leafOnly = Boolean(options?.leafOnly);
  let result = Array.from(keys);
  if (leafOnly) {
    result = result.filter((path) => isLeafValue(deepGet(preview?.preview_item, path)));
  }
  return result.sort((a, b) => a.localeCompare(b));
}
