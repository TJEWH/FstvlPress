const MEDIA_TAG_SEPARATOR = "::";

export function mediaTagTextValue(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return String(value.de || value.en || "").trim();
  }
  if (["string", "number", "boolean"].includes(typeof value)) {
    return String(value).trim();
  }
  return "";
}

export function normalizeMediaTagPart(value) {
  const source = mediaTagTextValue(value).normalize("NFC").trim().toLowerCase();
  if (!source) return "";
  return source
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function buildMediaTag(prefixValue, itemValue) {
  const prefix = normalizeMediaTagPart(prefixValue);
  const value = normalizeMediaTagPart(itemValue);
  if (!prefix || !value) return "";
  return `${prefix}${MEDIA_TAG_SEPARATOR}${value}`;
}
