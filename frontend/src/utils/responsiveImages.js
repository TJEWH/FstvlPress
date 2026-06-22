const FALLBACK_VARIANT_WIDTH_BY_NAME = {
  thumb: 240,
  thumbnail: 240,
  mobile: 768,
  half: 1024,
  tablet: 1024,
  desktop: 1440,
};

const LEGACY_RESPONSIVE_VARIANT_NAMES = new Set(["small"]);
const LEGACY_SMALL_VARIANT_URL_PATTERN = /_small\.(?:avif|gif|jpe?g|png|webp)$/i;

const FRONTEND_IMAGE_URL_KEYS = [
  "imageUrl",
];

const FRONTEND_IMAGE_WIDTH_KEYS = ["imageWidth"];
const FRONTEND_VARIANT_KEYS = [
  "responsiveVariants",
];

const BACKEND_IMAGE_URL_KEYS = [
  "image_url",
];

const BACKEND_IMAGE_WIDTH_KEYS = ["image_width"];
const BACKEND_VARIANT_KEYS = [
  "responsive_variants",
  "image_responsive_variants",
];

function normalizeScalarString(value) {
  if (value == null || typeof value === "object") return "";
  const text = String(value).trim();
  if (text === "[object Object]" || text.toLowerCase() === "null") return "";
  return text;
}

function isLegacyResponsiveVariantName(value) {
  return LEGACY_RESPONSIVE_VARIANT_NAMES.has(String(value || "").trim().toLowerCase());
}

function isLegacyResponsiveVariantUrl(value) {
  const path = String(value || "").trim().split("#", 1)[0].split("?", 1)[0];
  return LEGACY_SMALL_VARIANT_URL_PATTERN.test(path);
}

function readFirstString(source, keys = []) {
  if (!source || typeof source !== "object") return "";
  for (const key of keys) {
    if (!(key in source)) continue;
    const value = normalizeScalarString(source[key]);
    if (value) return value;
  }
  return "";
}

function readFirstStringWithImageFallback(source, keys = []) {
  const direct = readFirstString(source, keys);
  if (direct) return direct;
  const imagePayload = source && typeof source === "object" ? source.image : null;
  if (!imagePayload || typeof imagePayload !== "object") return "";
  return readFirstString(imagePayload, keys);
}

function readFirstStringDirect(source, keys = []) {
  if (!source || typeof source !== "object") return "";
  for (const key of keys) {
    if (!(key in source)) continue;
    const value = normalizeScalarString(source[key]);
    if (value) return value;
  }
  return "";
}

function readFirstPositiveNumber(source, keys = []) {
  if (!source || typeof source !== "object") return 0;
  for (const key of keys) {
    if (!(key in source)) continue;
    const raw = Number(source[key]);
    if (Number.isFinite(raw) && raw > 0) return raw;
  }
  return 0;
}

function readFirstPositiveNumberWithImageFallback(source, keys = []) {
  const direct = readFirstPositiveNumber(source, keys);
  if (direct > 0) return direct;
  const imagePayload = source && typeof source === "object" ? source.image : null;
  if (!imagePayload || typeof imagePayload !== "object") return 0;
  return readFirstPositiveNumber(imagePayload, keys);
}

function readFirstPositiveNumberDirect(source, keys = []) {
  if (!source || typeof source !== "object") return 0;
  for (const key of keys) {
    if (!(key in source)) continue;
    const raw = Number(source[key]);
    if (Number.isFinite(raw) && raw > 0) return raw;
  }
  return 0;
}

function resolveResponsiveImageWidth(source) {
  return readFirstPositiveNumberWithImageFallback(source, [
    "imageWidth",
    "image_width",
    "width",
    "w",
    "max_width",
    "maxWidth",
  ]);
}

function resolveResponsiveImageWidthWithKeys(source, keys = []) {
  if (!Array.isArray(keys) || !keys.length) return 0;
  return readFirstPositiveNumberDirect(source, keys);
}

function resolveResponsiveImageUrlWithKeys(source, keys = []) {
  if (!source || typeof source !== "object") return "";
  if (!Array.isArray(keys) || !keys.length) return "";
  return readFirstStringDirect(source, keys);
}

function buildStrictVariantCandidates(source, directKeys = [], extra = []) {
  if (Array.isArray(source) || typeof source !== "object" || !source) {
    return [source, ...(Array.isArray(extra) ? extra : [])];
  }
  return [
    ...directKeys.map((key) => source?.[key]),
    ...(Array.isArray(extra) ? extra : []),
  ];
}

function resolveResponsiveImageVariantsWithNaming(source, options = {}) {
  const urlKeys = Array.isArray(options.urlKeys) && options.urlKeys.length
    ? options.urlKeys
    : [];
  const widthKeys = Array.isArray(options.widthKeys) && options.widthKeys.length
    ? options.widthKeys
    : [];
  const variantKeys = Array.isArray(options.variantKeys) && options.variantKeys.length
    ? options.variantKeys
    : [];

  const variantCandidates = buildStrictVariantCandidates(
    source,
    variantKeys,
    options.variantCandidates
  );

  const resolved = mergeResponsiveVariants(variantCandidates);
  const variantsByUrl = new Map(resolved.map((entry) => [entry.url, entry]));
  const sourceWidth = resolveResponsiveImageWidthWithKeys(source, widthKeys);
  const sourceUrl = resolveResponsiveImageUrlWithKeys(source, urlKeys);
  if (sourceUrl && sourceWidth > 0 && !variantsByUrl.has(sourceUrl)) {
    variantsByUrl.set(sourceUrl, {
      name: "original",
      url: sourceUrl,
      width: Math.round(sourceWidth),
    });
  }

  return Array.from(variantsByUrl.values()).sort((a, b) => a.width - b.width);
}

export function inferResponsiveVariantWidth(rawName, fallback = 0) {
  const normalizedName = String(rawName || "").trim().toLowerCase();
  if (!normalizedName) return fallback;
  return FALLBACK_VARIANT_WIDTH_BY_NAME[normalizedName] || fallback;
}

export function normalizeResponsiveVariantEntry(rawEntry, fallbackName = "", fallbackWidth = 0) {
  if (typeof rawEntry === "string") {
    const url = String(rawEntry || "").trim();
    if (isLegacyResponsiveVariantName(fallbackName) || isLegacyResponsiveVariantUrl(url)) return null;
    const inferredWidth = inferResponsiveVariantWidth(fallbackName, fallbackWidth);
    if (!url || !Number.isFinite(inferredWidth) || inferredWidth <= 0) return null;
    return {
      ...(fallbackName ? { name: String(fallbackName || "").trim().toLowerCase() } : {}),
      url,
      width: Math.round(inferredWidth),
    };
  }

  if (!rawEntry || typeof rawEntry !== "object") return null;

  const url = String(rawEntry.url || rawEntry.href || rawEntry.src || "").trim();
  if (!url) return null;

  const name = String(
    rawEntry.name
      || rawEntry.variant
      || rawEntry.id
      || fallbackName
      || ""
  ).trim().toLowerCase();
  if (isLegacyResponsiveVariantName(name) || isLegacyResponsiveVariantUrl(url)) return null;

  const widthRaw = Number(
    rawEntry.width
      ?? rawEntry.w
      ?? inferResponsiveVariantWidth(name, fallbackWidth)
      ?? fallbackWidth
  );
  const width = Number.isFinite(widthRaw) && widthRaw > 0 ? Math.round(widthRaw) : 0;
  if (width <= 0) return null;

  const heightRaw = Number(rawEntry.height ?? rawEntry.h);
  const height = Number.isFinite(heightRaw) && heightRaw > 0 ? Math.round(heightRaw) : undefined;

  return {
    ...(name ? { name } : {}),
    url,
    width,
    ...(height ? { height } : {}),
  };
}

export function collectResponsiveVariants(rawValue, fallbackName = "", fallbackWidth = 0) {
  if (!rawValue) return [];

  if (Array.isArray(rawValue)) {
    return rawValue
      .map((entry) => normalizeResponsiveVariantEntry(entry, fallbackName, fallbackWidth))
      .filter(Boolean);
  }

  if (typeof rawValue === "object") {
    if (rawValue.url || rawValue.href || rawValue.src) {
      const single = normalizeResponsiveVariantEntry(rawValue, fallbackName, fallbackWidth);
      return single ? [single] : [];
    }
    return Object.entries(rawValue).flatMap(([variantName, variantEntry]) => {
      const normalized = normalizeResponsiveVariantEntry(variantEntry, variantName, fallbackWidth);
      return normalized ? [normalized] : [];
    });
  }

  return [];
}

export function mergeResponsiveVariants(candidates = []) {
  const variantsByUrl = new Map();
  (Array.isArray(candidates) ? candidates : []).forEach((candidate) => {
    collectResponsiveVariants(candidate).forEach((entry) => {
      const existing = variantsByUrl.get(entry.url);
      if (!existing || entry.width > existing.width) {
        variantsByUrl.set(entry.url, entry);
      }
    });
  });
  return Array.from(variantsByUrl.values()).sort((a, b) => a.width - b.width);
}

export function resolveResponsiveImageVariants(source, options = {}) {
  // Legacy/mixed resolver for arbitrary integration payloads.
  // Prefer resolveFrontendResponsiveImageVariants / resolveBackendResponsiveImageVariants
  // for fixed frontend/backend contexts.
  if (!source) return [];

  const variantCandidates = Array.isArray(source) || typeof source !== "object"
    ? [source]
    : [
      source.responsiveVariants,
      source.responsive_variants,
      source.imageResponsiveVariants,
      source.image_responsive_variants,
      source.variants,
      source.image_variants,
      source.image?.responsiveVariants,
      source.image?.responsive_variants,
      source.image?.imageResponsiveVariants,
      source.image?.image_responsive_variants,
      source.image?.variants,
      ...(Array.isArray(options.variantCandidates) ? options.variantCandidates : []),
    ];

  const resolved = mergeResponsiveVariants(variantCandidates);
  const variantsByUrl = new Map(resolved.map((entry) => [entry.url, entry]));
  const sourceWidth = resolveResponsiveImageWidth(source);
  const sourceUrl = resolveResponsiveImageUrl(source, options.urlKeys);
  if (sourceUrl && sourceWidth > 0 && !variantsByUrl.has(sourceUrl)) {
    variantsByUrl.set(sourceUrl, {
      name: "original",
      url: sourceUrl,
      width: Math.round(sourceWidth),
    });
  }

  return Array.from(variantsByUrl.values()).sort((a, b) => a.width - b.width);
}

export function resolveResponsiveImageUrl(source, keys = null) {
  if (!source || typeof source !== "object") return "";
  const defaultKeys = [
    "imageUrl",
    "image_url",
    "url",
    "src",
    "href",
    "logoUrl",
    "logo",
    "thumbnailUrl",
    "thumbnail",
  ];
  return readFirstStringWithImageFallback(source, Array.isArray(keys) && keys.length ? keys : defaultKeys);
}

export function resolveResponsiveImagePayload(source, options = {}) {
  // Mixed resolver for arbitrary integration payloads.
  // Prefer resolveFrontendResponsiveImagePayload / resolveBackendResponsiveImagePayload
  // for fixed frontend/backend contexts.
  return {
    url: resolveResponsiveImageUrl(source, options.urlKeys),
    responsiveVariants: resolveResponsiveImageVariants(source, options),
  };
}

export function resolveFrontendResponsiveImageUrl(source, keys = null) {
  return resolveResponsiveImageUrlWithKeys(
    source,
    Array.isArray(keys) && keys.length ? keys : FRONTEND_IMAGE_URL_KEYS
  );
}

export function resolveFrontendResponsiveImageVariants(source, options = {}) {
  return resolveResponsiveImageVariantsWithNaming(source, {
    ...options,
    urlKeys: Array.isArray(options.urlKeys) && options.urlKeys.length
      ? options.urlKeys
      : FRONTEND_IMAGE_URL_KEYS,
    widthKeys: Array.isArray(options.widthKeys) && options.widthKeys.length
      ? options.widthKeys
      : FRONTEND_IMAGE_WIDTH_KEYS,
    variantKeys: Array.isArray(options.variantKeys) && options.variantKeys.length
      ? options.variantKeys
      : FRONTEND_VARIANT_KEYS,
  });
}

export function resolveFrontendResponsiveImagePayload(source, options = {}) {
  return {
    url: resolveFrontendResponsiveImageUrl(source, options.urlKeys),
    responsiveVariants: resolveFrontendResponsiveImageVariants(source, options),
  };
}

export function resolveBackendResponsiveImageUrl(source, keys = null) {
  return resolveResponsiveImageUrlWithKeys(
    source,
    Array.isArray(keys) && keys.length ? keys : BACKEND_IMAGE_URL_KEYS
  );
}

export function resolveBackendResponsiveImageVariants(source, options = {}) {
  return resolveResponsiveImageVariantsWithNaming(source, {
    ...options,
    urlKeys: Array.isArray(options.urlKeys) && options.urlKeys.length
      ? options.urlKeys
      : BACKEND_IMAGE_URL_KEYS,
    widthKeys: Array.isArray(options.widthKeys) && options.widthKeys.length
      ? options.widthKeys
      : BACKEND_IMAGE_WIDTH_KEYS,
    variantKeys: Array.isArray(options.variantKeys) && options.variantKeys.length
      ? options.variantKeys
      : BACKEND_VARIANT_KEYS,
  });
}

export function resolveBackendResponsiveImagePayload(source, options = {}) {
  return {
    url: resolveBackendResponsiveImageUrl(source, options.urlKeys),
    responsiveVariants: resolveBackendResponsiveImageVariants(source, options),
  };
}

export function selectResponsiveVariantUrl(variants, preferredNames = ["thumb", "thumbnail"]) {
  const normalized = collectResponsiveVariants(variants);
  if (!normalized.length) return "";
  const preferred = normalized.find((entry) => preferredNames.includes(String(entry.name || "").toLowerCase()));
  return String((preferred || normalized[0]).url || "").trim();
}

export function buildResponsiveSrcset(variants) {
  const normalized = collectResponsiveVariants(variants)
    .filter((entry) => entry && entry.url && Number.isFinite(Number(entry.width)) && Number(entry.width) > 0)
    .sort((a, b) => Number(a.width) - Number(b.width));
  if (!normalized.length) return "";
  return normalized.map((entry) => `${entry.url} ${Math.round(Number(entry.width))}w`).join(", ");
}
