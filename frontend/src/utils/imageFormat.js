export function isVectorOrPngImageUrl(rawUrl) {
  const value = String(rawUrl || "").trim();
  if (!value) return false;

  const dataMatch = value.match(/^data:image\/([^;,]+)/i);
  if (dataMatch) {
    const mime = String(dataMatch[1] || "").toLowerCase();
    return mime === "png" || mime === "svg+xml";
  }

  const sanitized = value.split("#", 1)[0].split("?", 1)[0].trim().toLowerCase();
  return sanitized.endsWith(".png") || sanitized.endsWith(".svg");
}
