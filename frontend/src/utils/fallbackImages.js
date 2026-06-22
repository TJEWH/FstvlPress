import {
  resolveBackendResponsiveImagePayload,
  resolveFrontendResponsiveImagePayload,
} from "./responsiveImages.js";

function resolveFallbackImagePayload(source) {
  const frontendMedia = resolveFrontendResponsiveImagePayload(source);
  if (String(frontendMedia.url || "").trim()) return frontendMedia;
  return resolveBackendResponsiveImagePayload(source, {
    urlKeys: ["image_url", "url", "src", "href"],
  });
}

export function normalizeFallbackImageEntry(rawEntry, index = 0) {
  if (!rawEntry || typeof rawEntry !== "object") return null;
  const media = resolveFallbackImagePayload(rawEntry);
  const imageUrl = String(media.url || "").trim();
  if (!imageUrl) return null;
  return {
    id: String(rawEntry.id || `fallback-${index + 1}`),
    imageUrl,
    responsiveVariants: Array.isArray(media.responsiveVariants)
      ? media.responsiveVariants
      : [],
  };
}

export function normalizeFallbackImageList(rawList = []) {
  const normalized = [];
  const seenUrls = new Set();
  (Array.isArray(rawList) ? rawList : []).forEach((entry, index) => {
    const normalizedEntry = normalizeFallbackImageEntry(entry, index);
    if (!normalizedEntry) return;
    if (seenUrls.has(normalizedEntry.imageUrl)) return;
    seenUrls.add(normalizedEntry.imageUrl);
    normalized.push(normalizedEntry);
  });
  return normalized;
}

export function resolveFallbackImagePool(rawList = [], legacyImageUrl = "") {
  const fromList = normalizeFallbackImageList(rawList);
  if (fromList.length > 0) return fromList;
  const legacyUrl = String(legacyImageUrl || "").trim();
  if (!legacyUrl) return [];
  return [
    {
      id: "fallback-legacy",
      imageUrl: legacyUrl,
      responsiveVariants: [],
    },
  ];
}

function pickFirstDefined(source, keys, fallback = undefined) {
  if (!source || typeof source !== "object") return fallback;
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(source, key) && source[key] !== undefined) {
      return source[key];
    }
  }
  return fallback;
}

function normalizeNumber(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

export function normalizeFallbackZoom(value) {
  return normalizeNumber(value, 1, 1, 4);
}

export function normalizeFallbackFocal(value) {
  return normalizeNumber(value, 50, 0, 100);
}

export function normalizeFallbackRotation(value) {
  return normalizeNumber(value, 0, -180, 180);
}

export function normalizeFallbackImageConfig(raw = {}) {
  const source = raw && typeof raw === "object" ? raw : {};
  const legacyImageUrl = String(
    pickFirstDefined(source, ["legacyImageUrl", "imageUrl", "image_url"], "")
  ).trim();
  const images = normalizeFallbackImageList(
    Array.isArray(source.images) ? source.images : []
  );
  return {
    images,
    mediaTag: String(
      pickFirstDefined(source, ["mediaTag", "media_tag"], "")
    ).trim(),
    legacyImageUrl,
    zoom: normalizeFallbackZoom(
      pickFirstDefined(source, ["zoom", "imageZoom", "image_zoom"], 1)
    ),
    focalX: normalizeFallbackFocal(
      pickFirstDefined(source, ["focalX", "imageFocalX", "image_focal_x"], 50)
    ),
    focalY: normalizeFallbackFocal(
      pickFirstDefined(source, ["focalY", "imageFocalY", "image_focal_y"], 50)
    ),
    rotation: normalizeFallbackRotation(
      pickFirstDefined(source, ["rotation", "imageRotation", "image_rotation"], 0)
    ),
  };
}

export function resolveFallbackImageConfigPool(config = {}) {
  const normalized = normalizeFallbackImageConfig(config);
  return resolveFallbackImagePool(normalized.images, normalized.legacyImageUrl);
}

export function resolveEffectiveFallbackImageConfig({
  globalFallbacks = {},
  sectionFallbacks = {},
  useSectionFallbacks = false,
} = {}) {
  const normalizedGlobal = normalizeFallbackImageConfig(globalFallbacks);
  const normalizedSection = normalizeFallbackImageConfig(sectionFallbacks);
  const sectionPool = resolveFallbackImagePool(
    normalizedSection.images,
    normalizedSection.legacyImageUrl
  );
  if (useSectionFallbacks && sectionPool.length > 0) {
    return {
      ...normalizedSection,
      pool: sectionPool,
      source: "section",
    };
  }

  const globalPool = resolveFallbackImagePool(
    normalizedGlobal.images,
    normalizedGlobal.legacyImageUrl
  );
  return {
    ...normalizedGlobal,
    pool: globalPool,
    source: globalPool.length > 0 ? "global" : "",
  };
}

export function resolveFallbackImageForIndex(configOrPool = {}, index = 0) {
  const pool = Array.isArray(configOrPool)
    ? normalizeFallbackImageList(configOrPool)
    : Array.isArray(configOrPool?.pool)
      ? configOrPool.pool
      : resolveFallbackImageConfigPool(configOrPool);
  if (pool.length === 0) return null;
  const numericIndex = Number(index);
  const resolvedIndex = Number.isFinite(numericIndex) && numericIndex >= 0
    ? Math.floor(numericIndex)
    : 0;
  const fallbackImage = pool[resolvedIndex % pool.length];
  const normalizedConfig = Array.isArray(configOrPool)
    ? normalizeFallbackImageConfig()
    : normalizeFallbackImageConfig(configOrPool);
  return {
    imageUrl: String(fallbackImage?.imageUrl || "").trim(),
    responsiveVariants: Array.isArray(fallbackImage?.responsiveVariants)
      ? fallbackImage.responsiveVariants
      : [],
    zoom: normalizedConfig.zoom,
    focalX: normalizedConfig.focalX,
    focalY: normalizedConfig.focalY,
    rotation: normalizedConfig.rotation,
  };
}
