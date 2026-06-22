export function normalizeTag(tag) {
  if (!tag || typeof tag !== "object" || Array.isArray(tag)) {
    return { de: "", en: "" };
  }
  return {
    de: String(tag.de || "").trim(),
    en: String(tag.en || "").trim(),
  };
}

export function hasTagValue(tag) {
  const normalized = normalizeTag(tag);
  return Boolean(normalized.de || normalized.en);
}

export function getTagKey(tag) {
  const normalized = normalizeTag(tag);
  return `${normalized.de}\0${normalized.en}`;
}

export function tagMatches(a, b) {
  const left = normalizeTag(a);
  const right = normalizeTag(b);
  return left.de === right.de && left.en === right.en;
}

export function uniqueTags(tags) {
  const list = Array.isArray(tags) ? tags : [];
  const out = [];
  const seen = new Set();
  for (const tag of list) {
    const normalized = normalizeTag(tag);
    if (!hasTagValue(normalized)) continue;
    const key = getTagKey(normalized);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(normalized);
  }
  return out;
}

export function normalizeScopes(value) {
  const rawList = Array.isArray(value)
    ? value
    : (hasTagValue(value) ? [value] : []);
  return uniqueTags(rawList);
}
