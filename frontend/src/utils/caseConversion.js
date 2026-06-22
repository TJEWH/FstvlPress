function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function toSnakeCase(value) {
  return String(value || "")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
}

export function toCamelCase(value) {
  return String(value || "").replace(/_([a-z0-9])/g, (_, letter) => letter.toUpperCase());
}

function convertKeysDeep(value, keyMapper) {
  if (Array.isArray(value)) {
    return value.map((item) => convertKeysDeep(item, keyMapper));
  }
  if (isPlainObject(value)) {
    const next = {};
    for (const [rawKey, rawValue] of Object.entries(value)) {
      next[keyMapper(rawKey)] = convertKeysDeep(rawValue, keyMapper);
    }
    return next;
  }
  return value;
}

export function convertKeysToSnake(value) {
  return convertKeysDeep(value, toSnakeCase);
}

export function convertKeysToCamel(value) {
  return convertKeysDeep(value, toCamelCase);
}

export function normalizeMappingPathToSnake(pathValue) {
  const raw = String(pathValue || "").trim();
  if (!raw) return "";
  return raw.replace(/[A-Za-z_][A-Za-z0-9_]*/g, (token) => {
    if (!/[A-Z]/.test(token)) return token;
    return toSnakeCase(token);
  });
}

